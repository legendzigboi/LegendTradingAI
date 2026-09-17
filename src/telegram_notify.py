"""
Telegram message formatting for the paper trader.

Plain text only — no Markdown parsing issues.
Supports:
  - STRONG signal (full trade plan with TP1/TP2/TP3)
  - WEAK signal (watch only)
  - NO TRADE (with per-symbol breakdown)
  - TRADING DISABLED (data/health issue)
  - System boot / error alerts
"""

from datetime import datetime, timezone, timedelta
from src.telegram_bot import send_message


def _fmt_price(p):
    """Format a price with sensible decimals."""
    if p is None:
        return "—"
    if p >= 1000:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:.4f}"
    return f"{p:.6f}"


def format_strong_signal(symbol, direction, confidence, entry, stop, tps,
                         horizon_hours, model_version, setup_bullets, role):
    """
    Full trade plan for a strong signal.

    tps = [tp1, tp2, tp3]  (list of prices)
    setup_bullets = list of strings
    """
    emoji = "🟢" if direction == "long" else "🔴"
    dir_label = "LONG" if direction == "long" else "SHORT"

    # Risk/Reward: (TP1 - entry) / (entry - stop)  * adjusted for direction
    if direction == "long":
        rr = (tps[0] - entry) / (entry - stop) if (entry - stop) > 0 else 0
    else:
        rr = (entry - tps[0]) / (stop - entry) if (stop - entry) > 0 else 0

    bullets = "\n".join(f"• {b}" for b in setup_bullets) if setup_bullets else "• (details in DB)"

    return (
        f"{emoji} LEGEND SIGNAL\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Market:     Crypto\n"
        f"Symbol:     {symbol}\n"
        f"Direction:  {dir_label}\n"
        f"Timeframe:  1H\n\n"
        f"Entry:      {_fmt_price(entry)}\n"
        f"Stop Loss:  {_fmt_price(stop)}\n\n"
        f"TP1:        {_fmt_price(tps[0])}\n"
        f"TP2:        {_fmt_price(tps[1])}\n"
        f"TP3:        {_fmt_price(tps[2])}\n\n"
        f"Risk/Reward: 1:{rr:.2f}\n"
        f"Confidence:  {confidence*100:.1f}%\n\n"
        f"Setup:\n{bullets}\n\n"
        f"Entry window: 15 minutes\n"
        f"Signal expires: soon\n\n"
        f"Model:   {model_version}\n"
        f"Role:    {role.upper()}\n"
        f"Mode:    PAPER\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Paper trading only."
    )


def format_weak_signal(symbol, direction, confidence, entry, role):
    emoji = "🟡"
    return (
        f"{emoji} LEGEND SIGNAL — WEAK\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Symbol:     {symbol}\n"
        f"Direction:  {direction.upper()}\n"
        f"Confidence: {confidence*100:.1f}%\n"
        f"Current:    {_fmt_price(entry)}\n\n"
        f"Status:     WATCH ONLY\n"
        f"Action:     DO NOT ENTER\n\n"
        f"Why: Confidence below {0.62*100:.0f}% threshold.\n"
        f"Monitor for next candle.\n\n"
        f"Role: {role.upper()}\n"
        f"Mode: PAPER"
    )


def format_no_trade(symbols_checked, symbol_scores, timestamp):
    """
    symbol_scores = list of (symbol, direction, confidence) top picks.
    """
    lines = []
    for sym, direction, conf in symbol_scores[:5]:
        lines.append(f"{sym:12s} {direction.upper():5s} {conf*100:.0f}%")

    top_block = "\n".join(lines) if lines else "(none above 50%)"

    return (
        f"⚪ LEGEND TRADING AI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"NO TRADE\n\n"
        f"Time:            {timestamp:%Y-%m-%d %H:%M} UTC\n"
        f"Markets checked: {symbols_checked}\n\n"
        f"Closest candidates:\n{top_block}\n\n"
        f"Reason:\n"
        f"Market prediction too weak for risk.\n\n"
        f"Status: ONLINE"
    )


def format_trading_disabled(reason, timestamp):
    return (
        f"🔴 TRADING DISABLED\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Time:   {timestamp:%Y-%m-%d %H:%M} UTC\n"
        f"Reason: {reason}\n\n"
        f"No new positions permitted.\n"
        f"Investigating..."
    )


def format_boot_message(models_loaded, next_check_min):
    ts = datetime.now(tz=timezone.utc)
    return (
        f"🚀 LEGEND TRADING AI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"System BOOTED ✅\n\n"
        f"Time:           {ts:%Y-%m-%d %H:%M} UTC\n"
        f"Models loaded:  {models_loaded}\n"
        f"Mode:           PAPER\n"
        f"Next check:     in {next_check_min} min\n\n"
        f"Monitoring has begun."
    )


def format_error(component, error_msg):
    ts = datetime.now(tz=timezone.utc)
    return (
        f"⚠️ SYSTEM ALERT\n\n"
        f"Time:       {ts:%Y-%m-%d %H:%M} UTC\n"
        f"Component:  {component}\n"
        f"Error:      {error_msg[:200]}"
    )


# ---- Senders ----

def send_strong_signal(**kw):
    return send_message(format_strong_signal(**kw), parse_mode=None)

def send_weak_signal(**kw):
    return send_message(format_weak_signal(**kw), parse_mode=None)

def send_no_trade(symbols_checked, symbol_scores, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc)
    return send_message(
        format_no_trade(symbols_checked, symbol_scores, timestamp),
        parse_mode=None,
    )

def send_trading_disabled(reason):
    return send_message(
        format_trading_disabled(reason, datetime.now(tz=timezone.utc)),
        parse_mode=None,
    )

def send_boot(models_loaded, next_check_min=60):
    return send_message(format_boot_message(models_loaded, next_check_min), parse_mode=None)

def send_error(component, error_msg):
    return send_message(format_error(component, error_msg), parse_mode=None)


# Backwards-compatible aliases (used by paper_trader.py)
def send_signal(symbol, direction, confidence, price, horizon, role, model_name):
    """Legacy wrapper for paper_trader.py."""
    from src.live_features import fetch_klines
    candles = fetch_klines(symbol, "1h", limit=2)
    entry = float(candles[-2][4]) if candles else price

    if direction == "long":
        stop = entry * 0.992
        tp1 = entry * 1.008
        tp2 = entry * 1.015
        tp3 = entry * 1.025
    else:
        stop = entry * 1.008
        tp1 = entry * 0.992
        tp2 = entry * 0.985
        tp3 = entry * 0.975

    if confidence >= 0.62:
        return send_strong_signal(
            symbol=symbol, direction=direction, confidence=confidence,
            entry=entry, stop=stop, tps=[tp1, tp2, tp3],
            horizon_hours=horizon, model_version=model_name,
            setup_bullets=["(populated in v0.3 with multi-timeframe context)"],
            role=role,
        )
    else:
        return send_weak_signal(
            symbol=symbol, direction=direction, confidence=confidence,
            entry=entry, role=role,
        )


if __name__ == "__main__":
    print("Sending test STRONG signal...")
    ok = send_strong_signal(
        symbol="XRPUSDT", direction="long", confidence=0.72,
        entry=1.2856, stop=1.2760, tps=[1.2945, 1.3010, 1.3150],
        horizon_hours=10, model_version="v0.2_XRPUSDT_h10_long",
        setup_bullets=["1H momentum aligned", "4H trend supportive",
                       "volatility acceptable", "volume confirmation"],
        role="champion",
    )
    print("Sent ✅" if ok else "Failed ❌")
