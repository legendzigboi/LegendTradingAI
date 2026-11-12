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
    
    # 1. Verify account and TRADE ALLOWED status
    try:
        resp = requests.get(f"{BRIDGE_URL}/account_info", timeout=10)
        raw_account = resp.json()
        account_data = raw_account.get("data", raw_account)
        trade_allowed = account_data.get("trade_allowed")
        logger.info(f"✅ Connected to account: {account_data.get('login')}")
        logger.info(f"Trade Allowed: {trade_allowed}")
        
        if not trade_allowed:
            logger.error("❌ CRITICAL: Trade Allowed is False. The MT5 terminal has not enabled algorithmic trading.")
            logger.error("Please check the Docker logs for the 'RestGateway EA' initialization.")
            return
    except Exception as e:
        logger.error(f"Failed to connect to bridge: {e}")
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

    # 3. 🚨 EXPLICITLY SELECT THE SYMBOL 🚨
    logger.info(f"Selecting symbol {mt5_symbol} in Market Watch...")
    try:
        # The bridge accepts a JSON payload to select a symbol
        sel_resp = requests.post(f"{BRIDGE_URL}/symbol_select", json={"symbol": mt5_symbol}, timeout=10)
        logger.info(f"Symbol select response: {sel_resp.text}")
        time.sleep(2) # Wait for MT5 to load the symbol
    except Exception as e:
        logger.warning(f"Symbol selection warning: {e}")

    # 4. Get current price
    try:
        price_resp = requests.get(f"{BRIDGE_URL}/symbol_info_tick/{mt5_symbol}", timeout=10)
        raw_tick = price_resp.json()
        logger.info(f"Raw Tick Data: {raw_tick}")
        
        price_data = raw_tick.get("data", raw_tick)
        
        if direction == "LONG":
            price = price_data.get("ask")
            order_type = "BUY"
        else:
            price = price_data.get("bid")
            order_type = "SELL"

        if price is None or price == 0:
            logger.error(f"❌ Could not get price for {mt5_symbol}. Data: {price_data}")
            return
            
    except Exception as e:
        logger.error(f"Failed to get price for {mt5_symbol}: {e}")
        return

    # 5. Dynamically calculate SL/TP (to avoid Invalid Stops error)
    sl_pct = 0.005 # 0.5% away
    tp_pct = 0.01  # 1.0% away
    
    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp = price * (1 + tp_pct)
    else:
        sl = price * (1 + sl_pct)
        tp = price * (1 - tp_pct)

    # 6. Send the trade
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
