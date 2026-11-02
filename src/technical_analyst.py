def get_technical_overview(feats, direction, timeframe="15m"):
    """Translates raw model features into human-readable bullet points."""
    rsi = feats[12]      # rsi_14
    macd = feats[16]     # macd_hist
    sma_ratio = feats[7] # sma_ratio_20
    vol_ratio = feats[22] # volume_ratio_20

    # RSI
    if rsi > 70: rsi_text = f"{rsi:.1f} (Overbought)"
    elif rsi < 30: rsi_text = f"{rsi:.1f} (Oversold)"
    else: rsi_text = f"{rsi:.1f} (Neutral)"

    # MACD
    macd_text = "Bullish momentum" if macd > 0 else "Bearish momentum"

    # Trend
    trend_text = "Uptrend" if sma_ratio > 0 else "Downtrend"

    # Volume (Handle Forex 0 volume honestly)
    if vol_ratio == 0:
        vol_text = "N/A (Forex data unavailable)"
    else:
        vol_text = "Above average" if vol_ratio > 1.2 else ("Below average" if vol_ratio < 0.8 else "Normal")

    # 1m Warning
    warning = ""
    if timeframe == "1m":
        warning = "⚠️ WARNING: 1m timeframe is highly noisy.\n\n"

    return (
        f"{warning}"
        f"📊 TECHNICAL OVERVIEW\n"
        f"• RSI: {rsi_text}\n"
        f"• MACD: {macd_text}\n"
        f"• EMA Trend: {trend_text}\n"
        f"• Volume: {vol_text}\n"
        f"• Sentiment: {'Bullish' if direction == 'LONG' else 'Bearish'}"
    )
