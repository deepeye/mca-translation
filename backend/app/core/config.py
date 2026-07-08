from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://culturalbridge:culturalbridge@localhost:5432/culturalbridge"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-to-a-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BAILIAN_API_KEY: str = ""
    BAILIAN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    BAILIAN_MODEL_PLUS: str = "qwen-plus"
    BAILIAN_MODEL_MAX: str = "qwen-max"
    MCA_FILE_STORE_DIR: str = "./uploads"
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_CONCURRENT_LANGS: int = 4

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
