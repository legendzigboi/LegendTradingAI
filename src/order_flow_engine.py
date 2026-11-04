import requests
import logging

logger = logging.getLogger(__name__)

def get_order_flow_imbalance(symbol):
    """
    Fetches the top 50 bids and asks from Binance to detect whale walls.
    Returns: (imbalance_score, description)
    Score > 1.0 means Buy pressure. Score < 1.0 means Sell pressure.
    """
    if "USDT" not in symbol:
        return 1.0, "Forex/Stocks (N/A)" # Only works for Crypto

    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=50"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            
            bid_volume = sum(float(bid[1]) for bid in data['bids'])
            ask_volume = sum(float(ask[1]) for ask in data['asks'])
            
            if ask_volume == 0: return 1.0, "N/A"
            
            ratio = bid_volume / ask_volume
            
            if ratio > 1.5:
                return ratio, f"🟢 Strong Buy Pressure (Ratio: {ratio:.2f})"
            elif ratio < 0.6:
                return ratio, f"🔴 Strong Sell Pressure (Ratio: {ratio:.2f})"
            else:
                return ratio, f"⚪ Neutral (Ratio: {ratio:.2f})"
    except Exception as e:
        logger.error(f"Order Flow Error: {e}")
    
    return 1.0, "Data Unavailable"

def calculate_vwap_zscore(candles):
    """
    Calculates if the price is overextended from the VWAP.
    Returns a score from -3 to +3. 
    > 2 means overbought. < -2 means oversold.
    """
    try:
        if len(candles) < 20: return 0.0
        
        # Calculate VWAP
        typical_prices = [(float(c[2]) + float(c[3]) + float(c[4])) / 3 for c in candles]
        volumes = [float(c[5]) for c in candles]
        
        vwap = sum(tp * v for tp, v in zip(typical_prices, volumes)) / sum(volumes)
        current_price = float(candles[-1][4])
        
        # Calculate standard deviation of price
        import numpy as np
        std_dev = np.std([float(c[4]) for c in candles])
        
        z_score = (current_price - vwap) / std_dev if std_dev > 0 else 0
        return z_score
    except Exception:
        return 0.0
