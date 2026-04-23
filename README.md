# 🚀 TimesFM Action Server v2

A high-performance crypto forecasting server powered by **Google's TimesFM 2.5 (200M)** foundation model. It provides real-time probabilistic forecasts (mean and 10 quantile levels) using a local PyTorch serving architecture.

This project is built with **FastAPI** for low-latency endpoints and leverages **CCXT** for robust multi-exchange data fetching. It is designed to be cleanly deployed locally or on bare-metal environments.

---

## ✨ Features

- **Google TimesFM 2.5:** State-of-the-art time series foundation model running entirely locally.
- **FastAPI Backend:** High-performance REST API designed to act as a Tool/Action Server for autonomous AI Agents.
- **Multi-Exchange CCXT Engine:** Fetch real-time OHLCV data directly from Binance, Bybit, Coinbase, and other major exchanges.
- **Telegram Watcher Bot (`watcher.py`):** An integrated background process that continuously polls the server and sends precise, hourly forecast setups directly to your Senior Desk Telegram thread.

---

## ⚙️ Installation

### 1. Requirements
- Python 3.10+
- Minimum 4GB RAM (GPU highly recommended, natively optimized for NVIDIA RTX series)

### 2. Setup Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

*(Note: TimesFM requires installing from the official Google Research repo in editable mode if not included in the standard requirements).*

---

## 🚀 Running the Services

### 1. Start the TimesFM Action Server
The server must be started first to handle incoming forecasting requests.

```bash
# Navigate to the server root directory
cd ~/Escritorio/timesfm_actionserver

# Start the uvicorn server in reload mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
On startup, the server will load the TimesFM 2.5 200M model into memory (CPU/GPU). You'll see `✅ TimesFM 2.5 CARGADO Y COMPILADO CORRECTAMENTE` once it's ready to serve traffic.

### 2. Start the Telegram Watcher (`watcher.py`)
The `watcher.py` script acts as an active forecasting daemon. It queries the local forecast server and pushes actionable market logic (BTC & ETH trends, hit/miss sequence validation) directly to Telegram using `APScheduler`.

```bash
# In a separate terminal, make sure you are in the project root and environment is active
cd ~/Escritorio/timesfm_actionserver

# Ensure you have added your Telegram variables to your .env file:
# TELEGRAM_TOKEN, CHAT_ID, TOPIC_ID

# Run the watcher daemon
python3 watcher.py
```

---

## 🔌 API Endpoints

### `POST /forecast`
Generate deep forecasts for a specific ticker.

```bash
curl -X POST "http://localhost:8000/forecast" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "BTC-USD",
    "horizon": 24,
    "exchange": "binance",
    "use_covariates": false
  }'
```

### `POST /forecast/both`
Fetches parallel, asynchronous BTC and ETH forecasts to save execution time.

### `GET /health`
Returns system health, model loading status, and the current hardware device processing the heavy lifting.

---

## 🛠️ Architecture

- `/app/main.py`: FastAPI endpoints and lifespan management.
- `/app/model.py`: Singleton PyTorch loader and configuration for Google's TimesFM weights.
- `/app/skills/ccxt_skill.py`: Data-fetching engine designed to construct pristine OHLCV DataFrames.
- `/watcher.py`: Institutional-grade Telegram notification and validation daemon.

> **Note on Docker:** This repository has been streamlined for local bare-metal deployments (Native Python envs). Previous Docker configurations (`docker-compose.yml`, `Dockerfile`) have been intentionally deprecated to maintain an agile and clean local development and deployment cycle.
