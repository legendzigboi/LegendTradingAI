import logging
from datetime import datetime
from src.live_features import get_latest_features, fetch_klines
from src.xgb_pure import XGBPure
from src.trade_planner import build_trade_plan
from src.telegram_notify import send_message
from pathlib import Path

logger = logging.getLogger(__name__)
MODEL_DIR = Path("models/v0.2")

def format_price(price):
    if price >= 1000: return f"{price:,.2f}"
    elif price >= 1: return f"{price:.4f}"
    else: return f"{price:.6f}"

async def run_market_scan(context):
    """Scans the top markets and sends only high-confidence signals."""
    logger.info("Running Scheduled Market Scan...")
    
    # Markets to scan
    markets = [("BTCUSDT", "15m"), ("ETHUSDT", "15m"), ("XRPUSDT", "1h")]
    signals_found = 0
    
    for symbol, timeframe in markets:
        try:
            model_path = MODEL_DIR / f"v0.2_{symbol}_{timeframe}_h10_long.json"
            if not model_path.exists(): continue
            
            feats, _ = get_latest_features(symbol, timeframe)
            candles = fetch_klines(symbol, timeframe, limit=2)
            entry_price = float(candles[-2][4])
            atr_14 = feats[18]
            
            model = XGBPure(model_path)
            proba = model.predict_proba([feats])[0]
            
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            # Only alert if confidence is 70% or higher
            if confidence >= 0.70:
                plan = build_trade_plan(entry_price, direction, atr_14)
                msg = (
                    f"🚨 SCHEDULED HIGH-CONFIDENCE SIGNAL 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Pair: {symbol} [{timeframe}]\n"
                    f"Direction: {direction}\n"
                    f"Confidence: {confidence*100:.1f}%\n\n"
                    f"Entry: ${format_price(plan['entry'])}\n"
                    f"SL: ${format_price(plan['stop_loss'])}\n"
                    f"TP1: ${format_price(plan['tp1'])}\n"
                )
                send_message(msg)
                signals_found += 1
        except Exception as e:
            logger.error(f"Scan error on {symbol}: {e}")
            
    if signals_found == 0:
        send_message("⚪ Scheduled Scan: No qualified setups at 70%+ confidence right now.")
