from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

# Get the project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Supabase (mapped from NEXT_PUBLIC_ prefixed vars)
    SUPABASE_URL: str = Field(validation_alias="NEXT_PUBLIC_SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(validation_alias="NEXT_PUBLIC_SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(validation_alias="NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY")

    # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_BUCKET_NAME: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_ENDPOINT: str

    # RunPod
    RUNPOD_API_KEY: str
    RUNPOD_ENDPOINT_ID: str

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        extra = "ignore"

settings = Settings()

