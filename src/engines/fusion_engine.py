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

        if "error" in trend_res:
            return {"error": f"Trend Engine failed: {trend_res['error']}"}
        if "error" in scalper_res:
            return {"error": f"Scalper Engine failed: {scalper_res['error']}"}

        if trend_res["direction"] != scalper_res["direction"]:
            t_conf = trend_res["confidence"]
            s_conf = scalper_res["confidence"]
            
            if t_conf >= 0.70 and t_conf > s_conf + 0.05:
                return {
                    "status": "SUCCESS",
                    "engine": "Legend Fusion (Trend Override)",
                    "symbol": symbol,
                    "direction": trend_res["direction"],
                    "confidence": t_conf,
                    "timeframe": trend_res["timeframe"],
                    "plan": trend_res["plan"], # 🚨 FIX: Use Trend's plan
                    "features": trend_res["features"]
                }
            elif s_conf >= 0.70 and s_conf > t_conf + 0.05:
                return {
                    "status": "SUCCESS",
                    "engine": "Legend Fusion (Scalper Override)",
                    "symbol": symbol,
                    "direction": scalper_res["direction"],
                    "confidence": s_conf,
                    "timeframe": scalper_res["timeframe"],
                    "plan": scalper_res["plan"], # 🚨 FIX: Use Scalper's plan
                    "features": scalper_res["features"]
                }
            else:
                return {
                    "status": "NO_TRADE",
                    "reason": f"Conflict: Trend says {trend_res['direction']} ({t_conf*100:.0f}%), Scalper says {scalper_res['direction']} ({s_conf*100:.0f}%)",
                    "symbol": symbol
                }
        else:
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
