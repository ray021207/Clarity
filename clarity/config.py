"""Configuration management for Clarity using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class ClaritySettings(BaseSettings):
    """Main settings class loads from .env file."""

    # Anthropic API
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")

    # InsForge Backend-as-a-Service
    insforge_url: str = Field(..., description="InsForge project URL")
    insforge_api_key: str = Field(..., description="InsForge API key")

    # TinyFish Web Verification (Person B)
    tinyfish_api_key: str = Field(default="", description="TinyFish API key for web fact-checking")

    # Ada Conversational Explainer (Person C)
    ada_api_url: str = Field(default="", description="Ada API endpoint")
    ada_api_key: str = Field(default="", description="Ada API key")

    # Clarity Configuration
    clarity_env: str = Field(default="development", description="Environment: development, staging, production")
    clarity_log_level: str = Field(default="INFO", description="Log level")
    clarity_confidence_samples: int = Field(default=3, description="Number of samples for confidence agent")

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


# Global settings singleton
settings = ClaritySettings()
