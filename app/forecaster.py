"""
app/forecaster.py - Procesador de Salida de TimesFM 2.5 (CORREGIDO: con 'horizon')
"""
import logging
from typing import Optional

import numpy as np

from app.data import fetch_close_prices, utc_now_iso
from app.model import get_model
from app.schemas import ForecastResponse, QuantileInfo

logger = logging.getLogger(__name__)

# Niveles de cuantiles estándar que suele devolver el modelo
QUANTILE_LEVELS = [0.1, 0.25, 0.5, 0.75, 0.9]

def run_forecast(ticker: str, horizon: int, use_covariates: bool, exchange: str) -> ForecastResponse:
    """
    Ejecuta la predicción y formatea la respuesta.
    """
    # 1. Obtener datos (CCXT)
    prices, last_price, context_len = fetch_close_prices(ticker, exchange_id=exchange)
    
    # 2. Preparar entradas para TimesFM
    inputs = [prices]

    logger.info("Iniciando inferencia TimesFM para %s (horizon=%d)", ticker, horizon)

    try:
        model = get_model()
        
        # 3. Llamar al modelo (✅ AHORA SÍ LE PASAMOS EL HORIZON)
        raw_point, raw_quantiles = model.forecast(
            inputs=inputs,
            horizon=horizon  # <--- ESTE ERA EL CAMPO FALTANTE
        )

        # 4. Procesar 'forecast_mean' (Predicción media/punto)
        mean_vals = raw_point[0].flatten().tolist()[:horizon]

        # 5. Procesar 'quantiles'
        q_data = raw_quantiles[0] # (horizon, num_quantiles)
        num_q_available = q_data.shape[-1]
        levels = QUANTILE_LEVELS
        
        if num_q_available != len(levels):
            levels = [i / (num_q_available + 1) for i in range(1, num_q_available + 1)]

        quantile_list = []
        for i, level in enumerate(levels):
            if i < num_q_available:
                q_values = q_data[:horizon, i].tolist()
                quantile_list.append(QuantileInfo(level=level, values=q_values))

        # 6. Construir la Respuesta Final
        return ForecastResponse(
            ticker=ticker,
            exchange=exchange,
            last_price=float(last_price),
            forecast_mean=mean_vals,
            quantiles=quantile_list,
            horizon=horizon,
            context_length=context_len,
            timestamp=utc_now_iso(),
            covariates_used=use_covariates
        )

    except Exception as e:
        logger.error("Error durante la inferencia: %s", e, exc_info=True)
        raise RuntimeError(f"Error en la predicción: {e}")
