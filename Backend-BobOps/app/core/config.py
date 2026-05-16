from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "BobOps2 — DevFlow AI"
    DEBUG: bool = False

    # Supabase / PostgreSQL
    DATABASE_URL: str
    SUPABASE_URL: str = "https://atyinelljklmiowkmyhe.supabase.co"
    SUPABASE_ANON_KEY: str  # requerida — obtener en supabase.com → Project Settings → API
    SUPABASE_SERVICE_ROLE_KEY: str  # requerida — service_role key para Admin API

    # AI Provider selector: "ibm" | "openrouter"
    AI_PROVIDER: str = "ibm"

    # IBM watsonx
    IBM_BOB_API_KEY: str = ""
    IBM_BOB_BASE_URL: str = "https://us-south.ml.cloud.ibm.com"
    IBM_BOB_PROJECT_ID: str = ""
    IBM_BOB_MODEL_ID: str = "ibm/granite-8b-code-instruct"

    # OpenRouter (OpenAI-compatible)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openrouter/free"

    # JWT (fallback HS256 para compatibilidad)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"

settings = Settings()