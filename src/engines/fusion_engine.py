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

        # 🚨 SMART CONFLICT RESOLUTION 🚨
        if trend_res["direction"] != scalper_res["direction"]:
            # If they disagree, check if one has a massive confidence edge
            t_conf = trend_res["confidence"]
            s_conf = scalper_res["confidence"]
            
            if t_conf >= 0.70 and t_conf > s_conf + 0.05:
                # Trend is highly confident and clearly better, override Scalper
                fused_confidence = t_conf
                final_direction = trend_res["direction"]
                engine_name = "Legend Fusion (Trend Override)"
            elif s_conf >= 0.70 and s_conf > t_conf + 0.05:
                # Scalper is highly confident and clearly better, override Trend
                fused_confidence = s_conf
                final_direction = scalper_res["direction"]
                engine_name = "Legend Fusion (Scalper Override)"
            else:
                return {
                    "status": "NO_TRADE",
                    "reason": f"Conflict: Trend says {trend_res['direction']} ({t_conf*100:.0f}%), Scalper says {scalper_res['direction']} ({s_conf*100:.0f}%)",
                    "symbol": symbol
                }
        else:
            # They agree
            fused_confidence = (trend_res["confidence"] + scalper_res["confidence"]) / 2
            final_direction = trend_res["direction"]
            engine_name = "Legend Fusion"

        return {
            "status": "SUCCESS",
            "engine": engine_name,
            "symbol": symbol,
            "direction": final_direction,
            "confidence": fused_confidence,
            "timeframe": trend_res["timeframe"],
            "plan": trend_res["plan"],
            "features": trend_res["features"]
        }
