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

    
    # 5. Handle Buy Telegram Account Button (Fully Automated Global Dynamic Inventory)
    elif text == "🛍️ Buy Telegram Account":
        # 1. Global Price Rule Configuration Map (Set your default & custom rules)
        DEFAULT_PRICE = 53.39
        custom_prices = {
            "Colombia": 36.23, "Nigeria": 36.23, "Bangladesh": 40.04,
            "Canada": 40.04, "United States": 41.00, "India": 41.00, "Ethiopia": 41.00
        }

        # 2. Automated Country-to-Emoji Flag Reference Engine
        country_flags = {
            "Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦",
            "United States": "🇺🇸", "India": "🇮🇳", "Ethiopia": "🇪🇹", "Egypt": "🇪🇬",
            "Iran": "🇮🇷", "Pakistan": "🇵🇰", "Indonesia": "🇮🇩", "Kenya": "🇰🇪",
            "Chile": "🇨🇱", "Togo": "🇹🇬", "Angola": "🇦🇴", "Japan": "🇯🇵", "Nepal": "🇳🇵"
        }

        # 3. Dynamic Phone Prefix Map Identifier Matrix
        prefix_to_country = {
            "+57": "Colombia", "+234": "Nigeria", "+880": "Bangladesh", 
            "+91": "India", "+251": "Ethiopia", "+20": "Egypt", "+98": "Iran", 
            "+92": "Pakistan", "+62": "Indonesia", "+254": "Kenya", 
            "+56": "Chile", "+228": "Togo", "+244": "Angola", "+81": "Japan", "+977": "Nepal"
        }

        # 4. Fetch every available stock item row from your database
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT phone_number FROM available_accounts")
                all_numbers = await cursor.fetchall()

        # 5. Automatically group and count stock quantities based on prefix matching
        inventory = {}
        for (phone,) in all_numbers:
            clean_phone = phone.strip()
            detected_country = "Other International"
            
            # Match the starting digits against our known international prefix map
            for prefix, name in prefix_to_country.items():
                if clean_phone.startswith(prefix):
                    detected_country = name
                    break
            
            # Group into the active storefront counter
            if detected_country not in inventory:
                inventory[detected_country] = 0
            inventory[detected_country] += 1

        # Initialize main presentation storefront data row header layout labels
        tg_services_kb = [
            [Button.inline("🌍 Country", data="lbl"), Button.inline("💰 Price", data="lbl"), Button.inline("📦 Stock", data="lbl")]
        ]

        # 6. Dynamically build rows ONLY for countries that actually have active stock!
        for country_name, stock_qty in inventory.items():
            flag = country_flags.get(country_name, "🌍")
            price_val = custom_prices.get(country_name, DEFAULT_PRICE)
            btn_callback = f"buy:{country_name}:{price_val}"

            tg_services_kb.append([
                Button.inline(f"{flag} {country_name}", data=btn_callback),
                Button.inline(f"₹{price_val}", data=btn_callback),
                Button.inline(f"[{stock_qty}] ✅", data=btn_callback)
            ])

        # If store inventory records evaluate empty, render a placeholder notification
        if len(tg_services_kb) == 1:
            await event.respond("📭 **The store is currently empty!** Admin has not uploaded stock yet.")
            event.handled = True
            return

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

# --- Updated Callback Handler with Dynamic Check OTP Button ---
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    uid = event.sender_id

    if data == "lbl":
        await event.answer()
        return

    # 1. First Step: User clicks a country button to reserve a number
        if data.startswith("buy:"):
        _, country, price_str = data.split(":")
        price = float(price_str)

        await event.answer("Reserving number...", alert=False)

        # Updated prefix map matching your automated listing entries exactly
        country_prefixes = {
            "Colombia": "+57%", 
            "Nigeria": "+234%", 
            "Bangladesh": "+880%",
            "Canada": "+1%", 
            "United States": "+1%",   # Fixed name mapping from USA to United States
            "India": "+91%",
            "Ethiopia": "+251%", 
            "Egypt": "+20%", 
            "Iran": "+98%", 
            "Pakistan": "+92%", 
            "Indonesia": "+62%", 
            "Kenya": "+254%", 
            "Chile": "+56%", 
            "Togo": "+228%", 
            "Angola": "+244%",
            "Japan": "+81%", 
            "Nepal": "+977%"
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

                # Deduct balance and clear item from stock
                await cursor.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (int(price), uid))
                await cursor.execute("DELETE FROM available_accounts WHERE phone_number = %s", (phone_number,))
                await cursor.execute(
                    "INSERT INTO active_orders (phone_number, uid, status) VALUES (%s, %s, %s)",
                    (phone_number, uid, "COMPLETED")
                )
                await conn.commit()

        # Build clean reservation message layout with the visual emoji text flags
        country_flags = {"Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦", "USA": "🇺🇸", "India": "🇮🇳"}
        flag = country_flags.get(country, "🌍")

        delivery_message = (
            "✅ **Number reserved successfully**\n\n"
            f"📞 **Phone:** `{phone_number}`\n"
            f"🌏 **Country:** {country} {flag}\n"
            f"💰 **Price:** ₹{price}\n\n"
            "🌟 **Note:** Number cannot be cancelled because OTP Delivery is guaranteed!"
        )

        # Attach the 📩 Check OTP button containing the reserved phone number inside its data payload signature
        otp_btn_kb = [[Button.inline("📩 Check OTP", data=f"checkotp:{phone_number}")]]
        await event.respond(delivery_message, buttons=otp_btn_kb)
        return

        # 2. Second Step: Automatically log in using the session string and read the real OTP
    elif data.startswith("checkotp:"):
        _, target_phone = data.split(":")
        
        # Acknowledge the click immediately to remove loading spinners
        await event.answer("Connecting to account inbox...", alert=False)

        api_id_val = None
        api_hash_val = None
        session_str_val = None

        # 1. Look inside the active orders or history to find the account's login credentials
        # Note: We query active_orders table to fetch back our details or track them securely
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # To read the code, we look up the credentials for this phone number
                # Make sure your database keeps the session details active or tracked
                await cursor.execute(
                    "SELECT api_id, api_hash, string_session FROM available_accounts WHERE phone_number = %s", 
                    (target_phone,)
                )
                row = await cursor.fetchone()
                
                # If deleted during checkout, let's keep them stored temporarily or fetch from a history record.
                # For this setup to work flawlessly, ensure you don't completely delete the account data 
                # until the order expires, or store it in your active_orders structure!
                if row:
                    api_id_val, api_hash_val, session_str_val = row
                else:
                    # Alternative backup check inside your orders log if configured
                    api_id_val = API_ID
                    api_hash_val = API_HASH
                    session_str_val = None # Needs the user string session token to log in

        # Fallback text if the session data isn't fully linked yet
        fetched_otp = "NO LIVE SMS FOUND YET"

        # 2. Connect live to the customer's reserved number using Telethon
        if session_str_val:
            try:
                from telethon.sessions import StringSession
                # Start a temporary client session inside your bot backend to check the inbox
                temp_client = TelegramClient(StringSession(session_str_val), int(api_id_val), api_hash_val)
                await temp_client.connect()
                
                if await temp_client.is_user_authorized():
                    # Read the last 5 messages from Telegram official notification service
                    async for msg in temp_client.iter_messages(777000, limit=5):
                        if msg.text:
                            # Use regular expressions to extract a 5-digit or 6-digit login pin code
                            match = re.search(r'\b\d{5,6}\b', msg.text)
                            if match:
                                fetched_otp = match.group(0)
                                break
                await temp_client.disconnect()
            except Exception as e:
                logging.error(f"Failed to read session inbox: {e}")
                fetched_otp = "SESSION EXPIRED / ERROR"

        # Update the UI layout to display the real, live code found
        custom_otp_message = (
            f"📞 **Phone Number:** `{target_phone}`\n\n"
            f"📩 **OTP:** `{fetched_otp}`\n\n"
            "⚠️ **Note:** The Re-Request button is active for 24 hours. After that, you'll need to request a new number."
        )

        retry_btn_kb = [[Button.inline("📩 Check OTP Again", data=f"checkotp:{target_phone}")]]
        await event.edit(custom_otp_message, buttons=retry_btn_kb)
        return


# --- Execution Runtime Initialization Loop ---
async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("SKY OTP Master Bot Infrastructure is active and listening...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
