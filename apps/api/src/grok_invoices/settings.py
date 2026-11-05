from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from the environment, or from `.env` when running locally."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path(".data")
    release: str | None = None  # Only set on the server.
    platform_api_key: str | None = None
    demo_client_phone: str | None = None
    invoice_agent_token: str | None = None
    regulations_agent_token: str | None = None
    client_invite_token: str | None = None  # MCP invite. Not the platform API key.
    secret_encryption_key: str | None = None  # Fernet key for the KSeF token.


def get_settings() -> Settings:
    return Settings()
