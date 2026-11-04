import logging

logger = logging.getLogger(__name__)

def check_market_regime(candles):
    try:
        if len(candles) < 50:
            return True, "UNKNOWN", "Not enough data"

        closes = [float(c[4]) for c in candles[-50:]]
        
        def _ema(data, span):
            alpha = 2.0 / (span + 1)
            ema = [data[0]]
            for val in data[1:]:
                ema.append(alpha * val + (1 - alpha) * ema[-1])
            return ema[-1]

        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        
        ema_spread = abs(ema20 - ema50) / closes[-1]
        
        sma20 = sum(closes[-20:]) / 20
        variance = sum((x - sma20) ** 2 for x in closes[-20:]) / 19
        std20 = variance ** 0.5
        bb_width = (2 * std20) / sma20 if sma20 > 0 else 0

        # 🚨 RELAXED THRESHOLDS 🚨
        if bb_width < 0.0005: 
            return False, "SQUEEZE", f"Bollinger Bands are extremely tight ({bb_width*100:.3f}%). Market is dead."
            
        if ema_spread < 0.0002:
            return False, "RANGING", f"EMA20 and EMA50 are flat ({ema_spread*100:.3f}%). No trend."

        regime = "UPTREND" if ema20 > ema50 else "DOWNTREND"
        return True, regime, f"Market is in a clear {regime}."

    except Exception as e:
        logger.error(f"Regime Engine Error: {e}")
        return True, "UNKNOWN", "Regime check failed, defaulting to safe."
