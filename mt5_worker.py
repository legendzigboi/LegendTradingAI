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
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

def map_symbol_to_mt5(symbol):
    symbol = symbol.upper()
    if symbol.endswith("=X"): return symbol.replace("=X", "")
    if symbol == "GC=F": return "XAUUSD"
    if symbol == "BTCUSDT": return "BTCUSD"
    if symbol == "ETHUSDT": return "ETHUSD"
    return symbol

def main():
    logger.info("Initializing MT5 with login credentials...")
    
    # 🚨 Initialize with login details and a 2-minute timeout 🚨
    if not mt5.initialize(
        path=MT5_PATH, 
        login=MT5_LOGIN, 
        password=MT5_PASSWORD, 
        server=MT5_SERVER, 
        timeout=120000, 
        portable=True
    ):
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return

    logger.info("Connected to MT5!")
    
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Connected but not logged in.")
        mt5.shutdown()
        return
        
    logger.info(f"Logged in as: {account_info.login} on {account_info.server}")

    terminal_info = mt5.terminal_info()
    logger.info(f"Trade Allowed: {terminal_info.trade_allowed}")
    
    if not terminal_info.trade_allowed:
        logger.error("❌ CRITICAL: Trade Allowed is False. The common.ini fix didn't work.")
        mt5.shutdown()
        return

    # Get pending trades
    pending_trades = get_pending_mt5_trades()
    if not pending_trades:
        logger.info("No pending trades in the database.")
        mt5.shutdown()
        return

    trade = pending_trades[0]
    original_symbol = trade['symbol']
    mt5_symbol = map_symbol_to_mt5(original_symbol)
    direction = trade['direction']
    lot = trade['lot_size']

    logger.info(f"Mapping symbol: {original_symbol} -> {mt5_symbol}")

    mt5.symbol_select(mt5_symbol, True)
    time.sleep(2)

    tick = mt5.symbol_info_tick(mt5_symbol)
    if tick is None:
        logger.error(f"❌ Could not get price for {mt5_symbol}.")
        mt5.shutdown()
        return

    if direction == "LONG":
        price = tick.ask
        order_type = mt5.ORDER_TYPE_BUY
    else:
        price = tick.bid
        order_type = mt5.ORDER_TYPE_SELL

    if price is None or price == 0:
        logger.error(f"❌ Invalid price for {mt5_symbol}.")
        mt5.shutdown()
        return

    sl_pct = 0.005
    tp_pct = 0.01
    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp = price * (1 + tp_pct)
    else:
        sl = price * (1 + sl_pct)
        tp = price * (1 - tp_pct)

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
    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"✅ Order executed! Ticket: {result.order}")
        mark_mt5_trade_executed(trade['id'])
    else:
        logger.error(f"Order failed: {result.comment}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
