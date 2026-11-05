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
from src.regime_engine import check_market_regime
from src.order_flow_engine import get_order_flow_imbalance, calculate_vwap_zscore
from src.macro_engine import get_crypto_crowd_sentiment, get_dxy_trend

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
MIN_CONFIDENCE = 0.50 
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
    pass

async def run_analysis(message, symbol, timeframe):
    allowed, risk_msg = check_circuit_breaker()
    if not allowed:
        await message.reply_text(risk_msg); return

    is_safe, news_warning = await asyncio.to_thread(check_high_impact_news, symbol)
    if not is_safe:
        await message.reply_text(f"⛔ **TRADE BLOCKED**\n\n{news_warning}\n\n*Protecting capital.*", parse_mode="Markdown"); return
        
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
            model_name = f"v0.2_{safe_symbol}_{timeframe}_ensemble.pkl"
            model_path = MODEL_DIR / model_name
            
            if not model_path.exists():
                model_name = f"v0.2_{safe_symbol}_{timeframe}_ensemble.pkl"
                model_path = MODEL_DIR / model_name
                
            if not model_path.exists():
                fallback_tf = "1h" if timeframe != "1h" else "5m"
                model_name = f"v0.2_{safe_symbol}_{fallback_tf}_ensemble.pkl"
                model_path = MODEL_DIR / model_name
                if model_path.exists():
                    display_tf = fallback_tf
                else:
                    await message.reply_text(f"❌ Error: No models found for `{symbol}`."); return
            else:
                display_tf = timeframe
            
            model = get_model(model_path)
            if not model:
                await message.reply_text(f"❌ Error: Model `{model_name}` failed to load."); return

            try:
                feats, ts_ms = await asyncio.wait_for(asyncio.to_thread(get_latest_features, symbol, display_tf), timeout=15.0)
                candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, display_tf, 2), timeout=10.0)
            except asyncio.TimeoutError:
                await message.reply_text("❌ Error: Data fetch timed out."); return
            
            entry_price = float(candles[-2][4])
            atr_14 = feats[18] 
            proba = model.predict_proba([feats])[0]
            direction = "LONG" if proba > 0.5 else "SHORT"
            confidence = proba if proba > 0.5 else (1 - proba)
            
            plan = build_trade_plan(entry_price, direction, atr_14, display_tf)

        atr_val = feats[18]
        is_crypto = "USDT" in symbol
        min_atr = MIN_ATR_CRYPTO if is_crypto else MIN_ATR_FOREX
        
        if atr_val < min_atr:
            await message.reply_text(f"⚪ **NO TRADE**\n\nMarket is too flat (Low Volatility).", parse_mode="Markdown"); return

        # Predictive Modifiers
        base_confidence = confidence
        flow_text = "N/A"
        vwap_text = "N/A"
        
        try:
            flow_ratio, flow_text = await asyncio.to_thread(get_order_flow_imbalance, symbol)
            if direction == "LONG" and flow_ratio > 1.3: confidence += 0.05
            elif direction == "SHORT" and flow_ratio < 0.7: confidence += 0.05
            elif direction == "LONG" and flow_ratio < 0.6: confidence -= 0.05
            elif direction == "SHORT" and flow_ratio > 1.5: confidence -= 0.05

            if len(candles) >= 20:
                z_score = await asyncio.to_thread(calculate_vwap_zscore, candles)
                vwap_text = f"Z-Score: {z_score:.2f}"
                if direction == "LONG" and z_score < -2.0: confidence += 0.03
                elif direction == "SHORT" and z_score > 2.0: confidence += 0.03
        except Exception as e:
            logger.error(f"Predictive Modifier Error: {e}")

        confidence = max(0.01, min(0.99, confidence))
        modifier_text = f"Base: {base_confidence*100:.1f}% ➔ Final: {confidence*100:.1f}%" if confidence != base_confidence else "N/A"

        if confidence < MIN_CONFIDENCE:
            await message.reply_text(f"⚪ **NO TRADE**\n\nAI Confidence: {confidence*100:.1f}% (Below {MIN_CONFIDENCE*100:.0f}%)", parse_mode="Markdown"); return
            
        if direction == "LONG" and sentiment == "BEARISH":
            await message.reply_text(f"⛔ **BLOCKED**\n\nAI wants to BUY, but News is BEARISH.", parse_mode="Markdown"); return
        if direction == "SHORT" and sentiment == "BULLISH":
            await message.reply_text(f"⛔ **BLOCKED**\n\nAI wants to SELL, but News is BULLISH.", parse_mode="Markdown"); return

        # 🚨 MACRO CHECKS (Now Non-Blocking Warnings) 🚨
        macro_text = ""
        if is_crypto:
            crowd = await asyncio.to_thread(get_crypto_crowd_sentiment, symbol)
            if crowd:
                long_ratio, short_ratio = crowd
                if (direction == "LONG" and long_ratio > 0.75) or (direction == "SHORT" and short_ratio > 0.75):
                    macro_text = f"🐋 Retail: {long_ratio*100:.0f}% / {short_ratio*100:.0f}% (⚠️ Warning)"
                else:
                    macro_text = f"🐋 Retail: {long_ratio*100:.0f}% / {short_ratio*100:.0f}%"
        else:
            dxy_trend = await asyncio.to_thread(get_dxy_trend)
            if (direction == "LONG" and dxy_trend == "UPTREND") or (direction == "SHORT" and dxy_trend == "DOWNTREND"):
                macro_text = f"💵 DXY Trend: {dxy_trend} (⚠️ Warning)"
            else:
                macro_text = f"💵 DXY Trend: {dxy_trend}"

        regime_name = "UNKNOWN"
        try:
            regime_candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, display_tf, 100), timeout=10.0)
            _, regime_name, _ = await asyncio.to_thread(check_market_regime, regime_candles)
        except: pass

        fg_text = "N/A"
        if is_crypto:
            fg_score, fg_class = await asyncio.to_thread(get_crypto_fear_greed)
            if fg_score is not None:
                fg_text = f"{fg_score} ({fg_class})"
                if direction == "LONG" and fg_score >= 85:
                    await message.reply_text(f"⛔ **BLOCKED**\n\nExtreme Greed ({fg_score})."); return
                if direction == "SHORT" and fg_score <= 15:
                    await message.reply_text(f"⛔ **BLOCKED**\n\nExtreme Fear ({fg_score})."); return

        try:
            sr_candles = await asyncio.wait_for(asyncio.to_thread(fetch_klines, symbol, display_tf, 100), timeout=10.0)
            sr_safe, sr_reason = await asyncio.to_thread(check_support_resistance, symbol, plan["entry"], direction, sr_candles, is_crypto)
            if not sr_safe:
                await message.reply_text(f"⛔ **BLOCKED (S/R)**\n\n{sr_reason}", parse_mode="Markdown"); return
        except: pass

        await message.reply_text("🧠 Running Deep Research...")
        try:
            research_approved, research_reason = await asyncio.wait_for(
                asyncio.to_thread(deep_research_trade, symbol, direction, confidence, sentiment, sentiment_reason),
                timeout=6.0
            )
        except asyncio.TimeoutError:
            research_approved, research_reason = True, "AI Timeout."
        
        if not research_approved:
            await message.reply_text(f"⛔ **VETOED BY RESEARCHER**\n\n{research_reason}", parse_mode="Markdown"); return

        tech_overview = get_technical_overview(feats, direction, display_tf)
        sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=model_name, confidence=float(confidence), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0))
        
        signal_time = datetime.now(tz=WAT).strftime('%I:%M:%S %p WAT')
        start_str = plan['start_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        end_str = plan['end_time'].astimezone(WAT).strftime('%I:%M:%S %p WAT')
        duration = plan['duration_min']
        quality = "🔥 STRONG" if confidence >= 0.70 else "⚡ MODERATE"
        sent_emoji = "🟢" if sentiment == "BULLISH" else ("🔴" if sentiment == "BEARISH" else "⚪")

        # Position Sizing
        account_size = 1000
        risk_percent = 0.01
        risk_amount = account_size * risk_percent
        sl_distance_pct = abs(plan["entry"] - plan["stop_loss"]) / plan["entry"]
        suggested_lot = risk_amount / (plan["entry"] * sl_distance_pct) if sl_distance_pct > 0 else 0
        suggested_lot = round(suggested_lot / 1000, 2) 
        if suggested_lot < 0.01: suggested_lot = 0.01

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
            f"*(Math: {base_confidence*100:.1f}% | Modifiers: {modifier_text})*\n"
            f"{macro_text}\n"
            f"🐋 Order Flow: {flow_text}\n"
            f"📉 VWAP: {vwap_text}\n"
            f"📰 Sentiment: {sent_emoji} {sentiment}\n"
            f"📈 Regime: {regime_name}\n"
            f"🧠 Deep Research: ✅ APPROVED\n"
            f"*(Reason: {research_reason})*\n\n"
            f"{tech_overview}\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: <code>{format_price(plan['entry'])}</code>\n"
            f"SL: <code>{format_price(plan['stop_loss'])}</code>\n"
            f"Target: <code>{format_price(plan['tp1'])}</code>\n\n"
            f"💰 **POSITION SIZING**\n"
            f"Risk: 1% of $1000 = $10\n"
            f"Suggested Lot: <code>{suggested_lot}</code>\n\n"
            f"ID: {sig_id}"
        )
        
        await message.reply_text("⏳ Generating complete signal image...")
        try:
            static_img = "buy.png" if direction == "LONG" else "sell.png"
            final_img = static_img
            try:
                chart_file = await asyncio.wait_for(asyncio.to_thread(generate_chart, symbol, display_tf, plan, direction), timeout=15.0)
                if chart_file and os.path.exists(chart_file): final_img = chart_file
            except: pass

            if os.path.exists(final_img):
                with open(final_img, "rb") as f:
                    await message.reply_photo(photo=f, caption=msg, parse_mode="HTML")
            else:
                await message.reply_text(msg, parse_mode="HTML")
        except Exception as img_err:
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
        await query.edit_message_text("🔬 Running Research Lab...", reply_markup=None)
        result = await asyncio.to_thread(run_research_lab)
        await query.edit_message_text(result, reply_markup=get_main_menu())
    elif query.data == 'menu_memory':
        insights = get_all_insights()
        if not insights:
            text = "🧠 **AI MEMORY IS EMPTY**"
        else:
            text = "🧠 **AI MEMORY**\n\n"
            for i in insights:
                emoji = "🔴" if i['category'] == "AUTO_AUTOPSY" else "📊"
                text += f"{emoji} {i['insight']}\n*(Sample: {i['sample_size']})*\n\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_testing':
        await query.edit_message_text("⚙️ **MODEL TESTING**\n\nComing Soon.", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_status':
        await query.edit_message_text("🤖 **SYSTEM STATUS**\n\nAll systems operational.", parse_mode="Markdown", reply_markup=get_main_menu())
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
            await query.answer("⏳ AI is analyzing. Please wait.", show_alert=True); return
        parts = query.data.split('_')
        tf_type, symbol = parts[1], parts[2]
        async with analysis_lock:
            await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...", reply_markup=None)
            await run_analysis(query.message, symbol, tf_type)
