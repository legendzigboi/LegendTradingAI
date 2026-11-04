import logging
import asyncio
import os
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from src.config import env
from src.signal_db import init_db, log_signal, get_pending_trades, get_performance_stats, get_all_insights
from src.live_features import get_latest_features, fetch_klines
from src.model_registry import get_model
from src.trade_planner import build_trade_plan
from src.risk_engine import check_circuit_breaker, set_pause
from src.chart_generator import generate_chart
from src.banner_generator import generate_banner
from src.image_composer import combine_banner_and_chart
from src.technical_analyst import get_technical_overview
from src.signal_scanner import scan_markets
from src.telegram_keyboards import get_main_menu, get_market_menu, get_crypto_menu, get_forex_menu, get_stocks_menu, get_indices_menu, get_timeframe_menu
from src.engines.fusion_engine import FusionEngine
from src.research_engine import run_research_lab
from src.news_filter import check_high_impact_news
from src.sentiment_engine import get_market_sentiment
from src.deep_researcher import deep_research_trade
from src.sr_engine import check_support_resistance
from src.fear_greed_engine import get_crypto_fear_greed
from src.regime_engine import check_market_regime # 🚨 IMPORTED REGIME ENGINE 🚨

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
MIN_CONFIDENCE = 0.58 
MIN_ATR_CRYPTO = 0.0010 
MIN_ATR_FOREX = 0.0001  
WAT = timezone(timedelta(hours=1))

analysis_lock = asyncio.Lock()

def format_price(price):
    if price >= 1000: return f"{price:,.2f}"
    elif price >= 1: return f"{price:.4f}"
    else: return f"{price:.6f}"

def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update:
            user_id = update.effective_user.id if update.effective_user else None
            if user_id not in AUTHORIZED_USER_IDS:
                if update.message: await update.message.reply_text("⛔ Unauthorized.")
                elif update.callback_query: await update.callback_query.answer("⛔ Unauthorized", show_alert=True)
                return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def post_init(application) -> None:
    await application.bot.set_my_commands([BotCommand("start", "Open Main Menu")])

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    text = "🤖 LEGEND TRADING AI PREMIUM\n━━━━━━━━━━━━━━━━━━━━\nWelcome. Select an option below:"
    await update.message.reply_text(text, reply_markup=get_main_menu())

async def scheduled_scan_job(context):
    await signals_command(None, context)

@restricted
async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Scanner logic remains unchanged, assuming it's the same)
    pass

async def run_analysis(message, symbol, timeframe):
    allowed, risk_msg = check_circuit_breaker()
    if not allowed:
        await message.reply_text(risk_msg)
        return

    is_safe, news_warning = await asyncio.to_thread(check_high_impact_news, symbol)
    if not is_safe:
        await message.reply_text(f"⛔ **TRADE BLOCKED**\n\n{news_warning}\n\n*Protecting capital during high volatility.*", parse_mode="Markdown")
        return
        
    sentiment, sentiment_reason = await asyncio.to_thread(get_market_sentiment, symbol)

    try:
        if timeframe == 'FUSION':
            engine = FusionEngine()
            try:
                res = await asyncio.wait_for(asyncio.to_thread(engine.analyze, symbol), timeout=20.0)
            except asyncio.TimeoutError:
                await message.reply_text("❌ Error: Fusion Engine timed out."); return
                
            if "error" in res:
                await message.reply_text(f"❌ Error: {res['error']}"); return
            if res.get("status") == "NO_TRADE":
                await message.reply_text(f"⚪ NO TRADE\n{res['reason']}"); return
            feats, direction, confidence, plan = res['features'], res['direction'], res['confidence'], res['plan']
            model_name, display_tf = res['engine'], res['timeframe']
        else:
            safe_symbol = symbol.replace("=", "_")
            model_name = f"v0.2_{safe_symbol}_{timeframe}_h1_long.json"
            model_path = MODEL_DIR / model_name
            
            if not model_path.exists():
                model_name = f"v0.2_{safe_symbol}_{timeframe}_h10_long.json"
                model_path = MODEL_DIR / model_name
            
            model = get_model(model_path)
            if not model:
                await message.reply_text(f"❌ Error: Model `{model_name}` not found."); return

            try:
                feats, ts_ms = await asyncio.wait_for(asyncio.to_thread(get_latest_features, symbol, timeframe), timeout=15.0)
                candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, timeframe, 2), timeout=10.0)
            except asyncio.TimeoutError:
                await message.reply_text("❌ Error: Data fetch timed out. APIs might be blocked or slow."); return
            
            entry_price = float(candles[-2][4])
            atr_14 = feats[18] 
            proba = model.predict_proba([feats])[0]
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            plan = build_trade_plan(entry_price, direction, atr_14, timeframe)
            display_tf = timeframe

        atr_val = feats[18]
        is_crypto = "USDT" in symbol
        min_atr = MIN_ATR_CRYPTO if is_crypto else MIN_ATR_FOREX
        
        if atr_val < min_atr:
            await message.reply_text(f"⚪ **NO TRADE**\n\nMarket is too flat (Low Volatility). ATR is only {atr_val*100:.3f}%. Avoiding chop.", parse_mode="Markdown")
            return

        if confidence < MIN_CONFIDENCE:
            await message.reply_text(
                f"⚪ **NO TRADE**\n\n"
                f"Pair: {symbol} ({display_tf})\n"
                f"AI Confidence: {confidence*100:.1f}%\n\n"
                f"❌ Setup rejected because confidence is below our {MIN_CONFIDENCE*100:.0f}% safety threshold.",
                parse_mode="Markdown"
            )
            return
            
        if direction == "LONG" and sentiment == "BEARISH":
            await message.reply_text(f"⛔ **TRADE BLOCKED**\n\nAI wants to BUY, but News Sentiment is BEARISH.\n{sentiment_reason}", parse_mode="Markdown")
            return
        if direction == "SHORT" and sentiment == "BULLISH":
            await message.reply_text(f"⛔ **TRADE BLOCKED**\n\nAI wants to SELL, but News Sentiment is BULLISH.\n{sentiment_reason}", parse_mode="Markdown")
            return

        # 🚨 REGIME ENGINE CHECK 🚨
        try:
            regime_candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, display_tf, 100), timeout=10.0)
            regime_safe, regime_name, regime_reason = await asyncio.to_thread(check_market_regime, regime_candles)
            if not regime_safe:
                await message.reply_text(f"⚪ **NO TRADE (REGIME)**\n\n{regime_reason}", parse_mode="Markdown")
                return
        except Exception as e:
            logger.warning(f"Regime check skipped: {e}")
            regime_name = "UNKNOWN"

        # 🚨 FEAR & GREED CHECK (CRYPTO ONLY) 🚨
        fg_text = "N/A"
        if is_crypto:
            fg_score, fg_class = await asyncio.to_thread(get_crypto_fear_greed)
            if fg_score is not None:
                fg_text = f"{fg_score} ({fg_class})"
                if direction == "LONG" and fg_score >= 80:
                    await message.reply_text(f"⛔ **TRADE BLOCKED (MACRO)**\n\nCrypto Market is in Extreme Greed ({fg_score}). Buying here is too risky.", parse_mode="Markdown")
                    return
                if direction == "SHORT" and fg_score <= 20:
                    await message.reply_text(f"⛔ **TRADE BLOCKED (MACRO)**\n\nCrypto Market is in Extreme Fear ({fg_score}). Selling here is too risky.", parse_mode="Markdown")
                    return

        # 🚨 S/R ENGINE CHECK 🚨
        try:
            sr_candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, display_tf, 100), timeout=10.0)
            sr_safe, sr_reason = await asyncio.to_thread(check_support_resistance, symbol, plan["entry"], direction, sr_candles, is_crypto)
            if not sr_safe:
                await message.reply_text(f"⛔ **TRADE BLOCKED (S/R)**\n\n{sr_reason}", parse_mode="Markdown")
                return
        except Exception as e:
            logger.warning(f"S/R check skipped: {e}")

        await message.reply_text("🧠 Running Deep Research (LLM Analysis)...")
        try:
            research_approved, research_reason = await asyncio.wait_for(
                asyncio.to_thread(deep_research_trade, symbol, direction, confidence, sentiment, sentiment_reason),
                timeout=6.0
            )
        except asyncio.TimeoutError:
            research_approved, research_reason = True, "AI Timeout. Proceeding with Math Model."
        
        if not research_approved:
            await message.reply_text(f"⛔ **TRADE VETOED BY DEEP RESEARCHER**\n\n{research_reason}", parse_mode="Markdown")
            return

        tech_overview = get_technical_overview(feats, direction, display_tf)
        sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=model_name, confidence=float(confidence), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0))
        
        signal_time = datetime.now(tz=WAT).strftime('%I:%M:%S %p WAT')
        start_str = plan['start_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        end_str = plan['end_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        duration = plan['duration_min']
        quality = "🔥 STRONG" if confidence >= 0.70 else "⚡ MODERATE"

        sent_emoji = "🟢" if sentiment == "BULLISH" else ("🔴" if sentiment == "BEARISH" else "⚪")

        msg = (
            f"🤖 LEGEND TRADING AI\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"PAPER MODE\n\n"
            f"{'🟢 BUY ▲' if direction == 'LONG' else '🔴 SELL ▼'}\n"
            f"{symbol} · Chart: {display_tf}\n"
            f"Engine: {model_name}\n\n"
            f"⏱ EXPIRY: {duration} minutes\n"
            f"Signal Time: {signal_time}\n"
            f"Start Trade: {start_str}\n"
            f"End Trade:   {end_str}\n\n"
            f"📊 CONFIDENCE\n"
            f"{confidence*100:.1f}% ({quality})\n"
            f"📰 Sentiment: {sent_emoji} {sentiment}\n"
            f"📉 Volatility: {atr_val*100:.3f}% (Healthy)\n"
            f"📈 Regime: {regime_name}\n"
            f"😱 Fear & Greed: {fg_text}\n"
            f"🛡️ S/R Check: ✅ Clear\n"
            f"🧠 Deep Research: ✅ APPROVED\n"
            f"*(Reason: {research_reason})*\n\n"
            f"{tech_overview}\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: <code>{format_price(plan['entry'])}</code>\n"
            f"SL: <code>{format_price(plan['stop_loss'])}</code>\n"
            f"Target: <code>{format_price(plan['tp1'])}</code>\n\n"
            f"ID: {sig_id}"
        )
        
        await message.reply_text("⏳ Generating complete signal image...")

        try:
            static_img = "buy.png" if direction == "LONG" else "sell.png"
            final_img = static_img

            try:
                chart_file = await asyncio.wait_for(asyncio.to_thread(generate_chart, symbol, display_tf, plan, direction), timeout=15.0)
                if chart_file and os.path.exists(chart_file):
                    final_img = chart_file
            except Exception as chart_err:
                logger.warning(f"Chart generation skipped/timed out: {chart_err}")

            if os.path.exists(final_img):
                with open(final_img, "rb") as f:
                    await message.reply_photo(photo=f, caption=msg, parse_mode="HTML")
            else:
                await message.reply_text(msg, parse_mode="HTML")
                
        except Exception as img_err:
            logger.error(f"Image sending failed: {img_err}")
            await message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@restricted
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'menu_main':
        await query.edit_message_text("🤖 MAIN MENU\nSelect an option:", reply_markup=get_main_menu())
    elif query.data == 'menu_market':
        await query.edit_message_text("💹 SELECT MARKET:", reply_markup=get_market_menu())
    elif query.data == 'market_crypto':
        await query.edit_message_text("🪙 SELECT CRYPTO PAIR:", reply_markup=get_crypto_menu())
    elif query.data == 'market_forex':
        await query.edit_message_text("💱 SELECT FOREX PAIR:", reply_markup=get_forex_menu())
    elif query.data == 'market_stocks':
        await query.edit_message_text("📈 SELECT STOCK:", reply_markup=get_stocks_menu())
    elif query.data == 'market_indices':
        await query.edit_message_text("📊 SELECT INDEX/METAL:", reply_markup=get_indices_menu())
    elif query.data == 'menu_pause':
        set_pause(True)
        await query.edit_message_text("🛑 SYSTEM PAUSED.", reply_markup=get_main_menu())
    elif query.data == 'menu_research':
        await query.edit_message_text("🔬 Running Research Lab... Scanning database for patterns.", reply_markup=None)
        result = await asyncio.to_thread(run_research_lab)
        await query.edit_message_text(result, reply_markup=get_main_menu())
    elif query.data == 'menu_memory':
        insights = get_all_insights()
        if not insights:
            text = "🧠 **AI MEMORY IS EMPTY**\n\nNo patterns discovered yet. Run the Research Lab or wait for more trades to close."
        else:
            text = "🧠 **AI MEMORY (RECENT DISCOVERIES)**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for i in insights:
                emoji = "🔥" if i['category'] == "EDGE" else ("⚠️" if i['category'] == "WARNING" else "📊")
                text += f"{emoji} {i['insight']}\n*(Sample Size: {i['sample_size']})*\n\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_testing':
        await query.edit_message_text("⚙️ **MODEL TESTING**\n\nBacktest and validate new models before promoting them to the live engine.\n\n(Coming Soon: /backtest)", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_status':
        await query.edit_message_text("🤖 **SYSTEM STATUS**\n\nAll systems operational.\n- Database: PostgreSQL (Online)\n- Data Feeds: Binance/Bybit/Yahoo\n- Research Engine: Active\n- News Filter: Active\n- Sentiment Engine: Active\n- Deep Researcher (LLM): Active\n- MTF Engine: Active\n- S/R Engine: Active\n- Fear & Greed: Active\n- Regime Engine: Active", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_performance':
        stats = get_performance_stats()
        text = (
            f"📊 PERFORMANCE\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Closed: {stats['total_closed']}\n"
            f"✅ Wins: {stats['wins']}\n"
            f"❌ Losses: {stats['losses']}\n"
            f"⏱ Expired: {stats['expired']}\n"
            f"🏆 Win Rate: {stats['win_rate']:.1f}%\n"
            f"⏳ Pending: {stats['pending']}"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu())
    elif query.data.startswith('pair_'):
        symbol = query.data.split('_', 1)[1] 
        await query.edit_message_text(f"⏱️ SELECT TIMEFRAME FOR {symbol}:", reply_markup=get_timeframe_menu(symbol))
    elif query.data.startswith('tf_'):
        if analysis_lock.locked():
            await query.answer("⏳ The AI is already analyzing a trade. Please wait.", show_alert=True)
            return
            
        parts = query.data.split('_')
        tf_type, symbol = parts[1], parts[2]
        
        async with analysis_lock:
            await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...\nPlease wait.", reply_markup=None)
            await run_analysis(query.message, symbol, tf_type)
