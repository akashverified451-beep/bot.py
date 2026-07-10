import os
import random
import logging
import io
import sqlite3
import asyncio
from datetime import datetime
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import qrcode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

class DepositStates(StatesGroup):
    waiting_for_screenshot = State()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
        conn.commit()

def get_user_bal(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT balance FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else 0

def get_user_jd(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT join_date FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else "N/A"

def register_user(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone()
        if not row:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
            conn.commit()

def update_balance(uid, amount):
    register_user(uid)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amount, uid))
        conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
    register_user(msg.from_user.id)
    await msg.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=main_kb())

@dp.message(F.text == "💼 Wallet")
async def wallet_handler(msg: Message):
    register_user(msg.from_user.id)
    await msg.answer(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{get_user_bal(msg.from_user.id)}</b>\n\nPlease select your funding process.", reply_markup=balance_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 User Profile")
async def profile_handler(msg: Message):
    register_user(msg.from_user.id)
    uid = msg.from_user.id
    await msg.answer(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{get_user_bal(uid)}\n📅 <b>Join Date:</b> {get_user_jd(uid)}", parse_mode="HTML")

@dp.message(F.text == "🔙 Back to Main Menu")
async def back_handler(msg: Message):
    await msg.answer("👋 Welcome to SKY OTP BOT.", reply_markup=main_kb())

@dp.message(F.text == "🛍️ Buy Telegram Account")
async def buy_tg(msg: Message):
    await msg.answer("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode="HTML")

@dp.message(StateFilter(None), F.text == "➕ Add Funds")
async def add_funds_handler(msg: Message):
    uid = msg.from_user.id
    txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
    img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay <b>any amount</b> you wish to add to your wallet.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"req_{uid}_{txn}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("req_"))
async def handle_status_check(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("_")
    uid = parts[1]
    txn = parts[2]
    await state.set_state(DepositStates.waiting_for_screenshot)
    await state.update_data(txn=txn)
    await cb.answer()
    await cb.message.answer("📸 Please send a <b>screenshot of your payment receipt</b> now to submit for admin approval:", parse_mode="HTML")

@dp.message(DepositStates.waiting_for_screenshot, F.photo)
async def process_screenshot_submission(msg: Message, state: FSMContext):
    state_data = await state.get_data()
    txn = state_data.get("txn", "N/A")
    uid = msg.from_user.id
    await state.clear()
    
    photo_id = msg.photo[-1].file_id
    await msg.answer("⏳ <b>Receipt submitted!</b> The admin is verifying your transaction details now. Thank you.", parse_mode="HTML", reply_markup=main_kb())
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add_{uid}_{txn}_1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add_{uid}_{txn}_5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add_{uid}_{txn}_10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add_{uid}_{txn}_50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add_{uid}_{txn}_100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add_{uid}_{txn}_500")],
        [InlineKeyboardButton(text="📩 Confirm & Send Receipt", callback_data=f"send_{uid}_{txn}_0")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny_{uid}")]
    ])
    await bot.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_id, caption=f"🚨 <b>New Deposit Verification Request!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0", reply_markup=akb, parse_mode="HTML")

@dp.message(DepositStates.waiting_for_screenshot)
async def invalid_screenshot_submission(msg: Message):
    await msg.answer("❌ Invalid format. Please send an actual <b>Image/Screenshot</b> of your transaction payment receipt:")

@dp.callback_query(F.data.startswith("add_"))
async def admin_add_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    parts = cb.data.split("_")
    uid = int(parts[1])
    txn = parts[2]
    amt = int(parts[3])
    
    current_caption = cb.message.caption if cb.message.caption else ""
    session_amt = 0
    if "Session Added So Far: ₹" in current_caption:
        try: session_amt = int(current_caption.split("Session Added So Far: ₹")[1].strip())
        except Exception: session_amt = 0
        
    new_session_total = session_amt + amt
    update_balance(uid, amt)
    await cb.answer(f"Added +₹{amt}")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add_{uid}_{txn}_1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add_{uid}_{txn}_5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add_{uid}_{txn}_10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add_{uid}_{txn}_50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add_{uid}_{txn}_100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add_{uid}_{txn}_500")],
        [InlineKeyboardButton(text=f"📩 Confirm & Send ₹{new_session_total}", callback_data=f"send_{uid}_{txn}_{new_session_total}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny_{uid}")]
    ])
    await cb.message.edit_caption(caption=f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{new_session_total}", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("send_"))
async def admin_send_receipt_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    parts = cb.data.split("_")
    uid = int(parts[1])
    txn = parts[2]
    final_session_amt = int(parts[3])
    
    current_bal = get_user_bal(uid)
    await cb.message.edit_caption(caption=f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.")
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try: await bot.send_message(chat_id=uid, text=rcpt, parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("deny_"))
async def admin_deny_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.split("_")[1])
    await cb.message.edit_caption(caption=f"❌ Denied request from user <code>{uid}</code>.")
    try: await bot.send_message(chat_id=uid, text="❌ Your transaction review request was declined by the administrator.")
    except Exception: pass

@dp.callback_query(F.data == "cancel")
async def cancel_click(cb: CallbackQuery):
    try: await cb.message.delete()
    except Exception: pass

app = FastAPI()

