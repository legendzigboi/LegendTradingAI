import os
import sys
import time
import logging
import subprocess

# Apply patch if on Linux
if sys.platform.startswith("linux"):
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'wine-mt5-ipc-patch'))
        import patch_wine_mt5
        logging.info("✅ Applied Wine IPC Patch.")
    except ImportError:
        logging.warning("⚠️ Could not import wine patch.")

import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MT5_LOGIN = int(os.environ.get("MT5_LOGIN", 0))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

def main():
    logger.info("=== STARTING DIAGNOSTIC ===")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"MT5 Login: {MT5_LOGIN}")
    logger.info(f"MT5 Server: {MT5_SERVER}")
    
    # 🚨 1. Check if MT5 is actually running in the background 🚨
    logger.info("Checking running processes...")
    try:
        if sys.platform.startswith("linux"):
            out = subprocess.check_output(["ps", "aux"]).decode("utf-8")
            mt5_procs = [line for line in out.splitlines() if "terminal" in line.lower() or "wine" in line.lower()]
            logger.info(f"Found {len(mt5_procs)} Wine/MT5 processes:")
            for p in mt5_procs: logger.info(p)
        else:
            out = subprocess.check_output(["tasklist"]).decode("utf-8")
            mt5_procs = [line for line in out.splitlines() if "terminal" in line.lower()]
            logger.info(f"Found {len(mt5_procs)} MT5 processes:")
            for p in mt5_procs: logger.info(p)
    except Exception as e:
        logger.error(f"Failed to check processes: {e}")

    # 🚨 2. Try to initialize MT5 🚨
    logger.info("Attempting mt5.initialize()...")
    init_result = mt5.initialize(
        path=MT5_PATH, 
        login=MT5_LOGIN, 
        password=MT5_PASSWORD, 
        server=MT5_SERVER, 
        timeout=60000
    )

    if not init_result:
        logger.error(f"❌ Initialize FAILED. Error code: {mt5.last_error()}")
        sys.exit(1)

    logger.info("✅ Initialize SUCCESS!")
    logger.info(f"Terminal Info: {mt5.terminal_info()}")
    logger.info(f"Account Info: {mt5.account_info()}")
    
    mt5.shutdown()
    logger.info("=== DIAGNOSTIC COMPLETE ===")

if __name__ == "__main__":
    main()
