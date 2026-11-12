import os
import requests
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The bridge uses the /api prefix as per documentation
BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:5000/api")

def map_symbol_to_mt5(symbol):
    """Maps the bot's symbol to the MT5 broker's symbol (FBS)."""
    symbol = symbol.upper()
    if symbol.endswith("=X"):
        return symbol.replace("=X", "")
    if symbol == "GC=F":
        return "XAUUSD"
    if symbol == "BTCUSDT":
        return "BTCUSD"
    if symbol == "ETHUSDT":
        return "ETHUSD"
    return symbol

def main():
    logger.info(f"Connecting to MT5 Bridge at {BRIDGE_URL}...")
    
    # 1. Get account info (Official endpoint: /api/account_info)
    try:
        resp = requests.get(f"{BRIDGE_URL}/account_info", timeout=10)
        if resp.status_code != 200:
            logger.error(f"Bridge returned error: {resp.text}")
            return
        account_data = resp.json().get("data", {})
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
    original_symbol = trade['symbol']
    mt5_symbol = map_symbol_to_mt5(original_symbol)
    direction = trade['direction']
    lot = trade['lot_size']
    sl = trade['stop_loss']
    tp = trade['take_profit']

    logger.info(f"Mapping symbol: {original_symbol} -> {mt5_symbol}")

    # 3. Get current price (Official endpoint: /api/symbol_info_tick/<symbol>)
    try:
        price_resp = requests.get(f"{BRIDGE_URL}/symbol_info_tick/{mt5_symbol}", timeout=10)
        if price_resp.status_code != 200:
            logger.error(f"Failed to get tick: {price_resp.text}")
            return
        
        price_data = price_resp.json().get("data", {})
        
        if direction == "LONG":
            price = price_data.get("ask")
            order_type = "ORDER_TYPE_BUY"
        else:
            price = price_data.get("bid")
            order_type = "ORDER_TYPE_SELL"

        if price is None:
            logger.error(f"❌ Could not get price for {mt5_symbol}. Tick data: {price_data}")
            return
            
    except Exception as e:
        logger.error(f"Failed to get price for {mt5_symbol}: {e}")
        return

    # 4. Send the trade (Official endpoint: /api/order_send)
    # This uses the raw MqlTradeRequest structure as documented
    payload = {
        "action": "TRADE_ACTION_DEAL",
        "symbol": mt5_symbol,
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
        
        # The response structure is {"code": 200, "data": {...}}
        # The actual MT5 retcode is inside the data
        mt5_retcode = result.get("data", {}).get("retcode")
        
        if mt5_retcode == 10009:  # 10009 = TRADE_RETCODE_DONE
            logger.info(f"✅ Order executed! Response: {result}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed. MT5 Retcode: {mt5_retcode}. Response: {result}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")

if __name__ == "__main__":
    main()
