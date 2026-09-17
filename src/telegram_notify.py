"""
Telegram message formatting + sending for the paper trader.

Plain text only (no Markdown) — avoids Telegram parsing errors.
Reuses the send_message() helper from src/telegram_bot.py.
"""

from datetime import datetime, timezone
from src.telegram_bot import send_message


def format_signal(symbol, direction, confidence, price, horizon, role, model_name):
    """Format a trading signal message."""
    emoji = "🟢" if direction == "long" else "🔴"
    dir_label = "BUY" if direction == "long" else "SELL"

    role_tag = "PAPER (Champion)" if role == "champion" else "SHADOW (learning only)"

    return (
        f"{emoji} LEGEND TRADING AI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{dir_label} SIGNAL — {symbol}\n\n"
        f"Direction:  {direction.upper()}\n"
        f"Confidence: {confidence*100:.1f}%\n"
        f"Price:      ${price:.6f}\n"
        f"Horizon:    {horizon} bars\n"
        f"Model:      {model_name}\n"
        f"Role:       {role_tag}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Paper trading only."
    )


def format_no_trade(symbols_checked, timestamp):
    """Format a no-trade status message."""
    return (
        f"⚪ LEGEND TRADING AI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"NO TRADE\n\n"
        f"Time:            {timestamp:%Y-%m-%d %H:%M} UTC\n"
        f"Markets checked: {symbols_checked}\n\n"
        f"No setup passed the confidence threshold.\n"
        f"Status: ONLINE ✅"
    )


def format_boot_message(models_loaded, next_check_min):
    """Format the startup message."""
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
    """Format an error alert."""
    ts = datetime.now(tz=timezone.utc)
    return (
        f"⚠️ SYSTEM ALERT\n\n"
        f"Time:       {ts:%Y-%m-%d %H:%M} UTC\n"
        f"Component:  {component}\n"
        f"Error:      {error_msg[:200]}"
    )


def send_signal(symbol, direction, confidence, price, horizon, role, model_name):
    return send_message(
        format_signal(symbol, direction, confidence, price, horizon, role, model_name),
        parse_mode=None,
    )


def send_no_trade(symbols_checked):
    return send_message(
        format_no_trade(symbols_checked, datetime.now(tz=timezone.utc)),
        parse_mode=None,
    )


def send_boot(models_loaded, next_check_min=60):
    return send_message(
        format_boot_message(models_loaded, next_check_min),
        parse_mode=None,
    )


def send_error(component, error_msg):
    return send_message(
        format_error(component, error_msg),
        parse_mode=None,
    )


if __name__ == "__main__":
    print("Sending test signal...")
    ok = send_signal(
        symbol="XRPUSDT", direction="long", confidence=0.68,
        price=1.2856, horizon=10, role="champion",
        model_name="XRP_h10_long_v1",
    )
    print("Sent ✅" if ok else "Failed ❌")
