import os
import time
import MetaTrader5 as mt5
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MT5_LOGIN = int(os.environ.get("MT5_LOGIN", 0))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
# Use forward slashes for the path
MT5_PATH = "C:/Program Files/MetaTrader 5/terminal64.exe"

def main():
    logger.info("Initializing MT5...")
    # 1. Initialize (this will start the terminal if it's not running)
    if not mt5.initialize(path=MT5_PATH):
        logger.error(f"initialize() failed, error code = {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info("Connected to MT5 terminal. Logging in...")
    
    # 2. Explicitly login
    authorized = mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        logger.error(f"Login failed, error code = {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info(f"Logged in successfully as: {mt5.account_info().login}")

    # --- Trade Execution Logic ---
    positions = mt5.positions_get()
    if positions and len(positions) > 0:
        logger.info(f"Skipping: {len(positions)} trade(s) currently open on MT5.")
        mt5.shutdown()
        return

    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        mt5.shutdown()
        return

    trade = pending_trades[0]
    symbol = trade['symbol']
    direction = trade['direction']
    lot = trade['lot_size']
    sl = trade['stop_loss']
    tp = trade['take_profit']

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"Symbol {symbol} not found on FBS.")
        mt5.shutdown()
        return

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logger.error(f"Failed to select {symbol}.")
            mt5.shutdown()
            return

    order_type = mt5.ORDER_TYPE_BUY if direction == "LONG" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if direction == "LONG" else mt5.symbol_info_tick(symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 123456,
        "comment": "Legend AI",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info(f"Sending order: {request}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order failed: {result.comment}")
    else:
        logger.info(f"✅ Order executed! Ticket: {result.order}")
        mark_mt5_trade_executed(trade['id'])

    mt5.shutdown()

if __name__ == "__main__":
    main()
