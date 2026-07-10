import os
import random
import logging
import io
import sqlite3
import asyncio
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

# Clear global storage maps tracking targets dynamically 
user_screenshot_state = {}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT)")
        conn.commit()

def get_user_bal(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT balance FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else 0

def get_user_jd(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT join_date FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else "N/A"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛍️ Buy Telegram Account")],
        [KeyboardButton(text="🗨️ Buy Whatsapp OTP")],
        [KeyboardButton(text="💼 Wallet"), KeyboardButton(text="👤 User Profile")]
    ], resize_keyboard=True)

def balance_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Funds")],
        [KeyboardButton(text="🔙 Back to Main Menu")]
    ], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        if not conn.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
            conn.commit()
    await msg.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=main_kb())

@dp.message(F.text == "💼 Wallet")
async def wallet_handler(msg: Message):
    await msg.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{get_user_bal(msg.from_user.id)}</b>\n\nPlease select your funding process.", reply_markup=balance_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 User Profile")
async def profile_handler(msg: Message):
    uid = msg.from_user.id
    await msg.answer(text=f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{get_user_bal(uid)}\n📅 <b>Join Date:</b> {get_user_jd(uid)}", parse_mode="HTML")

@dp.message(F.text == "🔙 Back to Main Menu")
async def back_handler(msg: Message):
    await msg.answer("👋 Welcome to SKY OTP BOT.", reply_markup=main_kb())

@dp.message(F.text == "🛍️ Buy Telegram Account")
async def buy_tg(msg: Message):
    await msg.answer("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode="HTML")

@dp.message(F.text == "➕ Add Funds")
async def add_funds_handler(msg: Message):
    import qrcode
    uid = msg.from_user.id
    img = qrcode.make(f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = "👋 <b>Welcome to the Deposit System</b>\n\nScan the QR code below and pay <b>any amount</b> you wish to add to your wallet."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"status_check_{uid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("status_check_"))
async def handle_status_check(cb: CallbackQuery):
    target_uid = cb.data.replace("status_check_", "")
    user_screenshot_state[int(target_uid)] = True
    await cb.answer()
    await cb.message.answer("📸 Please send a <b>screenshot of your payment receipt</b> now to submit for admin approval:", parse_mode="HTML")

@dp.message(F.photo)
async def process_screenshot_submission(msg: Message):
    uid = msg.from_user.id
    if uid not in user_screenshot_state:
        return
        
    del user_screenshot_state[uid]
    photo_id = msg.photo[-1].file_id
    await msg.answer("⏳ <b>Receipt submitted!</b> The admin is verifying your transaction details now. Thank you.", parse_mode="HTML", reply_markup=main_kb())
    
    # Grid buttons pass clear, readable action commands directly matching target uid 
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add10_{uid}"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add50_{uid}")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add100_{uid}"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add500_{uid}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"denyreq_{uid}")]
    ])
    await bot.send_photo(chat_id=ADMIN_TELEGRAM_ID, photo=photo_id, caption=f"🚨 <b>New Deposit Verification Request!</b>\n👤 <b>User Profile:</b> <code>{uid}</code>", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("add10_"))
async def add_10_handler(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.replace("add10_", ""))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + 10 WHERE uid = ?", (uid,))
        conn.commit()
    await cb.answer("Added ₹10!")
    await cb.message.edit_caption(caption=f"✅ Approved & Accredited funds to user <code>{uid}</code>.", parse_mode="HTML")
    try: await bot.send_message(chat_id=uid, text=f"✅ <b>Payment Confirmed!</b>\n\n₹10 has been added to your wallet.\n💰 <b>Current Balance:</b> ₹{get_user_bal(uid)}", parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("add50_"))
async def add_50_handler(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.replace("add50_", ""))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + 50 WHERE uid = ?", (uid,))
        conn.commit()
    await cb.answer("Added ₹50!")
    await cb.message.edit_caption(caption=f"✅ Approved & Accredited funds to user <code>{uid}</code>.", parse_mode="HTML")
    try: await bot.send_message(chat_id=uid, text=f"✅ <b>Payment Confirmed!</b>\n\n₹50 has been added to your wallet.\n💰 <b>Current Balance:</b> ₹{get_user_bal(uid)}", parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("add100_"))
async def add_100_handler(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.replace("add100_", ""))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + 100 WHERE uid = ?", (uid,))
        conn.commit()
    await cb.answer("Added ₹100!")
    await cb.message.edit_caption(caption=f"✅ Approved & Accredited funds to user <code>{uid}</code>.", parse_mode="HTML")
    try: await bot.send_message(chat_id=uid, text=f"✅ <b>Payment Confirmed!</b>\n\n₹100 has been added to your wallet.\n💰 <b>Current Balance:</b> ₹{get_user_bal(uid)}", parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("add500_"))
async def add_500_handler(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.replace("add500_", ""))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + 500 WHERE uid = ?", (uid,))
        conn.commit()
    await cb.answer("Added ₹500!")
    await cb.message.edit_caption(caption=f"✅ Approved & Accredited funds to user <code>{uid}</code>.", parse_mode="HTML")
    try: await bot.send_message(chat_id=uid, text=f"✅ <b>Payment Confirmed!</b>\n\n₹500 has been added to your wallet.\n💰 <b>Current Balance:</b> ₹{get_user_bal(uid)}", parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("denyreq_"))
async def deny_request_handler(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.replace("denyreq_", ""))
    await cb.message.edit_caption(caption=f"❌ Request from user <code>{uid}</code> was declined.", parse_mode="HTML")
    try: await bot.send_message(chat_id=uid, text="❌ Your transaction review request was declined by the administrator.")
    except Exception: pass

@dp.callback_query(F.data == "cancel_action")
async def cancel_action_handler(cb: CallbackQuery):
    try: await cb.message.delete()
    except Exception: pass

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as error:
            logging.error(f"Execution restart: {error}")
            time.sleep(5)
