import requests
import logging

logger = logging.getLogger(__name__)

def get_crypto_fear_greed():
    """
    Fetches the Crypto Fear & Greed Index from alternative.me.
    Returns: (score, classification)
    """
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        if r.status_code == 200:
            data = r.json()
            score = int(data["data"][0]["value"])
            classification = data["data"][0]["value_classification"]
            return score, classification
    except Exception as e:
        logger.error(f"Fear & Greed Error: {e}")
    
    return None, "Unknown"
