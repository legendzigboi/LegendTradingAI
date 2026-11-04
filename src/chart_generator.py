import logging
import os

logger = logging.getLogger(__name__)

def generate_chart(symbol, timeframe, plan, direction):
    """
    Since Render Free Tier cannot build heavy matplotlib libraries, 
    we gracefully fall back to the static buy.png / sell.png images.
    """
    logger.info(f"Skipping heavy dynamic chart for {symbol}. Using static image fallback.")
    return None
