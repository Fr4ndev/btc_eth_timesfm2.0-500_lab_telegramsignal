#!/usr/bin/env python3
"""
TimesFM Watcher 3 (Images only) - 24 Ticks Edition (Estilo watcher.py a secas)
Genera gráficos PNG extendidos a 24 pasos usando el motor v10.
"""
import os
import io
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import ccxt.async_support as ccxt
import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TOPIC_ID = os.getenv("TOPIC_ID")

TIMESFM_URL = "http://127.0.0.1:8000/forecast"
SYMBOLS = ["BTC-USD", "ETH-USD"]
HORIZON = 24       # 24 valores (que el watcher.py asume como horas)
TIMEFRAME = "1d"   # Base backend TimesFM nativa

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("TimesFM_Watcher3")

ESTILO_GRAFICO = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    rc={"figure.facecolor": "#0b0e11", "axes.facecolor": "#0b0e11", "axes.grid": False}
)

exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})

async def fetch_ohlcv_ccxt(symbol: str, limit: int = 150):
    ccxt_symbol = symbol.replace('-USD', '/USDT')
    ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df.set_index("ts", inplace=True)
    return df

async def get_forecast(session, symbol):
    payload = {"ticker": symbol, "horizon": HORIZON, "exchange": "binance"}
    try:
        async with session.post(TIMESFM_URL, json=payload, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.error(f"Error HTTP {resp.status} - {await resp.text()}")
    except Exception as e:
        logger.error(f"Error fetch forecast para {symbol}: {e}")
    return None

def plot_forecast(df, forecast_data, symbol):
    future_dates = pd.date_range(start=df.index[-1] + pd.Timedelta(days=1), periods=HORIZON, freq="D")
    fc_mean = forecast_data["forecast_mean"]
    q10 = forecast_data["quantiles"][0]["values"]
    q90 = forecast_data["quantiles"][-1]["values"]

    # Padding del dataframe para abrir espacio en el eje de mplfinance
    full_idx = df.index.union(future_dates)
    df_plot = df.reindex(full_idx)
    
    s_mean = pd.Series(index=full_idx, dtype=float)
    s_mean[df.index[-1]] = df["close"].iloc[-1]
    for idx, val in zip(future_dates, fc_mean):
        s_mean[idx] = val

    s_q10 = pd.Series(index=full_idx, dtype=float)
    s_q90 = pd.Series(index=full_idx, dtype=float)
    s_q10[df.index[-1]] = df["close"].iloc[-1]
    s_q90[df.index[-1]] = df["close"].iloc[-1]
    for idx, (v10, v90) in zip(future_dates, zip(q10, q90)):
        s_q10[idx] = v10
        s_q90[idx] = v90

    ap = [
        mpf.make_addplot(s_mean, color='#1E90FF', width=2.0),
        mpf.make_addplot(s_q90, color='#1E90FF', width=0.5, alpha=0.5),
        mpf.make_addplot(s_q10, color='#1E90FF', width=0.5, alpha=0.5)
    ]

    h_short = fc_mean[1]   # corto (index 1)
    h_mid = fc_mean[11]    # medio (index 11)
    h_long = fc_mean[-1]   # largo (index 23)
    
    hlines_vals = [h_short, h_mid, h_long]
    hlines_colors = ['#FFD700', '#00C853', '#bc13fe'] # Oro, Verde, Morado

    buf = io.BytesIO()
    fig, axes = mpf.plot(
        df_plot,
        type="candle",
        style=ESTILO_GRAFICO,
        title=f"Predicción TimesFM - {symbol} (+24 Ticks)",
        figsize=(12, 7),
        addplot=ap,
        show_nontrading=False,
        hlines=dict(hlines=hlines_vals, colors=hlines_colors, linestyle="--", linewidths=1.0),
        returnfig=True,
        tight_layout=True
    )
    
    ax = axes[0]
    x_future = list(range(len(df)-1, len(df)+HORIZON))
    v_low = [df["close"].iloc[-1]] + q10
    v_high = [df["close"].iloc[-1]] + q90
    ax.fill_between(x_future, v_low, v_high, color='#1E90FF', alpha=0.15)
    
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0b0e11")
    buf.seek(0)
    buf.name = "chart24.png"
    import matplotlib.pyplot as plt
    plt.close(fig)
    return buf

def analyze_trend(h_val, current_price):
    if h_val > current_price * 1.001:
        return "Alcista 🟢"
    elif h_val < current_price * 0.999:
        return "Bajista 🔴"
    else:
        return "Neutral ⚪"

def build_telegram_message(symbol, data):
    f_mean = data["forecast_mean"]
    q10 = data["quantiles"][0]["values"]
    q90 = data["quantiles"][-1]["values"]
    current_price = data["last_price"]
    
    h1 = f_mean[0]
    h6 = f_mean[5]
    h12 = f_mean[11]
    h24 = f_mean[23] if len(f_mean) >= 24 else f_mean[-1]

    trend = analyze_trend(f_mean[-1], current_price)

    caption = (
       f"🏛️ **{symbol} TimesFM (Horizonte 24)** - {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
       f"💰 Precio actual: `${current_price:,.2f}`\n\n"
       f"🎯 **Forecast TimesFM:**\n"
       f"   • H1: `${h1:,.2f}`\n"
       f"   • H6: `${h6:,.2f}`\n"
       f"   • H12: `${h12:,.2f}`\n"
       f"   • H24: `${h24:,.2f}`\n\n"
       f"📊 **Tendencia Macro:** {trend}\n"
       f"━━━━━━━━━━━━━━━━━━━━━\n"
       f"📌 _TimesFM Quantum Model (24 Steps)_"
    )
    return caption

async def process_symbol(session, symbol, bot, thread_id):
    logger.info(f"Analizando {symbol} (Horizon = 24)...")
    
    data = await get_forecast(session, symbol)
    if not data:
        logger.error(f"Fallo obtener proyección TimesFM para {symbol}")
        return

    df = await fetch_ohlcv_ccxt(symbol, limit=120)
    if df is None or df.empty:
        logger.error(f"Fallo al descargar OHLCV para {symbol}")
        return
        
    msg = build_telegram_message(symbol, data)
    chart_buf = plot_forecast(df, data, symbol)
    
    try:
        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=chart_buf,
            caption=msg,
            parse_mode='Markdown',
            message_thread_id=thread_id
        )
        logger.info(f"Mensaje enviado exitosamente para {symbol}")
    except TelegramError as e:
        logger.error(f"Error Telegram: {e}")

async def run_analysis():
    logger.info("Iniciando ronda forecast 24 Ticks...")
    bot = Bot(token=TOKEN) if TOKEN else None
    if not bot:
        logger.error("Sin TELEGRAM_TOKEN, abortando.")
        return
        
    thread_id = int(TOPIC_ID) if TOPIC_ID else None
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            await process_symbol(session, symbol, bot, thread_id)
            await asyncio.sleep(2)
            
    logger.info("Ronda completada")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_analysis, 'interval', minutes=60)
    
    await run_analysis()
    scheduler.start()
    
    logger.info("🔥 Watcher3_Images iniciado (24 Ticks ext.)")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await exchange.close()
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot apagado.")
