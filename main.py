import ccxt
import pandas as pd
import time
import requests
import logging
import os
import mplfinance as mpf
from datetime import datetime
from keep_alive import keep_alive
keep_alive()


# === KONFIGURASI ===
symbol = "XAU/USDT:USDT"  # pair dari Bybit (spot/perpetual)
interval = '15m'
pip_factor = 0.1  # 1 pip = 0.01 untuk XAUUSDT
min_body_pips = 60
max_wick_pct = 0.2
token = '7615128019:AAEkB1qBE1Yjr-c7JqaN9xwAchzm-siNcpU'
chat_id = '6842727078'

# === SETUP LOGGING ===
log_file = "momentum_log.txt"
logging.basicConfig(filename=log_file,
                    level=logging.INFO,
                    format='%(asctime)s | %(message)s')


# === TELEGRAM ALERT ===
def send_alert(message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print("❌ Gagal kirim notifikasi:", response.text)
    except Exception as e:
        print("❌ Error kirim telegram:", e)


# === TELEGRAM CHART ===
def send_chart(df_chart, title):
    try:
        filename = "chart.png"
        df = df_chart.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        mpf.plot(df[['open', 'high', 'low', 'close']],
                 type='candle',
                 style='charles',
                 title=title,
                 volume=False,
                 savefig=filename)
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        with open(filename, 'rb') as photo:
            data = {"chat_id": chat_id}
            files = {"photo": photo}
            response = requests.post(url, data=data, files=files)
        if response.status_code != 200:
            print("❌ Gagal kirim chart:", response.text)
    except Exception as e:
        print("❌ Error kirim chart:", e)


# === CEK MOMENTUM ===
def process_candle(candle, df_chart, preview=False):
    open_, high, low, close = candle['open'], candle['high'], candle[
        'low'], candle['close']
    time_str = pd.to_datetime(candle['timestamp'],
                              unit='ms') + pd.Timedelta(hours=7)

    body = abs(close - open_)
    candle_range = high - low
    wicks = candle_range - body
    wick_pct = wicks / candle_range if candle_range > 0 else 1

    is_momentum = (body >= min_body_pips * pip_factor) and (wick_pct
                                                            <= max_wick_pct)
    direction = "BUY" if close > open_ else "SELL"
    jenis = "PREVIEW" if preview else "FINAL"

    if is_momentum:
        msg = f"[{jenis} 🚀 MOMENTUM {direction}] {time_str.strftime('%Y-%m-%d %H:%M')}\nHarga: {close:.2f}"
        send_alert(msg)
        send_chart(df_chart, f"{jenis} MOMENTUM {direction}")
        logging.info(msg)
        print(msg)
    else:
        print(
            f"Tidak ada momentum ({jenis}) di candle {time_str.strftime('%Y-%m-%d %H:%M')}"
        )


# === AMBIL DATA CCXT ===
def fetch_candles():
    exchange = ccxt.bybit()
    exchange.load_markets()
    candles = exchange.fetch_ohlcv(symbol, timeframe=interval, limit=10)
    df = pd.DataFrame(
        candles,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df


# === MAIN LOOP ===
print("🚀 Monitoring momentum candle dari Bybit...\n")

try:
    while True:
        now = pd.Timestamp.now()
        second = now.second
        minute = now.minute
        minute_in_candle = minute % 15

        df_all = fetch_candles()

        if minute_in_candle in [13, 14] and second < 5:
            candle = df_all.iloc[-1]
            process_candle(candle, df_all, preview=True)
            time.sleep(60)

        elif minute_in_candle == 0 and second < 5:
            candle = df_all.iloc[-2]
            process_candle(candle, df_all, preview=False)
            time.sleep(60)

        else:
            time.sleep(5)

except KeyboardInterrupt:
    print("⛔ Dihentikan oleh pengguna.")
