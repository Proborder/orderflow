from aiokafka import AIOKafkaProducer

from app.services.db_manager import DBManager


class BaseService:
    db: DBManager | None
    producer: AIOKafkaProducer | None

    def __init__(
        self,
        db: DBManager | None = None,
        producer: AIOKafkaProducer | None = None
    ) -> None:
        self.db = db
        self.producer = producer
