import requests
from datetime import datetime

def fetch_forex_klines(symbol, interval="15m", limit=250):
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h", "1d": "1d"}
    yf_interval = interval_map.get(interval, "15m")
    
    # FIXED YAHOO LIMITS: 1m=5d, 5m=1mo, 15m=1mo (60d max), 1h=1mo
    range_map = {"1m": "5d", "5m": "1mo", "15m": "1mo", "1h": "1mo", "1d": "5y"}
    range_str = range_map.get(interval, "1mo")
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={yf_interval}&range={range_str}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlc = result["indicators"]["quote"][0]
        
        rows = []
        for i in range(len(timestamps)):
            if ohlc["open"][i] is None: continue
            rows.append([
                timestamps[i] * 1000,
                str(ohlc["open"][i]), str(ohlc["high"][i]), str(ohlc["low"][i]), str(ohlc["close"][i]),
                str(ohlc["volume"][i]) if ohlc["volume"][i] else "0"
            ])
        return rows[-limit:]
    except Exception as e:
        print(f"Yahoo Finance Error for {symbol}: {e}")
        return []
