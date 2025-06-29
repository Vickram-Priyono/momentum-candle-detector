import pandas as pd
import time
import requests
import logging
import mplfinance as mpf
from datetime import datetime

# === KONFIGURASI ===
API_KEY = 'MASUKKAN_API_KEY_ALPHA_VANTAGE'
symbol_from = 'XAU'
symbol_to = 'USD'
interval = '15min'
pip_factor = 0.1  # 1 pip = 0.01 untuk XAUUSD
min_body_pips = 60
max_wick_pct = 0.2
token = 'TOKEN_BOT_TELEGRAM'
chat_id = 'CHAT_ID_TELEGRAM'

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
        df['timestamp'] = pd.to_datetime(df['timestamp'])
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
    open_, high, low, close = candle['open'], candle['high'], candle['low'], candle['close']
    time_str = candle['timestamp'] + pd.Timedelta(hours=7)
    body = abs(close - open_)
    candle_range = high - low
    wicks = candle_range - body
    wick_pct = wicks / candle_range if candle_range > 0 else 1
    is_momentum = (body >= min_body_pips * pip_factor) and (wick_pct <= max_wick_pct)
    direction = "BUY" if close > open_ else "SELL"
    jenis = "PREVIEW" if preview else "FINAL"

    if is_momentum:
        msg = f"[{jenis} 🚀 MOMENTUM {direction}] {time_str.strftime('%Y-%m-%d %H:%M')}\nHarga: {close:.2f}"
        send_alert(msg)
        send_chart(df_chart, f"{jenis} MOMENTUM {direction}")
        logging.info(msg)
        print(msg)
    else:
        print(f"Tidak ada momentum ({jenis}) di candle {time_str.strftime('%Y-%m-%d %H:%M')}")

# === AMBIL DATA dari ALPHA VANTAGE ===
def fetch_candles():
    url = f'https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol={symbol_from}&to_symbol={symbol_to}&interval={interval}&outputsize=compact&apikey={API_KEY}'
    response = requests.get(url)
    data = response.json()

    candles = data.get(f'Time Series FX ({interval})')
    if not candles:
        print("❌ Gagal ambil data dari Alpha Vantage:", data)
        return pd.DataFrame()

    records = []
    for ts, val in candles.items():
        try:
            records.append({
                'timestamp': pd.to_datetime(ts),
                'open': float(val['1. open']),
                'high': float(val['2. high']),
                'low': float(val['3. low']),
                'close': float(val['4. close'])
            })
        except:
            continue

    df = pd.DataFrame(records)

    if 'timestamp' not in df.columns:
        print("❌ Kolom 'timestamp' tidak ditemukan.")
        return pd.DataFrame()

    return df.sort_values('timestamp').reset_index(drop=True)

# === MAIN LOOP ===
print("🚀 Monitoring momentum candle dari Alpha Vantage...\n")

try:
    while True:
        now = pd.Timestamp.now()
        second = now.second
        minute = now.minute
        minute_in_candle = minute % 15

        df_all = fetch_candles()
        if df_all.empty or len(df_all) < 2:
            print("❌ Data tidak cukup. Coba lagi nanti.")
            time.sleep(60)
            continue

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

        # Hindari rate limit dari Alpha Vantage
        time.sleep(12)

except KeyboardInterrupt:
    print("\n⛔ Dihentikan oleh pengguna.")
