import asyncio
import logging
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from src.config import env
from src.engines.fusion_engine import FusionEngine
from src.engines.base_engine import TrendEngine
from src.signal_db import log_signal
from src.trade_planner import build_trade_plan

logger = logging.getLogger(__name__)

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
FOREX_STOCKS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "GC=F", "AAPL", "TSLA", "NVDA", "AMZN", "NDX"]
ALL_SYMBOLS = CRYPTO + FOREX_STOCKS
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "FUSION"]

async def run_auto_trader(context: ContextTypes.DEFAULT_TYPE):
    end_time = datetime.now() + timedelta(days=3)
    chat_id = int(env.get("TELEGRAM_CHAT_ID") or 0)
    bot = context.bot
    
    logger.info("🚀 AUTO-TRADER STARTED for 3 days...")
    try:
        await bot.send_message(chat_id=chat_id, text="🤖 **AUTO-TRADER ACTIVATED**\n\nI am now scanning ALL markets across ALL timeframes (1m to 1d + Fusion). This will take about 45-60 minutes per cycle. I will only message you if I find a 65%+ setup. See you in 3 days! 📊")
    except Exception as e:
        logger.error(f"Failed to send start message: {e}")

    while datetime.now() < end_time:
        try:
            logger.info("🔍 Auto-Scanner running new cycle...")
            for symbol in ALL_SYMBOLS:
                for tf in TIMEFRAMES:
                    try:
                        if tf == "FUSION":
                            engine = FusionEngine()
                            res = await asyncio.to_thread(engine.analyze, symbol)
                        else:
                            engine = TrendEngine()
                            res = await asyncio.to_thread(engine.analyze, symbol, tf)
                            
                        if "error" in res or res.get("status") == "NO_TRADE":
                            await asyncio.sleep(5)
                            continue
                            
                        direction = res["direction"]
                        confidence = res["confidence"]
                        plan = res["plan"]
                        display_tf = res["timeframe"]
                        model_name = res["engine"]
                        
                        if confidence >= 0.65:
                            sig_id = log_signal(
                                symbol=symbol, timeframe=display_tf, direction=direction, 
                                model_version=model_name, confidence=float(confidence), 
                                entry_price=plan["entry"], stop_loss=plan["stop_loss"], 
                                tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0)
                            )
                            
                            msg = (
                                f"🤖 **AUTO-SCANNER ALERT**\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"{'🟢 BUY ▲' if direction == 'LONG' else '🔴 SELL ▼'}\n"
                                f"{symbol} · {display_tf}\n"
                                f"Engine: {model_name}\n\n"
                                f"📊 CONFIDENCE: {confidence*100:.1f}%\n"
                                f"⏱ EXPIRY: {plan['duration_min']} minutes\n\n"
                                f"🎯 TRADE PLAN\n"
                                f"Entry: <code>{plan['entry']}</code>\n"
                                f"SL: <code>{plan['stop_loss']}</code>\n"
                                f"Target: <code>{plan['tp1']}</code>\n\n"
                                f"ID: {sig_id}"
                            )
                            await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
                            
                    except Exception as e:
                        logger.error(f"Auto-trader error on {symbol} {tf}: {e}")
                    
                    await asyncio.sleep(5)
                    
            logger.info("Auto-Scanner cycle complete. Sleeping for 1 hour...")
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"CRITICAL Auto-Trader Error: {e}")
            await asyncio.sleep(60)
            
    try:
        await bot.send_message(chat_id=chat_id, text="🛑 **AUTO-TRADER FINISHED**\n\nThe 3-day data gathering period is over. Please check the PERFORMANCE tab to review the results!")
    except Exception as e:
        logger.error(f"Failed to send end message: {e}")
