import os
import logging
import psycopg
import threading
import asyncio
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- PARAMETERS AND INSTANCES CORNER ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
DATABASE_URL = os.getenv("postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddNumberState(StatesGroup):
    waiting_for_data = State()

def get_db_connection():
    return psycopg.connect(DATABASE_URL)

# --- 1. HEALTH CHECK HTTP PING LISTENER ---
class HealthCheckHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - BOT PORT PIPELINE ACTIVE")

def run_health_server():
    """Binds an isolated socket to satisfy Render port monitoring requirements."""
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"🟢 Health check server listening continuously on port {port}")
    server.serve_forever()

# --- 2. SQL PERSISTENCE LAYER FUNCTIONS ---
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
                logging.info("🚀 Database matrix schemas initialized securely.")
    except Exception as e:
        logging.error(f"DB Init Error: {e}")

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

# --- 3. STORE INTERFACE CONFIGURATIONS ---
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
        [KeyboardButton(text="🛍️ Buy Telegram Account")],
        [KeyboardButton(text="💼 Wallet")]
    ], resize_keyboard=True)

def generate_services_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(text="🌍 Country", callback_data="noop"),
        InlineKeyboardButton(text="💰 Price", callback_data="noop"),
        InlineKeyboardButton(text="📦 Stock", callback_data="noop")
    ])
    for country in COUNTRY_SERVICES:
        stock = get_stock_count(country["id"])
        keyboard.append([
            InlineKeyboardButton(text=f"{country['flag']} {country['name']}", callback_data=f"select_co_{country['id']}"),
            InlineKeyboardButton(text=f"₹{country['price']}", callback_data=f"select_co_{country['id']}"),
            InlineKeyboardButton(text=f"[{stock}] ✅", callback_data=f"select_co_{country['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- 4. CORE ENGINE EVENT HANDLERS ---
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
        logging.error(f"Reg error: {e}")
    await msg.answer("👋 Welcome to SKY OTP BOT.", reply_markup=main_kb())

@dp.message(F.text == "🛍️ Buy Telegram Account")
async def show_tg_services(msg: Message):
    await msg.answer(text="🛍️ <b>Available Telegram Services</b>", reply_markup=generate_services_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("select_co_"))
async def show_confirmation_screen(cb: CallbackQuery):
    country_id = cb.data.replace("select_co_", "")
    country = next((c for c in COUNTRY_SERVICES if c["id"] == country_id), None)
    if not country: return await cb.answer("❌ Country context missing.")
    stock = get_stock_count(country_id)
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm Purchase", callback_data=f"conf_buy_{country['id']}")],
        [InlineKeyboardButton(text="❌ Cancel Purchase", callback_data="cancel_action")]
    ])
    confirmation_text = (
        f"Dear customer, after you click the confirm button, the number will be reserved for you.\n\n"
        f"🌍 <b>Country:</b> {country['name']} {country['flag']}\n"
        f"💰 <b>Price:</b> ₹{country['price']}\n"
        f"📦 <b>Stock:</b> {stock}"
    )
    await cb.message.edit_text(text=confirmation_text, reply_markup=confirm_kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("conf_buy_"))
async def execute_internal_purchase(cb: CallbackQuery):
    uid = cb.from_user.id
    country_id = cb.data.replace("conf_buy_", "")
    country = next((c for c in COUNTRY_SERVICES if c["id"] == country_id), None)
    
    user_balance = get_user_bal(uid)
    if user_balance < country["price"]:
        return await cb.message.edit_text(text=f"❌ Your balance (₹{user_balance}) is too low.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, phone_number FROM available_accounts WHERE country_id = %s AND is_sold = FALSE LIMIT 1 FOR UPDATE", (country_id,))
                account = cur.fetchone()
                if not account:
                    return await cb.message.edit_text("❌ <b>Out of Stock!</b>")
                    
                account_id, phone_number = account[0], account[1]
                cur.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (country["price"], uid))
                cur.execute("UPDATE available_accounts SET is_sold = TRUE WHERE id = %s", (account_id,))
                cur.execute("INSERT INTO active_orders (uid, account_id, phone_number, country_name, cost_inr, status, timestamp) VALUES (%s, %s, %s, %s, %s, 'WAITING', %s)", (uid, account_id, phone_number, country["name"], country["price"], datetime.now().isoformat()))
                conn.commit()
                
        await cb.message.edit_text(text=f"📱 <b>Your Number is Reserved!</b>\n\n🌍 <b>Country:</b> {country['name']}\n🔢 <b>Number:</b> <code>{phone_number}</code>\n\n👉 Enter this number in Telegram app now. Code will arrive here automatically.", parse_mode="HTML")
    except Exception as purchase_err:
        logging.error(f"Purchase failed: {purchase_err}")
        await cb.message.edit_text("❌ An error occurred.")

# --- 5. ADMINISTRATION CONTROL HANDLERS ---
@dp.message(Command("addnumber"))
async def start_add_number(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_TELEGRAM_ID: return
    await msg.answer("📥 Format: <code>country_id | phone_number | api_id | api_hash | string_session</code>", parse_mode="HTML")
    await state.set_state(AddNumberState.waiting_for_data)

@dp.message(AddNumberState.waiting_for_data)
async def process_number_data(msg: Message, state: FSMContext):
    parts = [p.strip() for p in msg.text.split("|")]
    if len(parts) != 5: return await msg.answer("❌ Format Error. Use | separator.")
    country_id, phone, api_id, api_hash, session_str = parts
    try:
