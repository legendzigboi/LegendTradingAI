"""
Live feature computation for paper trader.
Pure Python — no pandas, no numpy.
"""
import math
import time
from datetime import datetime, timezone
import requests

BINANCE = "https://data-api.binance.vision"
KLINES = "/api/v3/klines"

FEATURE_NAMES = [
    "return_1", "return_5", "return_20",
    "range", "body", "upper_wick", "lower_wick",
    "sma_ratio_20", "sma_ratio_50", "sma_ratio_200",
    "ema_ratio_9_21", "ema_ratio_21_50",
    "rsi_14", "rsi_7",
    "macd_line", "macd_signal", "macd_hist",
    "roc_10",
    "atr_14", "std_20",
    "bb_position", "bb_width",
    "volume_ratio_20", "volume_ratio_50", "obv_slope",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
]

def fetch_klines(symbol, interval="1h", limit=300):
    r = requests.get(BINANCE + KLINES, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=20)
    r.raise_for_status()
    return r.json()

def _ema(values, span):
    if not values: return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out

def _sma(values, window):
    if len(values) < window: return None
    return sum(values[-window:]) / window

def _std(values, window):
    if len(values) < window: return None
    recent = values[-window:]
    mean = sum(recent) / len(recent)
    var = sum((x - mean) ** 2 for x in recent) / (len(recent) - 1)
    return math.sqrt(var)

def compute_features(candles):
    if len(candles) < 210:
        raise ValueError(f"Need at least 210 candles, got {len(candles)}")

    opens = [float(c[1]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    closes = [float(c[4]) for c in candles]
    volumes = [float(c[5]) for c in candles]
    times_ms = [int(c[0]) for c in candles]

    close = closes[-1]; open_ = opens[-1]; high = highs[-1]; low = lows[-1]; vol = volumes[-1]

    ret1 = close / closes[-2] - 1
    ret5 = close / closes[-6] - 1
    ret20 = close / closes[-21] - 1

    rng = (high - low) / close if close else 0
    body = abs(close - open_) / close if close else 0
    upper_wick = (high - max(open_, close)) / close if close else 0
    lower_wick = (min(open_, close) - low) / close if close else 0

    sma20 = _sma(closes, 20); sma50 = _sma(closes, 50); sma200 = _sma(closes, 200)
    sma_ratio_20 = close / sma20 - 1 if sma20 else 0
    sma_ratio_50 = close / sma50 - 1 if sma50 else 0
    sma_ratio_200 = close / sma200 - 1 if sma200 else 0

    ema9 = _ema(closes, 9)[-1]; ema21 = _ema(closes, 21)[-1]; ema50 = _ema(closes, 50)[-1]
    ema_ratio_9_21 = ema9 / ema21 - 1 if ema21 else 0
    ema_ratio_21_50 = ema21 / ema50 - 1 if ema50 else 0

    def _rsi(period):
        if len(closes) < period + 1: return 50.0
        gains, losses = [], []
        for i in range(-period, 0):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0)); losses.append(max(-d, 0))
        avg_gain = sum(gains) / period; avg_loss = sum(losses) / period
        if avg_loss == 0: return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    rsi_14 = _rsi(14); rsi_7 = _rsi(7)

    ema12_series = _ema(closes, 12); ema26_series = _ema(closes, 26)
    macd_series = [a - b for a, b in zip(ema12_series, ema26_series)]
    macd_signal_series = _ema(macd_series, 9)
    macd_line = macd_series[-1]; macd_signal = macd_signal_series[-1]
    macd_hist = macd_line - macd_signal
    macd_line_n = macd_line / close if close else 0
    macd_signal_n = macd_signal / close if close else 0
    macd_hist_n = macd_hist / close if close else 0

    roc_10 = close / closes[-11] - 1 if len(closes) >= 11 else 0

    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    atr_14 = (sum(trs[-14:]) / 14) / close if len(trs) >= 14 and close else 0

    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    std_20 = _std(returns, 20) or 0

    std20_price = _std(closes, 20)
    bb_position = (close - sma20) / (2 * std20_price) if (sma20 and std20_price) else 0
    bb_width = (2 * std20_price) / sma20 if (sma20 and std20_price) else 0

    vol_sma20 = _sma(volumes, 20) or 1; vol_sma50 = _sma(volumes, 50) or 1
    volume_ratio_20 = vol / vol_sma20; volume_ratio_50 = vol / vol_sma50

    obv_series = [0.0]
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0: obv_series.append(obv_series[-1] + volumes[i])
        elif d < 0: obv_series.append(obv_series[-1] - volumes[i])
        else: obv_series.append(obv_series[-1])
    obv_slope = (obv_series[-1] - obv_series[-21]) / (vol_sma20 * 20) if len(obv_series) >= 21 else 0

    ts = datetime.fromtimestamp(times_ms[-1] / 1000, tz=timezone.utc)
    hour = ts.hour; dow = ts.weekday()
    hour_sin = math.sin(2 * math.pi * hour / 24); hour_cos = math.cos(2 * math.pi * hour / 24)
    dow_sin = math.sin(2 * math.pi * dow / 7); dow_cos = math.cos(2 * math.pi * dow / 7)
    is_weekend = 1 if dow >= 5 else 0

    features = [
        ret1, ret5, ret20, rng, body, upper_wick, lower_wick,
        sma_ratio_20, sma_ratio_50, sma_ratio_200,
        ema_ratio_9_21, ema_ratio_21_50,
        rsi_14, rsi_7, macd_line_n, macd_signal_n, macd_hist_n, roc_10,
        atr_14, std_20, bb_position, bb_width,
        volume_ratio_20, volume_ratio_50, obv_slope,
        hour_sin, hour_cos, dow_sin, dow_cos, is_weekend,
    ]
    return features, times_ms[-1]

def get_latest_features(symbol, timeframe="1h"):
    candles = fetch_klines(symbol, timeframe, limit=250)
    candles = candles[:-1] # Drop incomplete candle
    return compute_features(candles)
