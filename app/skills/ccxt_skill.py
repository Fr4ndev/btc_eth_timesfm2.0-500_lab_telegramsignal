"""
app/skills/ccxt_skill.py — Skill de obtención de datos OHLCV vía CCXT.

Responsabilidades:
  - Conectar a cualquier exchange compatible con ccxt.
  - Convertir tickers "BTC-USD" → "BTC/USDT" (formato ccxt).
  - Garantizar serie diaria continua sin huecos ni NaN (reindex + ffill).
  - Manejo granular de ccxt.NetworkError / ccxt.ExchangeError.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import ccxt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Mapeo de sufijos a quote currency ────────────────────────────────────────

_QUOTE_MAP: dict[str, str] = {
    "USD":  "USDT",
    "USDT": "USDT",
    "BUSD": "BUSD",
    "EUR":  "EUR",
}


def _normalize_symbol(ticker: str) -> str:
    """
    Convierte 'BTC-USD' → 'BTC/USDT', 'ETH-USDT' → 'ETH/USDT', etc.
    Si el formato ya es 'BASE/QUOTE', lo devuelve sin cambios.
    """
    ticker = ticker.upper().strip()

    if "/" in ticker:
        return ticker  # ya está en formato ccxt

    if "-" in ticker:
        base, quote = ticker.split("-", 1)
        quote = _QUOTE_MAP.get(quote, quote)
        return f"{base}/{quote}"

    # Sin separador: asumir que los últimos 4 chars son USDT
    if ticker.endswith("USDT"):
        return f"{ticker[:-4]}/USDT"
    if ticker.endswith("USD"):
        return f"{ticker[:-3]}/USDT"

    raise ValueError(f"No se puede normalizar el ticker: {ticker!r}")


# ─── CCXTHandler ───────────────────────────────────────────────────────────────

class CCXTHandler:
    """
    Wrapper sobre ccxt para obtener OHLCV diario de un exchange dado.

    Parameters
    ----------
    exchange_id : str   Identificador ccxt (ej: "binance", "bybit", "okx")
    limit       : int   Número máximo de velas a pedir (default 1000)
    timeframe   : str   Temporalidad ccxt (default "1d")
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        limit: int = 1000,
        timeframe: str = "1d",
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self.limit = limit
        self.timeframe = timeframe

        exchange_class = getattr(ccxt, self.exchange_id, None)
        if exchange_class is None:
            raise ValueError(
                f"Exchange '{exchange_id}' no encontrado en ccxt. "
                f"Disponibles: {ccxt.exchanges[:10]}…"
            )

        self._exchange: ccxt.Exchange = exchange_class(
            {
                "enableRateLimit": True,
                "timeout": 30_000,  # 30 s
            }
        )
        logger.info("CCXTHandler inicializado | exchange=%s timeframe=%s limit=%d",
                    self.exchange_id, self.timeframe, self.limit)

    # ── Fetching interno ───────────────────────────────────────────────────────

    def _fetch_raw_ohlcv(self, symbol: str) -> pd.DataFrame:
        """
        Descarga velas OHLCV y devuelve DataFrame con índice DatetimeIndex UTC.
        Maneja paginación implícita en ccxt si el exchange limita las respuestas.
        """
        try:
            logger.debug("Descargando OHLCV | exchange=%s symbol=%s",
                         self.exchange_id, symbol)
            raw = self._exchange.fetch_ohlcv(
                symbol,
                timeframe=self.timeframe,
                limit=self.limit,
            )
        except ccxt.NetworkError as exc:
            logger.error("NetworkError en %s/%s: %s", self.exchange_id, symbol, exc)
            raise RuntimeError(
                f"Error de red al conectar con {self.exchange_id}: {exc}"
            ) from exc
        except ccxt.ExchangeError as exc:
            logger.error("ExchangeError en %s/%s: %s", self.exchange_id, symbol, exc)
            raise RuntimeError(
                f"Error del exchange {self.exchange_id} para {symbol}: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("Error inesperado en %s/%s: %s", self.exchange_id, symbol, exc)
            raise RuntimeError(f"Error inesperado: {exc}") from exc

        if not raw:
            raise ValueError(
                f"El exchange {self.exchange_id} devolvió datos vacíos para {symbol}"
            )

        df = pd.DataFrame(
            raw,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("datetime").drop(columns=["timestamp"])
        df = df.sort_index()

        logger.debug("OHLCV raw: %d filas | %s → %s",
                     len(df), df.index[0].date(), df.index[-1].date())
        return df

    # ── Limpieza / reindex ─────────────────────────────────────────────────────

    @staticmethod
    def _fill_gaps(df: pd.DataFrame) -> pd.DataFrame:
        """
        Asegura frecuencia diaria continua sin huecos ni NaN.
        Estrategia: reindex a rango completo + forward-fill OHLCV, volume=0 en días huecos.
        """
        if df.empty:
            return df

        full_range = pd.date_range(
            start=df.index[0].normalize(),
            end=df.index[-1].normalize(),
            freq="D",
            tz="UTC",
        )
        df_reindexed = df.reindex(full_range)

        # Close, Open, High, Low → forward-fill (precio no cambió)
        for col in ["open", "high", "low", "close"]:
            df_reindexed[col] = df_reindexed[col].ffill()

        # Volume en días huecos → 0 (mercado cerrado / sin datos)
        df_reindexed["volume"] = df_reindexed["volume"].fillna(0.0)

        filled = len(full_range) - len(df)
        if filled > 0:
            logger.debug("Gaps rellenados: %d días", filled)

        return df_reindexed

    # ── API pública ────────────────────────────────────────────────────────────

    def fetch_ohlcv(self, ticker: str) -> pd.DataFrame:
        """
        Devuelve DataFrame OHLCV diario limpio (sin huecos, sin NaN).

        Parameters
        ----------
        ticker : str   Ej: "BTC-USD", "ETH/USDT", "SOL-USD"

        Returns
        -------
        pd.DataFrame  Columnas: open, high, low, close, volume | índice: DatetimeIndex UTC
        """
        symbol = _normalize_symbol(ticker)
        logger.info("Fetching OHLCV | %s → %s @ %s", ticker, symbol, self.exchange_id)

        df = self._fetch_raw_ohlcv(symbol)
        df = self._fill_gaps(df)

        if len(df) < 64:
            raise ValueError(
                f"Historial insuficiente para {ticker}: {len(df)} filas (mínimo 64)"
            )

        logger.info("OHLCV listo | %s: %d filas | last_close=%.4f",
                    ticker, len(df), df["close"].iloc[-1])
        return df

    def fetch_close_prices(
        self,
        ticker: str,
        max_context: int = 512,
    ) -> tuple[np.ndarray, float, int]:
        """
        Devuelve array de precios de cierre listo para TimesFM.

        Returns
        -------
        prices       : np.ndarray float32 shape (N,)
        last_price   : float
        context_len  : int
        """
        df = self.fetch_ohlcv(ticker)
        closes = df["close"].iloc[-max_context:].to_numpy(dtype=np.float32)
        return closes, float(closes[-1]), len(closes)

    def fetch_volume(
        self,
        ticker: str,
        max_context: int = 512,
    ) -> Optional[np.ndarray]:
        """
        Devuelve array de volumen diario (float32) alineado con close prices.
        Devuelve None si el fetch falla (el pipeline degrada gracefully).
        """
        try:
            df = self.fetch_ohlcv(ticker)
            vol = df["volume"].iloc[-max_context:].to_numpy(dtype=np.float32)
            return vol
        except Exception as exc:
            logger.warning("Fallo fetch_volume para %s: %s", ticker, exc)
            return None

    def last_price(self, ticker: str) -> float:
        """Precio de cierre más reciente."""
        symbol = _normalize_symbol(ticker)
        try:
            ticker_data = self._exchange.fetch_ticker(symbol)
            return float(ticker_data["last"])
        except Exception:
            # Fallback: último close del OHLCV
            _, price, _ = self.fetch_close_prices(ticker, max_context=1)
            return price
