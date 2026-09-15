"""
Legend Trading AI — Data Fetcher (LITE)

Lightweight version that does NOT require pandas.
Use this to test the Binance API from a phone/Termux.

For full data pipelines (with pandas), use src/data_fetcher.py
in Google Colab.

Usage:
    python -m src.data_fetcher_lite
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
import requests


BINANCE_BASE = "https://data-api.binance.vision"
KLINES_ENDPOINT = "/api/v3/klines"
MAX_LIMIT = 1000
REQUEST_DELAY = 0.2


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 10) -> list:
    """Fetch the most recent N candles for a symbol. Returns raw list."""
    url = BINANCE_BASE + KLINES_ENDPOINT
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def format_row(row: list) -> str:
    """Format one Binance kline row as readable text."""
    open_ms = row[0]
    open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    open_p, high, low, close, volume = row[1], row[2], row[3], row[4], row[5]
    return (
        f"{open_time:%Y-%m-%d %H:%M} UTC | "
        f"O {float(open_p):>10.2f}  "
        f"H {float(high):>10.2f}  "
        f"L {float(low):>10.2f}  "
        f"C {float(close):>10.2f}  "
        f"V {float(volume):>12.4f}"
    )


def ping() -> bool:
    """Check the Binance API responds."""
    url = BINANCE_BASE + "/api/v3/ping"
    try:
        r = requests.get(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Legend Trading AI — Binance API Test")
    print("=" * 70)

    print("\n[1] Ping test...")
    if not ping():
        print("    ❌ Binance API unreachable")
        raise SystemExit(1)
    print("    ✅ Binance API is responding")

    print("\n[2] Fetching last 10 BTC/USDT hourly candles...")
    rows = fetch_klines("BTCUSDT", interval="1h", limit=10)
    print(f"    ✅ Received {len(rows)} candles\n")

    print("=" * 70)
    for row in rows:
        print(format_row(row))
    print("=" * 70)

    print("\n✅ Data pipeline test COMPLETE")
    print("Free Binance data is accessible from your device.")
