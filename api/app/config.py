from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

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
        env_file = ".env"

settings = Settings()

