import os
import sys
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from psycopg_pool import AsyncConnectionPool

# --- SYSTEM WIDE LOGGING HUB ---
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] BOT: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- CORE PARAMETERS & RUNTIME ENV CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db"
)

# Global pool reference initialized inside main lifecycle loop
db_pool = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddNumberState(StatesGroup):
    waiting_for_data = State()

# --- ISOLATED CORE DATABASE CONTROLLERS (FLAT BLUEPRINTS) ---

async def init_db():
    """Builds database engine storage tables safely upon service startup."""
    async with db_pool.connection() as conn:
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
    logging.info("⚡ System database structures verified and online.")

async def register_user_profile(uid: int):
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT uid FROM users WHERE uid = %s;", (uid,))
            if not await cur.fetchone():
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await cur.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0.00, %s);", (uid, now))
                await conn.commit()

async def get_node_stock(country_id: str) -> int:
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM available_accounts WHERE country_id = %s AND is_sold = FALSE;", (country_id,))
            row = await cur.fetchone()
            return row[0] if row else 0

async def fetch_user_balance(uid: int) -> float:
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT balance FROM users WHERE uid = %s;", (uid,))
            row = await cur.fetchone()
            return float(row[0]) if row else 0.00

async def register_checkout_pipeline(uid: int, country_id: str, c_name: str, c_price: float):
    """Processes verification handshakes flatly without complex nested indentation blocks."""
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, phone_number FROM available_accounts WHERE country_id = %s AND is_sold = FALSE LIMIT 1 FOR UPDATE;",
                (country_id,)
            )
            account_record = await cur.fetchone()
            
            if not account_record:
                return None
                
            acc_id, phone_num = account_record[0], account_record[1]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            await cur.execute("""
                INSERT INTO active_orders (uid, account_id, phone_number, country_name, cost_inr, status, timestamp) 
                VALUES (%s, %s, %s, %s, %s, 'WAITING', %s);
            """, (uid, acc_id, phone_num, c_name, c_price, now_str))
            
            await conn.commit()
            return phone_num

# --- PREMIUM LAYOUT BUTTON CONFIGURATION ---
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
        status_lbl = f"[{stock}] AVAIL ✅" if stock > 0 else "🚫 EMPTY"
        keyboard.append([
            InlineKeyboardButton(text=f"{c['flag']} {c['name']}", callback_data=f"sel_{c['id']}"),
            InlineKeyboardButton(text=f"₹{c['price']}", callback_data=f"sel_{c['id']}"),
            InlineKeyboardButton(text=status_lbl, callback_data=f"sel_{c['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- USER COMMANDS & RECEIVER HOOKS ---

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await register_user_profile(msg.from_user.id)
    welcome_text = """👑 <b>WELCOME TO SKY CLOUD OTP SERVICES</b> 👑\n────────────────────────────────\n⚡ <i>Passive, automated 24/7 activation server protocols.</i>\n\n📦 Use the interactive console board below to manage your inventory channels instantly."""
    await msg.answer(text=welcome_text, reply_markup=main_kb(), parse_mode="HTML")

@dp.message(F.text == "⚡ INSTANT SMS STORE ⚡")
async def show_tg_services(msg: Message):
    store_text = "🛒 <b>LIVE INVENTORY ACTIVATION HUB</b>\n────────────────────────────────\n💡 Select your preferred localized zone channel reference parameters from the grid below:"
    kb = await generate_services_keyboard()
    await msg.answer(text=store_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("sel_"))
async def show_confirmation_screen(cb: CallbackQuery):
    c_id = cb.data.replace("sel_", "")
    country = next((item for item in COUNTRY_SERVICES if item["id"] == c_id), None)
    if not country:
        return await cb.answer("❌ Error: Country missing.")
        
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
    country = next((item for item in COUNTRY_SERVICES if item["id"] == c_id), None)
    
    if not country:
        return await cb.answer("❌ Context missing.")
        
    stock = await get_node_stock(c_id)
    if stock <= 0:
        return await cb.message.edit_text("❌ <b>Out of Stock!</b>\n\nThis target country node empty state changed while navigating checkout.", parse_mode="HTML")

    bal = await fetch_user_balance(uid)
    if bal < country["price"]:
        decline_text = f"❌ <b>TRANSACTION ATTEMPT REJECTED</b>\n────────────────────────────────\n⚠️ Insufficient funds inside your platform balance wallet.\n\n💰 <b>Your Balance:</b> ₹{bal:.2f}\n📈 <b>Required Cost:</b> ₹{country['price']:.2f}\n\n💳 Please top up your wallet profile instantly."
        return await cb.message.edit_text(text=decline_text, parse_mode="HTML")
        
    # Execution link targeting detached safe pool handler function
    phone_num = await register_checkout_pipeline(uid, c_id, country["name"], country["price"])
    
    if not phone_num:
