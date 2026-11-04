import logging

logger = logging.getLogger(__name__)

def check_support_resistance(symbol, current_price, direction, candles, is_crypto=True):
    try:
        if not candles or len(candles) < 50:
            return True, "Not enough data"

        lookback = 50
        recent_highs = [float(c[2]) for c in candles[-lookback:]]
        recent_lows = [float(c[3]) for c in candles[-lookback:]]

        resistance = max(recent_highs)
        support = min(recent_lows)

        # 🚨 RELAXED TOLERANCE: Only block if it's RIGHT at the wall 🚨
        tolerance = 0.003 if is_crypto else 0.001 

        if direction == "LONG":
            if current_price < resistance and (resistance - current_price) / current_price <= tolerance:
                return False, f"Too close to Resistance ({resistance:.4f})."
        
        elif direction == "SHORT":
            if current_price > support and (current_price - support) / current_price <= tolerance:
                return False, f"Too close to Support ({support:.4f})."

        return True, "S/R Clear"
    except Exception as e:
        logger.error(f"S/R Engine Error: {e}")
        return True, "S/R Check Skipped"
