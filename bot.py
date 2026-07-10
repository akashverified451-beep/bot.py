import os
import logging
import psycopg
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- CORE PARAMS & ENVIRONMENT CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddNumberState(StatesGroup):
    waiting_for_data = State()

def get_db_connection():
    return psycopg.connect(DATABASE_URL)

# --- BACKEND STORAGE DATA HANDLERS ---
def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid BIGINT PRIMARY KEY, 
                        balance NUMERIC(10, 2) DEFAULT 0.00, 
                        join_date TEXT,
                        screenshot_state BOOLEAN DEFAULT FALSE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS available_accounts (
                        id SERIAL PRIMARY KEY,
                        country_id TEXT,
                        phone_number TEXT UNIQUE,
                        api_id TEXT,
                        api_hash TEXT,
                        string_session TEXT,
                        is_sold BOOLEAN DEFAULT FALSE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_orders (
                        uid BIGINT,
                        account_id INTEGER,
                        phone_number TEXT,
                        country_name TEXT,
                        cost_inr NUMERIC(10, 2),
                        status TEXT DEFAULT 'WAITING',
                        timestamp TEXT
                    )
                """)
                conn.commit()
                logging.info("⚡ Premium Store database schemas initialized successfully.")
    except Exception as e:
        logging.error(f"Database sync fault exception: {e}")

def get_stock_count(country_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM available_accounts WHERE country_id = %s AND is_sold = FALSE", (country_id,))
                row = cur.fetchone()
                return row[0] if row else 0
    except Exception:
        return 0

def get_user_bal(uid):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                return float(row[0]) if row else 0.00
    except Exception:
        return 0.00

def get_user_profile_data(uid):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT join_date FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                return row[0] if row else "Unknown Date"
    except Exception:
        return "Unknown Date"

# --- PREMIUM STYLED PLATFORM CONFIGURATION ---
COUNTRY_SERVICES = [
    {"id": "colombia", "name": "Colombia", "flag": "🇨🇴", "price": 36.29},
    {"id": "nigeria", "name": "Nigeria", "flag": "🇳🇬", "price": 36.29},
    {"id": "bangladesh", "name": "Bangladesh", "flag": "🇧🇩", "price": 40.11},
    {"id": "canada", "name": "Canada", "flag": "🇨🇦", "price": 40.11},
    {"id": "usa", "name": "United States", "flag": "🇺🇸", "price": 41.06},
    {"id": "india", "name": "India", "flag": "🇮🇳", "price": 41.06},
    {"id": "iran", "name": "Iran", "flag": "🇮🇷", "price": 53.48},
]

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚡ INSTANT SMS STORE ⚡")],
        [KeyboardButton(text="💳 MY WALLET"), KeyboardButton(text="👤 ACCOUNT PROFILE")]
    ], resize_keyboard=True)

def generate_services_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton(text="🌐 COUNTRY PLATFORM", callback_data="noop"),
        InlineKeyboardButton(text="💎 RATE", callback_data="noop"),
        InlineKeyboardButton(text="🔥 AVAILABILITY", callback_data="noop")
    ])
    
    for country in COUNTRY_SERVICES:
        stock = get_stock_count(country["id"])
        status_text = f"[{stock}] AVAIL ✅" if stock > 0 else "🚫 EMPTY"
        keyboard.append([
            InlineKeyboardButton(text=f"{country['flag']} {country['name']}", callback_data=f"select_co_{country['id']}"),
            InlineKeyboardButton(text=f"₹{country['price']}", callback_data=f"select_co_{country['id']}"),
            InlineKeyboardButton(text=status_text, callback_data=f"select_co_{country['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- USER CHAT & STYLED FLOW RECEPTORS ---
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
                if not cur.fetchone():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cur.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0.00, %s)", (uid, now))
                    conn.commit()
    except Exception as e:
        logging.error(f"Registration failure hook: {e}")
        
    welcome_text = """👑 <b>WELCOME TO SKY CLOUD OTP SERVICES</b> 👑
────────────────────────────────
⚡ <i>Passive, automated 24/7 activation server protocols.</i>

📦 Use the interactive console board below to manage your inventory channels instantly."""
    
    await msg.answer(text=welcome_text, reply_markup=main_kb(), parse_mode="HTML")

@dp.message(F.text == "⚡ INSTANT SMS STORE ⚡")
async def show_tg_services(msg: Message):
    store_text = """🛒 <b>LIVE INVENTORY ACTIVATION HUB</b>
────────────────────────────────
💡 Select your preferred localized zone channel reference parameters from the visual data matrix grid list below:"""
    
    await msg.answer(text=store_text, reply_markup=generate_services_keyboard(), parse_mode="HTML")

# --- ADDED: EXPLICIT WALLET INTERFACE RECEIVER ---
@dp.message(F.text == "💳 MY WALLET")
async def show_my_wallet(msg: Message):
    uid = msg.from_user.id
    balance = get_user_bal(uid)
    
    wallet_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ DEPOSIT FUNDS (UPI)", callback_data="add_funds_upi")]
    ])
    
    wallet_text = f"""💳 <b>YOUR CONFIGURATION WALLET PROFILE</b>
────────────────────────────────
💰 <b>Current Balance:</b> <code>₹{balance:.2f}</code>
🏦 <b>Gateway Channel:</b> Automated Live UPI Node

⚠️ <i>To add funds to your runtime balance, tap the billing integration gateway button interface down below.</i>"""
    await msg.answer(text=wallet_text, reply_markup=wallet_kb, parse_mode="HTML")

# --- ADDED: EXPLICIT ACCOUNT PROFILE RECEIVER ---
@dp.message(F.text == "👤 ACCOUNT PROFILE")
async def show_account_profile(msg: Message):
    uid = msg.from_user.id
    balance = get_user_bal(uid)
    join_date = get_user_profile_data(uid)
    
    profile_text = f"""👤 <b>SKY STATIONS SYSTEM IDENTIFICATION</b>
────────────────────────────────
🆔 <b>User Telegram ID:</b> <code>{uid}</code>
📊 <b>Available Assets:</b> ₹{balance:.2f}
📅 <b>Node Activation Date:</b> {join_date}

🛡️ <i>Your access tokens are authorized across independent multi-region validation databases.</i>"""
    await msg.answer(text=profile_text, parse_mode="HTML")

@dp.callback_query(F.data.startswith("select_co_"))
async def show_confirmation_screen(cb: CallbackQuery):
    country_id = cb.data.replace("select_co_", "")
    country = next((c for c in COUNTRY_SERVICES if c["id"] == country_id), None)
    if not country: 
        return await cb.answer("❌ Selected listing context metadata corrupted.")
    
    stock = get_stock_count(country_id)
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 INITIALIZE TRANSACTION", callback_data=f"conf_buy_{country['id']}")],
        [InlineKeyboardButton(text="❌ ABORT PURSUIT", callback_data="cancel_action")]
    ])
    
    confirmation_text = f"""📋 <b>DIGITAL INVENTORY REVIEW INVOICE</b>
────────────────────────────────
👋 Hello buyer, checking current server node paths. Confirm your purchase reservation metrics details below:

🌍 <b>Target Country:</b> {country['flag']} {country['name']}
💸 <b>Service Cost:</b> <b>₹{country['price']}</b>
📦 <b>Node Stock:</b> <b>{stock} channels active</b>

⚠️ <i>Funds are securely deducted only upon successful OTP receipt callback validation rules.</i>"""

    await cb.message.edit_text(text=confirmation_text, reply_markup=confirm_kb, parse_mode="HTML")

@dp.callback_query(F.data == "cancel_action")
async def process_cancel_action(cb: CallbackQuery):
    await cb.answer("Transaction canceled.")
    await cb.message.edit_text(
        text="❌ <b>Transaction Aborted.</b>\n\nYour deployment attempt was stopped safely. Use the main menu to restart the store selection pipeline.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("conf_buy_"))
async def execute_internal_purchase(cb: CallbackQuery):
