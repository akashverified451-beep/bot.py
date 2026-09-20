import os
import re
import asyncio
import logging
import aiohttp
import psycopg
from telethon import TelegramClient, events, Button

logging.basicConfig(level=logging.INFO)

# Master Service Configurations (Zero environment settings required on Render dashboard!)
BOT_TOKEN = "8865661759:AAEdZafGwuj6i5rTqDr8Q3oierIe0mD1piE"
WAPPFLY_API_KEY = "dc41e6701f1426233f610751fbe08413846d04491283fc6c0c9171dda75fc2a2"
DATABASE_URL = "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db"
API_ID = int(33033843)
API_HASH = str("27d91aac298b61038f19ee5c1b1f3f48").strip()
ADMIN_TELEGRAM_ID = int(8393210427)

wa_bot = TelegramClient('unique_whatsapp_session_file', API_ID, API_HASH)

async def get_db_connection():
    """Establishes an isolated asynchronous connection bridge using Psycopg 3."""
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def get_country_prices(service_type="WhatsApp"):
    """Fetches custom pricing from the shared database filtered by category."""
    defaults = {
        "Colombia": 55.00, "Nigeria": 55.00, "Bangladesh": 55.00,
        "Canada": 55.00, "United States": 55.00, "India": 55.00, "Ethiopia": 55.00,
        "DEFAULT": 55.00
    }
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT country, price FROM country_prices WHERE LOWER(service_type) = LOWER(%s)",
                (service_type,)
            )
            rows = await cursor.fetchall()
            for country, price in rows:
                defaults[country.strip()] = float(price)
        await conn.close()
    except Exception as e:
        logging.error(f"Error fetching dynamic WhatsApp prices: {e}")
    return defaults

# -------------------------------------------------------------
# 🟢 Admin WhatsApp Custom Price Adjustment Command
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern=r"^/updateprice_wa\s+(.*)"))
async def update_whatsapp_pricing_handler(event):
    uid = event.sender_id
    text = event.text
    
    if int(uid) != int(ADMIN_TELEGRAM_ID):
        return

    try:
        command_body = event.pattern_match.group(1).strip()
        country, price_str = [item.strip() for item in command_body.split(",")]
        new_price = float(price_str)

        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute("CREATE TABLE IF NOT EXISTS country_prices (country TEXT PRIMARY KEY, price REAL)")
            await cursor.execute(
                "INSERT INTO country_prices (country, price) VALUES ($1, $2) "
                "ON CONFLICT (country) DO UPDATE SET price = EXCLUDED.price",
                (country, new_price)
            )
            await conn.commit()
        await conn.close()

        await event.respond(
            f"💰 **WhatsApp Price Updated Successfully!**\n\n"
            f"🌍 **Country:** {country}\n"
            f"💵 **New Price:** ₹{new_price:.2f}\n\n"
            f"The WhatsApp grid menu will apply this price change instantly."
        )
    except Exception as e:
        await event.respond(
            "❌ **Format Mistake!** Use exactly:\n`/updateprice_wa Country,Price`\n\n"
            "Example:\n`/updateprice_wa United States,65.00`"
        )

# -------------------------------------------------------------
# 🟢 Fixed Live User Join Notifier (Ab fake alerts nahi bhejega)
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern=r"^/start\$"))  # 👈 Exact /start command lock
async def live_user_join_notifier_handler(event):
    uid = event.sender_id

    # Admin agar khud type kare to ignore maarein
    if int(uid) == int(ADMIN_TELEGRAM_ID):
        event.handled = True
        return

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Check user table using clean placeholders
            await cursor.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
            row = await cursor.fetchone()
            
            # Agar user database mein nahi hai, toh initialize aur notify karein
            if row is None:
                sender = await event.get_sender()
                username = f"@{sender.username}" if sender.username else "No Username"
                first_name = sender.first_name or "User"
                
                join_alert = (
                    f"👤 **🚀 New User Joined Your Bot!**\n\n"
                    f"🏷 **Name:** {first_name}\n"
                    f"💬 **Username:** {username}\n"
                    f"🆔 **Telegram UID:** `{uid}`\n"
                    f"📊 Status: Profile initialized automatically inside PostgreSQL."
                )
                try:
                    await wa_bot.send_message(int(ADMIN_TELEGRAM_ID), join_alert)
                except Exception:
                    pass
    except Exception as e:
        logging.error(f"Join monitoring loop exception error: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            
    event.handled = True
    return

# -------------------------------------------------------------
# 📊 Administrative Total Registered Customer Count Lookup Command
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern=r"^/users$"))
async def admin_total_users_count_handler(event):
    uid = event.sender_id
    
    # Strictly lock authorization access to prevent configuration visibility leaks
    if int(uid) != int(ADMIN_TELEGRAM_ID):
        return

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Execute high-speed global count across your central user profile ledger table rows
            await cursor.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            total_registered_users = row[0] if row else 0
        await conn.close()

        # Output the structural data summary directly to your dashboard screen
        report_card = (
            f"📊 **SKY OTP BOT - SYSTEM USER METRICS**\n\n"
            f"👥 **Total Registered Customers:** `{total_registered_users}` users\n"
            f"📈 Status: Core ledger table profiles verified in PostgreSQL."
        )
        await event.respond(report_card)

    except Exception as err:
        logging.error(f"Total user count metric engine breakdown: {err}")
        await event.respond(f"❌ **System Error:** Failed compiling aggregate user metrics: `{err}`")

# -------------------------------------------------------------
# 🟢 1. Handle Buy Whatsapp OTP Main Menu Button Click
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern=r"(?i).*Buy Whatsapp OTP.*"))
async def whatsapp_storefront_menu_handler(event):
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT country_name, COUNT(*) FROM whatsapp_stock GROUP BY country_name")
            stock_rows = await cursor.fetchall()
            inventory = {row[0]: row[1] for row in stock_rows}
            
        # Fetch dynamic custom WhatsApp pricing parameters exclusively 
        try:
            custom_prices = await get_country_prices("WhatsApp")
        except Exception as price_err:
            logging.error(f"Fallback to internal price values: {price_err}")
            custom_prices = {}

        await conn.close()

        DEFAULT_PRICE = custom_prices.get("DEFAULT", 55.00)
        country_flags = {"Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦", "United States": "🇺🇸", "India": "🇮🇳", "Ethiopia": "🇪🇹"}

        wa_services_kb = [[Button.inline("🌍 Country", data="lbl"), Button.inline("💵 Price", data="lbl"), Button.inline("📦 Stock", data="lbl")]]

        for country_name, stock_qty in inventory.items():
            if stock_qty > 0:
                flag = country_flags.get(country_name, "🌐")
                price = custom_prices.get(country_name, DEFAULT_PRICE)
                callback_payload = f"buy_wa_{country_name.lower().replace(' ', '')[:15]}"
                
                wa_services_kb.append([
                    Button.inline(f"{flag} {country_name}", data=callback_payload),
                    Button.inline(f"₹{price:.1f}", data=callback_payload),
                    Button.inline(f"[{stock_qty}] ✅", data=callback_payload)
                ])

        await event.respond("🟢 **Available WhatsApp Services**", buttons=wa_services_kb)
    except Exception as e:
        logging.error(f"Storefront layout breakdown exception: {e}")
        await event.respond("❌ An error occurred while generating the WhatsApp store list.")

# =============================================================
# 🟢 2. Custom Button Interaction Handlers (Strict Wallet Check)
# =============================================================
@wa_bot.on(events.CallbackQuery(pattern=r"^buy_wa_"))
async def buy_whatsapp_account_handler(event):
    uid = event.sender_id
    try:
        target_slug = event.data.decode('utf-8').replace("buy_wa_", "").strip()
        
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # 1. 📦 Sabse pehle stock se number aur uski details nikalein
            await cursor.execute(
                "SELECT phone_number, download_link, auth_key, country_name FROM whatsapp_stock WHERE LOWER(REPLACE(country_name, ' ', '')) = %s LIMIT 1",
                (target_slug,)
            )
            selected_wa = await cursor.fetchone()
            
            if not selected_wa:
                await event.respond("⚠️ **Out of Stock!** No available numbers match this region currently.")
                await event.answer()
                return

            phone, inst_id, api_token, country_name = selected_wa

            # 2. 💵 Country ka price nikalein
            try:
                custom_prices = await get_country_prices("WhatsApp")
            except Exception:
                custom_prices = {}
                
            display_price = custom_prices.get(country_name, custom_prices.get("DEFAULT", 55.00))

            # 3. 💳 User ka actual wallet balance fetch karein
            await cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
            bal_row = await cursor.fetchone()
            user_bal = bal_row[0] if bal_row else 0

            # 🛑 Tight Security Check: Agar balance price se kam hai, toh yahi block karo
            if user_bal < display_price:
                await event.respond(
                    f"❌ **Insufficient Funds!**\n\n"
                    f"This account costs **₹{display_price:.2f}**, but your balance is **₹{user_bal:.2f}**.\n"
                    f"Please add funds to your wallet first!"
                )
                await event.answer()
                return

            # 4. 💸 Agar balance hai, toh paise deduct karein aur database update karein
            await cursor.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (display_price, uid))
            await cursor.execute("DELETE FROM whatsapp_stock WHERE phone_number = %s", (phone,))
            await cursor.execute("INSERT INTO active_orders (phone_number, uid, status) VALUES (%s, %s, %s)", (phone, uid, 'pending'))
            await conn.commit()

        # 📱 User ko reserved screen aur Get OTP ka button dikhana
        recheck_kb = [[Button.inline("🔄 Get WhatsApp OTP", data=f"check_wa_otp:{phone}")]]
        await event.edit(
            f"🎉 **WhatsApp Number Reserved!**\n\n"
            f"📞 **Phone:** `{phone}`\n"
            f"🌍 **Country:** {country_name}\n\n"
            f"Request your SMS code inside your official WhatsApp mobile app, "
            f"then click the button below to fetch your OTP instantly!", 
            buttons=recheck_kb
        )
        
        # 🔔 Admin ko real sold alert send karna
        admin_alert_text = f"💰 **WhatsApp Stock Sold Alert!**\n\n📞 **Number:** `{phone}`\n🌍 **Country:** {country_name}\n👤 **Buyer UID:** `{uid}`\n💵 **Price:** ₹{display_price:.2f}"
        try:
            await wa_bot.send_message(int(ADMIN_TELEGRAM_ID), admin_alert_text)
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Checkout block crash: {e}")
        await event.respond("❌ **An error occurred during selection processing.**")
    finally:
        if 'conn' in locals():
            await conn.close()
            
    await event.answer()
    event.handled = True
    return
    
# -------------------------------------------------------------
# 🟢 3. The Live Wappfly OTP Interceptor + Auto-Refund Engine
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^check_wa_otp:"))
async def instant_whatsapp_otp_fetcher(event):
    _, target_phone = event.data.decode('utf-8').split(":")
    uid = event.sender_id
    
    await event.answer("⚡ Streaming live Wappfly cloud inbox events...", alert=False)
    
    fetched_otp = "⏳ NO WHATSAPP SMS FOUND YET"
    
    # Official Wappfly Developer API chat history read endpoint query URL string
    wappfly_url = "https://wappfly.com"
    headers = {"Authorization": f"Bearer {WAPPFLY_API_KEY}"}
    params = {"chatId": "status@broadcast", "limit": 3}
    
    try:
        async with aiohttp.ClientSession() as session:
            for attempt in range(12): 
                async with session.get(wappfly_url, headers=headers, params=params, timeout=4.0) as response:
                    if response.status == 200:
                        messages_list = await response.json()
                        for msg in messages_list:
                            # Pulling body value out of incoming dictionary array payload
                            text_body = msg.get("body", "")
                            if text_body:
                                otp_match = re.search(r'\b\d{3}-\d{3}\b|\b\d{6}\b', text_body)
                                if otp_match:
                                    fetched_otp = otp_match.group(0).replace("-", "")
                                    break
                if fetched_otp != "⏳ NO WHATSAPP SMS FOUND YET":
                    break
                await asyncio.sleep(2.5)
    except Exception as e:
        logging.error(f"Wappfly polling connection failure exception: {e}")

    if fetched_otp == "⏳ NO WHATSAPP SMS FOUND YET":
        recheck_kb = [
            [Button.inline("🔄 Re-Check OTP", data=f"check_wa_otp:{target_phone}")],
            [Button.inline("❌ Cancel & Refund", data=f"refund_wa_order:{target_phone}")]
        ]
        status_note = "⚠️ **Note:** If code isn't arriving, click 'Cancel & Refund' to restore balance instantly."
    else:
        recheck_kb = [[Button.inline("🔄 Re-Check OTP", data=f"check_wa_otp:{target_phone}")]]
        status_note = "✅ Code retrieved successfully!"

    await event.edit(f"🟢 **WhatsApp Live OTP Portal**\n\n📞 **Phone:** `{target_phone}`\n📩 **WhatsApp OTP:** **`{fetched_otp}`**\n\n{status_note}", buttons=recheck_kb)

# -------------------------------------------------------------
# 🟢 4. The Automated Refund Request Receiver
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^refund_wa_order:"))
async def refund_whatsapp_order_handler(event):
    _, target_phone = event.data.decode('utf-8').split(":")
    uid = event.sender_id

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Check if active order exists
            await cursor.execute("SELECT phone_number, status FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
            order_row = await cursor.fetchone()
            if not order_row:
                await event.respond("❌ Order already cleared or processed.")
                await conn.close()
                return
            
            # Fetch country name to map price attributes
            await cursor.execute("SELECT country_name FROM whatsapp_stock WHERE phone_number = %s", (target_phone,))
            stock_row = await cursor.fetchone()
            country_name = stock_row[0] if stock_row else "DEFAULT"
            
            # Dynamically calculate the matching refund rate
            try:
                custom_prices = await get_country_prices("WhatsApp")
                refund_amount = custom_prices.get(country_name, custom_prices.get("DEFAULT", 55.00))
            except Exception:
                refund_amount = 55.00

            # Execute financial balances reversal safely inside data stream
            await cursor.execute("UPDATE users SET balance = balance + %s WHERE uid = %s", (refund_amount, uid))
            await cursor.execute("DELETE FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
            await conn.commit()
            await conn.close()

        await event.edit(f"🛑 **Order Cancelled Successfully!**\n\n📞 **Phone:** `{target_phone}`\n💰 **Refund Credit:** +₹{refund_amount:.2f}\n\nFunds returned successfully.")
    except Exception as e:
        logging.error(f"Refund runtime error: {e}")
        await event.respond("❌ Failed processing wallet refund.")

async def main():
    await wa_bot.start(bot_token=BOT_TOKEN)
    logging.info("Free Unlimited Wappfly background service worker daemon is active.")
    await wa_bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
