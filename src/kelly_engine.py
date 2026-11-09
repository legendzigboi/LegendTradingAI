import asyncio
from src.signal_db import get_historical_win_rate

async def calculate_kelly_position_size(symbol, timeframe, entry, stop_loss, tp1):
    hist_win_rate = await asyncio.to_thread(get_historical_win_rate, symbol, timeframe)
    
    risk_distance = abs(entry - stop_loss)
    reward_distance = abs(tp1 - entry)
    rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 1.0
    
    base_risk_pct = 0.01 
    
    if hist_win_rate is not None and hist_win_rate > 0:
        win_prob = hist_win_rate
        lose_prob = 1 - win_prob
        kelly_pct = (win_prob - (lose_prob / rr_ratio)) / 2
        base_risk_pct = max(0.001, min(0.025, kelly_pct))
        
    account_size = 1000
    risk_amount = account_size * base_risk_pct
    sl_distance_pct = risk_distance / entry
    
    suggested_lot = risk_amount / (entry * sl_distance_pct) if sl_distance_pct > 0 else 0
    suggested_lot = round(suggested_lot / 1000, 2) 
    if suggested_lot < 0.01: suggested_lot = 0.01

    sizing_text = f"Risk: {base_risk_pct*100:.2f}% of $1000 = ${risk_amount:.2f}"
    if hist_win_rate is not None:
        sizing_text += f"\n*(Based on {hist_win_rate*100:.1f}% historical win rate)*"

    return sizing_text, suggested_lot
