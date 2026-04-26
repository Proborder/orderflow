import asyncio
import uuid
from datetime import datetime, UTC

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import settings
from app.core.logger import logger
from app.schemas.messages import CommandMessage, EventMessage


class InventoryCommandManager:
    def __init__(self) -> None:
        self.consumer: AIOKafkaConsumer = AIOKafkaConsumer(
            settings.KAFKA_COMMAND_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_URL,
            group_id=settings.KAFKA_GROUP_ID,
            enable_auto_commit=False,
            value_deserializer=lambda value: value.decode("utf-8"),
        )
        self.producer: AIOKafkaProducer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_URL,
            value_serializer=lambda value: value.encode("utf-8"),
        )
        self.processed_message_ids: set[uuid.UUID] = set()

    async def start(self) -> None:
        await self.consumer.start()
        await self.producer.start()
        logger.info("inventory_command_started")

    async def stop(self) -> None:
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("inventory_command_stopped")

    async def consume(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0)
                try:
                    data = await self.consumer.getmany(
                        timeout_ms=settings.KAFKA_CONSUMER_TIMEOUT,
                        max_records=settings.KAFKA_CONSUMER_MAX_RECORDS,
                    )
                except KafkaError as ex:
                    logger.error("Kafka connection lost or error occurred", error=ex)
                    await asyncio.sleep(5)
                    continue

                if not data:
                    continue

                try:
                    for _, messages in data.items():
                        for message in messages:
                            command = CommandMessage.model_validate_json(message.value)
                            await self.handle_command(command)
                except Exception as ex:
                    for tp, messages in data.items():
                        first_offset = messages[0].offset
                        logger.info(f"Seeking back to offset {first_offset} for partition {tp.partition}")
                        self.consumer.seek(tp, first_offset)

                    await asyncio.sleep(5)
                    continue
                else:
                    await self.consumer.commit()

        except asyncio.CancelledError:
            logger.info("Inventory command worker shutdown")

    async def handle_command(self, command: CommandMessage) -> None:
        if command.message_id in self.processed_message_ids:
            logger.info("inventory_command_skipped", message_id=str(command.message_id))
            return

        if command.command_type == "reserve_inventory":
            event_type = self._reserve_event_type(command.message_id)
        elif command.command_type == "cancel_reservation":
            event_type = "inventory.reservation-cancelled"
        else:
            self.processed_message_ids.add(command.message_id)
            logger.info("inventory_command_unknown", message_id=str(command.message_id))
            return

        event = EventMessage(
            event_type=event_type,
            saga_id=command.saga_id,
            order_id=command.order_id,
            payload=command.payload,
            message_id=command.message_id,
            timestamp=datetime.now(),
        )

        try:
            await self.producer.send_and_wait(
                topic=settings.KAFKA_ORDER_TOPIC,
                key=str(command.order_id).encode("utf-8"),
                value=event.model_dump_json(),
            )
        except KafkaError as ex:
            logger.error("Failed to send event to Kafka", data=event, error=ex)
            raise KafkaError from ex
        else:
            self.processed_message_ids.add(command.message_id)
            logger.info(
                "Inventory event published",
                event_type=event.event_type,
                order_id=str(command.order_id),
                saga_id=str(command.saga_id),
            )

    def _reserve_event_type(self, message_id: uuid.UUID) -> str:
        if message_id.int % 100 < 80:
            return "inventory.reserved"
        return "inventory.reserve-failed"


inventory_command_manager = InventoryCommandManager()
