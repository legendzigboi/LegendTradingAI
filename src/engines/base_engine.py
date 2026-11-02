import logging
from pathlib import Path
from src.live_features import get_latest_features, fetch_klines
from src.xgb_pure import XGBPure
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
        model_name = f"v0.2_{safe_symbol}_{tf}_h10_long.json"
        model_path = MODEL_DIR / model_name
        
        if not model_path.exists():
            return {"error": f"Model {model_name} missing"}

        try:
            feats, _ = get_latest_features(symbol, tf)
            candles = fetch_klines(symbol, tf, limit=2)
            entry_price = float(candles[-2][4])
            atr_14 = feats[18] 

            model = XGBPure(model_path)
            proba = model.predict_proba([feats])[0]
            
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            plan = build_trade_plan(entry_price, direction, atr_14, tf)

            return {
                "engine": self.name,
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
