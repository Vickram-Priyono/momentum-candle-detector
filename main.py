import pandas as pd
import time
import requests
import logging
import mplfinance as mpf
from datetime import datetime, timezone


# === KONFIGURASI ===
GOLD_API_KEY = 'goldapi-1qe0smci31xqy-io'
symbol = 'XAU/USD'  # sesuai format GoldAPI
interval_minutes = 15
pip_factor = 0.1  # 1 pip = 0.01 untuk XAUUSD
min_body_pips = 60
max_wick_pct = 0.2
token = '7615128019:AAEkB1qBE1Yjr-c7JqaN9xwAchzm-siNcpU'
chat_id = '6842727078'

# === SETUP LOGGING ===
log_file = "momentum_log.txt"
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s | %(message)s')

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

# === AMBIL DATA CANDLE MANUAL DARI GOLDAPI.IO ===
def fetch_candles():
    url = f"https://www.goldapi.io/api/XAU/USD"
    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json"
    }

    records = []
    for i in range(10, 0, -1):
        ts = datetime.now(timezone.utc) - pd.Timedelta(minutes=i * interval_minutes)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("❌ Gagal ambil data:", response.text)
            continue
        data = response.json()
        try:
            records.append({
                'timestamp': ts,
                'open': float(data['open_price']),
                'high': float(data['high_price']),
                'low': float(data['low_price']),
                'close': float(data['price'])
            })
        except:
            continue
        time.sleep(1.2)  # delay agar tidak kena rate limit

    df = pd.DataFrame(records)
    return df

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

# === MAIN LOOP ===
print("🚀 Monitoring momentum candle dari GoldAPI.io...\n")

try:
    while True:
        now = pd.Timestamp.now()
        second = now.second
        minute = now.minute
        minute_in_candle = minute % interval_minutes

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

except KeyboardInterrupt:
    print("\n⛔ Dihentikan oleh pengguna.")
