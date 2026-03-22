"""Configuration management for Clarity using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class ClaritySettings(BaseSettings):
    """Main settings class loads from .env file."""

    # Anthropic API
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")
    groq_api_key: str = Field(default="", description="Groq API key (optional alternative provider)")

    # InsForge Backend-as-a-Service
    insforge_url: str = Field(default="", description="InsForge project URL (legacy, can be empty)")
    insforge_api_key: str = Field(default="", description="InsForge API key (legacy, can be empty)")
    insforge_database_url: str = Field(default="", description="InsForge PostgreSQL connection string")

    # TinyFish Web Verification (Person B)
    tinyfish_api_key: str = Field(default="", description="TinyFish API key for web fact-checking")

    # Ada Conversational Explainer (Person C)
    ada_api_url: str = Field(default="", description="Ada API endpoint")
    ada_api_key: str = Field(default="", description="Ada API key")

    # Clarity Configuration
    clarity_env: str = Field(default="development", description="Environment: development, staging, production")
    clarity_log_level: str = Field(default="INFO", description="Log level")
    clarity_confidence_samples: int = Field(default=3, description="Number of samples for confidence agent")
    clarity_verifier_model: str = Field(
        default="claude-sonnet-4-6",
        description="Model used by verification/auditor agents",
    )

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Global settings singleton
settings = ClaritySettings()
