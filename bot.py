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

# Initialize Telethon Bot Client Instance using your storage disk path
bot = TelegramClient("session_data/sky_otp_master_session_v3", API_ID, API_HASH)

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

# --- Keyboard Builders Matching the Custom Style ---
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

# --- Master Message Interaction Handler ---
@bot.on(events.NewMessage)
async def global_message_handler(event):
    if getattr(event, "handled", False) or not event.is_private:
        return
        
    uid = event.sender_id
    text = event.text or ""
    
    # 1. Handle /start Command
    if text.startswith("/start"):
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
                if not await cursor.fetchone():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0, %s)", (uid, now))
                    await conn.commit()
        await event.respond("👋 Hello! Welcome to SKY OTP Bot.\n\n✨ Use the buttons below to explore our services.", buttons=main_kb())
        event.handled = True
        return

    # 2. Handle Wallet Button
    elif text == "💼 Wallet":
        bal = await get_user_bal(uid)
        await event.respond(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", buttons=balance_kb(), parse_mode='html')
        event.handled = True
        return
    
    # 3. Handle Profile Button
    elif text == "👤 User Profile":
        bal = await get_user_bal(uid)
        jd = await get_user_jd(uid)
        await event.respond(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}", parse_mode='html')
        event.handled = True
        return
    
    # 4. Handle Back Button
    elif text == "🔙 Back to Main Menu":
        await event.respond("👋 Hello! Welcome to SKY OTP Bot.\n\n✨ Use the buttons below to explore our services.", buttons=main_kb())
        event.handled = True
        return
        
    # 5. Handle Buy Telegram Account Button
    elif text == "🛍️ Buy Telegram Account":
        tg_services_kb = [
            [Button.inline("🌍 Country", data="lbl"), Button.inline("💰 Price", data="lbl"), Button.inline("📦 Stock", data="lbl")],
            [Button.inline("🇨🇴 Colombia", data="buy:Colombia:36.23"), Button.inline("₹36.23", data="buy:Colombia:36.23"), Button.inline(" ✅", data="buy:Colombia:36.23")],
            [Button.inline("🇳🇬 Nigeria", data="buy:Nigeria:36.23"), Button.inline("₹36.23", data="buy:Nigeria:36.23"), Button.inline(" ✅", data="buy:Nigeria:36.23")],
            [Button.inline("🇧🇩 Bangladesh", data="buy:Bangladesh:40.04"), Button.inline("₹40.04", data="buy:Bangladesh:40.04"), Button.inline(" ✅", data="buy:Bangladesh:40.04")],
            [Button.inline("🇨🇦 Canada", data="buy:Canada:40.04"), Button.inline("₹40.04", data="buy:Canada:40.04"), Button.inline(" ✅", data="buy:Canada:40.04")],
            [Button.inline("🇺🇸 United States", data="buy:USA:41.00"), Button.inline("₹41.00", data="buy:USA:41.00"), Button.inline(" ✅", data="buy:USA:41.00")],
            [Button.inline("🇮🇳 India", data="buy:India:41.00"), Button.inline("₹41.00", data="buy:India:41.00"), Button.inline(" ✅", data="buy:India:41.00")]
        ]
        await event.respond("📊 <b>Available Telegram Services</b>", buttons=tg_services_kb, parse_mode='html')
        event.handled = True
        return

    # 6. Handle Buy Whatsapp OTP Button
    elif text == "🗨️ Buy Whatsapp OTP":
        await event.respond("🔄 <b>Live WhatsApp OTP Activation Enabled</b>\n\nPlease request your verification code now.", parse_mode='html')
        event.handled = True
        return

    # 7. Handle Promocode Button with Clickable Instagram Link
    elif text == "🎁 Promocode":
        promo_msg = (
            "<b>Follow me on Instagram to get exclusive promo codes:</b>\n\n"
            "⬇️ <b>Instagram Profile:</b>\n"
            "<a href='https://instagram.com'>@akash.verified</a>"
        )
        await event.respond(promo_msg, parse_mode='html', link_preview=False)
        event.handled = True
        return

    # 8. Handle Support Button with Professional Text
    elif text == "🆘 Support":
        support_msg = (
            "✈️ <b>To contact our official support team, please reach out via the details below:</b>\n\n"
            "📱 <b>Telegram ID:</b> @Sky_Verified\n"
            "⏰ <b>Working Hours:</b> 10:00 AM to 10:00 PM"
        )
        await event.respond(support_msg, parse_mode='html')
        event.handled = True
        return

    # 9. Handle Add Funds Button
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
        
        cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ : After making the payment, simply upload your Payment Screenshot for verification the payment.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
        
        await event.respond(cap, file=buf, buttons=[[Button.inline("❌ Cancel Request", data=f"cancel:{claim_id}")]], parse_mode='html')
        event.handled = True
        return
        
    # 10. Handle Screenshot Uploads
    elif event.photo:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT claim_id, txn FROM claims WHERE uid = %s ORDER BY claim_id DESC LIMIT 1", (uid,))
                row = await cursor.fetchone()
            
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

# --- Startup and Initialization Loop ---
async def main():
    # ✅ FIX: Automatically verify and create the folder so SQLite never throws an error
    session_dir = "session_data"
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)
        logging.info(f"Created missing directory structural path: {session_dir}")

    # 1. Initialize structural DB layout
    await init_db()
    
    # 2. Start the Telethon Bot Client using the token
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("🚀 SKY OTP Master Bot is now online and listening for events...")
    
    # 3. Keep the script alive and running
    await bot.run_until_disconnected()

if __name__ == "__main__":
    # Run the async loop
    asyncio.run(main())
