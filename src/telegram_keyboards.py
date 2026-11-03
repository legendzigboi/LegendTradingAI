from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🧠 AI SIGNALS (FUSION)", callback_data='menu_signals')],
        [InlineKeyboardButton("💹 SELECT MARKET", callback_data='menu_market')],
        [InlineKeyboardButton("🔬 RESEARCH LAB", callback_data='menu_research'),
         InlineKeyboardButton("🧠 AI MEMORY", callback_data='menu_memory')],
        [InlineKeyboardButton("⚙️ MODEL TESTING", callback_data='menu_testing'),
         InlineKeyboardButton("📊 PERFORMANCE", callback_data='menu_performance')],
        [InlineKeyboardButton("🤖 SYSTEM STATUS", callback_data='menu_status'),
         InlineKeyboardButton("🛑 PAUSE SIGNALS", callback_data='menu_pause')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_market_menu():
    keyboard = [
        [InlineKeyboardButton("🪙 Crypto (Binance)", callback_data='market_crypto')],
        [InlineKeyboardButton("💱 Forex (Real)", callback_data='market_forex')],
        [InlineKeyboardButton("🎰 OTC (Pocket Option)", callback_data='market_otc')],
        [InlineKeyboardButton("⬅️ Back", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_crypto_menu():
    keyboard = [
        [InlineKeyboardButton("BTC/USDT", callback_data='pair_BTCUSDT'),
         InlineKeyboardButton("ETH/USDT", callback_data='pair_ETHUSDT')],
        [InlineKeyboardButton("SOL/USDT", callback_data='pair_SOLUSDT'),
         InlineKeyboardButton("XRP/USDT", callback_data='pair_XRPUSDT')],
        [InlineKeyboardButton("BNB/USDT", callback_data='pair_BNBUSDT'),
         InlineKeyboardButton("DOGE/USDT", callback_data='pair_DOGEUSDT')],
        [InlineKeyboardButton("⬅️ Back", callback_data='menu_market')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_forex_menu():
    keyboard = [
        [InlineKeyboardButton("EUR/USD", callback_data='pair_EURUSD=X'),
         InlineKeyboardButton("GBP/USD", callback_data='pair_GBPUSD=X')],
        [InlineKeyboardButton("USD/JPY", callback_data='pair_USDJPY=X'),
         InlineKeyboardButton("AUD/USD", callback_data='pair_AUDUSD=X')],
        [InlineKeyboardButton("USD/CAD", callback_data='pair_USDCAD=X'),
         InlineKeyboardButton("GOLD (XAUUSD)", callback_data='pair_GC=F')],
        [InlineKeyboardButton("⬅️ Back", callback_data='menu_market')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_timeframe_menu(symbol):
    keyboard = [
        [InlineKeyboardButton("⚡ FUSION (Auto-AI)", callback_data=f'tf_FUSION_{symbol}')],
        [InlineKeyboardButton("1m", callback_data=f'tf_1m_{symbol}'),
         InlineKeyboardButton("5m", callback_data=f'tf_5m_{symbol}'),
         InlineKeyboardButton("15m", callback_data=f'tf_15m_{symbol}')],
        [InlineKeyboardButton("1h", callback_data=f'tf_1h_{symbol}'),
         InlineKeyboardButton("4h", callback_data=f'tf_4h_{symbol}'),
         InlineKeyboardButton("1d", callback_data=f'tf_1d_{symbol}')],
        [InlineKeyboardButton("⬅️ Back", callback_data='menu_market')]
    ]
    return InlineKeyboardMarkup(keyboard)
