from src.engines.base_engine import TrendEngine, ScalperEngine
import logging

logger = logging.getLogger(__name__)

class FusionEngine:
    def __init__(self):
        self.trend = TrendEngine() # Defaults to 15m
        self.scalper = ScalperEngine() # Defaults to 5m
        self.swing = TrendEngine()
        self.swing.default_timeframe = "1h" # Add 1h

    def analyze(self, symbol, timeframe=None):
        if timeframe is None or timeframe == 'FUSION':
            # 🚨 SUPER FUSION: Analyze 1h, 15m, and 5m simultaneously 🚨
            res_1h = self.swing.analyze(symbol, "1h")
            res_15m = self.trend.analyze(symbol, "15m")
            res_5m = self.scalper.analyze(symbol, "5m")

            # Filter out any errors
            valid_results = [r for r in [res_1h, res_15m, res_5m] if "error" not in r]

            if not valid_results:
                return {"error": "All engines failed to load models for this symbol."}

            # Find the setup with the highest confidence
            best_setup = max(valid_results, key=lambda x: x["confidence"])

            # Check if the best setup is actually good enough
            if best_setup["confidence"] < 0.55:
                return {
                    "status": "NO_TRADE", 
                    "reason": f"Scanned 1h, 15m, 5m. Highest confidence was only {best_setup['confidence']*100:.1f}%. Below 55% threshold.", 
                    "symbol": symbol
                }

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
            # If user clicked a specific timeframe (e.g., 5m), just use that
            base_engine = TrendEngine()
            res = base_engine.analyze(symbol, timeframe)
            
            if "error" in res: return res
            if res.get("status") == "NO_TRADE": return res
            
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
