import os
import random
import logging
import io
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart

# Production log tracking config
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid INTEGER, txn TEXT, session_amt INTEGER DEFAULT 0)")
        conn.commit()

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
    bal = get_user_bal(msg.from_user.id)
    await msg.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", reply_markup=balance_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 User Profile")
async def profile_handler(msg: Message):
    uid = msg.from_user.id
    bal = get_user_bal(uid)
    jd = get_user_jd(uid)
    await msg.answer(text=f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}", parse_mode="HTML")

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
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO claims (claim_id, uid, txn) VALUES (?, ?, ?)", (claim_id, uid, txn))
        conn.commit()
    
    img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ <b>CRITICAL STEP:</b> After making the payment, simply upload your <b>Payment Screenshot</b> straight into this chat window to notify the admin.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

@dp.message(F.photo)
async def process_stateless_screenshot(msg: Message):
    uid = msg.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT claim_id, txn FROM claims WHERE uid = ? ORDER BY claim_id DESC LIMIT 1", (uid,)).fetchone()
        
    if not row:
        await msg.answer("❌ You don't have any active deposit generation requests open. Please click '➕ Add Funds' first.")
        return
        
    claim_id, txn = row[0], row[1]
    photo_file_id = msg.photo[-1].file_id
    
    await msg.answer("⏳ <b>Screenshot Received!</b>\nYour proof has been sent to the admin for manual verification.")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(text="📩 Confirm & Send", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    
    admin_text = f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0"
    await bot.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_file_id, caption=admin_text, reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("add:"))
async def admin_add_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, claim_id, add_amt = cb.data.split(":")
    add_amt = int(add_amt)
    
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if not row:
            await cb.message.edit_caption(caption="❌ This claim has expired or was already closed.")
            return
        uid, txn, session_amt = row[0], row[1], row[2]
        new_session_amt = session_amt + add_amt
        
        conn.execute("UPDATE claims SET session_amt = ? WHERE claim_id = ?", (new_session_amt, claim_id))
        conn.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (add_amt, uid))
        conn.commit()
        
    await cb.answer(f"Added +₹{add_amt}")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(text=f"📩 Confirm & Send ₹{new_session_amt}", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    await cb.message.edit_caption(caption=f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{new_session_amt}", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("send:"))
async def admin_send_receipt_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, claim_id = cb.data.split(":")
    
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if not row:
            await cb.message.edit_caption(caption="❌ Already closed.")
            return
        uid, txn, final_session_amt = row[0], row[1], row[2]
        conn.execute("DELETE FROM claims WHERE claim_id = ?", (claim_id,))
        conn.commit()
        
    current_bal = get_user_bal(uid)
    await cb.message.edit_caption(caption=f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.")
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try:
        await bot.send_message(chat_id=uid, text=rcpt, parse_mode="HTML")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("deny:"))
async def admin_deny_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, claim_id = cb.data.split(":")
    
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT uid FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if row:
            uid = row[0]
            conn.execute("DELETE FROM claims WHERE claim_id = ?", (claim_id,))
            conn.commit()
