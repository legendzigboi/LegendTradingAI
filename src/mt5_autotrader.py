import asyncio
import logging
from datetime import datetime
import src.state as state
from src.auto_trader import CRYPTO, FOREX_STOCKS, TIMEFRAMES
from src.engines.fusion_engine import FusionEngine
from src.engines.base_engine import TrendEngine
from src.signal_db import log_signal, queue_mt5_trade
from src.kelly_engine import calculate_kelly_position_size

logger = logging.getLogger(__name__)

async def mt5_auto_trade_loop(bot, chat_id):
    logger.info("🚀 MT5 Auto-Trader Loop Started.")
    await bot.send_message(chat_id=chat_id, text="🚀 **MT5 AUTO-TRADER ACTIVATED**\n\nI will now scan all markets. When I find a 65%+ setup, I will queue it for MT5 execution. I will wait 15 minutes between scans so I don't spam the broker.")
    
    all_symbols = CRYPTO + FOREX_STOCKS
    
    while state.MT5_AUTO_TRADE_ACTIVE:
        try:
            best_setup = None
            highest_conf = 0.0
            
            # Quick scan of all markets (no delays to keep it fast)
            for symbol in all_symbols:
                for tf in TIMEFRAMES:
                    if not state.MT5_AUTO_TRADE_ACTIVE: break
                    
                    try:
                        if tf == "FUSION":
                            engine = FusionEngine()
                            res = await asyncio.to_thread(engine.analyze, symbol)
                        else:
                            engine = TrendEngine()
                            res = await asyncio.to_thread(engine.analyze, symbol, tf)
                            
                        if "error" not in res and res.get("status") == "SUCCESS":
                            if res["confidence"] >= 0.65 and res["confidence"] > highest_conf:
                                highest_conf = res["confidence"]
                                best_setup = res
                    except: pass
                    
                    await asyncio.sleep(1.5) # Rate limit protection
            
            if best_setup:
                symbol = best_setup["symbol"]
                direction = best_setup["direction"]
                plan = best_setup["plan"]
                display_tf = best_setup["timeframe"]
                
                # Get Kelly Size
                sizing_text, suggested_lot = await calculate_kelly_position_size(symbol, display_tf, plan['entry'], plan['stop_loss'], plan['tp1'])
                
                # Queue for MT5
                sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=best_setup["engine"], confidence=float(highest_conf), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=0, tp3=0)
                queue_mt5_trade(symbol=symbol, direction=direction, lot_size=suggested_lot, sl=plan["stop_loss"], tp=plan["tp1"])
                
                msg = (
                    f"🚀 **MT5 AUTO-TRADE QUEUED**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{'🟢 BUY ▲' if direction == 'LONG' else '🔴 SELL ▼'}\n"
                    f"{symbol} · {display_tf}\n"
                    f"Confidence: {highest_conf*100:.1f}%\n\n"
                    f"🎯 TRADE PLAN\n"
                    f"Entry: <code>{plan['entry']}</code>\n"
                    f"SL: <code>{plan['stop_loss']}</code>\n"
                    f"TP: <code>{plan['tp1']}</code>\n\n"
                    f"Lot Size: <code>{suggested_lot}</code>\n"
                    f"*(GitHub Actions will execute this within 15 minutes)*"
                )
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=chat_id, text="⚪ **MT5 SCAN COMPLETE**\n\nNo setups above 65% confidence found. Waiting 15 minutes before next scan.")
                
        except Exception as e:
            logger.error(f"MT5 Auto Loop Error: {e}")
            
        # Wait 15 minutes before the next scan
        for _ in range(15):
            if not state.MT5_AUTO_TRADE_ACTIVE: break
            await asyncio.sleep(60)

    logger.info("🛑 MT5 Auto-Trader Loop Stopped.")
    await bot.send_message(chat_id=chat_id, text="🛑 **MT5 AUTO-TRADER DEACTIVATED**\n\nI have stopped scanning for MT5 trades.")
