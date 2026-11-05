from src.engines.base_engine import TrendEngine, ScalperEngine
import logging

logger = logging.getLogger(__name__)

class FusionEngine:
    def __init__(self):
        self.trend = TrendEngine()
        self.scalper = ScalperEngine()
        self.swing = TrendEngine()
        self.swing.default_timeframe = "1h"

    def analyze(self, symbol, timeframe=None):
        if timeframe is None or timeframe == 'FUSION':
            res_1h = self.swing.analyze(symbol, "1h")
            res_15m = self.trend.analyze(symbol, "15m")
            res_5m = self.scalper.analyze(symbol, "5m")

            valid_results = [r for r in [res_1h, res_15m, res_5m] if "error" not in r]

            if not valid_results:
                # 🚨 REVEAL THE EXACT ERRORS 🚨
                errs = []
                if "error" in res_1h: errs.append(f"1h: {res_1h['error']}")
                if "error" in res_15m: errs.append(f"15m: {res_15m['error']}")
                if "error" in res_5m: errs.append(f"5m: {res_5m['error']}")
                return {"error": " | ".join(errs)}

            best_setup = max(valid_results, key=lambda x: x["confidence"])

            if best_setup["confidence"] < 0.55:
                return {"status": "NO_TRADE", "reason": f"Highest confidence was only {best_setup['confidence']*100:.1f}% on {best_setup['timeframe']}.", "symbol": symbol}

            return {
                "status": "SUCCESS",
                "engine": f"Legend Super Fusion (Best TF: {best_setup['timeframe']})",
                "symbol": symbol,
                "direction": best_setup["direction"],
                "confidence": best_setup["confidence"],
                "timeframe": best_setup["timeframe"],
                "plan": best_setup["plan"],
                "features": best_setup["features"]
            }
        else:
            base_engine = TrendEngine()
            res = base_engine.analyze(symbol, timeframe)
            if "error" in res: return res
            return {
                "status": "SUCCESS",
                "engine": f"Legend Trend ({timeframe})",
                "symbol": symbol,
                "direction": res["direction"],
                "confidence": res["confidence"],
                "timeframe": res["timeframe"],
                "plan": res["plan"],
                "features": res["features"]
            }
