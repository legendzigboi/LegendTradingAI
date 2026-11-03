import logging
from src.signal_db import get_all_closed_signals, save_insight

logger = logging.getLogger(__name__)

def run_research_lab():
    """
    Scans all closed trades and looks for statistical edges.
    Saves findings to the AI Memory database.
    """
    trades = get_all_closed_signals()
    
    if len(trades) < 10:
        return "⚠️ Not enough data to run research. Need at least 10 closed trades."

    insights_found = 0
    
    # Analyze by Symbol & Timeframe
    combos = {}
    for t in trades:
        key = f"{t['symbol']} {t['timeframe']}"
        if key not in combos:
            combos[key] = {"wins": 0, "total": 0, "high_conf_wins": 0, "high_conf_total": 0}
        
        combos[key]["total"] += 1
        if t["status"] == "WIN": combos[key]["wins"] += 1
        
        # Analyze High Confidence (>70%)
        if t["confidence"] >= 0.70:
            combos[key]["high_conf_total"] += 1
            if t["status"] == "WIN": combos[key]["high_conf_wins"] += 1

    # Generate Insights based on patterns
    for combo, stats in combos.items():
        if stats["total"] >= 5:
            wr = (stats["wins"] / stats["total"]) * 100
            if wr >= 65.0:
                insight = f"{combo} is highly profitable with a {wr:.1f}% win rate."
                if save_insight("PERFORMANCE", insight, wr, stats["total"]):
                    insights_found += 1
            elif wr <= 35.0:
                insight = f"WARNING: {combo} is struggling with only a {wr:.1f}% win rate. Consider avoiding."
                if save_insight("WARNING", insight, wr, stats["total"]):
                    insights_found += 1

        if stats["high_conf_total"] >= 3:
            hc_wr = (stats["high_conf_wins"] / stats["high_conf_total"]) * 100
            if hc_wr >= 70.0:
                insight = f"PREMIUM EDGE: {combo} wins {hc_wr:.1f}% of the time when AI Confidence is >70%."
                if save_insight("EDGE", insight, hc_wr, stats["high_conf_total"]):
                    insights_found += 1

    if insights_found == 0:
        return "🔬 Research complete. No new strong patterns discovered yet. Keep trading!"
    
    return f"🔬 Research complete! The bot discovered {insights_found} new patterns and saved them to AI Memory."
