from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os

# Get the project root directory (2 levels up from this file)
# Also check if we're running from api/ or project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
API_ROOT = Path(__file__).parent.parent

# Find .env file - check multiple locations
def find_env_file():
    candidates = [
        PROJECT_ROOT / ".env",
        API_ROOT / ".env",
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(PROJECT_ROOT / ".env")

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
        env_file = find_env_file()
        extra = "ignore"

settings = Settings()

