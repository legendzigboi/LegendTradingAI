import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Groq uses the OpenAI format but has a different base URL
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
    timeout=5.0
)

def deep_research_trade(symbol, direction, confidence, sentiment, sentiment_reason):
    """
    Asks the AI to act as a master trader and approve or veto the trade.
    """
    if not os.environ.get("GROQ_API_KEY"):
        return True, "No API key. Skipping Deep Research."

    prompt = f"""
    You are an elite hedge fund trader. 
    Analyze the following trade setup and decide whether to APPROVE or VETO it.
    
    Symbol: {symbol}
    Direction: {direction}
    Math Model Confidence: {confidence*100:.1f}%
    News Sentiment: {sentiment}
    Sentiment Reasoning: {sentiment_reason}
    
    Rules:
    - If the sentiment strongly contradicts the trade direction (e.g. going LONG on very bad news), VETO it.
    - If the confidence is high and news is neutral or supportive, APPROVE it.
    
    Reply EXACTLY in this format:
    VERDICT: [APPROVE or VETO]
    REASON: [One short sentence explaining why]
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # 🚨 UPDATED TO NEW GROQ MODEL 🚨
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        
        output = response.choices[0].message.content.strip()
        
        # Parse the output
        if "VERDICT: VETO" in output.upper():
            reason = output.split("REASON:")[-1].strip()
            return False, reason
        else:
            reason = output.split("REASON:")[-1].strip() if "REASON:" in output else "Approved by AI"
            return True, reason
            
    except Exception as e:
        # 🚨 LOG THE EXACT ERROR SO WE CAN SEE IT IN RENDER 🚨
        error_msg = str(e)
        logger.error(f"Deep Researcher Error: {error_msg}")
        return True, f"AI Error: {error_msg[:50]}..."
