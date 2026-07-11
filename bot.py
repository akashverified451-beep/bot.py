
import os
import random
import logging
import io
import sqlite3
import asyncio
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# Core Dashboard logging config
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Variables configuration strings 
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

pending_claims = {}

class DepositStates(StatesGroup):
    waiting_for_screenshot = State()

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logging.info(f"Created persistent database directory structure at: {db_dir}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
        conn.commit()
    logging.info(f"Connected successfully to SQLite database at: {DB_PATH}")

def get_user_bal(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT balance FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else 0

def get_user_jd(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT join_date FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else "N/A"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛍️ Buy Telegram Account")],
        [KeyboardButton(text="🗨️ Buy Whatsapp OTP")],
        [KeyboardButton(text="💼 Wallet"), KeyboardButton(text="👤 User Profile")]
    ], resize_keyboard=True)

def balance_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Funds")],
        [KeyboardButton(text="🔙 Back to Main Menu")]
    ], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        if not conn.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
            conn.commit()
    await msg.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=main_kb())

@dp.message(F.text == "💼 Wallet")
async def wallet_handler(msg: Message):
    await msg.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{get_user_bal(msg.from_user.id)}</b>\n\nPlease select your funding process.", reply_markup=balance_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 User Profile")
async def profile_handler(msg: Message):
    uid = msg.from_user.id
    await msg.answer(text=f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{get_user_bal(uid)}\n📅 <b>Join Date:</b> {get_user_jd(uid)}", parse_mode="HTML")

@dp.message(F.text == "🔙 Back to Main Menu")
async def back_handler(msg: Message):
    await msg.answer("👋 Welcome to SKY OTP BOT.", reply_markup=main_kb())

@dp.message(F.text == "🛍️ Buy Telegram Account")
async def buy_tg(msg: Message):
    await msg.answer("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode="HTML")

@dp.message(F.text == "➕ Add Funds")
async def add_funds_handler(msg: Message):
    import qrcode
    uid = msg.from_user.id
    txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
    
    claim_id = str(random.randint(1000, 9999))
    pending_claims[claim_id] = {"uid": uid, "txn": txn, "session_amt": 0}
    
    img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay <b>any amount</b> you wish to add to your wallet.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"req:{claim_id}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

# FIXED: Correct unpacking format applied to colon delimiter splits
@dp.callback_query(F.data.startswith("req:"))
async def handle_status_check(cb: CallbackQuery, state: FSMContext):
    _, claim_id = cb.data.split(":")
    if claim_id not in pending_claims:
        await cb.answer("❌ This payment session expired or has already been reviewed.")
        return
        
    await state.update_data(current_claim_id=claim_id)
    
    await cb.message.edit_caption(
        caption="⚠️ <b>Payment Verification Required</b>\n\n"
                "Please upload and send a clear <b>screenshot image</b> of your transaction payment receipt now.\n\n"
                "<i>*Note: Your deposit request will not reach the administrator without your screenshot image submission.</i>", 
        parse_mode="HTML"
    )
    
    await state.set_state(DepositStates.waiting_for_screenshot)
    await cb.answer()

@dp.message(DepositStates.waiting_for_screenshot, F.photo)
async def process_payment_screenshot(msg: Message, state: FSMContext):
    state_data = await state.get_data()
    claim_id = state_data.get("current_claim_id")
    
    if not claim_id or claim_id not in pending_claims:
        await msg.answer("❌ Your payment tracking context expired. Please tap '➕ Add Funds' to create a new request.")
        await state.clear()
        return

    uid = pending_claims[claim_id]["uid"]
    txn = pending_claims[claim_id]["txn"]
    
    photo_file_id = msg.photo[-1].file_id
    
    await msg.answer("⏳ <b>Screenshot Uploaded!</b>\nYour verification request along with your screenshot has been dispatched to the admin. Please await confirmation.", parse_mode="HTML")
    await state.clear()
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(text="📩 Confirm & Send Receipt", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    
    admin_text = f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0"
    await bot.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_file_id, caption=admin_text, reply_markup=akb, parse_mode="HTML")

@dp.message(DepositStates.waiting_for_screenshot)
async def process_invalid_screenshot_type(msg: Message):
    await msg.answer("❌ <b>Invalid File Type!</b>\n\nYou must send a <b>screenshot image</b> as proof. Text strings or stickers cannot be accepted for manual review. Please send the image.")

@dp.callback_query(F.data.startswith("add:"))
async def admin_add_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    _, claim_id, add_amt = cb.data.split(":")
    add_amt = int(add_amt)
    
    if claim_id not in pending_claims:
        await cb.message.edit_caption(caption="❌ This transaction claim tracking context has expired.")
        return
        
    uid = pending_claims[claim_id]["uid"]
    txn = pending_claims[claim_id]["txn"]
    
    pending_claims[claim_id]["session_amt"] += add_amt
    current_total = pending_claims[claim_id]["session_amt"]
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (add_amt, uid))
        conn.commit()
        
    await cb.answer(f"Added +₹{add_amt}")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(text=f"📩 Confirm & Send ₹{current_total}", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    await cb.message.edit_caption(caption=f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{current_total}", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("send:"))
async def admin_send_receipt_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    _, claim_id = cb.data.split(":")
    
    if claim_id not in pending_claims:
