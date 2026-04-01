from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_engine
from app.routers import health, teams, members, environments, promotion
from app.routers.members import transfer_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engine = init_engine(settings.DATABASE_URL)
    yield
    await engine.dispose()


app = FastAPI(
    title="DevExForge API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(teams.router)
app.include_router(members.router)
app.include_router(transfer_router)
app.include_router(environments.router)
app.include_router(promotion.router)
