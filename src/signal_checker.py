"""
Outcome checker for the paper trader.

For every pending signal in SQLite:
  - Determine how many 1h bars have elapsed since the signal
  - If >= the model's horizon, fetch the close at that bar
  - Record win/loss in the database
"""

from datetime import datetime, timezone
from src.signal_db import get_pending_signals, record_outcome
from src.live_features import fetch_klines


def check_all_pending():
    """
    Walk all pending signals and mark outcomes where possible.
    Returns counts.
    """
    pending = get_pending_signals()
    checked = 0
    still_pending = 0
    errors = 0

    for sig in pending:
        try:
            symbol = sig["symbol"]
            horizon = sig["horizon"]
            signal_ts = datetime.fromisoformat(sig["ts"].replace("Z", "+00:00"))

            # Fetch enough candles to cover signal + horizon + buffer
            candles = fetch_klines(symbol, "1h", limit=300)
            if not candles:
                still_pending += 1
                continue

            signal_ms = int(signal_ts.timestamp() * 1000)

            # Find the bar that matches the signal timestamp
            signal_idx = None
            for i, c in enumerate(candles):
                if c[0] == signal_ms:
                    signal_idx = i
                    break

            if signal_idx is None:
                # Signal candle has scrolled out of window.
                # If the signal is very old, force close using latest price.
                age_ms = candles[-1][0] - signal_ms
                age_bars = age_ms // (3600 * 1000)
                if age_bars >= horizon:
                    current_close = float(candles[-1][4])
                    record_outcome(sig["id"], current_close, int(age_bars))
                    checked += 1
                else:
                    still_pending += 1
                continue

            bars_elapsed = len(candles) - 1 - signal_idx

            if bars_elapsed >= horizon:
                outcome_idx = signal_idx + horizon
                if outcome_idx < len(candles):
                    outcome_close = float(candles[outcome_idx][4])
                    record_outcome(sig["id"], outcome_close, horizon)
                    checked += 1
                else:
                    still_pending += 1
            else:
                still_pending += 1

        except Exception as e:
            print(f"  ⚠ error checking signal {sig.get('id')}: {e}")
            errors += 1
            still_pending += 1

    return {
        "checked": checked,
        "pending": still_pending,
        "errors": errors,
        "total": len(pending),
    }


if __name__ == "__main__":
    result = check_all_pending()
    print(f"Checked: {result['checked']}")
    print(f"Still pending: {result['pending']}")
    print(f"Errors: {result['errors']}")
    print(f"Total: {result['total']}")
