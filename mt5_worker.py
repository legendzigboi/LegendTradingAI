import os
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:5000")

def main():
    logger.info(f"Connecting to MT5 Bridge at {BRIDGE_URL}...")
    
    # 1. Check if the bridge is alive and logged in
    try:
        resp = requests.get(f"{BRIDGE_URL}/api/account")
        if resp.status_code != 200:
            logger.error(f"Bridge not ready: {resp.text}")
            return
        logger.info(f"Connected to account: {resp.json().get('login')}")
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

    # 3. Send the trade command to the bridge
    payload = {
        "symbol": symbol,
        "volume": float(lot),
        "type": "BUY" if direction == "LONG" else "SELL",
        "sl": float(sl),
        "tp": float(tp),
        "magic": 123456,
        "comment": "Legend AI"
    }
    
    logger.info(f"Sending order via bridge: {payload}")
    try:
        resp = requests.post(f"{BRIDGE_URL}/api/trade", json=payload)
        if resp.status_code == 200:
            logger.info(f"✅ Order executed! Response: {resp.json()}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {resp.text}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
