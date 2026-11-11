import os
import time
import subprocess
import configparser
import MetaTrader5 as mt5
import logging
from src.signal_db import get_pending_mt5_trades, mark_mt5_trade_executed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MT5_LOGIN = int(os.environ.get("MT5_LOGIN", 0))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
# Path to the config file in portable mode
CONFIG_PATH = r"C:\Program Files\MetaTrader 5\Config\common.ini"

def enable_mt5_settings():
    logger.info("Force-enabling algorithmic trading in common.ini...")
    try:
        config = configparser.ConfigParser()
        # Preserve case sensitivity for keys
        config.optionxform = str
        
        if os.path.exists(CONFIG_PATH):
            config.read(CONFIG_PATH)
        
        if not config.has_section('Experts'):
            config.add_section('Experts')
        
        # 🚨 CRITICAL SETTINGS 🚨
        config.set('Experts', 'AllowLiveTrading', '1')
        config.set('Experts', 'AllowDllImport', '1')
        config.set('Experts', 'Enabled', '1')
        config.set('Experts', 'Account', str(MT5_LOGIN))
        config.set('Experts', 'Server', MT5_SERVER)
        
        with open(CONFIG_PATH, 'w') as configfile:
            config.write(configfile)
            
        logger.info("✅ Settings written to common.ini")
    except Exception as e:
        logger.error(f"Failed to edit common.ini: {e}")

def main():
    # 1. Force the settings before launch
    enable_mt5_settings()
    
    logger.info("Launching MT5 terminal in background...")
    try:
        subprocess.Popen([
            MT5_PATH,
            f"/login:{MT5_LOGIN}",
            f"/password:{MT5_PASSWORD}",
            f"/server:{MT5_SERVER}",
            "/portable"
        ])
    except Exception as e:
        logger.error(f"Failed to launch MT5: {e}")
        return

    logger.info("Waiting 25 seconds for MT5 to initialize...")
    time.sleep(25)

    logger.info("Connecting Python to MT5...")
    # Explicitly pass the path again
    if not mt5.initialize(path=MT5_PATH):
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return

    logger.info("Connected to MT5!")
    
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Connected but not logged in. Check credentials.")
        mt5.shutdown()
        return
    logger.info(f"Logged in as: {account_info.login} on {account_info.server}")

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
