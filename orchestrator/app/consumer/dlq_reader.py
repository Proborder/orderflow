import asyncio

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import CommitFailedError, KafkaError

from app.core.config import settings
from app.core.logger import logger
from app.schemas.messages import DlqEventMessage


class DLQReader:
    def __init__(self, consumer: AIOKafkaConsumer):
        self.consumer: AIOKafkaConsumer = consumer

    async def consume(self, stop_event: asyncio.Event):
        if self.consumer is None:
            raise RuntimeError("Kafka consumer is not initialized")

        try:
            while not stop_event.is_set():
                try:
                    data = await self.consumer.getmany(
                        timeout_ms=settings.KAFKA_CONSUMER_TIMEOUT,
                        max_records=settings.KAFKA_CONSUMER_MAX_RECORDS,
                    )
                except KafkaError as ex:
                    logger.error("Kafka connection lost or error occurred", error=ex)
                    await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                    continue

                if not data:
                    continue

                try:
                    for _, messages in data.items():
                        for message in messages:
                            event = DlqEventMessage.model_validate_json(message.value)
                            logger.error(
                                "Saga moved to DLQ | Type: %s | ID: %s | Retries: %s | Error: %s",
                                event.event_type,
                                event.saga_id,
                                event.retry_count,
                                event.last_error,
                                extra={
                                    "saga_id": str(event.saga_id),
                                    "failed_at": event.failed_at.isoformat(),
                                    "retry_count": event.retry_count
                                }
                            )

                    try:
                        await self.consumer.commit()
                    except CommitFailedError as ex:
                        logger.warning(
                            "Kafka rebalance occurred. Batch processed but offset not committed",
                            error=ex
                        )

                except Exception as ex:
                    logger.error("Dlq event batch processing failed", error=ex)
                    for tp, messages in data.items():
                        first_offset = messages[0].offset
                        logger.info(f"Seeking back to offset {first_offset} for partition {tp.partition}")
                        self.consumer.seek(tp, first_offset)

                    await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                    continue

        except asyncio.CancelledError:
            logger.info("Dlq reader worker shutdown")
