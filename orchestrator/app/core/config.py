from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int

    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    KAFKA_BOOTSTRAP_SERVERS_HOST: str
    KAFKA_BOOTSTRAP_SERVERS_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def KAFKA_BOOTSTRAP_URL(self):
        return f"{self.KAFKA_BOOTSTRAP_SERVERS_HOST}:{self.KAFKA_BOOTSTRAP_SERVERS_PORT}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
