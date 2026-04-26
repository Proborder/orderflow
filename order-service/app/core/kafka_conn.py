from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.core.logger import logger


class KafkaManager:
    def __init__(self, bootstrap_servers: str):
        self.producer: AIOKafkaProducer | None = None
        self.bootstrap_servers = bootstrap_servers

    async def setup(self):
        logger.info(f"Connect to Kafka bootstrap server: {self.bootstrap_servers}")
        self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers, enable_idempotence=True)
        await self.producer.start()
        logger.info(f"Success connect to Kafka bootstrap server: {self.bootstrap_servers}")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")


kafka_manager = KafkaManager(bootstrap_servers=settings.KAFKA_BOOTSTRAP_URL)
