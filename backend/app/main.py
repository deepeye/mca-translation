from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.reviews import router as reviews_router
from app.api.upload import router as upload_router
from app.api.ws import router as ws_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="CulturalBridge API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(reviews_router)
app.include_router(upload_router)
app.include_router(ws_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
