"""
Trade Planner: Calculates Entry, SL, and TP1/TP2/TP3.
Uses volatility (ATR) to set dynamic stops.
"""

def build_trade_plan(entry_price, direction, atr_14):
    """
    Calculates the trade levels based on direction and volatility.
    If ATR is too small, we use a minimum 0.5% move to avoid instant stop-outs.
    """
    if atr_14 < 0.005:
        atr_14 = 0.005  # Minimum 0.5% move
        
    if direction.upper() == "LONG":
        stop_loss = entry_price * (1 - (atr_14 * 1.5))
        tp1 = entry_price * (1 + (atr_14 * 1.0))
        tp2 = entry_price * (1 + (atr_14 * 2.0))
        tp3 = entry_price * (1 + (atr_14 * 3.0))
    else: # SHORT
        stop_loss = entry_price * (1 + (atr_14 * 1.5))
        tp1 = entry_price * (1 - (atr_14 * 1.0))
        tp2 = entry_price * (1 - (atr_14 * 2.0))
        tp3 = entry_price * (1 - (atr_14 * 3.0))
        
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3
    }
