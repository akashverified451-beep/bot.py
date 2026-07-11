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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAGSEER5HzYb69RK5zOlgR9KDmQArRR54VU")
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
    
    # Admin Stock Adder Command
    if text.startswith("/addstock") and uid == ADMIN_TELEGRAM_ID:
        try:
            # Expected format: /addstock phone,api_id,api_hash,string_session
            command_args = text.split(" ", 1)[1]
            phone, api_id_val, api_hash_val, session_str = command_args.split(",")
            
            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "INSERT INTO available_accounts (phone_number, api_id, api_hash, string_session) VALUES (%s, %s, %s, %s)",
                        (phone.strip(), api_id_val.strip(), api_hash_val.strip(), session_str.strip())
                    )
                    await conn.commit()
            
            await event.respond(f"✅ Successfully added account `{phone.strip()}` to stock pile!")
        except Exception as e:
            await event.respond(f"❌ **Format Error!** Use:\n`/addstock phone,api_id,api_hash,session_string`\n\nError: {e}")
        event.handled = True
        return

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
        
    # 5. Handle Buy Telegram Account Button (Pulls Real Database Numbers)
    elif text == "🛍️ Buy Telegram Account":
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM available_accounts WHERE phone_number LIKE '+57%'")
                stock_colombia = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM available_accounts WHERE phone_number LIKE '+234%'")
                stock_nigeria = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM available_accounts WHERE phone_number LIKE '+880%'")
                stock_bangladesh = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM available_accounts WHERE phone_number LIKE '+1%'")
                stock_usa_canada = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM available_accounts WHERE phone_number LIKE '+91%'")
                stock_india = (await cursor.fetchone())[0]

        tg_services_kb = [
            [Button.inline("🌍 Country", data="lbl"), Button.inline("💰 Price", data="lbl"), Button.inline("📦 Stock", data="lbl")],
            [Button.inline("🇨🇴 Colombia", data="buy:Colombia:36.23"), Button.inline("₹36.23", data="buy:Colombia:36.23"), Button.inline(f"📝 {stock_colombia}", data="buy:Colombia:36.23")],
            [Button.inline("🇳🇬 Nigeria", data="buy:Nigeria:36.23"), Button.inline("₹36.23", data="buy:Nigeria:36.23"), Button.inline(f"📝 {stock_nigeria}", data="buy:Nigeria:36.23")],
            [Button.inline("🇧🇩 Bangladesh", data="buy:Bangladesh:40.04"), Button.inline("₹40.04", data="buy:Bangladesh:40.04"), Button.inline(f"📝 {stock_bangladesh}", data="buy:Bangladesh:40.04")],
            [Button.inline("🇨🇦 Canada", data="buy:Canada:40.04"), Button.inline("₹40.04", data="buy:Canada:40.04"), Button.inline(f"📝 {stock_usa_canada}", data="buy:Canada:40.04")],
            [Button.inline("🇺🇸 United States", data="buy:USA:41.00"), Button.inline("₹41.00", data="buy:USA:41.00"), Button.inline(f"📝 {stock_usa_canada}", data="buy:USA:41.00")],
            [Button.inline("🇮🇳 India", data="buy:India:41.00"), Button.inline("₹41.00", data="buy:India:41.00"), Button.inline(f"📝 {stock_india}", data="buy:India:41.00")]
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
        
        # Build strict UPI standard format string payload
        upi_payload = f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP_BOT&tr={txn}&tn=Wallet_Refill_{claim_id}"
        
        # Draw and output the image matrix arrays via internal memory operations
        qr_img = qrcode.make(upi_payload)
        image_stream = io.BytesIO()
        qr_img.save(image_stream, format="PNG")
        image_stream.seek(0)
        
        deposit_instruction = (
            "💳 <b>Deposit System Initialized</b>\n\n"
            f"1️⃣ Scan the generated QR code with any UPI app.\n"
            f"2️⃣ Complete the payment transaction.\n"
            f"3️⃣ Copy your 12-digit transaction ID (UTR).\n\n"
            f"⚠️ <b>Claim ID:</b> <code>{claim_id}</code>\n\n"
            "Send your UTR/Txn ID here in the chat to claim your funds automatically."
        )
        
        # Send dynamic PNG buffer directly over Telegram without local storage leaks
        await bot.send_file(
            event.chat_id, 
            image_stream, 
            caption=deposit_instruction, 
            parse_mode='html'
        )
        event.handled = True
        return

# --- ADD THIS LOGIC TO ENABLE CALLBACK QUERIES ---
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    uid = event.sender_id

    # 1. ALWAYS answer immediately to stop the loading spinner/timeout error
    if data == "lbl":
        await event.answer("This is a table column label.", alert=False)
        return
    else:
        # Acknowledge all other clicks instantly so the error goes away
        await event.answer("Processing request...", alert=False)

    # 2. Process purchase sequence
    if data.startswith("buy:"):
        _, country, price_str = data.split(":")
        price = float(price_str)

        country_prefixes = {
            "Colombia": "+57%", "Nigeria": "+234%", "Bangladesh": "+880%",
            "Canada": "+1%", "USA": "+1%", "India": "+91%"
        }
        prefix = country_prefixes.get(country, "%")

        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # Check user wallet balance
                await cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
                user_row = await cursor.fetchone()
                user_balance = user_row[0] if user_row else 0

                if user_balance < price:
                    await event.respond(f"❌ **Insufficient Funds!**\n\nYour balance: ₹{user_balance}\nRequired amount: ₹{price}\n\nPlease refill your wallet.")
                    return

                # Fetch available stock item
                await cursor.execute(
                    "SELECT phone_number, api_id, api_hash, string_session FROM available_accounts WHERE phone_number LIKE %s LIMIT 1",
                    (prefix,)
                )
                account_row = await cursor.fetchone()

                if not account_row:
                    await event.respond(f"📭 **Out of Stock!**\n\nWe do not have any available accounts for **{country}** right now.")
                    return

                phone_number, api_id, api_hash, string_session = account_row

                # Atomically apply balance deduction and clear item from database stock
                await cursor.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (int(price), uid))
                await cursor.execute("DELETE FROM available_accounts WHERE phone_number = %s", (phone_number,))
                await cursor.execute(
                    "INSERT INTO active_orders (phone_number, uid, status) VALUES (%s, %s, %s)",
                    (phone_number, uid, "COMPLETED")
                )
                await conn.commit()

        # Securely deliver credentials package to user
        delivery_message = (
            "🎉 **Purchase Successful!**\n\n"
            f"🌍 **Country:** {country}\n"
            f"💰 **Debited Amount:** ₹{price}\n"
            f"📱 **Phone Number:** `{phone_number}`\n\n"
            "📋 **Your Session Credentials:**\n"
            f"• **API ID:** `{api_id}`\n"
            f"• **API HASH:** `{api_hash}`\n\n"
            "🔑 **String Session Token:**\n"
            f"<code>{string_session}</code>"
        )
        await event.respond(delivery_message, parse_mode='html')
        
        # Notify Admin
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, f"💰 **Sale!** User `{uid}` bought **{country}** (`{phone_number}`).")
        except Exception:
            pass

# --- Execution Runtime Initialization Loop ---
async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("SKY OTP Master Bot Infrastructure is active and listening...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
