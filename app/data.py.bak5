"""
app/data.py — Orquestador de datos.

Responsabilidades:
  - Delegar precios y volumen a CCXTHandler (Skill CCXT).
  - Obtener Fear & Greed Index desde API externa.
  - Construir matriz de covariables (volumen log-normalizado + F&G).
  - Proveer instancias CCXTHandler cacheadas por exchange_id.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import numpy as np
import requests

from app.config import get_settings
from app.skills.ccxt_skill import CCXTHandler

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Cache de handlers por exchange ───────────────────────────────────────────

@lru_cache(maxsize=8)
def _get_handler(exchange_id: str) -> CCXTHandler:
    """
    Devuelve (y cachea) una instancia CCXTHandler por exchange_id.
    El caché evita re-instanciar el cliente ccxt en cada petición.
    """
    logger.info("Creando CCXTHandler para exchange: %s", exchange_id)
    return CCXTHandler(
        exchange_id=exchange_id,
        limit=settings.CCXT_LIMIT,
        timeframe=settings.CCXT_TIMEFRAME,
    )


# ─── Precio de cierre ──────────────────────────────────────────────────────────

def fetch_close_prices(
    ticker: str,
    exchange_id: str = "binance",
) -> tuple[np.ndarray, float, int]:
    """
    Obtiene precios de cierre diarios vía CCXTHandler.

    Returns
    -------
    prices       : np.ndarray float32 (N,)
    last_price   : float
    context_len  : int
    """
    handler = _get_handler(exchange_id)
    return handler.fetch_close_prices(ticker, max_context=settings.TIMESFM_CONTEXT_LEN)


# ─── Volumen ───────────────────────────────────────────────────────────────────

def fetch_volume(
    ticker: str,
    context_len: int,
    exchange_id: str = "binance",
) -> Optional[np.ndarray]:
    """
    Obtiene volumen diario vía CCXTHandler.
    Devuelve None si falla (el pipeline de covariables degrada gracefully).
    """
    handler = _get_handler(exchange_id)
    vol = handler.fetch_volume(ticker, max_context=settings.TIMESFM_CONTEXT_LEN)
    if vol is not None:
        return vol[-context_len:]
    return None


# ─── Fear & Greed Index ────────────────────────────────────────────────────────

def fetch_fear_greed(limit: int = 512) -> Optional[np.ndarray]:
    """
    Descarga Fear & Greed Index histórico desde api.alternative.me.
    Devuelve array float32 en orden cronológico (más antiguo primero).
    Devuelve None si la API no responde.
    """
    try:
        url = f"{settings.FEAR_GREED_API}?limit={limit}&format=json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "data" not in data:
            raise ValueError("Respuesta inesperada de Fear & Greed API")

        values = [float(entry["value"]) for entry in data["data"]]
        values.reverse()   # La API devuelve newest-first; invertir a cronológico

        arr = np.array(values, dtype=np.float32)
        logger.info("Fear & Greed: %d entradas obtenidas", len(arr))
        return arr

    except requests.exceptions.Timeout:
        logger.warning("Fear & Greed API timeout")
        return None
    except Exception as exc:
        logger.warning("Fear & Greed fetch fallido: %s", exc)
        return None


# ─── Covariables ───────────────────────────────────────────────────────────────

def build_covariates(
    ticker: str,
    context_len: int,
    exchange_id: str = "binance",
) -> Optional[np.ndarray]:
    """
    Construye matriz de covariables de forma (context_len, num_features).

    Features (todas normalizadas a [0, 1]):
      col 0 — Volumen log-normalizado
      col 1 — Fear & Greed / 100

    Devuelve None si ningún feature está disponible.
    """
    features: list[np.ndarray] = []

    # ── Feature 0: Volumen log-normalizado ────────────────────────────────────
    vol = fetch_volume(ticker, context_len, exchange_id)
    if vol is not None and len(vol) >= context_len:
        vol_trimmed = vol[-context_len:]
        log_vol = np.log1p(vol_trimmed.astype(np.float64))
        vol_range = log_vol.max() - log_vol.min()
        if vol_range > 1e-8:
            vol_norm = ((log_vol - log_vol.min()) / vol_range).astype(np.float32)
        else:
            vol_norm = np.zeros(context_len, dtype=np.float32)
        features.append(vol_norm)
        logger.debug("Covariable Volumen añadida | shape=%s", vol_norm.shape)
    else:
        logger.warning("Volumen no disponible o insuficiente para %s", ticker)

    # ── Feature 1: Fear & Greed ────────────────────────────────────────────────
    fg = fetch_fear_greed(limit=context_len + 30)
    if fg is not None and len(fg) >= context_len:
        fg_trimmed = (fg[-context_len:] / 100.0).astype(np.float32)
        features.append(fg_trimmed)
        logger.debug("Covariable Fear & Greed añadida | shape=%s", fg_trimmed.shape)
    else:
        logger.warning("Fear & Greed no disponible o insuficiente")

    if not features:
        logger.warning("Sin covariables disponibles para %s — pipeline degradado", ticker)
        return None

    cov_matrix = np.column_stack(features)   # (context_len, num_features)
    logger.info(
        "Covariables construidas para %s@%s | shape=%s | features=%d",
        ticker, exchange_id, cov_matrix.shape, len(features),
    )
    return cov_matrix


# ─── Utilidad ──────────────────────────────────────────────────────────────────

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
