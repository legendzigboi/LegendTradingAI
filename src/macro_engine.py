import requests
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

def get_crypto_crowd_sentiment(symbol):
    """
    Fetches the Long/Short ratio from Binance Futures.
    If ratio > 3.0 (75% long), the crowd is too greedy. We should VETO LONGS.
    """
    if "USDT" not in symbol: return None
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                long_ratio = float(data[0]['longAccount'])
                short_ratio = float(data[0]['shortAccount'])
                return long_ratio, short_ratio
    except Exception as e:
        logger.error(f"Crowd sentiment error: {e}")
    return None

def get_dxy_trend():
    """
    Fetches the US Dollar Index (DXY) 1-hour trend.
    Returns "UPTREND", "DOWNTREND", or "NEUTRAL"
    """
    try:
        df = yf.download("DX-Y.NYB", interval="1h", period="5d", progress=False)
        if df.empty: return "NEUTRAL"
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        closes = df['Close'].tolist()
        if len(closes) < 50: return "NEUTRAL"
        
        # Simple EMA calculation
        def ema(data, span):
            alpha = 2.0 / (span + 1)
            ema_val = data[0]
            for val in data[1:]: ema_val = alpha * val + (1 - alpha) * ema_val
            return ema_val

        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        
        if ema20 > ema50 * 1.0005: return "UPTREND"
        elif ema20 < ema50 * 0.9995: return "DOWNTREND"
        return "NEUTRAL"
    except Exception as e:
        logger.error(f"DXY fetch error: {e}")
        return "NEUTRAL"
