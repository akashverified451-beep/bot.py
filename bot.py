import os
import random
import logging
import io
import sqlite3
from datetime import datetime
from telethon import TelegramClient, events, Button

# Set up logging for Render dashboard monitoring
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load secure configuration states
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAGN9YLH9ykLKDtvewuJydI3efFkW5grAQo")
API_ID = int(os.getenv("API_ID", "35742827")) 
API_HASH = os.getenv("API_HASH", "f2955d75aa8ace7c421a2bb6152c5dd3")

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

# Database Configuration
DB_PATH = "production.db"

# Initialize Telethon Bot Client Instance
bot = TelegramClient("sky_otp_bot_session_v2", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid INTEGER, txn TEXT, session_amt INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()
    logging.info("Fresh database tables created successfully.")

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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        check_user = cursor.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone()
        if not check_user:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
            conn.commit()
        conn.close()
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
        
        await event.respond(
            cap,
            file=buf,
            buttons=[[Button.inline("❌ Cancel", data="cancel")]],
            parse_mode='html'
        )
        
    # Handle Screenshot Uploads
    elif event.photo:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        row = cursor.execute("SELECT claim_id, txn FROM claims WHERE uid = ? ORDER BY claim_id DESC LIMIT 1", (uid,)).fetchone()
        conn.close()
            
        if not row:
            await event.respond("❌ You don't have any active deposit generation requests open. Please click '➕ Add Funds' first.")
            return
            
        claim_id = row[0]
        txn = row[1]
        
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    
    if not row:
        conn.close()
        await event.edit("❌ This claim has expired or was already closed.")
        return
        
    uid = row[0]
    txn = row[1]
    session_amt = row[2]
    new_session_amt = session_amt + add_amt
    
    cursor.execute("UPDATE claims SET session_amt = ? WHERE claim_id = ?", (new_session_amt, claim_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (add_amt, uid))
    conn.commit()
    conn.close()
        
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    
    if not row:
        conn.close()
        await event.edit("❌ Already closed.")
        return
        
    uid = row[0]
    txn = row[1]
    final_session_amt = row[2]
    
    cursor.execute("DELETE FROM claims WHERE claim_id = ?", (claim_id,))
    conn.commit()
    conn.close()
        
    current_bal = get_user_bal(uid)
    await event.edit(f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.", parse_mode='html')
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try:
        await bot.send_message(entity=uid, message=rcpt, parse_mode='html')
    except Exception:
        pass

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"deny:")))
async def admin_deny_click(event):
    if event.sender_id != ADMIN_TELEGRAM_ID:
        return
        
    data_str = event.data.decode('utf-8')
    _, claim_id = data_str.split(":")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
