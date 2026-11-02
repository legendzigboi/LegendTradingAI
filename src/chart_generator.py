import json
import requests
from datetime import datetime, timezone
from src.live_features import fetch_klines

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
        
        # Increased timeout to 30 seconds
        response = requests.post("https://quickchart.io/chart", json={"chart": chart_config}, timeout=30)
        if response.status_code == 200:
            with open("chart.png", "wb") as f:
                f.write(response.content)
            return "chart.png"
        else:
            print(f"QuickChart HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"Chart generation error: {e}")
    return None
