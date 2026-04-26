from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BOOTSTRAP_SERVERS_HOST: str
    KAFKA_BOOTSTRAP_SERVERS_PORT: int

    KAFKA_COMMAND_TOPIC: str
    KAFKA_GROUP_ID: str
    KAFKA_ORDER_TOPIC: str

    KAFKA_CONSUMER_TIMEOUT: int
    KAFKA_CONSUMER_MAX_RECORDS: int

    @property
    def KAFKA_BOOTSTRAP_URL(self):
        return f"{self.KAFKA_BOOTSTRAP_SERVERS_HOST}:{self.KAFKA_BOOTSTRAP_SERVERS_PORT}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
