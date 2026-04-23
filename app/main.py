"""
app/main.py — TimesFM Action Server v2 (ccxt edition)

Endpoints:
  GET  /health
  POST /forecast          → ticker, horizon, exchange, use_covariates
  POST /forecast/both     → BTC + ETH en paralelo
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.data import utc_now_iso
from app.forecaster import run_forecast
from app.model import get_device_info, is_loaded, load_model
from app.schemas import (
    BothForecastRequest,
    BothForecastResponse,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
)

# ─── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-30s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carga TimesFM al iniciar, libera recursos al cerrar."""
    logger.info("══════ TimesFM Action Server v2 arrancando ══════")
    try:
        # asyncio.to_thread evita bloquear el event loop durante la carga del modelo
        await asyncio.to_thread(load_model, settings)
        logger.info("✓ Modelo listo en %s", get_device_info())
    except Exception as exc:
        # El server arranca igualmente; /health reportará el fallo
        logger.critical("Fallo al cargar modelo: %s", exc, exc_info=True)
    yield
    logger.info("══════ TimesFM Action Server v2 cerrando ══════")


# ─── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TimesFM Action Server v2",
    description=(
        "API de predicción crypto con TimesFM 2.0 (500M PyTorch) + ccxt.\n\n"
        "Soporta BTC-USD y ETH-USD. Exchange configurable por petición.\n"
        "Optimizado para NVIDIA RTX 4060/4070 (Asus TUF Gaming)."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("ValueError: %s | path=%s", exc, request.url.path)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def _runtime_error(request: Request, exc: RuntimeError) -> JSONResponse:
    logger.error("RuntimeError: %s | path=%s", exc, request.url.path)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servidor y del modelo",
    tags=["ops"],
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if is_loaded() else "loading",
        model_loaded=is_loaded(),
        device=get_device_info(),
        timestamp=utc_now_iso(),
    )


@app.post(
    "/forecast",
    response_model=ForecastResponse,
    summary="Forecast de un único ticker",
    tags=["forecast"],
)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """
    Forecast de precio crypto con TimesFM.

    Ejemplo (Binance):
    ```json
    {"ticker": "BTC-USD", "horizon": 30, "exchange": "binance"}
    ```
    Ejemplo (Bybit con covariables):
    ```json
    {"ticker": "ETH-USD", "horizon": 14, "exchange": "bybit", "use_covariates": true}
    ```
    """
    if not is_loaded():
        raise HTTPException(503, detail="Modelo cargando — intenta en unos segundos")

    logger.info(
        "POST /forecast | ticker=%s exchange=%s horizon=%d covariates=%s",
        req.ticker, req.exchange, req.horizon, req.use_covariates,
    )

    try:
        result: ForecastResponse = await asyncio.to_thread(
            run_forecast,
            req.ticker,
            req.horizon,
            req.use_covariates,
            req.exchange,
        )
        return result
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error en /forecast: %s", exc, exc_info=True)
        raise HTTPException(500, detail=f"Error de inferencia: {exc}") from exc


@app.post(
    "/forecast/both",
    response_model=BothForecastResponse,
    summary="Forecast paralelo de BTC-USD y ETH-USD",
    tags=["forecast"],
)
async def forecast_both(req: BothForecastRequest) -> BothForecastResponse:
    """
    Ejecuta BTC-USD y ETH-USD concurrentemente usando asyncio.gather.

    Ejemplo:
    ```json
    {"horizon": 14, "exchange": "bybit", "use_covariates": false}
    ```
    """
    if not is_loaded():
        raise HTTPException(503, detail="Modelo cargando — intenta en unos segundos")

    logger.info(
        "POST /forecast/both | exchange=%s horizon=%d covariates=%s",
        req.exchange, req.horizon, req.use_covariates,
    )

    try:
        btc_coro = asyncio.to_thread(
            run_forecast, "BTC-USD", req.horizon, req.use_covariates, req.exchange
        )
        eth_coro = asyncio.to_thread(
            run_forecast, "ETH-USD", req.horizon, req.use_covariates, req.exchange
        )

        btc_result, eth_result = await asyncio.gather(btc_coro, eth_coro)

        return BothForecastResponse(
            btc=btc_result,
            eth=eth_result,
            exchange=req.exchange,
            timestamp=utc_now_iso(),
        )
    except Exception as exc:
        logger.error("Error en /forecast/both: %s", exc, exc_info=True)
        raise HTTPException(500, detail=f"Error de inferencia paralela: {exc}") from exc


# ─── Entrypoint directo ────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,    # SIEMPRE 1 — modelo singleton en VRAM
        log_level=settings.LOG_LEVEL,
        reload=False,
    )
