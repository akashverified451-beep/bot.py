import os
import re
import random
import logging
import io
import asyncio
from datetime import datetime
import psycopg
import qrcode
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# Set up logging for Render dashboard monitoring
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load secure configuration states
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAGN9YLH9ykLKDtvewuJydI3efFkW5grAQo")
API_ID = int(os.getenv("API_ID", "33033843")) 
API_HASH = os.getenv("API_HASH", "27d91aac298b61038f19ee5c1b1f3f48")

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

# Database Connection Pool
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

# Dictionary to hold the monitoring client sessions
active_clients = {}

def get_db_connection():
    """Establishes an isolated bridge line with the Render PostgreSQL engine."""
    return psycopg.connect(DATABASE_URL)

def init_db():
    """Create required tables if they don't exist in PostgreSQL."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS users (uid BIGINT PRIMARY KEY, balance INT DEFAULT 0, join_date TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid BIGINT, txn TEXT, session_amt INT DEFAULT 0)")
            cursor.execute("CREATE TABLE IF NOT EXISTS active_orders (phone_number TEXT, uid BIGINT, status TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS available_accounts (phone_number TEXT, api_id TEXT, api_hash TEXT, string_session TEXT)")
            conn.commit()
    logging.info("PostgreSQL structural database tables checked/created successfully.")

def get_user_bal(uid):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
            row = cursor.fetchone()
            return row[0] if row else 0

def get_user_jd(uid):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT join_date FROM users WHERE uid = %s", (uid,))
            row = cursor.fetchone()
            return row[0] if row else "N/A"

# Initialize Telethon Bot Client Instance (Clean Session to avoid locking)
bot = TelegramClient("sky_otp_master_session", API_ID, API_HASH)

# --- Keyboard Builders ---
def main_kb():
    return [
        [Button.text("🛍️ Buy Telegram Account", resize=True), Button.text("🗨️ Buy Whatsapp OTP", resize=True)],
        [Button.text("💼 Wallet", resize=True), Button.text("👤 User Profile", resize=True)]
    ]

def balance_kb():
    return [
        [Button.text("➕ Add Funds", resize=True)],
        [Button.text("🔙 Back to Main Menu", resize=True)]
    ]

# --- Force Command & Interaction Handlers ---
@bot.on(events.NewMessage)
async def global_message_handler(event):
    if not event.is_private:
        return
        
    uid = event.sender_id
    text = event.text or ""
    
    # Handle /start Command
    if text.startswith("/start"):
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
                if not cursor.fetchone():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0, %s)", (uid, now))
                    conn.commit()
        await event.respond("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", buttons=main_kb())
        return

    # Handle Wallet Button
    if text == "💼 Wallet":
        bal = get_user_bal(uid)
        await event.respond(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", buttons=balance_kb(), parse_mode='html')
    
    # Handle Profile Button
    elif text == "👤 User Profile":
        bal = get_user_bal(uid)
        jd = get_user_jd(uid)
        await event.respond(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}", parse_mode='html')
    
    # Handle Back Button
    elif text == "🔙 Back to Main Menu":
        await event.respond("👋 Welcome to SKY OTP BOT.", buttons=main_kb())
        
    # Handle Buy Button
    elif text == "🛍️ Buy Telegram Account":
        await event.respond("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode='html')

    # Handle Add Funds Button
    elif text == "➕ Add Funds":
        txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
        claim_id = str(random.randint(1000, 9999))
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO claims (claim_id, uid, txn) VALUES (%s, %s, %s)", (claim_id, uid, txn))
                conn.commit()
        
        img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        buf.name = "qr.png" 
        
        cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ <b>CRITICAL STEP:</b> After making the payment, simply upload your <b>Payment Screenshot</b> straight into this chat window to notify the admin.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
        
        await event.respond(
            cap,
            file=buf,
            buttons=[[Button.inline("❌ Cancel", data="cancel")]],
            parse_mode='html'
        )
        
    # Handle Screenshot Uploads
    elif event.photo:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT claim_id, txn FROM claims WHERE uid = %s ORDER BY claim_id DESC LIMIT 1", (uid,))
                row = cursor.fetchone()
            
        if not row:
            await event.respond("❌ You don't have any active deposit generation requests open. Please click '➕ Add Funds' first.")
            return
            
        claim_id, txn = row[0], row[1]
        await event.respond("⏳ <b>Screenshot Received!</b>\nYour proof has been sent to the admin for manual verification.", parse_mode='html')
        
        akb = [
            [Button.inline("➕ ₹1", data=f"add:{claim_id}:1"), Button.inline("➕ ₹5", data=f"add:{claim_id}:5")],
            [Button.inline("➕ ₹10", data=f"add:{claim_id}:10"), Button.inline("➕ ₹50", data=f"add:{claim_id}:50")],
            [Button.inline("➕ ₹100", data=f"add:{claim_id}:100"), Button.inline("➕ ₹500", data=f"add:{claim_id}:500")],
            [Button.inline("📩 Confirm & Send", data=f"send:{claim_id}")],
            [Button.inline("❌ Decline Request", data=f"deny:{claim_id}")]
        ]
        
        admin_text = f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹0"
        await bot.send_message(entity=ADMIN_TELEGRAM_ID, message=admin_text, file=event.photo, buttons=akb, parse_mode='html')

# --- Admin Callback Button Processors ---
@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"add:")))
async def admin_add_click(event):
    if event.sender_id != ADMIN_TELEGRAM_ID:
        return
    
    data_str = event.data.decode('utf-8')
    _, claim_id, add_amt = data_str.split(":")
    add_amt = int(add_amt)
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = %s", (claim_id,))
            row = cursor.fetchone()
            
            if not row:
                await event.edit("❌ This claim has expired or was already closed.")
                return
                
            uid, txn, session_amt = row[0], row[1], row[2]
            new_session_amt = session_amt + add_amt
            
            cursor.execute("UPDATE claims SET session_amt = %s WHERE claim_id = %s", (new_session_amt, claim_id))
            cursor.execute("UPDATE users SET balance = balance + %s WHERE uid = %s", (add_amt, uid))
            conn.commit()
        
    await event.answer(f"Added +₹{add_amt}")
    
    akb = [
        [Button.inline("➕ ₹1", data=f"add:{claim_id}:1"), Button.inline("➕ ₹5", data=f"add:{claim_id}:5")],
        [Button.inline("➕ ₹10", data=f"add:{claim_id}:10"), Button.inline("➕ ₹50", data=f"add:{claim_id}:50")],
        [Button.inline("➕ ₹100", data=f"add:{claim_id}:100"), Button.inline("➕ ₹500", data=f"add:{claim_id}:500")],
        [Button.inline(f"📩 Confirm & Send ₹{new_session_amt}", data=f"send:{claim_id}")],
        [Button.inline("❌ Decline Request", data=f"deny:{claim_id}")]
    ]
    
    updated_text = f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{new_session_amt}"
    await event.edit(updated_text, buttons=akb, parse_mode='html')

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"send:")))
async def admin_send_receipt_click(event):
    if event.sender_id != ADMIN_TELEGRAM_ID:
        return
        
    data_str = event.data.decode('utf-8')
    _, claim_id = data_str.split(":")
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = %s", (claim_id,))
            row = cursor.fetchone()
            
            if not row:
                await event.edit("❌ Already closed.")
                return
                
