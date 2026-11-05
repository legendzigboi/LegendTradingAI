import logging
from pathlib import Path
from src.live_features import get_latest_features, fetch_klines
from src.model_registry import get_model, get_model_error
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
        
        # Try Ensemble (.pkl) first
        model_name = f"v0.2_{safe_symbol}_{tf}_ensemble.pkl"
        model_path = MODEL_DIR / model_name
        
        # Fallback to XGBoost (.json)
        if not model_path.exists():
            model_name = f"v0.2_{safe_symbol}_{tf}_h1_long.json"
            model_path = MODEL_DIR / model_name
            if not model_path.exists():
                model_name = f"v0.2_{safe_symbol}_{tf}_h10_long.json"
                model_path = MODEL_DIR / model_name
                
        # Final fallback to different timeframe
        if not model_path.exists():
            fallback_tf = "1h" if tf != "1h" else "5m"
            model_name = f"v0.2_{safe_symbol}_{fallback_tf}_ensemble.pkl"
            model_path = MODEL_DIR / model_name
            if model_path.exists():
                tf = fallback_tf
            else:
                return {"error": f"Missing: {model_name}"}

        model = get_model(model_path)
        if not model:
            real_err = get_model_error(model_path)
            return {"error": f"Failed to load {model_name} -> {real_err}"}

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
                "engine": f"{self.name} ({tf})",
                "symbol": symbol,
                "timeframe": tf,
                "direction": direction,
                "confidence": confidence,
                "plan": plan,
                "features": feats
            }
        except Exception as e:
            return {"error": f"Math Error: {str(e)[:30]}"}

# 🚨 THE MISSING CLASSES ARE BACK 🚨
class TrendEngine(BaseEngine):
    def __init__(self):
        super().__init__("Legend Trend", "15m")

class ScalperEngine(BaseEngine):
    def __init__(self):
        super().__init__("Legend Scalper", "5m")
