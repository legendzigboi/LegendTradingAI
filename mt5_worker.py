import os
import time
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:5000/api")

def map_symbol_to_mt5(symbol):
    symbol = symbol.upper()
    if symbol.endswith("=X"): return symbol.replace("=X", "")
    if symbol == "GC=F": return "XAUUSD"
    if symbol == "BTCUSDT": return "BTCUSD"
    if symbol == "ETHUSDT": return "ETHUSD"
    return symbol

def main():
    logger.info(f"Connecting to MT5 Bridge at {BRIDGE_URL}...")
    
    try:
        resp = requests.get(f"{BRIDGE_URL}/account_info", timeout=10)
        raw_account = resp.json()
        account_data = raw_account.get("data", raw_account)
        logger.info(f"✅ Connected to account: {account_data.get('login')}")
        logger.info(f"Trade Allowed: {account_data.get('trade_allowed')}")
    except Exception as e:
        logger.error(f"Failed to connect to bridge: {e}")
        return

    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        return

    trade = pending_trades[0]
    mt5_symbol = map_symbol_to_mt5(trade['symbol'])
    direction = trade['direction']
    lot = trade['lot_size']

    logger.info(f"Mapping symbol: {trade['symbol']} -> {mt5_symbol}")

    # Select symbol
    try:
        requests.get(f"{BRIDGE_URL}/symbol_select/{mt5_symbol}", timeout=5)
        time.sleep(1)
    except: pass

    # Get current price
    try:
        price_resp = requests.get(f"{BRIDGE_URL}/symbol_info_tick/{mt5_symbol}", timeout=10)
        price_data = price_resp.json().get("data", {})
        
        if direction == "LONG":
            price = price_data.get("ask")
            order_type = "BUY"
        else:
            price = price_data.get("bid")
            order_type = "SELL"

        if price is None or price == 0:
            logger.error(f"❌ Could not get price for {mt5_symbol}.")
            return
            
    except Exception as e:
        logger.error(f"Failed to get price: {e}")
        return

    # 🚨 DYNAMIC SL/TP CALCULATION 🚨
    # If the price moved, old SL/TP are invalid. We calculate fresh ones.
    sl_pct = 0.005 # 0.5% away
    tp_pct = 0.01  # 1.0% away
    
    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp = price * (1 + tp_pct)
    else:
        sl = price * (1 + sl_pct)
        tp = price * (1 - tp_pct)

    # Send the trade
    payload = {
        "symbol": mt5_symbol,
        "order_type": order_type,
        "volume": float(lot),
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "comment": "Legend AI"
    }
    
    logger.info(f"Sending order via bridge: {payload}")
    try:
        resp = requests.post(f"{BRIDGE_URL}/order/open", json=payload, timeout=10)
        result = resp.json()
        
        if result.get("code") == 200 or result.get("data", {}).get("retcode") == 10009:
            logger.info(f"✅ Order executed! Response: {result}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {result}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
