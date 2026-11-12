import os
import time
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The REST API runs on port 8000
API_URL = os.environ.get("MT5_API_URL", "http://localhost:8000")

def map_symbol_to_mt5(symbol):
    symbol = symbol.upper()
    if symbol.endswith("=X"): return symbol.replace("=X", "")
    if symbol == "GC=F": return "XAUUSD"
    if symbol == "BTCUSDT": return "BTCUSD"
    if symbol == "ETHUSDT": return "ETHUSD"
    return symbol

def main():
    logger.info(f"Connecting to MT5 REST API at {API_URL}...")
    
    # 1. Check if the API is alive
    try:
        resp = requests.get(f"{API_URL}/api/account_info", timeout=10)
        if resp.status_code != 200:
            logger.error(f"API returned error: {resp.text}")
            return
        account_data = resp.json()
        logger.info(f"✅ Connected to account: {account_data.get('login')}")
        logger.info(f"Trade Allowed: {account_data.get('trade_allowed')}")
        
        if not account_data.get('trade_allowed'):
            logger.error("❌ CRITICAL: Trade Allowed is False. You must enable Algo Trading in the VNC interface.")
            return
    except Exception as e:
        logger.error(f"Failed to connect to API: {e}")
        return

    # 2. Get pending trades
    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        return

    trade = pending_trades[0]
    original_symbol = trade['symbol']
    mt5_symbol = map_symbol_to_mt5(original_symbol)
    direction = trade['direction']
    lot = trade['lot_size']

    logger.info(f"Mapping symbol: {original_symbol} -> {mt5_symbol}")

    # 3. Get current price
    try:
        tick_resp = requests.get(f"{API_URL}/api/symbol_info_tick/{mt5_symbol}", timeout=10)
        tick_data = tick_resp.json()
        
        if direction == "LONG":
            price = tick_data.get("ask")
            order_type = "BUY"
        else:
            price = tick_data.get("bid")
            order_type = "SELL"

        if price is None or price == 0:
            logger.error(f"❌ Could not get price for {mt5_symbol}. Data: {tick_data}")
            return
            
    except Exception as e:
        logger.error(f"Failed to get price: {e}")
        return

    # 4. Dynamically calculate SL/TP
    sl_pct = 0.005
    tp_pct = 0.01
    
    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp = price * (1 + tp_pct)
    else:
        sl = price * (1 + sl_pct)
        tp = price * (1 - tp_pct)

    # 5. Send the trade
    payload = {
        "symbol": mt5_symbol,
        "order_type": order_type,
        "volume": float(lot),
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "comment": "Legend AI"
    }
    
    logger.info(f"Sending order via API: {payload}")
    try:
        resp = requests.post(f"{API_URL}/api/order/open", json=payload, timeout=10)
        result = resp.json()
        
        if result.get("code") == 200 or result.get("retcode") == 10009:
            logger.info(f"✅ Order executed! Response: {result}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {result}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
