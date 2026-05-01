from app.core.config import settings
from app.core.kafka_conn import kafka_manager
from app.schemas.messages import CommandMessage, OrderEventMessage


class CommandsProducer:
    def __init__(self):
        self.producer = kafka_manager.producer

    async def send_inventory_command(self, command: CommandMessage) -> None:
        await self.producer.send_and_wait(
            topic=settings.KAFKA_INVENTORY_COMMANDS_TOPIC,
            value=command.model_dump_json(),
            key=str(command.order_id)
        )

    async def send_payment_command(self, command: CommandMessage) -> None:
        await self.producer.send_and_wait(
            topic=settings.KAFKA_PAYMENT_COMMANDS_TOPIC,
            value=command.model_dump_json(),
            key=str(command.order_id)
        )

    async def send_order_status(self, message: OrderEventMessage) -> None:
        await self.producer.send_and_wait(
            topic=settings.KAFKA_ORDER_TOPIC,
            value=message.model_dump_json(),
            key=str(message.order_id)
        )
