import os
import re
import asyncio
import logging
import aiohttp
import psycopg2
from telethon import TelegramClient, events, Button

logging.basicConfig(level=logging.INFO)

# Core Configurations (Render will pass these into both workers)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", 0))

# Boot up the client instance for your WhatsApp worker
wa_bot = TelegramClient('whatsapp_worker_runtime', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# -------------------------------------------------------------
# 🟢 1. Handle Buy Whatsapp OTP Main Menu Button Click
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern=r"(?i)/?Buy Whatsapp OTP.*"))
async def whatsapp_storefront_menu_handler(event):
    uid = event.sender_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch live stock counts grouped by country name
        cursor.execute(
            "SELECT country_name, COUNT(*) FROM whatsapp_stock GROUP BY country_name"
        )
        stock_rows = cursor.fetchall()
        inventory = {row[0]: row[1] for row in stock_rows}
        
        # 2. Fetch custom price adjustments (Fall back to default if table missing)
        custom_prices = {}
        try:
            cursor.execute("SELECT country, price FROM country_prices")
            price_rows = cursor.fetchall()
            custom_prices = {row[0]: row[1] for row in price_rows}
        except Exception:
            pass
            
        cursor.close()
        conn.close()

        DEFAULT_PRICE = custom_prices.get("DEFAULT", 55.00)
        
        country_flags = {
            "Colombia": "🇨🇴", "Nigeria": "🇳🇬", "Bangladesh": "🇧🇩", "Canada": "🇨🇦",
            "United States": "🇺🇸", "India": "🇮🇳", "Ethiopia": "🇪🇹", "Togo": "🇹🇬", "Pakistan": "🇵🇰"
        }

        # 3. Create the Grid Header Row
        wa_services_kb = [
            [
                Button.inline("🌍 Country", data="lbl"),
                Button.inline("💵 Price", data="lbl"),
                Button.inline("📦 Stock", data="lbl")
            ]
        ]

        # 4. Generate Dynamic Grid Rows exactly like your Telegram menu
        for country_name, stock_qty in inventory.items():
            if stock_qty > 0:
                flag = country_flags.get(country_name, "🌐")
                price = custom_prices.get(country_name, DEFAULT_PRICE)
                
                # Truncate callback payloads heavily to stay safely under 64 bytes
                callback_payload = f"buy_wa_{country_name.lower().replace(' ', '')[:15]}"
                
                country_row = [
                    Button.inline(f"{flag} {country_name}", data=callback_payload),
                    Button.inline(f"₹{price:.1f}", data=callback_payload),
                    Button.inline(f"[{stock_qty}] ✅", data=callback_payload)
                ]
                wa_services_kb.append(country_row)

        # 5. Output the finished grid menu directly to the user screen
        await event.respond("🟢 **Available WhatsApp Services**", buttons=wa_services_kb)

    except Exception as e:
        import logging
        logging.error(f"Critical crash inside WhatsApp storefront builder: {e}")
        await event.respond("❌ An error occurred while generating the WhatsApp store list.")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# -------------------------------------------------------------
# 🟢 1. EXTRA WHATSAPP COMMANDS & LAYOUTS GO HERE!
# -------------------------------------------------------------
@wa_bot.on(events.NewMessage(pattern='/wasettings'))
async def wa_custom_settings_handler(event):
    uid = event.sender_id
    if int(uid) == int(ADMIN_TELEGRAM_ID):
        # You can style this menu keyboard however you want!
        wa_settings_kb = [
            [Button.inline("🔧 Change Keyboard Style", data="wa_style_change")],
            [Button.inline("📈 Boost WhatsApp Prices", data="wa_price_boost")]
        ]
        await event.respond("⚙️ **WhatsApp Custom Admin Panel**\nModify your layouts directly below:", buttons=wa_settings_kb)

# -------------------------------------------------------------
# 🟢 2. THE CUSTOM BUTTON INTERACTION HANDLERS GO HERE!
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^buy_wa_"))
async def buy_whatsapp_account_handler(event):
    # This completely handles the purchase step when a user clicks a WhatsApp country button!
    target_slug = event.data.decode('utf-8').replace("buy_wa_", "").strip()
    uid = event.sender_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch available stock matching selection criteria
        cursor.execute(
            "SELECT phone_number, download_link, auth_key, country_name "
            "FROM whatsapp_stock WHERE LOWER(country_name) LIKE %s LIMIT 1",
            (f"%{target_slug}%",)
        )
        selected_wa = cursor.fetchone()

        if not selected_wa:
            await event.respond("⚠️ **Out of Stock!** No available numbers match your requested country.")
            cursor.close()
            conn.close()
            return

        phone, inst_id, api_token, country_name = selected_wa
        display_price = 55.00 # Set your default custom WhatsApp price here!

        # 2. Verify user financial capability balance
        cursor.execute("SELECT balance FROM users WHERE uid = %s", (uid,))
        bal_row = cursor.fetchone()
        user_bal = bal_row[0] if (bal_row and bal_row[0] is not None) else 0

        if user_bal < display_price:
            await event.respond(f"❌ **Insufficient Funds!**\nThis costs **₹{display_price:.2f}**, but your balance is **₹{user_bal:.2f}**.")
            cursor.close()
            conn.close()
            return

        # 3. Process transaction states atomically
        cursor.execute("UPDATE users SET balance = balance - %s WHERE uid = %s", (display_price, uid))
        cursor.execute("DELETE FROM whatsapp_stock WHERE phone_number = %s", (phone,))
        
        # Pack your Green-API tokens seamlessly inside the active order record configuration
        bundled_wa_meta = f"{inst_id}|{api_token}"
        cursor.execute(
            "INSERT INTO active_orders (phone_number, uid, status) VALUES (%s, %s, %s)",
            (phone, uid, bundled_wa_meta)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # 4. Output successful receipt directly to customer dashboard
        recheck_kb = [[Button.inline("🔄 Get WhatsApp OTP", data=f"check_wa_otp:{phone}")]]
        
        success_delivery = (
            f"🎉 **WhatsApp Number Reserved Successfully!**\n\n"
            f"📞 **Phone Number:** `{phone}`\n"
            f"🌍 **Country:** {country_name}\n"
            f"💵 **Price:** ₹{display_price:.2f}\n\n"
            f"📥 **Instructions:** Request Code via SMS inside your official WhatsApp app, then use the button below to fetch the code live!"
        )
        await event.edit(success_delivery, buttons=recheck_kb)

    except Exception as wa_buy_err:
        logging.error(f"WhatsApp storefront checkout crash: {wa_buy_err}")
        await event.respond("❌ An error occurred while processing your storefront selection request.")

# -------------------------------------------------------------
# 🟢 3. THE LIVE OTP LOOKUP LOGIC GOES HERE!
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^check_wa_otp:"))
async def instant_whatsapp_otp_fetcher(event):
    _, target_phone = event.data.decode('utf-8').split(":")
    uid = event.sender_id
    
    await event.answer("⚡ Streaming live WhatsApp incoming chat logs...", alert=False)
    
    instance_id = None
    api_token = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
    row = cursor.fetchone()
    if row and row[0]:
        instance_id, api_token = row[0].split("|", 1)
    cursor.close()
    conn.close()

    fetched_otp = "⏳ NO WHATSAPP SMS FOUND YET"

    if instance_id and api_token:
        get_chats_url = f"https://green-api.com{instance_id}/getChatHistory/{api_token}"
        payload = {"chatId": "5511933007000@c.us", "count": 3}
        
        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(12): 
                    async with session.post(get_chats_url, json=payload, timeout=5.0) as response:
                        if response.status == 200:
                            messages = await response.json()
                            for msg in messages:
                                text_content = msg.get("textMessage", "") or msg.get("extendedTextMessage", {}).get("text", "")
                                if text_content:
                                    otp_match = re.search(r'\b\d{3}-\d{3}\b|\b\d{6}\b', text_content)
                                    if otp_match:
                                        fetched_otp = otp_match.group(0).replace("-", "")
                                        break
                    if fetched_otp != "⏳ NO WHATSAPP SMS FOUND YET":
                        break
                    await asyncio.sleep(2.5)
        except Exception as api_err:
            logging.error(f"Live WhatsApp connection error: {api_err}")

    custom_otp_message = (
        f"🟢 **WhatsApp Live OTP Portal**\n\n"
        f"📞 **Phone Number:** `{target_phone}`\n"
        f"📩 **WhatsApp OTP:** **`{fetched_otp}`**\n\n"
        f"Click re-check if your code hasn't appeared yet."
    )
    
    recheck_kb = [[Button.inline("🔄 Re-Check WhatsApp OTP", data=f"check_wa_otp:{target_phone}")]]
    await event.edit(custom_otp_message, buttons=recheck_kb)

async def main():
    logging.info("WhatsApp background service worker engine is running cleanly...")
    await wa_bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
