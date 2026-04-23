**¡Perfecto!** Aquí tienes un **README.md** completo, claro, profesional y actualizado para tu proyecto.

Copia y pega esto directamente en un archivo llamado `README.md` dentro de la carpeta `~/Escritorio/timesfm_actionserver`:

```markdown
# TimesFM Action Server + Telegram Forecast Bot

**Proyecto**: Servidor de predicciones con TimesFM 2.5-200M + Bot de Telegram para BTC y ETH.

**Estado actual**: Funcionando correctamente (CPU mode).

---

## 📋 Cómo Iniciar el Proyecto (Paso a Paso)

### 1. Iniciar el Servidor TimesFM (Puerto 8000)

```bash
cd ~/Escritorio/timesfm_actionserver
source venv/bin/activate

# Recomendado: usar el script
./run.sh
```

O manualmente:

```bash
export HF_TOKEN="hf_tu_token_aqui"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Iniciar el Bot de Telegram (watcher.py)

```bash
cd ~/Escritorio/discretionalcalls
source venv/bin/activate   # si tienes otro venv, ajústalo

python3 watcher.py
```

El bot enviará automáticamente cada **60 minutos** un mensaje a tu chat/thread de Telegram con el forecast de BTC y ETH.

---

## 📡 Mejores Comandos CURL (Endpoints)

### Forecast individual

```bash
# BTC a 24 horas (recomendado)
curl -X POST http://127.0.0.1:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"ticker": "BTC-USD", "horizon": 24, "exchange": "binance"}'

# ETH a 24 horas
curl -X POST http://127.0.0.1:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"ticker": "ETH-USD", "horizon": 24, "exchange": "binance"}'

# BTC a 12 horas (más reactivo)
curl -X POST http://127.0.0.1:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"ticker": "BTC-USD", "horizon": 12, "exchange": "binance"}'

# BTC a 6 horas (muy corto plazo)
curl -X POST http://127.0.0.1:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"ticker": "BTC-USD", "horizon": 6, "exchange": "binance"}'
```

**Horizontes recomendados:**
- **24 horas** → Mejor para visión de tendencia (recomendado principal)
- **12 horas** → Buen equilibrio reactividad / fiabilidad
- **6 horas** → Trading intradía más agresivo

---

## 📁 Estructura del Proyecto

```
timesfm_actionserver/
├── app/
│   ├── main.py                 # FastAPI + endpoints
│   ├── model.py                # Carga y gestión de TimesFM
│   ├── forecaster.py           # Lógica de predicción
│   ├── schemas.py
│   └── data.py
├── run.sh                      # Script recomendado para iniciar
├── venv/
└── README.md

discretionalcalls/
├── watcher.py                  # Bot de Telegram (envía cada hora)
└── .env                        # TELEGRAM_TOKEN, CHAT_ID, TOPIC_ID
```

---

## 🚀 Scripts Recomendados

### `run.sh` (en timesfm_actionserver/)

```bash
#!/bin/bash
cd ~/Escritorio/timesfm_actionserver
source venv/bin/activate
export HF_TOKEN="tu_token_aqui"

echo "🚀 Iniciando TimesFM Action Server 2.5-200M..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Hazlo ejecutable:
```bash
chmod +x run.sh
```

### watcher.py (ya lo tienes)

Envía automáticamente cada 60 minutos forecast de BTC y ETH a Telegram.

---

## 🔄 Automejora Continua (Roadmap Personal)

### Fase 1 - Actual (Hecho)
- Servidor TimesFM 2.5-200M funcionando en CPU
- Bot de Telegram enviando forecasts cada hora
- Soporte para BTC y ETH

### Fase 2 - Próximas mejoras (Prioridad alta)
- [ ] Añadir soporte para SOL, BNB y otros activos
- [ ] Integración con CCXTV2 (Order Flow + Microestructura)
- [ ] Crear endpoint `/forecast/mix` que combine TimesFM + CCXTV2
- [ ] Añadir métricas de precisión histórica (backtesting)
- [ ] Mejorar formato de mensajes en Telegram (con emojis y alertas)

### Fase 3 - Avanzado
- Migrar a GPU (CUDA) para mayor velocidad
- Añadir covariates (funding rate, OI, volumen)
- Dashboard web simple
- Sistema de alertas inteligente (cuando TimesFM + CCXTV2 coinciden)

---

## Notas Importantes

- El modelo **2.5-200M** es más ligero y estable que el 2.0-500M.
- Actualmente **no usa covariates** (solo precio histórico).
- El horizonte más fiable parece ser **12-24 horas**.
- Siempre combina la predicción de TimesFM con tu análisis de Order Flow (CCXTV2) antes de tomar decisiones.

---

**¿Quieres que te prepare ahora?**

1. El archivo `run.sh` completo y bonito
2. Una versión mejorada de `watcher.py` con mejor formato
3. El script `mix_analyzer.py` que combine TimesFM + CCXTV2

Dime qué quieres primero y te lo entrego listo para usar.

¡Ya tienes un sistema funcionando! Ahora solo hay que pulirlo y mejorarlo paso a paso. 

¿Qué quieres hacer ahora?
