from src.engines.base_engine import TrendEngine, ScalperEngine
from src.model_registry import get_model
from src.live_features import get_latest_features
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
MODEL_DIR = Path("models/v0.2")

class FusionEngine:
    def __init__(self):
        self.trend = TrendEngine()
        self.scalper = ScalperEngine()

    def analyze(self, symbol, timeframe=None):
        if timeframe is None or timeframe == 'FUSION':
            trend_res = self.trend.analyze(symbol)
            scalper_res = self.scalper.analyze(symbol)

            if "error" in trend_res: return {"error": f"Trend Engine failed: {trend_res['error']}"}
            if "error" in scalper_res: return {"error": f"Scalper Engine failed: {scalper_res['error']}"}

            # Smart Conflict Resolution (No MTF block)
            if trend_res["direction"] != scalper_res["direction"]:
                t_conf = trend_res["confidence"]
                s_conf = scalper_res["confidence"]
                
                # Just pick the one with the higher confidence, no matter what
                if t_conf > s_conf:
                    final_dir, final_conf, engine_name = trend_res["direction"], t_conf, "Legend Fusion (Trend Priority)"
                    plan, feats, display_tf = trend_res["plan"], trend_res["features"], trend_res["timeframe"]
                else:
                    final_dir, final_conf, engine_name = scalper_res["direction"], s_conf, "Legend Fusion (Scalper Priority)"
                    plan, feats, display_tf = scalper_res["plan"], scalper_res["features"], scalper_res["timeframe"]
            else:
                final_dir = trend_res["direction"]
                final_conf = (trend_res["confidence"] + scalper_res["confidence"]) / 2
                engine_name = "Legend Fusion"
                plan, feats, display_tf = trend_res["plan"], trend_res["features"], trend_res["timeframe"]

        else:
            base_engine = TrendEngine()
            res = base_engine.analyze(symbol, timeframe)
            
            if "error" in res: return res
            if res.get("status") == "NO_TRADE": return res
            
            final_dir = res["direction"]
            final_conf = res["confidence"]
            engine_name = f"Legend Trend ({timeframe})"
            plan, feats, display_tf = res["plan"], res["features"], res["timeframe"]

        return {
            "status": "SUCCESS",
            "engine": engine_name,
            "symbol": symbol,
            "direction": final_dir,
            "confidence": final_conf,
            "timeframe": display_tf,
            "plan": plan,
            "features": feats
        }
