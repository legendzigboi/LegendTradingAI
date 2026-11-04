import os
import logging
from openai import OpenAI
from src.signal_db import save_insight

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
    timeout=8.0
)

def analyze_losing_trade(trade):
    """
    Triggers an LLM autopsy when a trade hits a Stop Loss.
    """
    if not os.environ.get("GROQ_API_KEY"):
        return

    prompt = f"""
    You are an elite risk manager. Analyze this LOSING trade and provide a 1-sentence insight on why it failed and what to avoid next time.
    
    Symbol: {trade['symbol']}
    Timeframe: {trade['timeframe']}
    Direction: {trade['direction']}
    Entry: {trade['entry_price']}
    Stop Loss: {trade['stop_loss']}
    Take Profit: {trade['tp1']}
    Return: {trade['actual_return']*100:.2f}%
    
    Was it a fake breakout? A news spike? Choppy market? Provide the insight.
    """

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=60
        )
        insight = response.choices[0].message.content.strip()
        
        # Save to AI Memory (Research Lab)
        save_insight(
            category="AUTO_AUTOPSY",
            insight=f"[{trade['symbol']} {trade['timeframe']}] {insight}",
            win_rate=0.0,
            sample_size=1
        )
        return insight
    except Exception as e:
        logger.error(f"Critic Engine Error: {e}")
        return None
