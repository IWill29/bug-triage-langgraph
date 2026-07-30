"""
Configuration management for the triage service
Loads settings from environment variables
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
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
    
    # LangSmith (optional)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "bug-triage-dev"
    langsmith_tracing: bool = True
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    
    # LLM Models
    fast_model: str = "gpt-4o-mini"
    premium_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"
    
    # Thresholds
    confidence_threshold: float = 0.70
    embedding_threshold: float = 0.72
    duplicate_confidence_threshold: float = 0.80
    
    # Retry limits
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
