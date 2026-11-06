import requests
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

def get_crypto_crowd_sentiment(symbol):
    if "USDT" not in symbol: return None
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return float(data[0]['longAccount']), float(data[0]['shortAccount'])
    except: pass
    return None

def get_dxy_trend():
    try:
        df = yf.download("DX-Y.NYB", interval="1h", period="5d", progress=False)
        if df.empty: return "NEUTRAL"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        closes = df['Close'].tolist()
        if len(closes) < 50: return "NEUTRAL"
        
        def ema(data, span):
            alpha = 2.0 / (span + 1)
            ema_val = data[0]
            for val in data[1:]: ema_val = alpha * val + (1 - alpha) * ema_val
            return ema_val

        if ema(closes, 20) > ema(closes, 50) * 1.0005: return "UPTREND"
        elif ema(closes, 20) < ema(closes, 50) * 0.9995: return "DOWNTREND"
        return "NEUTRAL"
    except: return "NEUTRAL"

# 🚨 NEW: US 10-YEAR TREASURY YIELD 🚨
def get_us10y_trend():
    try:
        # ^TNX is the ticker for US10Y on Yahoo Finance
        df = yf.download("^TNX", interval="1h", period="5d", progress=False)
        if df.empty: return "NEUTRAL"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        closes = df['Close'].tolist()
        if len(closes) < 50: return "NEUTRAL"
        
        def ema(data, span):
            alpha = 2.0 / (span + 1)
            ema_val = data[0]
            for val in data[1:]: ema_val = alpha * val + (1 - alpha) * ema_val
            return ema_val

        if ema(closes, 20) > ema(closes, 50) * 1.0005: return "UPTREND"
        elif ema(closes, 20) < ema(closes, 50) * 0.9995: return "DOWNTREND"
        return "NEUTRAL"
    except: return "NEUTRAL"

# 🚨 NEW: S&P 500 INDEX 🚨
def get_spx_trend():
    try:
        # ^GSPC is the ticker for SPX on Yahoo Finance
        df = yf.download("^GSPC", interval="1h", period="5d", progress=False)
        if df.empty: return "NEUTRAL"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        closes = df['Close'].tolist()
        if len(closes) < 50: return "NEUTRAL"
        
        def ema(data, span):
            alpha = 2.0 / (span + 1)
            ema_val = data[0]
            for val in data[1:]: ema_val = alpha * val + (1 - alpha) * ema_val
            return ema_val

        if ema(closes, 20) > ema(closes, 50) * 1.0005: return "UPTREND"
        elif ema(closes, 20) < ema(closes, 50) * 0.9995: return "DOWNTREND"
        return "NEUTRAL"
    except: return "NEUTRAL"
