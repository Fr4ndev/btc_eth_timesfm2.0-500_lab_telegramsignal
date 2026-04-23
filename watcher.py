#!/usr/bin/env python3
"""
TimesFM Forecast Bot for Telegram
Sends hourly forecasts for BTC and ETH to a Telegram thread.
Based on the same structure as heatmap_bot.py
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== CONFIGURATION ==================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TOPIC_ID = os.getenv("TOPIC_ID")  # Opcional, para threads

TIMESFM_URL = "http://127.0.0.1:8000/forecast"
SYMBOLS = ["BTC-USD", "ETH-USD"]
HORIZON = 24   # Predicción a 24 horas (puedes cambiarlo)
HISTORY_FILE = "timesfm_history.json"  # Para guardar predicciones previas y evaluar aciertos

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("TimesFM_Bot")

# ================== FUNCIONES ==================

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

async def get_forecast(session, symbol, horizon=HORIZON):
    """Obtiene forecast de TimesFM"""
    payload = {"ticker": symbol, "horizon": horizon, "exchange": "binance"}
    try:
        async with session.post(TIMESFM_URL, json=payload, timeout=15) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"Error {resp.status} para {symbol}")
                return None
    except Exception as e:
        logger.error(f"Excepción forecast {symbol}: {e}")
        return None

def analyze_trend(forecast_mean):
    """Determina tendencia basada en los primeros 3 valores"""
    if len(forecast_mean) < 3:
        return "neutral"
    slope = forecast_mean[2] - forecast_mean[0]
    if slope > forecast_mean[0] * 0.001:   # +0.1%
        return "alcista 🟢"
    elif slope < -forecast_mean[0] * 0.001:
        return "bajista 🔴"
    else:
        return "neutral ⚪"

def check_previous_accuracy(symbol, current_price, history):
    """Compara forecast de la hora anterior con el precio actual"""
    if symbol not in history:
        return None
    prev = history[symbol]
    prev_time = datetime.fromisoformat(prev['timestamp'])
    now = datetime.now()
    # Solo si la predicción es de hace menos de 2 horas
    if (now - prev_time).total_seconds() > 7200:
        return None
    
    prev_forecast_h1 = prev['forecast_mean'][0]
    error_pct = abs((current_price - prev_forecast_h1) / prev_forecast_h1) * 100
    hit = error_pct < 0.5
    return {
        'forecast': prev_forecast_h1,
        'actual': current_price,
        'error_pct': round(error_pct, 2),
        'hit': hit
    }

def format_message(symbol, data, history):
    """Formatea el mensaje para Telegram"""
    last_price = data['last_price']
    forecast_mean = data['forecast_mean']
    horizon = data['horizon']
    
    # Valores clave
    h1 = forecast_mean[0] if horizon >= 1 else None
    h6 = forecast_mean[5] if horizon >= 6 else None
    h12 = forecast_mean[11] if horizon >= 12 else None
    h24 = forecast_mean[23] if horizon >= 24 else None
    
    trend = analyze_trend(forecast_mean)
    prev_check = check_previous_accuracy(symbol, last_price, history)
    
    # Emoji por tendencia
    trend_emoji = "📈" if "alcista" in trend else "📉" if "bajista" in trend else "➖"
    
    msg = f"{trend_emoji} *{symbol}* - {datetime.now().strftime('%H:%M')}\n"
    msg += f"💰 Precio actual: `${last_price:,.2f}`\n"
    msg += "🔮 *Forecast TimesFM:*\n"
    if h1: msg += f"  • 1h: `${h1:,.2f}`\n"
    if h6: msg += f"  • 6h: `${h6:,.2f}`\n"
    if h12: msg += f"  • 12h: `${h12:,.2f}`\n"
    if h24: msg += f"  • 24h: `${h24:,.2f}`\n"
    msg += f"📊 Tendencia: {trend}\n"
    
    if prev_check:
        if prev_check['hit']:
            msg += f"✅ *Acierto previo*: predicho `${prev_check['forecast']:,.2f}` vs real `${prev_check['actual']:,.2f}` (error {prev_check['error_pct']}%)\n"
        else:
            msg += f"❌ *Fallo previo*: predicho `${prev_check['forecast']:,.2f}` vs real `${prev_check['actual']:,.2f}` (error {prev_check['error_pct']}%)\n"
    
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "_Modelo: timesfm-2.0-500m-pytorch_"
    return msg

async def process_symbol(session, symbol, bot, thread_id, history):
    """Obtiene forecast, actualiza historial y envía mensaje"""
    data = await get_forecast(session, symbol)
    if not data:
        logger.error(f"No se pudo obtener forecast para {symbol}")
        return
    
    msg = format_message(symbol, data, history)
    
    # Actualizar historial
    history[symbol] = {
        'timestamp': datetime.now().isoformat(),
        'last_price': data['last_price'],
        'forecast_mean': data['forecast_mean'],
        'trend': analyze_trend(data['forecast_mean'])
    }
    save_history(history)
    
    # Enviar a Telegram
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode='Markdown',
            message_thread_id=thread_id
        )
        logger.info(f"Mensaje enviado para {symbol}")
    except TelegramError as e:
        logger.error(f"Error Telegram: {e}")

async def run_analysis():
    """Ejecuta una ronda de análisis para todos los símbolos"""
    logger.info("Iniciando ronda de forecast...")
    bot = Bot(token=TOKEN) if TOKEN else None
    if not bot:
        logger.error("No se encontró TELEGRAM_TOKEN")
        return
    
    thread_id = int(TOPIC_ID) if TOPIC_ID else None
    history = load_history()
    
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            await process_symbol(session, symbol, bot, thread_id, history)
            await asyncio.sleep(2)  # Pequeña pausa entre mensajes
    
    logger.info("Ronda completada")

async def main():
    scheduler = AsyncIOScheduler()
    # Ejecutar cada 60 minutos
    scheduler.add_job(run_analysis, 'interval', minutes=60)
    # Ejecutar inmediatamente al inicio
    await run_analysis()
    scheduler.start()
    
    logger.info("🔥 TimesFM Forecast Bot iniciado. Enviando cada 60 minutos.")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot detenido.")
