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
# IMPORTANT: Revoke your current Bot Token via @BotFather and set these inside Render Settings!
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAGN9YLH9ykLKDtvewuJydI3efFkW5grAQo")
API_ID = int(os.getenv("API_ID", "33033843")) 
API_HASH = os.getenv("API_HASH", "27d91aac298b61038f19ee5c1b1f3f48")

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

# Database Connection Pool
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

# Dictionary to hold the monitoring client sessions
active_clients = {}

async def get_db_connection():
    """Establishes an isolated non-blocking bridge line with the Render PostgreSQL engine."""
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def init_db():
    """Create required tables asynchronously if they don't exist in PostgreSQL."""
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("CREATE TABLE IF NOT EXISTS users (uid BIGINT PRIMARY KEY, balance INT DEFAULT 0, join_date TEXT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid BIGINT, txn TEXT, session_amt INT DEFAULT 0)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS active_orders (phone_number TEXT, uid BIGINT, status TEXT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS available_accounts (phone_number TEXT, api_id TEXT, api_hash TEXT, string_session TEXT)")
            await conn.commit()
    logging.info("PostgreSQL structural database tables checked/created successfully.")

async def get_user_bal(uid):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_user_jd(uid):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT join_date FROM users WHERE uid = %s", (uid,))
            row = await cursor.fetchone()
            return row[0] if row else "N/A"

# Initialize Telethon Bot Client Instance
bot = TelegramClient("session_data/sky_otp_master_session_v3", API_ID, API_HASH)

# --- Keyboard Builders Matching the New Style ---
def main_kb():
    return [
        [Button.text("🛍️ Buy Telegram Account", resize=True)],
        [Button.text("🗨️ Buy Whatsapp OTP", resize=True)],
        [Button.text("💼 Wallet", resize=True), Button.text("👤 User Profile", resize=True)],
        [Button.text("🆘 Support", resize=True), Button.text("🎁 Promocode", resize=True)]
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
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
                if not await cursor.fetchone():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0, %s)", (uid, now))
                    await conn.commit()
        # ✅ MATCHED: Text matches your friend's welcoming style
        await event.respond("👋 Hello! Welcome to SKY OTP Bot.\n\n✨ Use the buttons below to explore our services.", buttons=main_kb())
        return

    # Handle Wallet Button
    if text == "💼 Wallet":
        bal = await get_user_bal(uid)
        await event.respond(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", buttons=balance_kb(), parse_mode='html')
    
    # Handle Profile Button
    elif text == "👤 User Profile":
        bal = await get_user_bal(uid)
        jd = await get_user_jd(uid)
        await event.respond(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}", parse_mode='html')
    
    # Handle Back Button
    elif text == "🔙 Back to Main Menu":
        await event.respond("👋 Hello! Welcome to SKY OTP Bot.\n\n✨ Use the buttons below to explore our services.", buttons=main_kb())
        
    # Handle Buy Buttons
    elif text == "🛍️ Buy Telegram Account":
        await event.respond("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode='html')

    elif text == "🗨️ Buy Whatsapp OTP":
        await event.respond("🔄 <b>Live WhatsApp OTP Activation Enabled</b>\n\nPlease request your verification code now.", parse_mode='html')

    # ✅ UPDATED: Clean English layout with clickable Instagram Link
    elif text == "🎁 Promocode":
        promo_msg = (
            "<b>Follow me on Instagram to get exclusive promo codes:</b>\n\n"
            "⬇️ <b>Instagram Profile:</b>\n"
            "<a href='https://instagram.com'>@akash.verified</a>"
        )
        await event.respond(promo_msg, parse_mode='html', link_preview=False)

    # ✅ ADDED: Professional English formatting for the Support button handler
    elif text == "🆘 Support":
        support_msg = (
            "✈️ <b>To contact our official support team, please reach out via the details below:</b>\n\n"
            "📱 <b>Telegram ID:</b> @Sky_Verified\n"
            "⏰ <b>Working Hours:</b> 10:00 AM to 10:00 PM"
        )
        await event.respond(support_msg, parse_mode='html')

    
    # Handle Add Funds Button
    elif text == "➕ Add Funds":
        txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
        claim_id = str(random.randint(1000, 9999))
        
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("INSERT INTO claims (claim_id, uid, txn) VALUES (%s, %s, %s)", (claim_id, uid, txn))
                await conn.commit()
        
        img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        buf.name = "qr.png" 
        
        # ✅ UPDATED: Message formatting updated as requested
        cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ : After making the payment, simply upload your Payment Screenshot for verification the payment.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
        
        await event.respond(
            cap,
            file=buf,
            buttons=[[Button.inline("❌ Cancel Request", data=f"cancel:{claim_id}")]],
            parse_mode='html'
        )
    
    # Handle Screenshot Uploads
    elif event.photo:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT claim_id, txn FROM claims WHERE uid = %s ORDER BY claim_id DESC LIMIT 1", (uid,))
                row = await cursor.fetchone()
            
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
    
    await event.answer()  # Stops the loading spinner instantly
    
    data_str = event.data.decode('utf-8')
    _, claim_id, add_amt = data_str.split(":")
    add_amt = int(add_amt)
    
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = %s", (str(claim_id),))
            row = await cursor.fetchone()
            
            if not row:
                await event.edit("❌ This claim has expired or was already closed.")
                return
                
            # ✅ FIXED: Correct and safe indexing for tuple fields
            uid = row[0]
            txn = row[1]
            session_amt = row[2]
            new_session_amt = session_amt + add_amt
            
            # Update the temporary claim total and add the balance directly to the user
            await cursor.execute("UPDATE claims SET session_amt = %s WHERE claim_id = %s", (new_session_amt, str(claim_id)))
            await cursor.execute("UPDATE users SET balance = balance + %s WHERE uid = %s", (add_amt, uid))
            await conn.commit()
    
    akb = [
        [Button.inline("➕ ₹1", data=f"add:{claim_id}:1"), Button.inline("➕ ₹5", data=f"add:{claim_id}:5")],
        [Button.inline("➕ ₹10", data=f"add:{claim_id}:10"), Button.inline("➕ ₹50", data=f"add:{claim_id}:50")],
        [Button.inline("➕ ₹100", data=f"add:{claim_id}:100"), Button.inline("➕ ₹500", data=f"add:{claim_id}:500")],
        [Button.inline(f"📩 Confirm & Send ₹{new_session_amt}", data=f"send:{claim_id}")],
        [Button.inline("❌ Decline Request", data=f"deny:{claim_id}")]
    ]
    
    updated_text = f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN Ref:</b> <code>{txn}</code>\n\n💰 <b>Session Added So Far:</b> ₹{new_session_amt}"
    await event.edit(updated_text, buttons=akb, parse_mode='html')


# --- 2. FIXED CONFIRM & SEND BUTTON HANDLER ---
@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"send:")))
async def admin_send_receipt_click(event):
    if event.sender_id != ADMIN_TELEGRAM_ID:
        return
        
    await event.answer()  # Stops the loading spinner instantly
    data_str = event.data.decode('utf-8')
    _, claim_id = data_str.split(":")
    
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT uid, txn, session_amt FROM claims WHERE claim_id = %s", (str(claim_id),))
            row = await cursor.fetchone()
            
            if not row:
                await event.edit("❌ Already closed or claim not found.")
                return
                
            # ✅ FIXED: Using identical correct indexing matching the add handler
            uid = row[0]
            txn = row[1]
            session_amt = row[2]
            
            # Remove completed claim tracking log entry
            await cursor.execute("DELETE FROM claims WHERE claim_id = %s", (str(claim_id),))
            await conn.commit()

    # Inform the user and complete the admin view update
    try:
        await bot.send_message(entity=uid, message=f"✅ <b>Deposit Confirmed!</b>\n\n💰 ₹{session_amt} has been successfully added to your wallet balance.", parse_mode='html')
        await event.edit(f"✅ Approved and sent ₹{session_amt} to user <code>{uid}</code>", parse_mode='html')
    except Exception as e:
        logging.error(f"Failed to send confirmation message to user: {e}")
        await event.edit(f"✅ Approved in DB, but couldn't message user. Amount: ₹{session_amt}", parse_mode='html')

# --- 3. FIXED CANCEL & DENY BUTTON HANDLER ---
@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"deny:") or d.startswith(b"cancel:")))
async def cancel_or_deny_click(event):
    await event.answer()  # Stops the loading spinner instantly
    
    data_str = event.data.decode('utf-8')
    
    if ":" in data_str:
        action, claim_id = data_str.split(":", 1)
    else:
        await event.edit("❌ This request data structure is broken.")
        return
    
    async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("DELETE FROM claims WHERE claim_id = %s", (str(claim_id),))
            await conn.commit()
            
    await event.edit("❌ Request has been declined and cancelled successfully.")

# --- Startup and Initialization Loop ---
async def main():
    # 1. Initialize structural DB layout
    init_db()
    
    # 2. Start the Telethon Bot Client using the token
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("🚀 SKY OTP Master Bot is now online and listening for events...")
    
    # 3. Keep the script alive and running
    await bot.run_until_disconnected()

if __name__ == "__main__":
    # Run the async loop
    asyncio.run(main())
