from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = Field(
        default="dev-only-change-me",
        validation_alias="SECRET_KEY",
    )

    database_url: str = Field(
        default="postgresql+psycopg://app:app@localhost:5432/payment_endpoint",
        validation_alias="DATABASE_URL",
    )

    debug: bool = Field(
        default=False,
        validation_alias="FLASK_DEBUG",
    )

    test_database_url: str | None = Field(
        default=None,
        validation_alias="TEST_DATABASE_URL",
    )

