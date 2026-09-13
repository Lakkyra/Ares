"""Ares configuration settings managed via Pydantic."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    app_name: str = "Ares"
    app_version: str = "0.1.0"
    debug: bool = False

    # LLM Provider configuration
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude models")
    openai_api_key: str = Field(default="", description="OpenAI API key for GPT models")
    primary_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Primary agent model"
    )
    fallback_model: str = Field(default="gpt-4o", description="Fallback agent model")

    # Observability (Langfuse)
    langfuse_public_key: str = Field(default="", description="Langfuse public API key")
    langfuse_secret_key: str = Field(default="", description="Langfuse secret key")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )

    # Checkpointer Database (PostgreSQL)
    postgres_host: str = Field(default="localhost", description="Postgres host for checkpointing")
    postgres_port: int = Field(default=5432, description="Postgres port")
    postgres_db: str = Field(default="ares_checkpoints", description="Postgres database name")
    postgres_user: str = Field(default="ares", description="Postgres user")
    postgres_password: str = Field(default="ares_password", description="Postgres password")

    # Sandbox configuration
    sandbox_image: str = Field(
        default="ares-sandbox:latest", description="Docker image for sandbox"
    )
    sandbox_timeout_seconds: int = Field(default=30, description="Max execution time per test run")
    sandbox_memory_limit: str = Field(default="1g", description="Container memory limit")
    sandbox_cpu_limit: float = Field(default=1.0, description="Container CPU limit")

    @property
    def postgres_dsn(self) -> str:
        """Construct PostgreSQL connection DSN."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
