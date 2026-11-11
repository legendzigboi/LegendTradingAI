import requests
import logging
from src.live_features import fetch_klines

logger = logging.getLogger(__name__)

def get_live_price(symbol):
    """
    Fetches the absolute latest price. 
    For Crypto: Binance. For Forex/Stocks: Yahoo Finance.
    """
    try:
        # Fetch just 1 candle to get the latest close
        candles = fetch_klines(symbol, interval="1m", limit=1)
        if candles and len(candles) > 0:
            # Binance format vs Yahoo format
            if isinstance(candles[0], dict): # Yahoo
                return float(candles[0]['close'])
            else: # Binance list
                return float(candles[0][4])
    except Exception as e:
        logger.error(f"Live price fetch error: {e}")
    return None

def adjust_plan_to_live_price(symbol, plan):
    """
    Adjusts the Entry, SL, and TP based on the live price.
    """
    live_price = get_live_price(symbol)
    if not live_price:
        return plan, False

    bot_entry = plan["entry"]
    
    # If the live price is more than 0.1% away from the bot's entry, adjust the plan
    if abs(live_price - bot_entry) / bot_entry > 0.001:
        difference = live_price - bot_entry
        
        plan["entry"] = live_price
        plan["stop_loss"] += difference
        plan["tp1"] += difference
        plan["tp2"] += difference
        plan["tp3"] += difference
        
        logger.info(f"Slippage Sync: Adjusted plan for {symbol} by {difference:.5f}")
        return plan, True
        
    return plan, False
