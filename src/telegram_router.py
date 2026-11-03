import logging
import asyncio
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from src.config import env
from src.signal_db import init_db, log_signal, get_pending_trades, get_performance_stats
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

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
WAT = timezone(timedelta(hours=1))

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

async def run_analysis(message, symbol, timeframe):
    allowed, risk_msg = check_circuit_breaker()
    if not allowed:
        await message.reply_text(risk_msg)
        return

    try:
        if timeframe == 'FUSION':
            engine = FusionEngine()
            res = await asyncio.to_thread(engine.analyze, symbol)
            if "error" in res:
                await message.reply_text(f"❌ Error: {res['error']}"); return
            if res.get("status") == "NO_TRADE":
                await message.reply_text(f"⚪ NO TRADE\n{res['reason']}"); return
            feats, direction, confidence, plan = res['features'], res['direction'], res['confidence'], res['plan']
            model_name, display_tf = res['engine'], res['timeframe']
        else:
            safe_symbol = symbol.replace("=", "_")
            model_name = f"v0.2_{safe_symbol}_{timeframe}_h10_long.json"
            model_path = MODEL_DIR / model_name
            
            model = get_model(model_path)
            if not model:
                await message.reply_text(f"❌ Error: Model `{model_name}` not found."); return

            feats, ts_ms = await asyncio.to_thread(get_latest_features, symbol, timeframe)
            candles = await asyncio.to_thread(fetch_klines, symbol, timeframe, 2)
            entry_price = float(candles[-2][4])
            atr_14 = feats[18] 
            proba = model.predict_proba([feats])[0]
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            # EXACT EXPIRY
            plan = build_trade_plan(entry_price, direction, atr_14, timeframe)
            display_tf = timeframe

        tech_overview = get_technical_overview(feats, direction, display_tf)
        sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=model_name, confidence=float(confidence), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0))
        
        signal_time = datetime.now(tz=WAT).strftime('%I:%M:%S %p WAT')
        start_str = plan['start_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        end_str = plan['end_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        duration = plan['duration_min']
        quality = "🔥 STRONG" if confidence >= 0.70 else ("⚡ MODERATE" if confidence >= 0.62 else "⚠️ WEAK")

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
            f"{confidence*100:.1f}% ({quality})\n\n"
            f"{tech_overview}\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: {format_price(plan['entry'])}\n"
            f"SL: {format_price(plan['stop_loss'])}\n"
            f"Target: {format_price(plan['tp1'])}\n\n"
            f"ID: {sig_id}"
        )
        
        await message.reply_text("⏳ Generating complete signal...")

        # Generate both images (banner is instant, chart takes a few seconds)
        banner_file = await asyncio.to_thread(generate_banner, direction)
        chart_file = await asyncio.to_thread(generate_chart, symbol, display_tf, plan, direction)

        # Send them together as one Photo with the caption
        if banner_file and chart_file:
            combined_file = combine_banner_and_chart(banner_file, chart_file)
            if combined_file:
                with open(combined_file, "rb") as f:
                    await message.reply_photo(photo=f, caption=msg)
            else:
                await message.reply_text(msg)
        else:
            await message.reply_text(msg)

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
    elif query.data == 'menu_pause':
        set_pause(True)
        await query.edit_message_text("🛑 SYSTEM PAUSED.", reply_markup=get_main_menu())
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
        await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...\nPlease wait.")
        await run_analysis(query.message, symbol, tf_type)
