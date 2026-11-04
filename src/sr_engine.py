import logging

logger = logging.getLogger(__name__)

def check_support_resistance(symbol, current_price, direction, candles, is_crypto=True):
    """
    Checks if the current price is too close to a major Support or Resistance level.
    Returns: (is_safe, reason)
    """
    try:
        if not candles or len(candles) < 50:
            return True, "Not enough data for S/R"

        # Look at the last 50 candles
        lookback = 50
        recent_highs = [float(c[2]) for c in candles[-lookback:]]
        recent_lows = [float(c[3]) for c in candles[-lookback:]]

        resistance = max(recent_highs)
        support = min(recent_lows)

        # Set tolerance based on asset class (Crypto is more volatile)
        tolerance = 0.005 if is_crypto else 0.0015 # 0.5% for Crypto, 0.15% for Forex/Stocks

        if direction == "LONG":
            # If we are close to resistance, but NOT breaking through it
            if current_price < resistance and (resistance - current_price) / current_price <= tolerance:
                return False, f"Too close to Resistance ({resistance:.4f}). Risk of reversal."
        
        elif direction == "SHORT":
            # If we are close to support, but NOT breaking through it
            if current_price > support and (current_price - support) / current_price <= tolerance:
                return False, f"Too close to Support ({support:.4f}). Risk of bounce."

        return True, "S/R Clear"
    except Exception as e:
        logger.error(f"S/R Engine Error: {e}")
        return True, "S/R Check Skipped"
