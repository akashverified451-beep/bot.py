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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

# Dictionaries to track claim states safely without crashing FSM Context
pending_claims = {}
user_screenshot_state = {}

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
    
    img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay <b>any amount</b> you wish to add to your wallet.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"req:{txn}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

# STEP 1: Ask user for the screenshot when they tap check status
@dp.callback_query(F.data.startswith("req:"))
async def handle_status_check(cb: CallbackQuery):
    txn = cb.data.split(":")[1]
    uid = cb.from_user.id
    
    # Put user in screenshot-waiting mode linked to their Transaction Ref
    user_screenshot_state[uid] = txn
    
    await cb.answer()
    await cb.message.answer("📸 Please send a <b>screenshot of your payment receipt</b> now to submit for admin approval:", parse_mode="HTML")

# STEP 2: Process the uploaded screenshot and send it instantly to you
@dp.message(F.photo)
async def process_screenshot_submission(msg: Message):
    uid = msg.from_user.id
    
    # Check if the user was actually supposed to send a screenshot
    if uid not in user_screenshot_state:
        return
        
    txn = user_screenshot_state[uid]
    del user_screenshot_state[uid] # Clear user state immediately
    
    claim_id = str(random.randint(1000, 9999))
    pending_claims[claim_id] = {"uid": uid, "txn": txn, "session_amt": 0}
    
    photo_id = msg.photo[-1].file_id
    await msg.answer("⏳ <b>Receipt submitted!</b> The admin is verifying your transaction details now. Thank you.", parse_mode="HTML", reply_markup=main_kb())
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(text="📩 Confirm & Send Receipt", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    
    await bot.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_id, caption=f"🚨 <b>New Deposit Verification Request!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("add:"))
async def admin_add_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    _, claim_id, add_amt = cb.data.split(":")
    add_amt = int(add_amt)
    
    if claim_id not in pending_claims:
        await cb.answer("❌ This transaction claim has expired.", show_alert=True)
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
        await cb.message.edit_caption(caption="❌ Expired session context.")
        return
        
    uid = pending_claims[claim_id]["uid"]
    txn = pending_claims[claim_id]["txn"]
    final_session_amt = pending_claims[claim_id]["session_amt"]
    
    del pending_claims[claim_id]
    
    current_bal = get_user_bal(uid)
    await cb.message.edit_caption(caption=f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.")
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try: await bot.send_message(chat_id=uid, text=rcpt, parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("deny:"))
async def admin_deny_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    _, claim_id = cb.data.split(":")
    
    if claim_id in pending_claims:
        uid = pending_claims[claim_id]["uid"]
        del pending_claims[claim_id]
        await cb.message.edit_caption(caption=f"❌ Denied request from user <code>{uid}</code>.")
        try: await bot.send_message(chat_id=uid, text="❌ Your transaction review request was declined by the administrator.")
        except Exception: pass

@dp.callback_query(F.data == "cancel")
