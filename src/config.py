"""
Configuration management for the triage service
Loads settings from environment variables
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    """Application configuration loaded from environment"""
    
    # Database
    database_url: str
    
    # Gitea
    gitea_url: str
    gitea_token: str
    gitea_repo_owner: str = "triagebot"
    gitea_repo_name: str = "bug-reports"
    
    # OpenAI
    openai_api_key: str

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Rate limiting (POST /api/triage)
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    
    # LLM Models
    fast_model: str = "gpt-4o-mini"
    premium_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536
    
    # Thresholds
    confidence_threshold: float = 0.70
    embedding_threshold: float = 0.72
    duplicate_confidence_threshold: float = 0.80
    
    # Retry limits
    max_retries: int = 3


# Global settings instance
settings = Settings()
