import os
import time
import rpyc
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def map_symbol_to_mt5(symbol):
    symbol = symbol.upper()
    if symbol.endswith("=X"): return symbol.replace("=X", "")
    if symbol == "GC=F": return "XAUUSD"
    if symbol == "BTCUSDT": return "BTCUSD"
    if symbol == "ETHUSDT": return "ETHUSD"
    return symbol

def main():
    logger.info("Connecting to MT5 via raw RPyC...")
    
    conn = None
    for attempt in range(30): # Wait up to 5 minutes
        try:
            # 🚨 THE FIX: Connect directly to the existing container on 8001 🚨
            conn = rpyc.classic.connect("localhost", 8001)
            logger.info("✅ RPyC connection established.")
            break
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/30: Connection failed ({e}). Retrying in 10s...")
            time.sleep(10)
            
    if conn is None:
        logger.error("❌ CRITICAL: Could not connect to RPyC server on port 8001.")
        return

    # Get the MetaTrader5 module from the remote connection
    mt5 = conn.modules.MetaTrader5

    # 1. Initialize and check account
    try:
        if not mt5.initialize():
            logger.error(f"❌ mt5.initialize() failed on remote server: {mt5.last_error()}")
            return

        account_info = mt5.account_info()
        if account_info is None:
            logger.error("❌ Could not retrieve account info. MT5 might not be logged in.")
            return
        
        logger.info(f"✅ Connected to account: {account_info.login}")
        
        terminal_info = mt5.terminal_info()
        logger.info(f"Trade Allowed: {terminal_info.trade_allowed}")
        
        if not terminal_info.trade_allowed:
            logger.error("❌ CRITICAL: Trade Allowed is False. You must enable Algo Trading in the VNC interface.")
            return
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return

    # 2. Get pending trades
    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        conn.close()
        return

    trade = pending_trades[0]
    original_symbol = trade['symbol']
    mt5_symbol = map_symbol_to_mt5(original_symbol)
    direction = trade['direction']
    lot = trade['lot_size']

    logger.info(f"Mapping symbol: {original_symbol} -> {mt5_symbol}")

    # 3. Select the symbol
    logger.info(f"Selecting symbol {mt5_symbol}...")
    try:
        mt5.symbol_select(mt5_symbol, True)
        time.sleep(2)
    except Exception as e:
        logger.warning(f"Symbol selection warning: {e}")

    # 4. Get current price
    try:
        tick = mt5.symbol_info_tick(mt5_symbol)
        if tick is None:
            logger.error(f"❌ Could not get price for {mt5_symbol}.")
            conn.close()
            return
        
        if direction == "LONG":
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL

        if price is None or price == 0:
            logger.error(f"❌ Invalid price for {mt5_symbol}.")
            conn.close()
            return
            
    except Exception as e:
        logger.error(f"Failed to get price for {mt5_symbol}: {e}")
        conn.close()
        return

    # 5. Dynamically calculate SL/TP
    sl_pct = 0.005
    tp_pct = 0.01
    
    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp = price * (1 + tp_pct)
    else:
        sl = price * (1 + sl_pct)
        tp = price * (1 - tp_pct)

    # 6. Send the trade
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": mt5_symbol,
        "volume": float(lot),
        "type": order_type,
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 123456,
        "comment": "Legend AI",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    logger.info(f"Sending order: {request}")
    try:
        result = mt5.order_send(request)
        
        if result.retcode == 10009:
            logger.info(f"✅ Order executed! Ticket: {result.order}")
            mark_mt5_trade_executed(trade['id'])
        else:
            logger.error(f"Order failed: {result.comment}")
    except Exception as e:
        logger.error(f"Error sending order: {e}")
    finally:
        mt5.shutdown()
        conn.close()

if __name__ == "__main__":
    main()
