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

# --- 3. Live OTP Lookup ---
@wa_bot.on(events.CallbackQuery(pattern=r"^check_wa_otp:"))
async def instant_whatsapp_otp_fetcher(event):
    # Fetches OTP via Green-API
    # ... (full API interaction logic, re.search for OTP, and retries are in the original file)
    await event.edit("🟢 **WhatsApp Live OTP Portal**\n📩 **OTP:** `123456`", 
                     buttons=[[Button.inline("🔄 Re-Check", data="check_wa_otp:num")]])

# --- 4. Main Application Loop ---
async def main():
    await wa_bot.start(bot_token=BOT_TOKEN)
    await wa_bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
