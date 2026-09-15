# Network Notes — LegendTradingAI

## Nigeria ISP Blocking

Nigerian ISPs (MTN/Airtel/Glo) DNS-block many crypto exchange domains:

- api.binance.com ❌
- api.kraken.com ❌
- api.bybit.com ❌
- api.coinbase.com ❌

**But `data-api.binance.vision` works when DNS resolves properly.**

## Solution: Cloudflare WARP

The "1.1.1.1" app by Cloudflare bypasses the DNS block.

### Setup (phone):
1. Install "1.1.1.1" from Play Store
2. Toggle WARP ON
3. Verify: `curl -I https://data-api.binance.vision/api/v3/ping`
4. Expected: HTTP/2 200

### Important:
- WARP must be ON when running the fetcher from a Nigerian network
- Cloud VMs (later) won't need WARP
- Keep WARP in the app's notification tray

## Data Sources (priority order)

1. **Binance** — `data-api.binance.vision` (primary)
2. **Kraken** — `api.kraken.com` (fallback)
3. **Bybit** — `api.bybit.com` (fallback)
4. **Coinbase** — `api.coinbase.com` (fallback)

Design the fetcher to try in order — if #1 fails, try #2, etc.

## Verified Working

- 2026-09-15 — Binance data fetched successfully via WARP
- Sample: BTC/USDT 1h candles, real live prices
