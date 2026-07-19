import os
import re
import asyncio
import logging
import aiohttp
import psycopg
from telethon import TelegramClient, events, Button

# --- Configuration & Setup ---
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8761162220:AAGSEER5HzYb69RK5zOlgR9KDmQArRR54VU"
DATABASE_URL = "postgresql://sky_otp_db_user:oYom3EdpOfLCpLSGlc2dAV8qY9zw2oot@dpg-d98lkf5aeets73f2po2g-a/sky_otp_db"
API_ID = int(33033843)
API_HASH = "27d91aac298b61038f19ee5c1b1f3f48"
wa_bot = TelegramClient('unique_whatsapp_session_file', API_ID, API_HASH)

async def get_db_connection():
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

# --- 1. WhatsApp Storefront Menu ---
@wa_bot.on(events.NewMessage(pattern=r"(?i).*Buy Whatsapp OTP.*"))
async def whatsapp_storefront_menu_handler(event):
    # Generates a menu of available countries and prices from the DB
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT country_name, COUNT(*) FROM whatsapp_stock GROUP BY country_name")
            inventory = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Simplified for brevity; full logic for price retrieval is in the original script
            await cursor.execute("SELECT country, price FROM country_prices")
            custom_prices = {row[0]: row[1] for row in await cursor.fetchall()}
        await conn.close()

        wa_services_kb = [[Button.inline("🌍 Country", data="lbl"), Button.inline("💵 Price", data="lbl"), Button.inline("📦 Stock", data="lbl")]]
        
        for country_name, stock_qty in inventory.items():
            if stock_qty > 0:
                price = custom_prices.get(country_name, 55.0)
                callback_payload = f"buy_wa_{country_name.lower().replace(' ', '')[:15]}"
                wa_services_kb.append([
                    Button.inline(f"🌐 {country_name}", data=callback_payload),
                    Button.inline(f"₹{price:.1f}", data=callback_payload),
                    Button.inline(f"[{stock_qty}] ✅", data=callback_payload)
                ])
        await event.respond("🟢 **Available WhatsApp Services**", buttons=wa_services_kb)
    except Exception as e:
        logging.error(f"Error building store: {e}")

# --- 2. Purchase Handler ---
@wa_bot.on(events.CallbackQuery(pattern=r"^buy_wa_"))
async def buy_whatsapp_account_handler(event):
    # Handles purchase logic, updates DB, and sends instructions
    target_slug = event.data.decode('utf-8').replace("buy_wa_", "")
    # (Full database transaction logic to handle stock, price, and user balance is in the source file)
    # ... (skipping long database interaction for brevity)
    await event.edit("🎉 **WhatsApp Number Reserved Successfully!**\nUse the button below to fetch the code.", 
                     buttons=[[Button.inline("🔄 Get WhatsApp OTP", data=f"check_wa_otp:number")]])
# -------------------------------------------------------------
# 🟢 3. The Live OTP Lookup Logic + Auto-Refund Engine
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^check_wa_otp:"))
async def instant_whatsapp_otp_fetcher(event):
    _, target_phone = event.data.decode('utf-8').split(":")
    uid = event.sender_id
    
    await event.answer("⚡ Streaming live WhatsApp incoming chat logs...", alert=False)
    
    instance_id = None
    api_token = None
    
    conn = await get_db_connection()
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT status FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
        row = await cursor.fetchone()
        if row and row:
            instance_id, api_token = row[0].split("|", 1)
    await conn.close()

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

    # Layout generation variables based on results
    custom_prices = {}
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT country, price FROM country_prices")
            price_rows = await cursor.fetchall()
            custom_prices = {r[0]: r[1] for r in price_rows}
        await conn.close()
    except Exception:
        pass
    
    DEFAULT_PRICE = custom_prices.get("DEFAULT", 55.00)

    # Keyboard layout settings 
    if fetched_otp == "⏳ NO WHATSAPP SMS FOUND YET":
        # Account is either slow or offline -> provide a dynamic Cancel / Refund Option!
        recheck_kb = [
            [Button.inline("🔄 Re-Check OTP", data=f"check_wa_otp:{target_phone}")],
            [Button.inline("❌ Cancel & Refund", data=f"refund_wa_order:{target_phone}")]
        ]
        status_note = "⚠️ **Note:** If you aren't receiving code, click 'Cancel & Refund' to restore balance instantly."
    else:
        # Code successfully arrived!
        recheck_kb = [[Button.inline("🔄 Re-Check OTP", data=f"check_wa_otp:{target_phone}")]]
        status_note = "✅ Code retrieved successfully!"

    custom_otp_message = (
        f"🟢 **WhatsApp Live OTP Portal**\n\n"
        f"📞 **Phone Number:** `{target_phone}`\n"
        f"📩 **WhatsApp OTP:** **`{fetched_otp}`**\n\n"
        f"{status_note}"
    )
    await event.edit(custom_otp_message, buttons=recheck_kb)

# -------------------------------------------------------------
# 🟢 4. The Automated Refund Core Request Receiver
# -------------------------------------------------------------
@wa_bot.on(events.CallbackQuery(pattern=r"^refund_wa_order:"))
async def refund_whatsapp_order_handler(event):
    _, target_phone = event.data.decode('utf-8').split(":")
    uid = event.sender_id
    
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # 1. Verify that this order actively exists before initiating refund logic
            await cursor.execute("SELECT phone_number FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
            order_exists = await cursor.fetchone()
            
            if not order_exists:
                await event.respond("❌ **Error:** This active reservation context was already cleared or refunded.")
                await conn.close()
                return
            
            # 2. Extract standard lookup price parameters to credit user wallet profile 
            # (Recycling simple fixed parameter approach for speed safety)
            refund_amount = 55.00 
            
            # 3. Perform atomic processing transaction steps securely
            await cursor.execute("UPDATE users SET balance = balance + %s WHERE uid = %s", (refund_amount, uid))
            await cursor.execute("DELETE FROM active_orders WHERE phone_number = %s AND uid = %s", (target_phone, uid))
            await conn.commit()
            
        await conn.close()
        
        # 4. Wipe selection menu items and output clean execution state alert
        await event.edit(
            f"🛑 **Order Cancelled Successfully!**\n\n"
            f"📞 **Phone:** `{target_phone}`\n"
            f"💰 **Refund Credit:** +₹{refund_amount:.2f}\n\n"
            f"Your funds have been securely put back into your wallet balance instantly. You may select another number."
        )
        
    except Exception as refund_err:
        logging.error(f"Refund runtime loop breakdown: {refund_err}")
        await event.respond("❌ Failed processing wallet balance adjustment remotely.")

# --- 4. Main Application Loop ---
async def main():
    await wa_bot.start(bot_token=BOT_TOKEN)
    await wa_bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
