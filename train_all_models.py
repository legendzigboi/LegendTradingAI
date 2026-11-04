import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
import requests
import yfinance as yf
import os
import time
import joblib
from datetime import datetime, timezone

os.makedirs("models/v0.2", exist_ok=True)

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
FOREX_STOCKS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "GC=F", "AAPL", "TSLA", "NVDA", "AMZN", "NDX"]
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
TF_MS = {"1m": 60000, "5m": 300000, "15m": 900000, "30m": 1800000, "1h": 3600000, "4h": 14400000, "1d": 86400000}

def fetch_crypto(symbol, interval):
    days = 25 if interval == "1m" else (50 if interval == "5m" else (80 if interval in ["15m", "30m"] else 365 * 3))
    end_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(tz=timezone.utc).timestamp() - days*86400) * 1000)
    rows, cursor = [], start_ms
    while cursor < end_ms:
        try:
            r = requests.get("https://data-api.binance.vision/api/v3/klines", params={"symbol": symbol, "interval": interval, "startTime": cursor, "endTime": end_ms, "limit": 1000}, timeout=15)
            batch = r.json()
            if not batch or not isinstance(batch, list): break
            rows.extend(batch)
            if len(batch) < 1000: break
            cursor = batch[-1][0] + TF_MS[interval]
        except: break
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume","close_time","qvol","trades","tb","tq","ignore"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
    return df[["open_time","open","high","low","close","volume"]].set_index("open_time").sort_index()

def fetch_yahoo(symbol, interval):
    period_map = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "4h": "730d", "1d": "5y"}
    try:
        df = yf.download(symbol, interval=interval, period=period_map.get(interval, "60d"), progress=False, auto_adjust=False)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        if 'date' in df.columns: df = df.rename(columns={'date': 'open_time'})
        elif 'datetime' in df.columns: df = df.rename(columns={'datetime': 'open_time'})
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        if 'volume' not in df.columns: df['volume'] = 0
        return df[["open_time","open","high","low","close","volume"]].set_index("open_time").sort_index()
    except Exception:
        return pd.DataFrame()

def compute_features(df):
    d = df.copy(); close = d["close"]; high = d["high"]; low = d["low"]; open_ = d["open"]; vol = d["volume"]
    out = pd.DataFrame(index=d.index)
    out["return_1"] = close.pct_change(1); out["return_5"] = close.pct_change(5); out["return_20"] = close.pct_change(20)
    out["range"] = (high - low) / close; out["body"] = (close - open_).abs() / close
    out["upper_wick"] = (high - np.maximum(open_, close)) / close; out["lower_wick"] = (np.minimum(open_, close) - low) / close
    sma20 = close.rolling(20).mean(); sma50 = close.rolling(50).mean(); sma200 = close.rolling(200).mean()
    out["sma_ratio_20"] = close / sma20 - 1; out["sma_ratio_50"] = close / sma50 - 1; out["sma_ratio_200"] = close / sma200 - 1
    ema9 = close.ewm(span=9, adjust=False).mean(); ema21 = close.ewm(span=21, adjust=False).mean(); ema50 = close.ewm(span=50, adjust=False).mean()
    out["ema_ratio_9_21"] = ema9 / ema21 - 1; out["ema_ratio_21_50"] = ema21 / ema50 - 1
    delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    out["rsi_14"] = 100 - (100 / (1 + (gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan))))
    out["rsi_7"] = 100 - (100 / (1 + (gain.rolling(7).mean() / loss.rolling(7).mean().replace(0, np.nan))))
    macd_line = ema9 - close.ewm(span=26, adjust=False).mean(); macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    out["macd_line"] = macd_line / close; out["macd_signal"] = macd_signal / close; out["macd_hist"] = (macd_line - macd_signal) / close
    out["roc_10"] = close.pct_change(10)
    prev_close = close.shift(1); tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    out["atr_14"] = tr.rolling(14).mean() / close; out["std_20"] = close.pct_change().rolling(20).std()
    std20 = close.rolling(20).std(); out["bb_position"] = (close - sma20) / (2 * std20 + 1e-9); out["bb_width"] = (2 * std20) / (sma20 + 1e-9)
    vol_sma20 = vol.rolling(20).mean(); vol_sma50 = vol.rolling(50).mean()
    out["volume_ratio_20"] = vol / (vol_sma20 + 1e-9); out["volume_ratio_50"] = vol / (vol_sma50 + 1e-9)
    direction = np.sign(close.diff()).fillna(0); obv = (direction * vol).cumsum()
    out["obv_slope"] = obv.diff(20) / (vol_sma20 * 20 + 1e-9)
    hour = d.index.hour; dow = d.index.dayofweek
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24); out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["dow_sin"] = np.sin(2 * np.pi * dow / 7); out["dow_cos"] = np.cos(2 * np.pi * dow / 7); out["is_weekend"] = (dow >= 5).astype(int)
    return out

def train_model_ensemble(symbol, tf, is_crypto):
    print(f"Downloading {symbol} on {tf}...", end=" ")
    df = fetch_crypto(symbol, tf) if is_crypto else fetch_yahoo(symbol, tf)
    
    if len(df) < 250: 
        print("⚠ Not enough data")
        return
    
    print(f"Got {len(df)} rows. Training Ensemble...", end=" ")
    feats = compute_features(df)
    H = 1 
    future_return = df["close"].shift(-H) / df["close"] - 1
    labels = pd.Series(np.nan, index=df.index)
    min_move = 0.0005 if tf in ["1m", "5m"] else 0.001
    labels[future_return > min_move] = 1; labels[future_return < -min_move] = 0
    
    combined = feats.copy(); combined["label"] = labels; combined = combined.dropna()
    X = combined.drop(columns=["label"]); y = combined["label"].astype(int)
    X = X.iloc[:-H]; y = y.iloc[:-H]
    
    if len(X) < 100: 
        print("⚠ Not enough clean rows")
        return

    # 🚨 THE ENSEMBLE VOTING CLASSIFIER (2 out of 3 must agree) 🚨
    clf1 = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    clf2 = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    clf3 = lgb.LGBMClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, verbosity=-1)
    
    eclf = VotingClassifier(estimators=[('xgb', clf1), ('rf', clf2), ('lgbm', clf3)], voting='hard')
    
    eclf.fit(X, y)
    
    safe_sym = symbol.replace("=", "_")
    suffix = "h1" if is_crypto else "h10"
    joblib.dump(eclf, f"models/v0.2/v0.2_{safe_sym}_{tf}_{suffix}_ensemble.pkl")
    print(f"✅ Saved!")

if __name__ == "__main__":
    print("🚀 STARTING FULL ENSEMBLE RETRAIN...")
    for sym in CRYPTO:
        for tf in TIMEFRAMES:
            train_model_ensemble(sym, tf, True)
            time.sleep(1)
            
    for sym in FOREX_STOCKS:
        for tf in TIMEFRAMES:
            train_model_ensemble(sym, tf, False)
            time.sleep(1)
    print("✅ ALL ENSEMBLE MODELS RETRAINED!")
