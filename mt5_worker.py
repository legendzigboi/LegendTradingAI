import os
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:5000")

def main():
    logger.info(f"Connecting to MT5 Bridge at {BRIDGE_URL}...")
    
    # 1. Check if the bridge is alive and logged in (using the correct endpoint)
    try:
        resp = requests.get(f"{BRIDGE_URL}/account_info", timeout=10)
        if resp.status_code != 200:
            logger.error(f"Bridge returned error: {resp.text}")
            return
        account_data = resp.json()
        logger.info(f"✅ Connected to account: {account_data.get('login')}")
    except Exception as e:
        logger.error(f"Failed to connect to bridge: {e}")
        return

    # 2. Get pending trades from your database
    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        return

    trade = pending_trades[0]
    symbol = trade['symbol']
    direction = trade['direction']
    lot = trade['lot_size']
    sl = trade['stop_loss']
    tp = trade['take_profit']

    # Get current price for the order (required by order_send)
    try:
        price_resp = requests.get(f"{BRIDGE_URL}/symbol_info_tick?symbol={symbol}", timeout=10)
        price_data = price_resp.json()
        if direction == "LONG":
            price = price_data.get("ask")
            order_type = "ORDER_TYPE_BUY"
        else:
            price = price_data.get("bid")
            order_type = "ORDER_TYPE_SELL"
    except Exception as e:
        logger.error(f"Failed to get price for {symbol}: {e}")
        return

    # 3. Send the trade command (using the correct endpoint and MT5 payload format)
    payload = {
        "action": "TRADE_ACTION_DEAL",
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 123456,
        "comment": "Legend AI",
        "type_time": "ORDER_TIME_GTC",
        "type_filling": "ORDER_FILLING_IOC",
    }
    
    logger.info(f"Sending order via bridge: {payload}")
    try:
        resp = requests.post(f"{BRIDGE_URL}/order_send", json=payload, timeout=10)
        result = resp.json()
        
        # Check the return code (10009 means successful in MT5)
        if result.get("retcode") == 10009:
            logger.info(f"✅ Order executed! Ticket: {result.get('order')}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {result}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
