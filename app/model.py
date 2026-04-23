"""
app/model.py - SOLUCIÓN DEFINITIVA: Parámetros correctos de ForecastConfig
"""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_model: Optional[Any] = None
_model_loaded: bool = False
_device_info: str = "unloaded"

def load_model(settings):
    global _model, _model_loaded, _device_info

    logger.info("Cargando TimesFM 2.5-200M...")

    try:
        import timesfm
        from timesfm.configs import ForecastConfig

        # 1. Cargar el modelo
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            "google/timesfm-2.5-200m-pytorch",
            torch_compile=False, 
        )

        # 2. Crear ForecastConfig con los NOMBRES CORRECTOS (según la radiografía)
        # max_horizon=128 es clave para que acepte peticiones de 1 a 128 días
        forecast_config = ForecastConfig(
            max_context=512,      # Historia máxima
            max_horizon=128,      # Futuro máximo (¡Adiós error > 0!)
            per_core_batch_size=16 # Velocidad
        )

        # 3. Compilar
        logger.info("Compilando con max_context=512, max_horizon=128...")
        model.compile(forecast_config=forecast_config)
        
        logger.info("✅ TimesFM 2.5 CARGADO Y COMPILADO CORRECTAMENTE.")
        
        _model = model
        _model_loaded = True
        _device_info = "cpu"
        
        return True

    except Exception as e:
        logger.error("❌ Error: %s", e, exc_info=True)
        raise RuntimeError(f"Fallo: {e}")

def get_model() -> Any:
    if not _model_loaded or _model is None:
        raise RuntimeError("Modelo no cargado.")
    return _model

def get_device_info() -> str:
    return _device_info

def is_loaded() -> bool:
    return _model_loaded
