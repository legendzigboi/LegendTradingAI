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
from src.telegram_keyboards import get_main_menu, get_market_menu, get_crypto_menu, get_forex_menu, get_timeframe_menu
from src.engines.fusion_engine import FusionEngine
from src.research_engine import run_research_lab
from src.news_filter import check_high_impact_news
from src.sentiment_engine import get_market_sentiment

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
WAT = timezone(timedelta(hours=1))
MIN_CONFIDENCE = 0.60 

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
                if update.message: await update.message.reply_text("⛔ Unauthorized.", parse_mode=None)
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
    chat_id = update.effective_chat.id if update else AUTHORIZED_USER_IDS[0]
    
    if update and getattr(update, 'message', None):
        await update.message.reply_text("🔍 Scanning all markets for PREMIUM setups...")
    else:
        await context.bot.send_message(chat_id=chat_id, text="⏰ SCHEDULED SCAN: Scanning markets...")
    
    results = await asyncio.to_thread(scan_markets, min_confidence=MIN_CONFIDENCE)
    
    if not results:
        await context.bot.send_message(chat_id=chat_id, text="⚪ NO PREMIUM TRADE\nNo setups passed the strict filters right now.")
        return

    for res in results[:2]:
        is_safe, news_warning = await asyncio.to_thread(check_high_impact_news, res['symbol'])
        if not is_safe:
            await context.bot.send_message(chat_id=chat_id, text=f"⛔ TRADE BLOCKED: {news_warning}")
            continue

        start_str = res['plan']['start_time'].astimezone(WAT).strftime('%I:%M %p WAT')
        end_str = res['plan']['end_time'].astimezone(WAT).strftime('%I:%M %p WAT')
        duration = res['plan']['duration_min']
        quality = "🔥 STRONG" if res['confidence'] >= 0.70 else "⚡ MODERATE"
        
        msg = (
            f"🤖 LEGEND TRADING AI\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"PAPER MODE\n\n"
            f"{'🟢 BUY ▲' if res['direction'] == 'LONG' else '🔴 SELL ▼'}\n"
            f"{res['symbol']} · {res['timeframe']}\n\n"
            f"⏱ EXPIRY: {duration} minutes\n"
            f"Start: {start_str}\n"
            f"End: {end_str}\n\n"
            f"📊 CONFIDENCE\n"
            f"{res['confidence']*100:.1f}% ({quality})\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: {format_price(res['plan']['entry'])}\n"
            f"SL: {format_price(res['plan']['stop_loss'])}\n"
            f"Target: {format_price(res['plan']['tp1'])}\n"
        )
        
        try:
            static_img = "buy.png" if res['direction'] == "LONG" else "sell.png"
            if os.path.exists(static_img):
                with open(static_img, "rb") as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption=msg)
            else:
                await context.bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            logger.error(f"Scanner image error: {e}")
            await context.bot.send_message(chat_id=chat_id, text=msg)

async def run_analysis(message, symbol, timeframe):
    allowed, risk_msg = check_circuit_breaker()
    if not allowed:
        await message.reply_text(risk_msg, parse_mode=None)
        return

    # 1. News Filter
    is_safe, news_warning = await asyncio.to_thread(check_high_impact_news, symbol)
    if not is_safe:
        await message.reply_text(f"⛔ **TRADE BLOCKED**\n\n{news_warning}\n\n*Protecting capital during high volatility.*", parse_mode="Markdown")
        return
        
    # 2. Sentiment Filter
    sentiment, sentiment_reason = await asyncio.to_thread(get_market_sentiment, symbol)

    try:
        if timeframe == 'FUSION':
            engine = FusionEngine()
            try:
                res = await asyncio.wait_for(asyncio.to_thread(engine.analyze, symbol), timeout=20.0)
            except asyncio.TimeoutError:
                await message.reply_text("❌ Error: Fusion Engine timed out.", parse_mode=None); return
                
            if "error" in res:
                await message.reply_text(f"❌ Error: {res['error']}", parse_mode=None); return
            if res.get("status") == "NO_TRADE":
                await message.reply_text(f"⚪ NO TRADE\n{res['reason']}", parse_mode=None); return
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
                await message.reply_text(f"❌ Error: Model `{model_name}` not found.", parse_mode=None); return

            try:
                feats, ts_ms = await asyncio.wait_for(asyncio.to_thread(get_latest_features, symbol, timeframe), timeout=15.0)
                candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, timeframe, 2), timeout=10.0)
            except asyncio.TimeoutError:
                await message.reply_text("❌ Error: Data fetch timed out. APIs might be blocked or slow.", parse_mode=None); return
            
            entry_price = float(candles[-2][4])
            atr_14 = feats[18] 
            proba = model.predict_proba([feats])[0]
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            plan = build_trade_plan(entry_price, direction, atr_14, timeframe)
            display_tf = timeframe

        if confidence < MIN_CONFIDENCE:
            await message.reply_text(
                f"⚪ **NO TRADE**\n\n"
                f"Pair: {symbol} ({display_tf})\n"
                f"AI Confidence: {confidence*100:.1f}%\n\n"
                f"❌ Setup rejected because confidence is below our {MIN_CONFIDENCE*100:.0f}% safety threshold to avoid losses.",
                parse_mode="Markdown"
            )
            return
            
        # 🚨 SENTIMENT CHECK 🚨
        if direction == "LONG" and sentiment == "BEARISH":
            await message.reply_text(f"⛔ **TRADE BLOCKED**\n\nAI wants to BUY, but News Sentiment is BEARISH.\n{sentiment_reason}", parse_mode="Markdown")
            return
        if direction == "SHORT" and sentiment == "BULLISH":
            await message.reply_text(f"⛔ **TRADE BLOCKED**\n\nAI wants to SELL, but News Sentiment is BULLISH.\n{sentiment_reason}", parse_mode="Markdown")
            return

        tech_overview = get_technical_overview(feats, direction, display_tf)
        sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=model_name, confidence=float(confidence), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0))
        
        signal_time = datetime.now(tz=WAT).strftime('%I:%M:%S %p WAT')
        start_str = plan['start_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        end_str = plan['end_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        duration = plan['duration_min']
        quality = "🔥 STRONG" if confidence >= 0.70 else "⚡ MODERATE"

        # Add Sentiment to the message
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
            f"📰 Sentiment: {sent_emoji} {sentiment}\n\n"
            f"{tech_overview}\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: {format_price(plan['entry'])}\n"
            f"SL: {format_price(plan['stop_loss'])}\n"
            f"Target: {format_price(plan['tp1'])}\n\n"
            f"ID: {sig_id}"
        )
        
        await message.reply_text("⏳ Generating complete signal...")

        try:
            static_img = "buy.png" if direction == "LONG" else "sell.png"
            final_img = static_img

            try:
                chart_file = await asyncio.wait_for(asyncio.to_thread(generate_chart, symbol, display_tf, plan, direction), timeout=5.0)
                if chart_file and os.path.exists(chart_file):
                    final_img = chart_file
            except Exception as chart_err:
                logger.warning(f"Chart generation skipped/timed out: {chart_err}")

            if os.path.exists(final_img):
                with open(final_img, "rb") as f:
                    await message.reply_photo(photo=f, caption=msg)
            else:
                await message.reply_text(msg)
                
        except Exception as img_err:
            logger.error(f"Image sending failed: {img_err}")
            await message.reply_text(msg)

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}", parse_mode=None)

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
        await query.edit_message_text("🤖 **SYSTEM STATUS**\n\nAll systems operational.\n- Database: PostgreSQL (Online)\n- Data Feeds: Binance/Bybit\n- Research Engine: Active\n- News Filter: Active\n- Sentiment Engine: Active", parse_mode="Markdown", reply_markup=get_main_menu())
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
        symbol = query.data.split('_')[1]
        await query.edit_message_text(f"⏱️ SELECT TIMEFRAME FOR {symbol}:", reply_markup=get_timeframe_menu(symbol))
    elif query.data.startswith('tf_'):
        parts = query.data.split('_')
        tf_type, symbol = parts[1], parts[2]
        await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...\nPlease wait.", reply_markup=None)
        await run_analysis(query.message, symbol, tf_type)
