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
        # If user clicked FUSION, use default Trend (15m) & Scalper (5m)
        if timeframe is None or timeframe == 'FUSION':
            trend_res = self.trend.analyze(symbol)
            scalper_res = self.scalper.analyze(symbol)

            if "error" in trend_res: return {"error": f"Trend Engine failed: {trend_res['error']}"}
            if "error" in scalper_res: return {"error": f"Scalper Engine failed: {scalper_res['error']}"}

            # Smart Conflict Resolution
            if trend_res["direction"] != scalper_res["direction"]:
                t_conf = trend_res["confidence"]
                s_conf = scalper_res["confidence"]
                
                if t_conf >= 0.70 and t_conf > s_conf + 0.05:
                    final_dir, final_conf, engine_name = trend_res["direction"], t_conf, "Legend Fusion (Trend Override)"
                    plan, feats, display_tf = trend_res["plan"], trend_res["features"], trend_res["timeframe"]
                elif s_conf >= 0.70 and s_conf > t_conf + 0.05:
                    final_dir, final_conf, engine_name = scalper_res["direction"], s_conf, "Legend Fusion (Scalper Override)"
                    plan, feats, display_tf = scalper_res["plan"], scalper_res["features"], scalper_res["timeframe"]
                else:
                    return {"status": "NO_TRADE", "reason": f"Conflict: Trend says {trend_res['direction']} ({t_conf*100:.0f}%), Scalper says {scalper_res['direction']} ({s_conf*100:.0f}%)", "symbol": symbol}
            else:
                final_dir = trend_res["direction"]
                final_conf = (trend_res["confidence"] + scalper_res["confidence"]) / 2
                engine_name = "Legend Fusion"
                plan, feats, display_tf = trend_res["plan"], trend_res["features"], trend_res["timeframe"]

        # If user clicked a specific timeframe (e.g. 5m)
        else:
            base_engine = TrendEngine()
            res = base_engine.analyze(symbol, timeframe)
            
            if "error" in res: return res
            if res.get("status") == "NO_TRADE": return res
            
            final_dir = res["direction"]
            final_conf = res["confidence"]
            engine_name = f"Legend Trend ({timeframe})"
            plan, feats, display_tf = res["plan"], res["features"], res["timeframe"]

        # 🚨 MULTI-TIMEFRAME CONFLUENCE CHECK 🚨
        # Map current timeframe to a higher timeframe
        htf_map = {"1m": "15m", "5m": "1h", "15m": "4h", "1h": "1d", "4h": "1d", "1d": None}
        higher_tf = htf_map.get(display_tf)
        
        if higher_tf:
            try:
                safe_symbol = symbol.replace("=", "_")
                # Try to load the higher timeframe model
                htf_model_name = f"v0.2_{safe_symbol}_{higher_tf}_h1_long.json"
                htf_model_path = MODEL_DIR / htf_model_name
                if not htf_model_path.exists():
                    htf_model_name = f"v0.2_{safe_symbol}_{higher_tf}_h10_long.json"
                    htf_model_path = MODEL_DIR / htf_model_name

                if htf_model_path.exists():
                    htf_model = get_model(htf_model_path)
                    if htf_model:
                        htf_feats, _ = get_latest_features(symbol, higher_tf)
                        htf_proba = htf_model.predict_proba([htf_feats])[0]
                        htf_dir = "LONG" if htf_proba > 0.5 else "SHORT"
                        htf_conf = htf_proba if htf_proba > 0.5 else (1 - htf_proba)

                        # Check for conflict
                        if htf_dir != final_dir and htf_conf >= 0.60:
                            return {
                                "status": "NO_TRADE",
                                "reason": f"MTF Conflict: Setup is {final_dir}, but {higher_tf} trend is strongly {htf_dir} ({htf_conf*100:.0f}%).",
                                "symbol": symbol
                            }
                        else:
                            engine_name += f" [MTF {higher_tf} Confirmed]"
            except Exception as e:
                logger.warning(f"MTF check failed, proceeding anyway: {e}")

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
