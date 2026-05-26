"""
Opus Backtrader - FastAPI Application

Main entry point for the backend API server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.routes import health, backtest, strategies, data, scraper, converter
from .ws.backtest_ws import backtest_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="AI-powered quantitative trading system API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(health.router)
app.include_router(backtest.router, prefix=settings.api_prefix)
app.include_router(strategies.router, prefix=settings.api_prefix)
app.include_router(data.router, prefix=settings.api_prefix)
app.include_router(scraper.router, prefix=settings.api_prefix)
app.include_router(converter.router, prefix=settings.api_prefix)

# WebSocket
app.websocket("/ws/backtest")(backtest_websocket)
