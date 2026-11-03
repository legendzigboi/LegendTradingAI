import json
import requests
import urllib.parse
from datetime import datetime, timezone
import logging
from src.live_features import fetch_klines

logger = logging.getLogger(__name__)

def generate_chart(symbol, timeframe, plan, direction):
    try:
        candles = fetch_klines(symbol, timeframe, limit=30)
        labels = [datetime.fromtimestamp(c[0]/1000, tz=timezone.utc).strftime('%H:%M') for c in candles]
        data = [[float(c[1]), float(c[2]), float(c[3]), float(c[4])] for c in candles]

        chart_config = {
            "type": "candlestick",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": f"{symbol} {timeframe}",
                    "data": data,
                    "color": {"up": "rgba(0, 200, 0, 1)", "down": "rgba(200, 0, 0, 1)"}
                }]
            },
            "options": {
                "plugins": {
                    "annotation": {
                        "annotations": {
                            "entry": {"type": "line", "mode": "horizontal", "scaleID": "y", "value": plan['entry'], "borderColor": "blue", "borderWidth": 2},
                            "sl": {"type": "line", "mode": "horizontal", "scaleID": "y", "value": plan['stop_loss'], "borderColor": "red", "borderWidth": 2},
                            "tp1": {"type": "line", "mode": "horizontal", "scaleID": "y", "value": plan['tp1'], "borderColor": "green", "borderWidth": 2}
                        }
                    }
                }
            }
        }
        
        # Increased timeout to 30 seconds for Render's network
        response = requests.post("https://quickchart.io/chart", json={"chart": chart_config}, timeout=30)
        
        if response.status_code == 200:
            with open("chart.png", "wb") as f:
                f.write(response.content)
            return "chart.png"
        else:
            logger.error(f"QuickChart HTTP Error {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
    
    return None
