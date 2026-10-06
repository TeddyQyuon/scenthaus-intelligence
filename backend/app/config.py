from pathlib import Path
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/scenthaus"
    )
    secret_key: str = "development-only-change-this-secret-key"
    environment: str = "development"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    artifact_dir: Path = Path(__file__).resolve().parents[1] / "artifacts"
    admin_email: str = "admin@scenthaus.demo"
    admin_password: str = ""
    demo_mode: bool = True
    mlflow_tracking_uri: str = "sqlite:///" + str(
        Path(__file__).resolve().parents[1] / "mlflow.db"
    )
    retention_days: int = 180
    cron_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def secure(self):
        if self.database_url.startswith(("postgres://", "postgresql://")):
            self.database_url = (
                "postgresql+psycopg://" + self.database_url.split("://", 1)[1]
            )
        if self.environment == "production" and (
            len(self.secret_key) < 32 or self.secret_key.startswith("development")
        ):
            raise ValueError(
                "Production requires a unique SECRET_KEY of at least 32 characters"
            )
        return self

    @property
    def origins(self):
        origins = [s.strip() for s in self.allowed_origins.split(",") if s.strip()]
        for key in ["VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"]:
            host = os.environ.get(key, "")
            if host and "/" not in host and ":" not in host:
                origins.append("https://" + host)
        return list(dict.fromkeys(origins))


settings = Settings()
