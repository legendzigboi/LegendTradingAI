import logging
from pathlib import Path
from src.live_features import get_latest_features, fetch_klines
from src.model_registry import get_model
from src.trade_planner import build_trade_plan

logger = logging.getLogger(__name__)
MODEL_DIR = Path("models/v0.2")

class BaseEngine:
    def __init__(self, name, default_timeframe):
        self.name = name
        self.default_timeframe = default_timeframe

    def analyze(self, symbol, timeframe=None):
        tf = timeframe or self.default_timeframe
        safe_symbol = symbol.replace("=", "_")
        
        # Try the new H1 models first (Crypto)
        model_name = f"v0.2_{safe_symbol}_{tf}_h1_long.json"
        model_path = MODEL_DIR / model_name
        
        # If H1 doesn't exist, fallback to H10 (Forex)
        if not model_path.exists():
            model_name = f"v0.2_{safe_symbol}_{tf}_h10_long.json"
            model_path = MODEL_DIR / model_name
            
        # 🚨 SMART TIMEFRAME FALLBACK 🚨
        if not model_path.exists():
            fallback_tf = "5m" if tf == "15m" else "1h"
            model_name = f"v0.2_{safe_symbol}_{fallback_tf}_h10_long.json"
            model_path = MODEL_DIR / model_name
            if model_path.exists():
                logger.info(f"Fallback: Using {fallback_tf} model for {symbol} instead of {tf}")
                tf = fallback_tf # Update tf so the trade plan matches

        model = get_model(model_path)
        if not model:
            return {"error": f"Model {model_name} missing or failed to load"}

        try:
            feats, _ = get_latest_features(symbol, tf)
            candles = fetch_klines(symbol, tf, limit=2)
            entry_price = float(candles[-2][4])
            atr_14 = feats[18]

            proba = model.predict_proba([feats])[0]

            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)

            plan = build_trade_plan(entry_price, direction, atr_14, tf)

            return {
                "engine": f"{self.name} ({tf})", # Show which timeframe was used
                "symbol": symbol,
                "timeframe": tf,
                "direction": direction,
                "confidence": confidence,
                "plan": plan,
                "features": feats
            }
        except Exception as e:
            return {"error": str(e)}

class TrendEngine(BaseEngine):
    def __init__(self):
        super().__init__("Legend Trend", "15m")

class ScalperEngine(BaseEngine):
    def __init__(self):
        super().__init__("Legend Scalper", "5m")
