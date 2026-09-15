"""
Legend Trading AI — Data Fetcher

Fetches free OHLCV market data from Binance public API.

No API key needed. Uses:
    https://data-api.binance.vision

Usage (test):
    python -m src.data_fetcher
"""

from __future__ import annotations

import time
from typing import Optional
import requests
import pandas as pd

# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
BINANCE_BASE = "https://data-api.binance.vision"
KLINES_ENDPOINT = "/api/v3/klines"

# Binance max candles per request
MAX_LIMIT = 1000

# Seconds between requests (be polite; Binance allows more)
REQUEST_DELAY = 0.2


# ------------------------------------------------------------
# Fetch a single batch of candles
# ------------------------------------------------------------
def _fetch_batch(
    symbol: str,
    interval: str,
    start_ms: Optional[int] = None,
    limit: int = MAX_LIMIT,
) -> list:
    """Fetch one page of OHLCV candles from Binance."""
    url = BINANCE_BASE + KLINES_ENDPOINT
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if start_ms is not None:
        params["startTime"] = start_ms

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------
# Convert Binance klines to a clean pandas DataFrame
# ------------------------------------------------------------
def _to_dataframe(rows: list) -> pd.DataFrame:
    """
    Binance kline format (each row):
        [ open_time, open, high, low, close, volume,
          close_time, quote_vol, trades, taker_base,
          taker_quote, ignore ]
    """
    if not rows:
        return pd.DataFrame()

    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_base", "taker_quote", "ignore",
    ]
    df = pd.DataFrame(rows, columns=cols)

    # Convert timestamp (ms) to pandas UTC datetime
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    # Numeric conversion
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only what we need
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    df = df.set_index("open_time").sort_index()

    return df


# ------------------------------------------------------------
# Public: fetch full history between two dates
# ------------------------------------------------------------
def fetch_ohlcv(
    symbol: str,
    interval: str = "1h",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles.

    Args:
        symbol:   e.g. "BTCUSDT"
        interval: "1m", "5m", "1h", "4h", "1d"
        start:    ISO date string, e.g. "2020-01-01"
        end:      ISO date string, e.g. "2025-01-01" (optional)

    Returns:
        pandas DataFrame indexed by UTC open_time.
    """
    start_ms = None
    if start:
        start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)

    end_ms = None
    if end:
        end_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)

    all_rows: list = []
    cursor = start_ms

    while True:
        rows = _fetch_batch(symbol, interval, cursor)
        if not rows:
            break

        all_rows.extend(rows)
        last_open_ms = rows[-1][0]

        # Stop if we've reached the end
        if end_ms is not None and last_open_ms >= end_ms:
            break

        # Stop if we got fewer than max (means we reached today)
        if len(rows) < MAX_LIMIT:
            break

        cursor = last_open_ms + 1
        time.sleep(REQUEST_DELAY)

    df = _to_dataframe(all_rows)

    # Trim to requested end
    if end_ms is not None and not df.empty:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]

    return df


# ------------------------------------------------------------
# Self-test (run: python -m src.data_fetcher)
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Fetching BTC/USDT hourly candles (last ~7 days)...")
    df = fetch_ohlcv("BTCUSDT", interval="1h")

    print(f"\nRows fetched: {len(df)}")
    print(f"First bar:    {df.index[0]}")
    print(f"Last bar:     {df.index[-1]}")
    print(f"\nLast 5 closes:")
    print(df.tail(5)[["close", "volume"]])
