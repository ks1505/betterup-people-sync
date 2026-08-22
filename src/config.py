import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BetterUp People Tech Onboarding Sync Engine"
    API_V1_STR: str = "/api/v1"
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "mock-anthropic-key")
    USE_MOCK_AI: bool = True  # Fallback to simulated Claude responses if API key is mock
    HARDWARE_SLA_DAYS: int = 7
    BACKGROUND_CHECK_SLA_DAYS: int = 5
    OKTA_PROVISION_SLA_DAYS: int = 3
    AUDIT_LOG_FILE: str = os.path.join(os.path.dirname(__file__), "..", "audit_ledger.json")

settings = Settings()
