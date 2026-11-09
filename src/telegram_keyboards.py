from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.risk_engine import SYSTEM_PAUSED # Import the global state

def get_main_menu():
    # 🚨 DYNAMIC PAUSE/RESUME BUTTON 🚨
    if SYSTEM_PAUSED:
        status_button = InlineKeyboardButton("▶️ RESUME SIGNALS", callback_data='menu_resume')
    else:
        status_button = InlineKeyboardButton("🛑 PAUSE SIGNALS", callback_data='menu_pause')

    keyboard = [
        [InlineKeyboardButton("🧠 AI SIGNALS (FUSION)", callback_data='menu_signals')],
        [InlineKeyboardButton("💹 SELECT MARKET", callback_data='menu_market')],
        [InlineKeyboardButton("🔬 RESEARCH LAB", callback_data='menu_research'),
         InlineKeyboardButton("🧠 AI MEMORY", callback_data='menu_memory')],
        [InlineKeyboardButton("⚙️ MODEL TESTING", callback_data='menu_testing'),
         InlineKeyboardButton("📊 PERFORMANCE", callback_data='menu_performance')],
        [InlineKeyboardButton("🤖 SYSTEM STATUS", callback_data='menu_status'),
         status_button] # The dynamic button goes here
    ]
    return InlineKeyboardMarkup(keyboard)

# ... (Leave the rest of the keyboard functions exactly as they are) ...
