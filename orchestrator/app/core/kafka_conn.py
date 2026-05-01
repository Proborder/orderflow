from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.core.config import settings
from app.core.logger import logger


class KafkaManager:
    def __init__(self, bootstrap_servers: str):
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.bootstrap_servers = bootstrap_servers

    async def setup(self):
        logger.info(f"Connect to Kafka bootstrap server: {self.bootstrap_servers}")
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            enable_idempotence=True,
            value_serializer=lambda value: value.encode("utf-8"),
            key_serializer=lambda key: key.encode("utf-8")
        )
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_ORDER_TOPIC,
            bootstrap_servers=self.bootstrap_servers,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            enable_auto_commit=False,
            value_deserializer=lambda value: value.decode("utf-8")
        )
        try:
            await self.producer.start()
            await self.consumer.start()
        except Exception as ex:
            await self.stop()
            logger.error("Kafka consumer or producer error", error=ex)
            raise

        logger.info(f"Success connect to Kafka bootstrap server: {self.bootstrap_servers}")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")


kafka_manager = KafkaManager(bootstrap_servers=settings.KAFKA_BOOTSTRAP_URL)
