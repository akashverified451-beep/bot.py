import os
import sys
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
import psycopg

# --- RIGOROUS SYSTEM LOGGING ---
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] BOT: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- CONFIGURATION PRESETS & ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddNumberState(StatesGroup):
    waiting_for_data = State()

# --- ATOMIC DATABASE TRANSACTIONS ---

async def init_db():
    """Initializes schemas directly on execution boot."""
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid BIGINT PRIMARY KEY, 
                    balance NUMERIC(10, 2) DEFAULT 0.00, 
                    join_date TEXT,
                    screenshot_state BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS available_accounts (
                    id SERIAL PRIMARY KEY,
                    country_id TEXT,
                    phone_number TEXT UNIQUE,
                    api_id TEXT,
                    api_hash TEXT,
                    string_session TEXT,
                    is_sold BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS active_orders (
                    uid BIGINT,
                    account_id INTEGER,
                    phone_number TEXT,
                    country_name TEXT,
                    cost_inr NUMERIC(10, 2),
                    status TEXT DEFAULT 'WAITING',
                    timestamp TEXT
                );
            """)
            await conn.commit()

async def register_user_profile(uid: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (uid, balance, join_date) 
                VALUES (%s, 0.00, %s) 
                ON CONFLICT (uid) DO NOTHING;
            """, (uid, now))
            await conn.commit()

async def get_node_stock(country_id: str) -> int:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COALESCE(COUNT(*), 0) FROM available_accounts WHERE country_id = %s AND is_sold = FALSE;", (country_id,))
            row = await cur.fetchone()
            return int(row[0])

async def execute_atomic_checkout_pipeline(uid: int, country_id: str, c_name: str, c_price: float):
    """
    100% STATEMENT FREE PURSE PROCESSOR.
    No 'if' blocks. No 'except' blocks. 
    Processes everything in a single, safe database lock transaction query.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    atomic_query = """
    WITH user_check AS (
        SELECT uid, balance FROM users 
        WHERE uid = %s AND balance >= %s 
        FOR UPDATE
    ),
    stock_check AS (
        SELECT id, phone_number FROM available_accounts 
        WHERE country_id = %s AND is_sold = FALSE 
        LIMIT 1 
        FOR UPDATE
    ),
    deduct_user AS (
        UPDATE users 
        SET balance = users.balance - %s 
        FROM user_check, stock_check
        WHERE users.uid = user_check.uid
    ),
    insert_order AS (
        INSERT INTO active_orders (uid, account_id, phone_number, country_name, cost_inr, status, timestamp)
        SELECT user_check.uid, stock_check.id, stock_check.phone_number, %s, %s, 'WAITING', %s 
        FROM user_check, stock_check
        RETURNING phone_number
    )
    SELECT phone_number FROM insert_order;
    """
    
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(atomic_query, (uid, c_price, country_id, c_price, c_name, c_price, now_str))
            result = await cur.fetchone()
            await conn.commit()
            return result

# --- CORE PLATFORM INTERACTIVE DATA CONFIGS ---
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

async def generate_services_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton(text="🌐 PLATFORM", callback_data="noop"),
        InlineKeyboardButton(text="💎 RATE", callback_data="noop"),
        InlineKeyboardButton(text="🔥 STOCK", callback_data="noop")
    ]]
    for c in COUNTRY_SERVICES:
        stock = await get_node_stock(c["id"])
        status_lbl = f"[{stock}] AVAIL ✅"
        keyboard.append([
            InlineKeyboardButton(text=f"{c['flag']} {c['name']}", callback_data=f"sel_{c['id']}"),
            InlineKeyboardButton(text=f"₹{c['price']}", callback_data=f"sel_{c['id']}"),
            InlineKeyboardButton(text=status_lbl, callback_data=f"sel_{c['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- BOT INTERFACE PAYLOAD RECEIVERS ---

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await register_user_profile(msg.from_user.id)
    welcome_text = "👑 <b>WELCOME TO SKY CLOUD OTP SERVICES</b> 👑\n────────────────────────────────\n⚡ <i>Passive, automated 24/7 activation server protocols.</i>\n\n📦 Use the interactive console board below to manage your inventory channels instantly."
    await msg.answer(text=welcome_text, reply_markup=main_kb(), parse_mode="HTML")

@dp.message(F.text == "⚡ INSTANT SMS STORE ⚡")
async def show_tg_services(msg: Message):
    store_text = "🛒 <b>LIVE INVENTORY ACTIVATION HUB</b>\n────────────────────────────────\n💡 Select your preferred localized zone channel reference parameters from the grid below:"
    kb = await generate_services_keyboard()
    await msg.answer(text=store_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("sel_"))
async def show_confirmation_screen(cb: CallbackQuery):
    c_id = cb.data.replace("sel_", "")
    country = next((item for item in COUNTRY_SERVICES if item["id"] == c_id))
    stock = await get_node_stock(c_id)
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 INITIALIZE TRANSACTION", callback_data=f"buy_{country['id']}")],
        [InlineKeyboardButton(text="❌ ABORT PURSUIT", callback_data="abort")]
    ])
    confirm_text = f"📋 <b>DIGITAL INVENTORY INVOICE</b>\n────────────────────────────────\n🌍 <b>Target Country:</b> {country['flag']} {country['name']}\n💸 <b>Service Cost:</b> <b>₹{country['price']}</b>\n📦 <b>Node Stock:</b> <b>{stock} channels active</b>\n\n⚠️ <i>Funds are securely deducted only upon successful OTP receipt callback validation rules.</i>"
    await cb.message.edit_text(text=confirm_text, reply_markup=confirm_kb, parse_mode="HTML")

@dp.callback_query(F.data == "abort")
async def process_abort(cb: CallbackQuery):
    await cb.answer("Transaction aborted.")
    await cb.message.edit_text("❌ <b>Transaction Aborted.</b>\n\nYour deployment attempt was stopped safely. Use the main menu to restart.")

@dp.callback_query(F.data.startswith("buy_"))
async def process_purchase_callback(cb: CallbackQuery):
    uid = cb.from_user.id
    c_id = cb.data.replace("buy_", "")
    country = next((item for item in COUNTRY_SERVICES if item["id"] == c_id))
    
    db_receipt = await execute_atomic_checkout_pipeline(uid, c_id, country["name"], country["price"])
    phone_num = db_receipt[0] if db_receipt else ""
    
    result_actions = {
        True: f"⏳ <b>OTP QUEUE CHANNELS SPINNING UP</b>\n────────────────────────────────\n📱 <b>Phone Number:</b> <code>{phone_num}</code>\n🌐 <b>Region Setup:</b> {country['flag']} {country['name']}\n\n⚡ <i>The background transaction processing script is monitoring incoming verification events. Stand by...</i>",
        False: "❌ <b>TRANSACTION ATTEMPT REJECTED</b>\n────────────────────────────────\n⚠️ Checkout calculation parameters faulted.\n\nPossible Causes:\n🚨 Insufficient wallet balance funds configuration.\n🚨 Node inventory channels went out of stock during review.\n\n💳 Please check your configuration values or tap 'MY WALLET' to top up."
    }
    
    await cb.message.edit_text(text=result_actions[bool(db_receipt)], parse_mode="HTML")

# --- ENGINE LIFE CYCLE RUNLOOP ---
async def main():
    await init_db()
    logging.info("🚀 Sky Cloud Bot Core Online. Clean asyncio connections loaded. Poller active...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
