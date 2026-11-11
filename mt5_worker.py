import os
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:5000/api")

def get_account_info():
    """Tries multiple endpoints to get account info."""
    for endpoint in ["/account", "/account_info"]:
        try:
            resp = requests.get(f"{BRIDGE_URL}{endpoint}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Handle both direct data and nested "data" key
                account = data.get("data", data)
                if account.get("login"):
                    return account
        except Exception:
            pass
    return None

def get_symbol_price(symbol):
    """Tries multiple endpoints to get the current tick price."""
    endpoints = [
        f"/tick/{symbol}",
        f"/symbol_info_tick/{symbol}",
        f"/symbol_info_tick?symbol={symbol}"
    ]
    for endpoint in endpoints:
        try:
            resp = requests.get(f"{BRIDGE_URL}{endpoint}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                tick = data.get("data", data)
                if tick.get("bid") is not None and tick.get("ask") is not None:
                    return tick
        except Exception:
            pass
    return None

def main():
    logger.info(f"Connecting to MT5 Bridge at {BRIDGE_URL}...")
    
    # 1. Check account
    account = get_account_info()
    if not account:
        logger.error("❌ Could not retrieve account info. Bridge might not be logged in.")
        return
    logger.info(f"✅ Connected to account: {account.get('login')}")

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

    # 3. Get current price
    tick = get_symbol_price(symbol)
    if not tick:
        logger.error(f"❌ Could not get price for {symbol}. The symbol might not be available on this broker.")
        return

    if direction == "LONG":
        price = tick.get("ask")
        order_type = "ORDER_TYPE_BUY"
    else:
        price = tick.get("bid")
        order_type = "ORDER_TYPE_SELL"

    if price is None:
        logger.error(f"❌ Price is None for {symbol} (direction: {direction}). Tick data: {tick}")
        return

    # 4. Send the trade command
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
        # Try the documented order endpoint
        resp = requests.post(f"{BRIDGE_URL}/order", json=payload, timeout=10)
        result = resp.json()
        
        # Check return code (10009 is success)
        if result.get("retcode") == 10009 or result.get("data", {}).get("retcode") == 10009:
            logger.info(f"✅ Order executed! Response: {result}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {result}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
