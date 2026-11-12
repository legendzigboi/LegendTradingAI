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
    logger.info("Connecting to MT5 via RPyC...")
    try:
        # Connect to the RPyC server exposed by the container
        conn = rpyc.classic.connect("localhost", 8001)
        mt5 = conn.modules.MetaTrader5
        logger.info("✅ Connected to MT5 terminal.")
    except Exception as e:
        logger.error(f"Failed to connect to MT5 RPyC: {e}")
        return

    # 1. Check account and TRADE ALLOWED status
    try:
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("❌ Could not retrieve account info. MT5 might not be logged in.")
            return
        
        logger.info(f"✅ Connected to account: {account_info.login}")
        logger.info(f"Trade Allowed: {mt5.terminal_info().trade_allowed}")
        
        if not mt5.terminal_info().trade_allowed:
            logger.error("❌ CRITICAL: Trade Allowed is False. The MT5 terminal has not enabled algorithmic trading.")
            logger.error("Please check the VNC interface to enable Algo Trading.")
            return
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
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
            return
        
        if direction == "LONG":
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL

        if price is None or price == 0:
            logger.error(f"❌ Invalid price for {mt5_symbol}.")
            return
            
    except Exception as e:
        logger.error(f"Failed to get price for {mt5_symbol}: {e}")
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

if __name__ == "__main__":
    main()
