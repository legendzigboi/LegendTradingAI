import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
    timeout=5.0
)

def deep_research_trade(symbol, direction, confidence, sentiment, sentiment_reason):
    if not os.environ.get("GROQ_API_KEY"):
        return True, "No API key."

    prompt = f"""
    You are an elite hedge fund trader. 
    Analyze this trade: {symbol} {direction} (Confidence: {confidence*100:.1f}%). News Sentiment: {sentiment}.
    Reply EXACTLY in this format with NO OTHER TEXT:
    VERDICT: [APPROVE or VETO]
    REASON: [One short sentence explaining why]
    """

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=60
        )
        
        output = response.choices[0].message.content.strip()
        
        if "VERDICT: VETO" in output.upper():
            reason = output.split("REASON:")[-1].strip() if "REASON:" in output else "Risk detected by AI."
            return False, reason
        else:
            reason = output.split("REASON:")[-1].strip() if "REASON:" in output else "Strong setup confirmed by AI."
            return True, reason
            
    except Exception as e:
        return True, "AI Timeout."
