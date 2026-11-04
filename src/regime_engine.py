import logging

logger = logging.getLogger(__name__)

def check_market_regime(candles):
    """
    Analyzes the last 50 candles to determine if the market is trending or consolidating.
    Returns: (is_tradeable, regime_name, reason)
    """
    try:
        if len(candles) < 50:
            return True, "UNKNOWN", "Not enough data"

        closes = [float(c[4]) for c in candles[-50:]]
        
        # 1. Calculate EMAs (20 and 50)
        def _ema(data, span):
            alpha = 2.0 / (span + 1)
            ema = [data[0]]
            for val in data[1:]:
                ema.append(alpha * val + (1 - alpha) * ema[-1])
            return ema[-1]

        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        
        # EMA Spread as a percentage of price
        ema_spread = abs(ema20 - ema50) / closes[-1]
        
        # 2. Calculate Bollinger Band Width
        sma20 = sum(closes[-20:]) / 20
        variance = sum((x - sma20) ** 2 for x in closes[-20:]) / 19
        std20 = variance ** 0.5
        bb_width = (2 * std20) / sma20 if sma20 > 0 else 0

        # 🚨 REGIME RULES 🚨
        # If BB width is tiny, it's a squeeze (wait for breakout)
        if bb_width < 0.002: 
            return False, "SQUEEZE", f"Bollinger Bands are too tight ({bb_width*100:.3f}%). Waiting for volatility expansion."
            
        # If EMAs are basically flat, it's ranging (chop)
        if ema_spread < 0.001:
            return False, "RANGING", f"EMA20 and EMA50 are flat ({ema_spread*100:.3f}%). No clear trend."

        # If we pass both, it's a trending market
        regime = "UPTREND" if ema20 > ema50 else "DOWNTREND"
        return True, regime, f"Market is in a clear {regime}."

    except Exception as e:
        logger.error(f"Regime Engine Error: {e}")
        return True, "UNKNOWN", "Regime check failed, defaulting to safe."
