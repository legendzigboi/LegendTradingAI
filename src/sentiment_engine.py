import requests
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

# Free RSS feeds
FEEDS = {
    "CRYPTO": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "FOREX": "https://finance.yahoo.com/news/rssindex"
}

BULLISH_WORDS = ["surge", "rally", "bull", "gain", "soar", "jump", "high", "record", "buy", "up", "growth", "adopt", "approve"]
BEARISH_WORDS = ["crash", "drop", "bear", "loss", "plunge", "fall", "low", "sell", "down", "fear", "ban", "reject", "hack", "lawsuit"]

def get_market_sentiment(symbol):
    """
    Fetches news and calculates a sentiment score.
    Returns: "BULLISH", "BEARISH", or "NEUTRAL"
    """
    # Determine which feed to use
    feed_url = FEEDS["CRYPTO"] if "USDT" in symbol else FEEDS["FOREX"]
    
    try:
        r = requests.get(feed_url, timeout=10)
        if r.status_code != 200:
            return "NEUTRAL", "Could not fetch news."
            
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        
        bull_score = 0
        bear_score = 0
        
        # Scan the top 10 headlines
        for item in items[:10]:
            title = item.find("title").text.lower() if item.find("title") is not None else ""
            
            for word in BULLISH_WORDS:
                if word in title: bull_score += 1
            for word in BEARISH_WORDS:
                if word in title: bear_score += 1
                
        if bull_score > bear_score + 2:
            return "BULLISH", f"News is very positive (Bullish: {bull_score}, Bearish: {bear_score})"
        elif bear_score > bull_score + 2:
            return "BEARISH", f"News is very negative (Bullish: {bull_score}, Bearish: {bear_score})"
        else:
            return "NEUTRAL", f"News is mixed (Bullish: {bull_score}, Bearish: {bear_score})"
            
    except Exception as e:
        logger.error(f"Sentiment Engine Error: {e}")
        return "NEUTRAL", "Sentiment analysis failed."
