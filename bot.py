import sys
import asyncio

# --- Python 3.12+ / 3.14 Pyrogram Lifecycle Hotfix ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import os
import random
import logging
import io
import sqlite3
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)

# Set up logging for Render dashboard monitoring
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load secure configuration states
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

# Initialize Pyrogram Bot Client Instance
app = Client(
    "sky_otp_bot",
    bot_token=BOT_TOKEN
)

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid INTEGER, txn TEXT, session_amt INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

def get_user_bal(uid):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT balance FROM users WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    return row[0] if row else 0

def get_user_jd(uid):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT join_date FROM users WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    return row[0] if row else "N/A"

# --- Keyboard Builders ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛍️ Buy Telegram Account")],
        [KeyboardButton("🗨️ Buy Whatsapp OTP")],
        [KeyboardButton("💼 Wallet"), KeyboardButton("👤 User Profile")]
    ], resize_keyboard=True)

def balance_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Add Funds")],
        [KeyboardButton("🔙 Back to Main Menu")]
    ], resize_keyboard=True)

# --- Command & Interaction Handlers ---
@app.on_message(filters.command("start"))
async def cmd_start(client: Client, msg: Message):
    uid = msg.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    check_user = cursor.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone()
    if not check_user:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
        conn.commit()
    conn.close()
    await msg.reply_text("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=main_kb())

@app.on_message(filters.text & filters.private)
async def text_menu_routing(client: Client, msg: Message):
    uid = msg.from_user.id
    text = msg.text

    if text == "💼 Wallet":
        bal = get_user_bal(uid)
        await msg.reply_text(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", reply_markup=balance_kb())
    
    elif text == "👤 User Profile":
        bal = get_user_bal(uid)
        jd = get_user_jd(uid)
        await msg.reply_text(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}")
    
    elif text == "🔙 Back to Main Menu":
        await msg.reply_text("👋 Welcome to SKY OTP BOT.", reply_markup=main_kb())
        
    elif text == "🛍️ Buy Telegram Account":
        await msg.reply_text("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.")

    elif text == "➕ Add Funds":
        import qrcode
        txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
        claim_id = str(random.randint(1000, 9999))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO claims (claim_id, uid, txn) VALUES (?, ?, ?)", (claim_id, uid, txn))
        conn.commit()
        conn.close()
        
        img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        buf.name = "qr.png" 
        
        cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ <b>CRITICAL STEP:</b> After making the payment, simply upload your <b>Payment Screenshot</b> straight into this chat window to notify the admin.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
        
        await msg.reply_photo(
            photo=buf, 
            caption=cap, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )

# Catch client payment receipt uploads statelessly
@app.on_message(filters.photo & filters.private)
async def process_stateless_screenshot(client: Client, msg: Message):
    uid = msg.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT claim_id, txn FROM claims WHERE uid = ? ORDER BY claim_id DESC LIMIT 1", (uid,)).fetchone()
    conn.close()
        
    if not row:
        await msg.reply_text("❌ You don't have any active deposit generation requests open. Please click '➕ Add Funds' first.")
        return
        
    claim_id = row[0]
    txn = row[1]
    photo_file_id = msg.photo.file_id
    
    await msg.reply_text("⏳ <b>Screenshot Received!</b>\nYour proof has been sent to the admin for manual verification.")
    
    akb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton("➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton("➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton("➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton("➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton("➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton("📩 Confirm & Send", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton("❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    
    admin_text = f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0"
    await client.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_file_id, caption=admin_text, reply_markup=akb)

# --- Admin Interactivity Callback Query Processors ---
@app.on_callback_query(filters.regex("^add:"))
async def admin_add_click(client: Client, cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, claim_id, add_amt = cb.data.split(":")
    add_amt = int(add_amt)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    
    if not row:
        conn.close()
        await cb.message.edit_caption("❌ This claim has expired or was already closed.")
        return
        
    uid = row[0]
    txn = row[1]
    session_amt = row[2]
    new_session_amt = session_amt + add_amt
    
    cursor.execute("UPDATE claims SET session_amt = ? WHERE claim_id = ?", (new_session_amt, claim_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (add_amt, uid))
    conn.commit()
    conn.close()
        
    await cb.answer(f"Added +₹{add_amt}")
    
    akb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ₹1", callback_data=f"add:{claim_id}:1"), InlineKeyboardButton("➕ ₹5", callback_data=f"add:{claim_id}:5")],
        [InlineKeyboardButton("➕ ₹10", callback_data=f"add:{claim_id}:10"), InlineKeyboardButton("➕ ₹50", callback_data=f"add:{claim_id}:50")],
        [InlineKeyboardButton("➕ ₹100", callback_data=f"add:{claim_id}:100"), InlineKeyboardButton("➕ ₹500", callback_data=f"add:{claim_id}:500")],
        [InlineKeyboardButton(f"📩 Confirm & Send ₹{new_session_amt}", callback_data=f"send:{claim_id}")],
        [InlineKeyboardButton("❌ Decline Request", callback_data=f"deny:{claim_id}")]
    ])
    await cb.message.edit_caption(f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{new_session_amt}", reply_markup=akb)

@app.on_callback_query(filters.regex("^send:"))
async def admin_send_receipt_click(client: Client, cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, claim_id = cb.data.split(":")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    
    if not row:
        conn.close()
        await cb.message.edit_caption("❌ Already closed.")
        return
        
    uid = row[0]
    txn = row[1]
    final_session_amt = row[2]
    
    cursor.execute("DELETE FROM claims WHERE claim_id = ?", (claim_id,))
    conn.commit()
    conn.close()
        
    current_bal = get_user_bal(uid)
    await cb.message.edit_caption(f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.")
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try:
        await client.send_message(chat_id=uid, text=rcpt)
    except Exception:
        pass

