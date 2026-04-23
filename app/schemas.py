"""
app/schemas.py — Pydantic v2 request/response models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SUPPORTED_TICKERS: frozenset[str] = frozenset({"BTC-USD", "ETH-USD"})


# ─── Requests ──────────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    ticker: str = Field(..., examples=["BTC-USD"])
    horizon: int = Field(default=30, ge=1, le=512, description="Pasos a predecir (días)")
    use_covariates: bool = Field(default=False, description="Fear&Greed + Volumen como covariables")
    exchange: str = Field(default="binance", description="Exchange ccxt (binance, bybit, okx…)")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in SUPPORTED_TICKERS:
            raise ValueError(f"ticker debe ser uno de {sorted(SUPPORTED_TICKERS)}")
        return v

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        return v.lower().strip()


class BothForecastRequest(BaseModel):
    horizon: int = Field(default=30, ge=1, le=512)
    use_covariates: bool = Field(default=False)
    exchange: str = Field(default="binance")

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        return v.lower().strip()


# ─── Responses ─────────────────────────────────────────────────────────────────

class QuantileInfo(BaseModel):
    level: float
    values: list[float]


class ForecastResponse(BaseModel):
    ticker: str
    exchange: str                          # 🆕
    last_price: float
    forecast_mean: list[float]
    quantiles: list[QuantileInfo]
    horizon: int
    context_length: int
    timestamp: str
    model_version: str = "timesfm-2.0-500m-pytorch"
    covariates_used: bool = False


class BothForecastResponse(BaseModel):
    btc: ForecastResponse
    eth: ForecastResponse
    exchange: str
    timestamp: str


class HealthResponse(BaseModel):
    status: Literal["ok", "loading", "error"]
    model_loaded: bool
    device: str
    timestamp: str
