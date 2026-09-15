"""
Legend Trading AI — Data Engine

Downloads historical OHLCV data from Binance public API.
Pure Python + requests (no pandas / pyarrow required).

Features:
  - Symbol discovery from Binance exchangeInfo
  - Liquidity filter (24h quote volume)
  - Rate-limit-aware downloader
  - Retry with exponential backoff
  - Checkpointing (resume after crash)
  - Quality validation (gaps, OHLC sanity, duplicates)
  - CSV output (auto-switches to Parquet if pyarrow present)
  - Summary report

Usage:
    python -m src.data_engine                     # default: seed symbols, all timeframes in config
    python -m src.data_engine --test              # quick test: 3 symbols, 1h only
    python -m src.data_engine --symbols BTCUSDT ETHUSDT --timeframes 1h
    python -m src.data_engine --discover          # auto-discover eligible symbols
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# Import project config (loads settings.yaml + .env)
from src.config import settings, ROOT, env


# ============================================================
# Constants
# ============================================================
BINANCE_BASE = "https://data-api.binance.vision"
KLINES = "/api/v3/klines"
EXCHANGE_INFO = "/api/v3/exchangeInfo"
TICKER_24H = "/api/v3/ticker/24hr"

# Binance max candles per request
MAX_LIMIT = 1000

# Timeframe -> duration in milliseconds (for pagination)
TF_MS = {
    "5m":  5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h":  60 * 60 * 1000,
    "4h":  4 * 60 * 60 * 1000,
    "1d":  24 * 60 * 60 * 1000,
}

# Where things live
DATA_DIR = ROOT / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = ROOT / "data" / "download_checkpoint.json"
SUMMARY_FILE    = ROOT / "data" / "download_summary.csv"


# ============================================================
# HTTP client with retry + backoff
# ============================================================
class BinanceClient:
    """Thin wrapper around Binance public endpoints with retry logic."""

    def __init__(self, min_delay: float = 0.25, max_retries: int = 5):
    self.session = requests.Session()
    # Critical fix: WARP + keep-alive breaks Python requests.
    # Force fresh connection per request.
    self.session.headers.update({"Connection": "close"})
    self.min_delay = min_delay
    self.max_retries = max_retries
    self._last_call = 0.0

    def _wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_call = time.time()

    def get(self, path: str, params: Optional[dict] = None) -> dict | list:
        url = BINANCE_BASE + path
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                r = self.session.get(url, params=params, timeout=20)

                if r.status_code == 200:
                    return r.json()

                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", "5"))
                    print(f"    ⚠ 429 rate-limited, sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                if r.status_code >= 500:
                    backoff = 2 ** attempt
                    print(f"    ⚠ {r.status_code} server error, retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue

                # 4xx other than 429 — likely a real error
                print(f"    ❌ HTTP {r.status_code}: {r.text[:200]}")
                return []

            except requests.RequestException as e:
                backoff = 2 ** attempt
                print(f"    ⚠ network error ({e}), retry {attempt}/{self.max_retries} in {backoff}s")
                time.sleep(backoff)

        print(f"    ❌ Failed after {self.max_retries} retries: {url}")
        return []


# ============================================================
# Symbol discovery
# ============================================================
def get_all_spot_usdt_symbols(client: BinanceClient) -> list[str]:
    """Return all active spot USDT-quoted symbols from Binance."""
    info = client.get(EXCHANGE_INFO)
    symbols = []
    for s in info.get("symbols", []):
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("isSpotTradingAllowed", False)
        ):
            symbols.append(s["symbol"])
    return sorted(set(symbols))


def get_24h_quote_volume(client: BinanceClient) -> dict[str, float]:
    """Return {symbol: 24h_quote_volume_usdt}."""
    data = client.get(TICKER_24H)
    out = {}
    for row in data:
        try:
            out[row["symbol"]] = float(row["quoteVolume"])
        except (KeyError, ValueError):
            continue
    return out


def filter_eligible_symbols(
    all_symbols: list[str],
    volumes: dict[str, float],
    min_volume_usdt: float = 5_000_000,
    max_symbols: int = 30,
) -> list[str]:
    """Filter by liquidity, rank, and cap."""
    eligible = [
        s for s in all_symbols
        if volumes.get(s, 0) >= min_volume_usdt
    ]
    eligible.sort(key=lambda s: volumes.get(s, 0), reverse=True)
    return eligible[:max_symbols]


# ============================================================
# Kline fetching
# ============================================================
def fetch_klines_range(
    client: BinanceClient,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
) -> list[list]:
    """Fetch all klines between start_ms and end_ms (paginated)."""
    all_rows = []
    cursor = start_ms
    tf_ms = TF_MS[interval]

    while cursor < end_ms:
        rows = client.get(KLINES, {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": MAX_LIMIT,
        })

        if not isinstance(rows, list) or not rows:
            break

        all_rows.extend(rows)

        last_open = rows[-1][0]
        if len(rows) < MAX_LIMIT:
            break

        cursor = last_open + tf_ms  # next candle after last one

    return all_rows


# ============================================================
# Quality validation
# ============================================================
def validate_klines(rows: list[list], interval: str) -> dict:
    """Return validation summary. Never modifies data."""
    result = {
        "count": len(rows),
        "duplicates": 0,
        "invalid_ohlc": 0,
        "largest_gap_hours": 0.0,
        "first_ts": None,
        "last_ts": None,
    }
    if not rows:
        return result

    seen = set()
    prev_open = None
    max_gap_ms = 0

    for r in rows:
        open_ms = r[0]
        if open_ms in seen:
            result["duplicates"] += 1
        seen.add(open_ms)

        try:
            o, h, l, c = float(r[1]), float(r[2]), float(r[3]), float(r[4])
            if not (l <= o <= h and l <= c <= h and l <= h):
                result["invalid_ohlc"] += 1
        except (ValueError, TypeError):
            result["invalid_ohlc"] += 1

        if prev_open is not None:
            gap = open_ms - prev_open
            if gap > max_gap_ms:
                max_gap_ms = gap
        prev_open = open_ms

    result["first_ts"] = datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc).isoformat()
    result["last_ts"]  = datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc).isoformat()
    result["largest_gap_hours"] = round(max_gap_ms / (1000 * 3600), 2)
    return result


# ============================================================
# Storage (CSV for now; Parquet if pyarrow available)
# ============================================================
def save_klines(rows: list[list], symbol: str, interval: str) -> Path:
    """Save klines to disk. CSV if no pyarrow; Parquet otherwise."""
    filename = f"{symbol}_{interval}"
    csv_path = DATA_DIR / f"{filename}.csv"

    # Simple, portable CSV
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["open_time", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([
                datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).isoformat(),
                r[1], r[2], r[3], r[4], r[5],
            ])

    # Try Parquet if pyarrow exists
    try:
        import pyarrow as pa            # noqa
        import pyarrow.parquet as pq    # noqa
        import pandas as pd

        df = pd.DataFrame(rows, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qvol", "trades", "tb", "tq", "ignore",
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df[["open_time", "open", "high", "low", "close", "volume"]]
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        parquet_path = DATA_DIR / f"{filename}.parquet"
        df.to_parquet(parquet_path, index=False)
        csv_path.unlink(missing_ok=True)
        return parquet_path
    except ImportError:
        return csv_path


# ============================================================
# Checkpoint manager
# ============================================================
def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"completed": [], "failed": []}


def save_checkpoint(state: dict):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2))


def task_key(symbol: str, interval: str) -> str:
    return f"{symbol}_{interval}"


# ============================================================
# Main orchestration
# ============================================================
def run(symbols: list[str], timeframes: list[str], years: int = 5):
    client = BinanceClient()
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get("completed", []))
    failed = set(checkpoint.get("failed", []))

    end_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(tz=timezone.utc).timestamp() - years * 365 * 86400) * 1000)

    total = len(symbols) * len(timeframes)
    done = 0

    print("=" * 70)
    print(f"Legend Trading AI — Data Engine")
    print(f"Symbols: {len(symbols)}  |  Timeframes: {len(timeframes)}  |  Total: {total}")
    print(f"Range: {years} years")
    print("=" * 70)

    summaries = []

    for symbol in symbols:
        for tf in timeframes:
            key = task_key(symbol, tf)
            done += 1

            if key in completed:
                print(f"[{done}/{total}] SKIP {key} (already downloaded)")
                continue

            print(f"[{done}/{total}] {key} ...")
            t0 = time.time()

            rows = fetch_klines_range(client, symbol, tf, start_ms, end_ms)
            if not rows:
                print(f"    ❌ no data")
                failed.add(key)
                continue

            quality = validate_klines(rows, tf)
            path = save_klines(rows, symbol, tf)
            elapsed = time.time() - t0

            print(f"    ✅ {quality['count']} bars | "
                  f"gap≤{quality['largest_gap_hours']}h | "
                  f"invalid={quality['invalid_ohlc']} | "
                  f"dupes={quality['duplicates']} | "
                  f"{elapsed:.1f}s")

            summaries.append({
                "symbol": symbol, "timeframe": tf,
                "bars": quality["count"],
                "first": quality["first_ts"], "last": quality["last_ts"],
                "largest_gap_hours": quality["largest_gap_hours"],
                "invalid_ohlc": quality["invalid_ohlc"],
                "duplicates": quality["duplicates"],
                "file": str(path.name),
            })

            completed.add(key)
            checkpoint["completed"] = sorted(completed)
            checkpoint["failed"] = sorted(failed)
            save_checkpoint(checkpoint)

    # Summary CSV
    if summaries:
        with open(SUMMARY_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
            writer.writeheader()
            writer.writerows(summaries)

    print("=" * 70)
    print(f"Done. {len(completed)} completed, {len(failed)} failed.")
    print(f"Data:    {DATA_DIR}")
    print(f"Summary: {SUMMARY_FILE}")
    print(f"Checkpoint: {CHECKPOINT_FILE}")
    print("=" * 70)


# ============================================================
# CLI
# ============================================================
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true", help="quick test: 3 symbols, 1h only")
    p.add_argument("--discover", action="store_true", help="auto-discover eligible symbols")
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--timeframes", nargs="+", default=None)
    p.add_argument("--years", type=int, default=None)
    return p.parse_args()


def main():
    args = parse_args()
    data_cfg = settings.get("data", {})
    disc_cfg = settings.get("market_discovery", {})

    years = args.years or data_cfg.get("target_historical_years", 5)

    # Timeframes
    if args.timeframes:
        timeframes = args.timeframes
    elif args.test:
        timeframes = ["1h"]
    else:
        timeframes = data_cfg.get("timeframes", ["1h"])

    # Symbols
    client = BinanceClient()

    if args.symbols:
        symbols = [s.replace("/", "").upper() for s in args.symbols]
    elif args.test:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    elif args.discover:
        print("Discovering symbols...")
        all_syms = get_all_spot_usdt_symbols(client)
        vols = get_24h_quote_volume(client)
        filters = disc_cfg.get("filters", {})
        symbols = filter_eligible_symbols(
            all_syms, vols,
            min_volume_usdt=filters.get("min_quote_volume_24h_usdt", 5_000_000),
            max_symbols=disc_cfg.get("maximum_symbols", 30),
        )
        print(f"Discovered {len(symbols)} eligible symbols")
    else:
        seeds = disc_cfg.get("seed_symbols", [])
        symbols = [s.replace("/", "").upper() for s in seeds]
        if not symbols:
            print("No symbols. Use --test, --discover, or --symbols")
            sys.exit(1)

    run(symbols, timeframes, years=years)


if __name__ == "__main__":
    main()
