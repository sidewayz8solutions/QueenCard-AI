from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routes.jobs import router as jobs_router
from .routes.storage import router as storage_router
from .routes.loras import router as loras_router
from .routes.models import router as models_router
from .routes.training import router as training_router

app = FastAPI(title="queencard-ai control plane")

# Allow all origins in development
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    settings.FRONTEND_ORIGIN,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(jobs_router, prefix="/api", tags=["jobs"])
app.include_router(storage_router, prefix="/api", tags=["storage"])
app.include_router(loras_router, prefix="/api", tags=["loras"])
app.include_router(models_router, prefix="/api", tags=["models"])
app.include_router(training_router, prefix="/api", tags=["training"])

@app.get("/health")
def health():
    return {"ok": True}

