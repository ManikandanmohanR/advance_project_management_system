from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    APP_NAME: str = "Project & Team Management API"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "pm_system"
    DATABASE_URL_OVERRIDE: str | None = None  # used by tests

    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"

    FIRST_ADMIN_NAME: str = "Admin"
    FIRST_ADMIN_EMAIL: str = "admin@gmail.com"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"

    @property
    def database_url(self):
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return URL.create(
            "mysql+pymysql", username=self.DB_USER, password=self.DB_PASSWORD,
            host=self.DB_HOST, port=self.DB_PORT, database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        )


settings = Settings()
