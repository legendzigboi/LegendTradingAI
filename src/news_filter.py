import requests
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

def check_high_impact_news(symbol):
    """
    Checks Forex Factory calendar for High Impact news.
    Returns (is_safe, reason)
    """
    # Determine the currency to look for (e.g., EURUSD=X -> USD/EUR)
    currency = None
    if "USD" in symbol: currency = "USD"
    elif "EUR" in symbol: currency = "EUR"
    elif "GBP" in symbol: currency = "GBP"
    elif "JPY" in symbol: currency = "JPY"
    elif "AUD" in symbol: currency = "AUD"
    elif "CAD" in symbol: currency = "CAD"
    
    # If it's Crypto (BTCUSDT), high impact USD news still matters heavily
    if "USDT" in symbol or symbol in ["BTCUSDT", "ETHUSDT"]:
        currency = "USD"

    if not currency:
        return True, ""

    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return True, "" # If API fails, don't block trading
            
        events = r.json()
        now = datetime.now(timezone.utc)
        
        for event in events:
            # Check for High Impact events for this currency
            if event.get("impact") == "High" and event.get("country") == currency:
                # Parse event time
                event_time_str = event.get("date")
                # Example format: "2023-10-06T08:30:00-04:00"
                try:
                    event_time = datetime.fromisoformat(event_time_str)
                    # Check if event is within the next 30 mins or last 15 mins
                    time_diff = (event_time - now).total_seconds() / 60.0
                    if -15 <= time_diff <= 30:
                        return False, f"High Impact {currency} News: {event.get('title')} at {event_time.strftime('%H:%M UTC')}"
                except Exception:
                    continue
                    
        return True, ""
    except Exception as e:
        logger.error(f"News filter error: {e}")
        return True, "" # Fail safe (allow trade if API is down)
