from src.engines.base_engine import TrendEngine, ScalperEngine
import logging

logger = logging.getLogger(__name__)

class FusionEngine:
    def __init__(self):
        self.trend = TrendEngine()
        self.scalper = ScalperEngine()

    def analyze(self, symbol):
        trend_res = self.trend.analyze(symbol)
        scalper_res = self.scalper.analyze(symbol)

        # Show the REAL error instead of hiding it
        if "error" in trend_res:
            return {"error": f"Trend Engine failed: {trend_res['error']}"}
        if "error" in scalper_res:
            return {"error": f"Scalper Engine failed: {scalper_res['error']}"}

        if trend_res["direction"] != scalper_res["direction"]:
            return {
                "status": "NO_TRADE",
                "reason": f"Conflict: Trend says {trend_res['direction']}, Scalper says {scalper_res['direction']}",
                "symbol": symbol
            }

        fused_confidence = (trend_res["confidence"] + scalper_res["confidence"]) / 2
        
        return {
            "status": "SUCCESS",
            "engine": "Legend Fusion",
            "symbol": symbol,
            "direction": trend_res["direction"],
            "confidence": fused_confidence,
            "timeframe": trend_res["timeframe"],
            "plan": trend_res["plan"],
            "features": trend_res["features"]
        }
