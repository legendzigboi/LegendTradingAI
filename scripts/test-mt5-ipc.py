import MetaTrader5 as mt5
import os
import sys

login = int(os.environ.get("FBS_DEMO_LOGIN", 0))
password = os.environ.get("FBS_DEMO_PASSWORD", "")
server = os.environ.get("FBS_DEMO_SERVER", "")

print("--- STARTING MT5 IPC TEST ---")
if not mt5.initialize():
    print(f"INITIALIZATION FAILED: {mt5.last_error()}")
    sys.exit(1)

print("MT5 Initialized. Logging in...")
authorized = mt5.login(login=login, password=password, server=server)
if not authorized:
    print(f"LOGIN FAILED: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

print("LOGIN SUCCESSFUL!")
print(f"Account: {mt5.account_info().login}")
print(f"Balance: {mt5.account_info().balance}")
mt5.shutdown()
