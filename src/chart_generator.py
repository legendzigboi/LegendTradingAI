import pandas as pd
import mplfinance as mpf
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_chart(symbol, timeframe, plan, direction):
    try:
        from src.live_features import fetch_klines
        
        # Fetch last 50 candles for a clean chart
        candles = fetch_klines(symbol, timeframe, 50)
        if not candles or len(candles) < 10:
            return None

        # Convert to pandas DataFrame for mplfinance
        df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'ignore1', 'ignore2', 'ignore3', 'ignore4', 'ignore5'])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        df.set_index('time', inplace=True)

        # Define our custom style (Binance-like dark mode)
        mc = mpf.make_marketcolors(up='#0ECB81', down='#F6465D', edge='inherit', wick='inherit', volume='in')
        s  = mpf.make_mpf_style(marketcolors=mc, gridstyle='', y_on_right=True, facecolor='#1E2329')

        # Draw horizontal lines for Entry, SL, and TP
        hlines_dict = dict(hlines=[plan['entry'], plan['stop_loss'], plan['tp1']], 
                           colors=['#FCD535', '#F6465D', '#0ECB81'], 
                           linewidths=[1.5, 1.5, 1.5], 
                           linestyle='--')

        chart_file = f"chart_{symbol}_{timeframe}.png"
        
        # Generate and save the chart
        mpf.plot(df, type='candle', style=s, volume=True, 
                 title=f"\n{symbol} - {timeframe}", 
                 hlines=hlines_dict, 
                 savefig=dict(fname=chart_file, dpi=100, bbox_inches='tight'),
                 figsize=(10, 6))

        return chart_file
    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        return None
