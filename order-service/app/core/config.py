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

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self):
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def KAFKA_BOOTSTRAP_URL(self):
        return f"{self.KAFKA_BOOTSTRAP_SERVERS_HOST}:{self.KAFKA_BOOTSTRAP_SERVERS_PORT}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
