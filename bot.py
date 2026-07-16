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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAGSEER5HzYb69RK5zOlgR9KDmQArRR54VU")
API_ID = int(os.getenv("API_ID", "33033843")) 
API_HASH = os.getenv("API_HASH", "27d91aac298b61038f19ee5c1b1f3f48")

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

# Database Connection URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db")

# Initialize Telethon Bot Client Instance using your storage disk path
bot = TelegramClient("session_data/sky_otp_master_session_v3", API_ID, API_HASH)

async def get_db_connection():
    """Establishes an isolated non-blocking bridge line with the Render PostgreSQL engine."""
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def init_db():
    """Create required tables asynchronously if they don't exist in PostgreSQL."""
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("CREATE TABLE IF NOT EXISTS users (uid BIGINT PRIMARY KEY, balance INT DEFAULT 0, join_date TEXT)")
                await cursor.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, uid BIGINT, txn TEXT, session_amt INT DEFAULT 0)")
                await cursor.execute("CREATE TABLE IF NOT EXISTS active_orders (phone_number TEXT, uid BIGINT, status TEXT)")
                await cursor.execute("CREATE TABLE IF NOT EXISTS available_accounts (phone_number TEXT PRIMARY KEY, api_id TEXT, api_hash TEXT, string_session TEXT)")
                await cursor.execute("CREATE TABLE IF NOT EXISTS country_prices (country TEXT PRIMARY KEY, price NUMERIC)")
                await conn.commit()
        logging.info("PostgreSQL structural database tables checked/created successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

async def get_country_prices():
    """Fetches real-time custom pricing from the database with hardcoded defaults as fallbacks."""
    defaults = {
        "Colombia": 36.23, "Nigeria": 36.23, "Bangladesh": 40.04,
        "Canada": 40.04, "United States": 41.00, "India": 41.00, "Ethiopia": 41.00,
        "DEFAULT": 53.39
    }
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT country, price FROM country_prices")
                rows = await cursor.fetchall()
                for country, price in rows:
                    defaults[country.strip()] = float(price)
    except Exception as e:
        logging.error(f"Error fetching dynamic prices: {e}")
    return defaults

async def get_user_bal(uid):
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        logging.error(f"Error fetching user balance for {uid}: {e}")
        return 0

async def get_user_jd(uid):
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT join_date FROM users WHERE uid = %s", (uid,))
                row = await cursor.fetchone()
                return row[0] if row else "N/A"
    except Exception as e:
        logging.error(f"Error fetching join date for {uid}: {e}")
        return "N/A"

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

    # Ensure user exists in database upon active interaction
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
                if not await cursor.fetchone():
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (%s, 0, %s)", (uid, join_date))
                    await conn.commit()
    except Exception as e:
        logging.error(f"User check-in database error: {e}")

    # Admin Stock Adder Command with Integrated Live Price Configuration Matrix
    if text.startswith("/addstock") and uid == ADMIN_TELEGRAM_ID:
        try:
            # Expected formats:
            # OPTION A (With custom price): /addstock phone,api_id,api_hash,session_string,price
            # OPTION B (Keep existing price): /addstock phone,api_id,api_hash,session_string
            if " " not in text:
                await event.respond("❌ **Format mismatch!** Use: `/addstock phone,api_id,api_hash,session_string,price`")
                event.handled = True
                return

            command_args = text.split(" ", 1)[1]
            args_list = command_args.split(",")
            
            if len(args_list) < 4:
                raise ValueError("Insufficient arguments provided.")
                
            phone = args_list[0].strip()
            api_id_val = args_list[1].strip()
            api_hash_val = args_list[2].strip()
            session_str = args_list[3].strip()
            
            # Detect optional trailing pricing variable argument parameter
            set_custom_price = None
            if len(args_list) >= 5:
                set_custom_price = float(args_list[4].strip())
            
            progress_msg = await event.respond("⏳ **Verifying login credentials against Telegram servers...**")
            
            # 1. Spawn temporary runtime client to validate authentication safety
            temp_client = TelegramClient(
                StringSession(session_str), 
                int(api_id_val), 
                api_hash_val,
                connection_retries=1
            )
            
            is_valid = False
            try:
                await temp_client.connect()
                is_valid = await temp_client.is_user_authorized()
            except Exception as auth_error:
                logging.warning(f"Session string check failed: {auth_error}")
                is_valid = False
            finally:
                await temp_client.disconnect()
                
            if not is_valid:
                await progress_msg.edit("❌ **Stock Rejected!** The session string or API credentials provided are invalid or expired.")
                event.handled = True
                return
                
            # 2. Derive structural country mappings to set price targets correctly
            prefix_to_country = {
                "+57": "Colombia", "+234": "Nigeria", "+880": "Bangladesh", 
                "+91": "India", "+251": "Ethiopia", "+20": "Egypt", "+98": "Iran", 
                "+92": "Pakistan", "+62": "Indonesia", "+254": "Kenya", 
                "+56": "Chile", "+228": "Togo", "+244": "Angola", "+81": "Japan", "+977": "Nepal"
            }
            
            clean_phone = phone
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone
                
            detected_country = "Other International"
            for prefix in sorted(prefix_to_country.keys(), key=len, reverse=True):
                if clean_phone.startswith(prefix):
                    detected_country = prefix_to_country[prefix]
                    break
            
            # 3. Commit verification loops safely to your storage engine
            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    # Save stock credentials record
                    await cursor.execute(
                        """INSERT INTO available_accounts (phone_number, api_id, api_hash, string_session) 
                           VALUES (%s, %s, %s, %s) 
                           ON CONFLICT (phone_number) DO UPDATE SET 
                           api_id = EXCLUDED.api_id, api_hash = EXCLUDED.api_hash, string_session = EXCLUDED.string_session""",
                        (phone, api_id_val, api_hash_val, session_str)
                    )
                    
                    # Update dynamic pricing if custom value is provided
                    price_note = ""
                    if set_custom_price is not None:
                        await cursor.execute(
                            """INSERT INTO country_prices (country, price) VALUES (%s, %s) 
                               ON CONFLICT (country) DO UPDATE SET price = EXCLUDED.price""",
                            (detected_country, set_custom_price)
                        )
                        price_note = f"\n💰 **Price Auto-Configured:** ₹{set_custom_price:.2f} for {detected_country}"
                        
                    await conn.commit()
            
            await progress_msg.edit(f"✅ **Stock Verified & Active!**\n\n📞 Phone: `{phone}`\n🌍 Target Group: **{detected_country}**{price_note}")
        except Exception as e:
            await event.respond(
                f"❌ **Format Error!** Use one of these patterns:\n\n"
                f"🔹 **With New Price:**\n`/addstock phone,api_id,api_hash,session,price`\n\n"
                f"🔹 **Keep Current Price:**\n`/addstock phone,api_id,api_hash,session`"
            )
        event.handled = True
        return



    # Admin Quick Price Modifier Command
    if text.startswith("/updateprice") and uid == ADMIN_TELEGRAM_ID:
        try:
            # Expected format: /updateprice CountryName,Price
            if " " not in text:
                await event.respond("❌ **Format Error!** Use:\n`/updateprice CountryName,Price`\n\nExample: `/updateprice India,48`")
                event.handled = True
                return

            command_args = text.split(" ", 1)[1]
            country_param, price_param = command_args.split(",")
            
            target_country = country_param.strip()
            new_price = float(price_param.strip())
            
            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """INSERT INTO country_prices (country, price) VALUES (%s, %s) 
                           ON CONFLICT (country) DO UPDATE SET price = EXCLUDED.price""",
                        (target_country, new_price)
                    )
                    await conn.commit()
            
            await event.respond(f"💰 **Live Price Updated!**\n\n🌍 Country: **{target_country}**\n💵 New Price: **₹{new_price:.2f}**\n\n*All current and future stock for this country will use this price instantly.*")
        except Exception as e:
            logging.error(f"Updateprice command error: {e}")
            await event.respond(f"❌ **Format Error!** Use:\n`/updateprice CountryName,Price`\n\nExample: `/updateprice India,48`")
        event.handled = True
        return

    # Admin Stock Verification & Cleanup Engine
    if text.startswith("/cleanstock") and uid == ADMIN_TELEGRAM_ID:
        try:
            status_msg = await event.respond("🔍 **Scanning database stock...** Please wait.")
            
            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT phone_number, api_id, api_hash, string_session FROM available_accounts")
                    all_stock = await cursor.fetchall()
            
            if not all_stock:
                await status_msg.edit("📦 Your stock pile is completely empty. Nothing to clean!")
                event.handled = True
                return
                
            from telethon.sessions import StringSession
            dead_accounts = []
            checked_count = 0
            
            for phone, api_id, api_hash, session_str in all_stock:
                checked_count += 1
                # Update status message occasionally to avoid rate limiting
                if checked_count % 3 == 0 or checked_count == len(all_stock):
                    try:
                        await status_msg.edit(f"⏳ Checking account {checked_count}/{len(all_stock)} (`{phone}`)...")
                    except Exception:
                        pass # Ignore temporary Telegram UI glitches
                
                temp_client = TelegramClient(
                    StringSession(session_str.strip()), 
                    int(api_id.strip()), 
                    api_hash.strip(),
                    connection_retries=1
                )
                
                is_valid = False
                try:
                    await temp_client.connect()
                    is_valid = await temp_client.is_user_authorized()
                except Exception as check_err:
                    logging.warning(f"Error checking session for {phone}: {check_err}")
                    is_valid = False
                finally:
                    await temp_client.disconnect()
                
                if not is_valid:
                    dead_accounts.append(phone)

            # Delete dead accounts from the database
            if dead_accounts:
                async with await get_db_connection() as conn:
                    async with conn.cursor() as cursor:
                        for phone_to_delete in dead_accounts:
                            await cursor.execute("DELETE FROM available_accounts WHERE phone_number = %s", (phone_to_delete,))
                        await conn.commit()
                
                await status_msg.edit(
                    f"🧹 **Cleanup Complete!**\n\n"
                    f"✅ Total Checked: `{len(all_stock)}` accounts\n"
                    f"🗑️ Dead/Fake Removed: `{len(dead_accounts)}` accounts\n"
                    f"📦 Remaining Active Stock: `{len(all_stock) - len(dead_accounts)}` accounts"
                )
            else:
                await status_msg.edit(f"✨ **All clean!** All `{len(all_stock)}` accounts in your database are 100% valid and working.")
                
        except Exception as e:
            logging.error(f"Cleanup processing error: {e}")
            await event.respond(f"❌ **Cleanup Error:** {e}")
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
    if text == "💼 Wallet":
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
        
    # Handle Back Button Action cleanly
    elif text == "🔙 Back to Main Menu":
        try:
            await event.respond("👋 Welcome back! Select an option from the menu below:", buttons=...)
        except Exception as menu_err:
            logging.error(f"Error drawing main menu view: {menu_err}")
        event.handled = True
        return
        
    # 5. Handle Buy Telegram Account Button
        if text == "🛍 Buy Telegram Account":
            custom_prices = await get_country_prices()
            DEFAULT_PRICE = custom_prices.get("DEFAULT", 53.39)

        # 2. Automated Country-to-Emoji Flag
        country_flags = {
            "Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩",
            "Canada": "🇨🇦", "United States": "🇺🇸", "India": "🇮🇳",
            "Ethiopia": "🇪🇹", "Egypt": "🇪🇬", "Iran": "🇮🇷",
            "Pakistan": "🇵🇰", "Indonesia": "🇮🇩", "Kenya": "🇰🇪",
            "Chile": "🇨🇱", "Togo": "🇹🇬", "Angola": "🇦🇴",
            "Japan": "🇯🇵", "Nepal": "🇳🇵", "Myanmar": "🇲🇲"
        }

        # 3. Dynamic Phone Prefix Map Identification
        prefix_to_country = {
            "+57": "Colombia", "+234": "Nigeria", "+880": "Bangladesh",
            "+91": "India", "+251": "Ethiopia", "+20": "Egypt", "+98": "Iran",
            "+92": "Pakistan", "+62": "Indonesia", "+254": "Kenya",
            "+56": "Chile", "+228": "Togo", "+244": "Angola", "+81": "Japan",
            "+977": "Nepal", "+95": "Myanmar"
        }

        # List of known Canadian Area Codes
        canada_area_codes = [
            "204", "226", "236", "249", "250",
            "431", "437", "438", "450", "506",
            "604", "613", "639", "647", "705",
            "825", "867", "873", "902", "905"
        ]
    
        async with await get_db_connection() as conn:
      async with await get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT phone_number FROM available_accounts")
            all_numbers = await cursor.fetchall()

    inventory = {}
    for (phone_num,) in all_numbers:
        if not phone_num: continue
        clean_phone = phone_num.strip()
        if not clean_phone.startswith("+"): clean_phone = "+" + clean_phone
        detected_country = "Other International"
        if clean_phone.startswith("+1") and len(clean_phone) >= 5:
            area_code = clean_phone[2:5]
            if area_code in canada_area_codes: detected_country = "Canada"
            else: detected_country = "United States"
        else:
            for prefix in sorted(prefix_to_country.keys(), key=len, reverse=True):
                if clean_phone.startswith(prefix):
                    detected_country = prefix_to_country[prefix]
                    break
        detected_country = detected_country.strip()
        inventory[detected_country] = inventory.get(detected_country, 0) + 1

        if not inventory:
        await event.respond("⚠ **Storefront Notice:**\n\n There are currently no active accounts in stock.")
        event.handled = True
        return

        tg_services_kb = [
        [
            Button.inline("🌍 Country", data="lbl"),
            Button.inline("💰 Price", data="lbl"),
            Button.inline("📦 Stock", data="lbl")
        ]
    ]

    # 7. Dynamically generate rows ordered by available inventory sizing
    for country_name, stock_qty in inventory.items():
        flag = country_flags.get(country_name, "🇺🇳")
        price = custom_prices.get(country_name, DEFAULT_PRICE)

        callback_payload = f"buy_tg_{country_name}"

        country_row = [
            Button.inline(f"{flag} {country_name}", data=callback_payload),
            Button.inline(f"₹{price:.1f}", data=callback_payload),
            Button.inline(f"[{stock_qty}] ✅", data=callback_payload)
        ]
        tg_services_kb.append(country_row)

        await event.respond("📊 **Available Telegram Services**", buttons=tg_services_kb)
        event.handled = True
        return

    # # 6. Handle Buy Whatsapp OTP Button
    if text == "🛍 Buy Whatsapp OTP":
        await event.respond("<b>Live Whatsapp OTP Service...</b>")
        event.handled = True
        return

    # # 7. Handle Promocode Button
    if text == "🎟 Promocode":
        promo_msg = (
            "<b>Follow me on Instagram to get promo codes</b>\n"
            "⬇️ <b>Instagram Profile:</b>\n"
            "<a href='https://instagram.com'>Click Here</a>"
        )
        await event.respond(promo_msg, parse_mode='html')
        event.handled = True
        return

    # # 8. Handle Support Button with Professional Care
    if text == "🆘 Support":
        support_msg = (
            "❌ <b>To contact our official support:</b>\n"
            "🗣 <b>Telegram ID:</b> @Sky_Verified\n"
            "⏰ <b>Working Hours:</b> 10:00 AM to ..."
        )
        await event.respond(support_msg, parse_mode='html')
        event.handled = True
        return

    if text == "➕ Add Funds":
        txn = "".join([str(random.randint(0, 9)) for _ in range(10)])
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
        cap = f"👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay.\n\n⚠️ After making the payment, simply upload your Payment Screenshot for verification the payment.\n\n📌 <b>Transaction Reference:</b>\n<code>{txn}</code>"
        
        await event.respond(
            cap,
            file=buf,
            buttons=[[Button.inline("❌ Cancel Request", data=f"cancel:{claim_id}")]],
            parse_mode='html'
        )
    
    # Handle Screenshot Uploads
    if event.photo:
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
        
    try:
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
    except Exception as general_err:
        logging.error(f"Admin confirmation process error: {general_err}")

# --- 3. FIXED CANCEL & DENY BUTTON HANDLER ---
@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"deny:") or d.startswith(b"cancel:")))
async def cancel_or_deny_click(event):
    try:
        await event.answer()  # Stops the loading spinner instantly
        data_str = event.data.decode('utf-8')
        
        if ":" in data_str:
            action, claim_id = data_str.split(":", 1)
        else:
            await event.edit("❌ This request data structure is broken.")
            return
        
        async with await get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # Fetch user details to optionally notify them before record purging
                await cursor.execute("SELECT uid FROM claims WHERE claim_id = %s", (str(claim_id),))
                row = await cursor.fetchone()
                
                await cursor.execute("DELETE FROM claims WHERE claim_id = %s", (str(claim_id),))
                await conn.commit()
                
                if action == "deny" and row:
                    try:
                        await bot.send_message(entity=row[0], message="❌ **Deposit Rejected:** Your payment screenshot verification failed or was declined by the administrator.")
                    except Exception:
                        pass
                        
            await event.edit(f"❌ Request [{claim_id}] has been processed and removed.")
    except Exception as e:
        logging.error(f"Error processing cancel/deny runtime actions: {e}")

# --- Complete High-Speed Error-Free Callback Query Handler ---
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    uid = event.sender_id

    if data == "lbl":
        await event.answer()
        return

    # # 1. First Step: User clicks a country purchase button
    if data.startswith("buy_tg_"):
        try:
            await event.answer("Validating warehouse stock pipeline...", alert=False)
            target_slug = data.replace("buy_tg_", "").strip()
            
            # Fetch live database prices dynamically instead of hardcoding
            custom_prices = await get_country_prices()
            DEFAULT_PRICE = custom_prices.get("DEFAULT", 53.39)
            
            country_flags = {
                "Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦",
                "United States": "🇺🇸", "India": "🇮🇳", "Ethiopia": "🇪🇹"
            }
            
            prefix_to_country = {
                "+57": "Colombia", "+234": "Nigeria", "+880": "Bangladesh", 
                "+91": "India", "+251": "Ethiopia", "+20": "Egypt", "+98": "Iran", 
                "+92": "Pakistan", "+62": "Indonesia", "+254": "Kenya", 
                "+56": "Chile", "+228": "Togo", "+244": "Angola", "+81": "Japan", "+977": "Nepal"
            }

            canada_area_codes = [
                "204", "226", "236", "249", "250", "289", "306", "343", "365", "403", "416", "418", 
                "431", "437", "438", "450", "506", "514", "519", "548", "579", "581", "587", "600", 
                "604", "613", "639", "647", "705", "709", "742", "778", "780", "782", "807", "819", 
                "825", "867", "873", "902", "905"
            ]

            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT phone_number, api_id, api_hash, string_session FROM available_accounts")
                    all_stock = await cursor.fetchall()
                    
                    selected_account = None
                    detected_country_name = "Other International"
                    
                    for phone, api_id, api_hash, session_str in all_stock:
                        clean_phone = phone.strip()
                        if not clean_phone.startswith("+"):
                            clean_phone = "+" + clean_phone
                        
                        if clean_phone.startswith("+1") and len(clean_phone) >= 5:
                            area_code = clean_phone[2:5]
                            account_country = "Canada" if area_code in canada_area_codes else "United States"
                        else:
                            account_country = "Other International"
                            for prefix in sorted(prefix_to_country.keys(), key=len, reverse=True):
                                if clean_phone.startswith(prefix):
                                    account_country = prefix_to_country[prefix]
                                    break
                        
                        # Match slug strings correctly matching the storefront payload mutations
                        current_slug = account_country.lower().replace(" ", "_")[:20]
                        if current_slug == target_slug:
                            selected_account = (phone, api_id, api_hash, session_str)
                            detected_country_name = account_country
                            break
                    
                    if not selected_account:
                        await event.respond("⚠️ **Out of Stock!** No available numbers match your requested country target group.")
                        return
                    
                    phone_to_buy, api_id_to_buy, api_hash_to_buy, session_to_buy = selected_account
                    
                    # Check balance check loops to make sure users can buy accounts cleanly
                    display_price = custom_prices.get(detected_country_name, DEFAULT_PRICE)
                    await cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
                    bal_row = await cursor.fetchone()
                    user_bal = bal_row[0] if bal_row else 0
                    
                    if user_bal < display_price:
                        await event.respond(f"❌ **Insufficient Funds!**\n\nThis account costs **₹{display_price:.2f}**, but your wallet only holds **₹{user_bal:.2f}**.\n\nPlease top up your funds first.")
                        return
                    
                    # Deduct balance and update tables cleanly
                    await cursor.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (display_price, uid))
                    await cursor.execute("DELETE FROM available_accounts WHERE phone_number = %s", (phone_to_buy,))
                    
                    # Packaging connection components safely into the data rows string variable parameter
                    bundled_meta = f"{api_id_to_buy}|{api_hash_to_buy}|{session_to_buy}"
                    await cursor.execute(
                        "INSERT INTO active_orders (phone_number, uid, status) VALUES (%s, %s, %s)",
                        (phone_to_buy, uid, bundled_meta)
                    )
                    await conn.commit()

            display_flag = country_flags.get(detected_country_name, "🌐")
            success_msg = (
                f"✅ **Number reserved successfully**\n\n"
                f"📞 **Phone:** `{phone_to_buy}`\n"
                f"🌍 **Country:** {detected_country_name} {display_flag}\n"
                f"💰 **Price:** ₹{display_price:.2f}\n\n"
                f"🌟 **Note:** Your account reservation is active. Use the button below to check your dynamic inbox updates!"
            )
            
            await event.respond(success_msg, buttons=[[Button.inline("✉️ Check OTP", data=f"checkotp:{phone_to_buy}")]])
        except Exception as e:
            logging.error(f"Error during storefront purchase handler: {e}")
            await event.respond("❌ An error occurred while processing your selection request.")
        return


        # 2. Second Step: Extract stored data logs and execute instant validation hook
    elif data.startswith("checkotp:"):
        try:
            _, target_phone = data.split(":")
            target_phone = target_phone.strip()
            
            await event.answer("🔄 Scanning account inbox instantly...", alert=False)
            
            api_id_val = None
            api_hash_val = None
            session_str_val = None
            
            async with await get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    # Query active_orders table to fetch backup key details securely
                    await cursor.execute(
                        "SELECT status FROM active_orders WHERE phone_number = %s AND uid = %s", 
                        (target_phone, uid)
                    )
                    row = await cursor.fetchone()
                    if row and row[0]:
                        try:
                            api_id_val, api_hash_val, session_str_val = row[0].split("|", 2)
                        except ValueError:
                            pass

            fetched_otp = "⏳ NO LIVE SMS FOUND YET"

            if session_str_val:
                temp_client = None
                try:
                    from telethon.sessions import StringSession
                    
                    temp_client = TelegramClient(
                        StringSession(session_str_val.strip()), 
                        int(api_id_val.strip()), 
                        api_hash_val.strip(),
                        connection_retries=1,
                        retry_delay=1
                    )
                    
                    # Fast connection timeout constraint
                    await asyncio.wait_for(temp_client.connect(), timeout=4.0)
                    
                    if await temp_client.is_user_authorized():
                        # Scan exclusively the official Telegram notifications user profile
                        async for msg in temp_client.iter_messages(777000, limit=1):
                            if msg.text:
                                otp_match = re.search(r'\b\d{5,6}\b', msg.text)
                                if otp_match:
                                    fetched_otp = otp_match.group(0)
                                else:
                                    # Clean and format plain text snippets safely
                                    fetched_otp = msg.text[:40].replace('\n', ' ').strip()
                    else:
                        fetched_otp = "❌ SESSION EXPIRED / TERMINATED"
                        
                except Exception as e:
                    logging.error(f"Instant Live Check Fault: {e}")
                    fetched_otp = "⏳ NO LIVE SMS FOUND YET"
                    
                finally:
                    if temp_client is not None:
                        try:
                            if temp_client.is_connected():
                                await temp_client.disconnect()
                        except Exception:
                            pass

            # 1. Dynamically read global price entries and country matching settings
            custom_prices = await get_country_prices()
            DEFAULT_PRICE = custom_prices.get("DEFAULT", 53.39)
            
            country_flags = {
                "Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦",
                "United States": "🇺🇸", "India": "🇮🇳", "Ethiopia": "🇪🇹"
            }
            
            prefix_to_country = {
                "+57": "Colombia", "+234": "Nigeria", "+880": "Bangladesh", 
                "+91": "India", "+251": "Ethiopia", "+20": "Egypt", "+98": "Iran", 
                "+92": "Pakistan", "+62": "Indonesia", "+254": "Kenya", 
                "+56": "Chile", "+228": "Togo", "+244": "Angola", "+81": "Japan", "+977": "Nepal"
            }

            # 2. Extract country metadata matching the active phone string selection
            clean_phone_check = target_phone
            if not clean_phone_check.startswith("+"):
                clean_phone_check = "+" + clean_phone_check

            detected_country = "Other International"
            for prefix in sorted(prefix_to_country.keys(), key=len, reverse=True):
                if clean_phone_check.startswith(prefix):
                    detected_country = prefix_to_country[prefix]
                    break

            display_flag = country_flags.get(detected_country, "🌐")
            display_price = custom_prices.get(detected_country, DEFAULT_PRICE)

            # 3. Dynamic layout structures display accurate metrics seamlessly
            custom_otp_message = (
                f"{display_flag} **{detected_country}**   ₹{display_price:.1f}   ✅\n\n"
                f"📞 **Phone Number:** `{target_phone}`\n"
                f"📩 **OTP:** **`{fetched_otp}`**\n\n"
                f"⚠️ **Note:** The Re-Request button is active for 24 hours. "
                f"After that, you'll need to request a new number."
            )
            
            # Use respond or edit safely to update the UI framework screen directly
            await event.respond(
                custom_otp_message, 
                buttons=[[Button.inline("🔄 Re-Request OTP", data=f"checkotp:{target_phone}")]]
            )
            
        except Exception as general_err:
            logging.error(f"Global error inside checkotp handler: {general_err}")



# --- Execution Runtime Initialization Loop ---
async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("SKY OTP Master Bot Infrastructure is Online.")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
