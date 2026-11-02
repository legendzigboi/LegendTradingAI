import logging
from pathlib import Path
from src.live_features import get_latest_features, fetch_klines
from src.xgb_pure import XGBPure
from src.trade_planner import build_trade_plan

logger = logging.getLogger(__name__)
MODEL_DIR = Path("models/v0.2")

SCAN_LIST = [
    ("BTCUSDT", "15m"), ("ETHUSDT", "15m"), ("XRPUSDT", "15m"),
    ("BTCUSDT", "1h"), ("ETHUSDT", "1h"), ("XRPUSDT", "1h")
]

def scan_markets(min_confidence=0.68):
    results = []
    for symbol, timeframe in SCAN_LIST:
        try:
            model_name = f"v0.2_{symbol}_{timeframe}_h10_long.json"
            model_path = MODEL_DIR / model_name
            if not model_path.exists(): continue
                
            feats, _ = get_latest_features(symbol, timeframe)
            candles = fetch_klines(symbol, timeframe, limit=2)
            entry_price = float(candles[-2][4])
            atr_14 = feats[18]
            
            model = XGBPure(model_path)
            proba = model.predict_proba([feats])[0]
            
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            # Multi-Timeframe Check
            if timeframe == "15m":
                htf_model_path = MODEL_DIR / f"v0.2_{symbol}_1h_h10_long.json"
                if htf_model_path.exists():
                    htf_feats, _ = get_latest_features(symbol, "1h")
                    htf_model = XGBPure(htf_model_path)
                    htf_proba = htf_model.predict_proba([htf_feats])[0]
                    htf_direction = "LONG" if htf_proba > 0.5 else "SHORT"
                    
                    if direction != htf_direction:
                        logger.info(f"Rejected {symbol} {timeframe} due to HTF conflict.")
                        continue # Skip this signal
            
            if confidence >= min_confidence:
                plan = build_trade_plan(entry_price, direction, atr_14, timeframe)
                results.append({
                    "symbol": symbol, "timeframe": timeframe, "direction": direction,
                    "confidence": confidence, "plan": plan
                })
        except Exception as e:
            logger.error(f"Scan error: {e}")
            
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results
