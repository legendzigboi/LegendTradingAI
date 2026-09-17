"""
Legend Trading AI — Paper Trader

Runs every hour. For each champion model:
  1. Fetch live 1h candles for its symbol
  2. Compute 30 features
  3. Predict probability
  4. If above threshold, log signal + send Telegram
  5. Check pending signals for outcomes

Usage:
    python -m src.paper_trader              # run one cycle (test)
    python -m src.paper_trader --loop       # run forever
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.xgb_pure import XGBPure
from src.live_features import get_latest_features, FEATURE_NAMES
from src.signal_db import init_db, log_signal
from src.signal_checker import check_all_pending
from src.telegram_notify import send_signal, send_no_trade, send_boot, send_error


# ============================================================
# Config
# ============================================================
MODEL_DIR = Path("models/v0.2")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "paper_trader.log"

CONFIDENCE_HIGH = 0.62      # STRONG signal
CONFIDENCE_LOW  = 0.55      # WEAK signal (below → no signal)
# Anything below CONFIDENCE_LOW on the "predict long" side and above
# (1 - CONFIDENCE_LOW) on the "predict short" side = no trade

# Champion portfolio: only these run in the LIVE loop.
# Other 135 models stay in shadow mode (logged, not alerted).
CHAMPIONS = [
    # symbol, horizon, direction
    ("XRPUSDT",   10, "long"),
    ("XRPUSDT",   20, "long"),
    ("SOLUSDT",   10, "long"),
    ("DOTUSDT",    5, "long"),
    ("INJUSDT",   10, "long"),
    ("ATOMUSDT",  10, "long"),
    ("DOGEUSDT",  20, "long"),
    ("AVAXUSDT",  20, "short"),
    # Add LTC/ADA based on v0.2 top performers
    ("LTCUSDT",   20, "long"),
    ("ADAUSDT",   20, "long"),
]

SHADOW_ADDITIONAL = [
    ("BTCUSDT",   10, "long"),
    ("BTCUSDT",   20, "long"),
    ("ETHUSDT",   10, "long"),
    ("BNBUSDT",   10, "long"),
]

# Horizons → assumed bar duration in hours
HORIZON_HOURS = {5: 5, 10: 10, 20: 20}


def log(msg):
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_model(symbol, horizon, direction):
    """Load a model + its metadata. Returns (XGBPure, meta) or (None, None)."""
    base = f"{symbol}_h{horizon}_{direction}"
    model_path = MODEL_DIR / f"v0.2_{base}.json"
    meta_path = MODEL_DIR / f"v0.2_{base}_meta.json"
    if not model_path.exists() or not meta_path.exists():
        return None, None
    try:
        model = XGBPure(model_path)
        meta = json.loads(meta_path.read_text())
        return model, meta
    except Exception as e:
        log(f"  ⚠ could not load {base}: {e}")
        return None, None


def make_trade_plan(entry_price, direction, horizon_hours):
    """
    Simple target/stop rules — adjust as strategy evolves.
    For now: 1.0% target, 0.8% stop (roughly R:R 1.25).
    """
    if direction == "long":
        target = entry_price * 1.010
        stop = entry_price * 0.992
    else:
        target = entry_price * 0.990
        stop = entry_price * 1.008
    return round(target, 8), round(stop, 8)


def run_cycle():
    """One full pass through all champions + shadows."""
    log("=" * 60)
    log("Starting hourly cycle")

    # Init DB
    init_db()

    # ---- 1. Check outcomes of prior signals ----
    try:
        result = check_all_pending()
        log(f"Outcome check: {result['checked']} checked, {result['pending']} pending")
    except Exception as e:
        log(f"  ⚠ outcome check failed: {e}")

    # ---- 2. Run predictions ----
    strong_signals = 0
    weak_signals = 0
    markets_checked = 0

    for role, portfolio in [("champion", CHAMPIONS), ("shadow", SHADOW_ADDITIONAL)]:
        # Group by symbol so we fetch features once per symbol
        symbols = sorted(set(s for s, _, _ in portfolio))

        for symbol in symbols:
            try:
                feats, ts_ms = get_latest_features(symbol)
            except Exception as e:
                log(f"  ❌ {symbol}: feature error {e}")
                continue

            markets_checked += 1
            bar_time = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            entry_price = None  # will set after fetching

            # Fetch latest price for entry (close of last completed candle)
            # live_features returns features only; get price from a quick fetch
            from src.live_features import fetch_klines
            candles = fetch_klines(symbol, "1h", limit=2)
            if not candles:
                continue
            entry_price = float(candles[-2][4])  # last completed candle close

            # Loop all (symbol, H, direction) combos for this symbol
            combos = [(H, d) for s, H, d in portfolio if s == symbol]

            for H, direction in combos:
                model, meta = load_model(symbol, H, direction)
                if model is None:
                    continue

                # Predict
                proba = model.predict_proba([feats])[0]
                # For 'short' or 'both', we look at low proba as bearish signal
                # Define "signal strength" for the direction requested
                if direction == "long":
                    conf = proba
                elif direction == "short":
                    conf = 1 - proba
                else:  # both
                    conf = max(proba, 1 - proba)

                if conf < CONFIDENCE_LOW:
                    continue  # no signal at all

                if conf < CONFIDENCE_HIGH:
                    signal_type = "WEAK"
                    weak_signals += 1
                else:
                    signal_type = "STRONG"
                    strong_signals += 1

                target, stop = make_trade_plan(entry_price, direction, HORIZON_HOURS[H])

                # Log to DB
                sig_id = log_signal(
                    symbol=symbol, horizon=H, direction=direction,
                    role=role, model_version="v0.2",
                    confidence=float(conf),
                    entry_price=entry_price,
                    target_price=target,
                    stop_price=stop,
                    signal_type=signal_type,
                )

                # Send Telegram only for champions + strong signals
                if role == "champion":
                    try:
                        send_signal(
                            symbol=symbol, direction=direction,
                            confidence=float(conf), price=entry_price,
                            horizon=H, role=role,
                            model_name=f"v0.2_{symbol}_h{H}_{direction}",
                        )
                    except Exception as e:
                        log(f"  ⚠ telegram send failed: {e}")

                log(f"  [{role}] {symbol} H={H} {direction} conf={conf:.3f} → {signal_type} (id={sig_id})")

    # ---- 3. Summary ----
    if strong_signals == 0 and weak_signals == 0:
        log(f"No signals this cycle. Markets checked: {markets_checked}")
        # Send a "no trade" only once per hour — skip to avoid spam
        # send_no_trade(markets_checked)
    else:
        log(f"Signals: {strong_signals} strong, {weak_signals} weak")

    log("Cycle complete")
    return {"strong": strong_signals, "weak": weak_signals, "markets": markets_checked}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="run forever, hourly")
    parser.add_argument("--boot", action="store_true", help="send boot message")
    args = parser.parse_args()

    if args.boot:
        try:
            send_boot(models_loaded=len(CHAMPIONS) + len(SHADOW_ADDITIONAL), next_check_min=60)
            log("Boot message sent")
        except Exception as e:
            log(f"Boot message failed: {e}")

    if args.loop:
        log("Starting paper trader in LOOP mode (runs every hour)")
        # Send boot once at start
        try:
            send_boot(models_loaded=len(CHAMPIONS) + len(SHADOW_ADDITIONAL), next_check_min=60)
        except Exception:
            pass

        while True:
            try:
                run_cycle()
            except Exception as e:
                log(f"❌ Cycle error: {e}")
                try:
                    send_error("paper_trader.run_cycle", str(e))
                except Exception:
                    pass

            # Wait until top of the next hour + 30 seconds
            now = datetime.now(tz=timezone.utc)
            next_hour = now.replace(minute=0, second=30, microsecond=0)
            if next_hour <= now:
                next_hour = next_hour.replace(hour=next_hour.hour)  # advance 1h
                from datetime import timedelta
                next_hour = next_hour + timedelta(hours=1)
            wait_sec = (next_hour - now).total_seconds()
            log(f"Sleeping {wait_sec/60:.1f} min until next cycle")
            time.sleep(max(wait_sec, 30))
    else:
        result = run_cycle()
        print(f"\nCycle result: {result}")


if __name__ == "__main__":
    main()
