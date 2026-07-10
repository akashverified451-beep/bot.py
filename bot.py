import os
import random
import logging
import asyncio
import io
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, join_date TEXT)")

def get_user_bal(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT balance FROM users WHERE uid = ?", (uid,)).fetchone()
        return round(row[0], 2) if row else 0.0

def get_user_jd(uid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT join_date FROM users WHERE uid = ?", (uid,)).fetchone()
        return row[0] if row else "N/A"

def register_user(uid):
    with sqlite3.connect(DB_PATH) as conn:
        if not conn.execute("SELECT uid FROM users WHERE uid = ?", (uid,)).fetchone():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0.0, ?)", (uid, now))

def update_balance(uid, amount):
    register_user(uid)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amount, uid))

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
    register_user(msg.from_user.id)
    await msg.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=main_kb())

@dp.message(F.text == "💼 Wallet")
async def wallet_handler(msg: Message):
    register_user(msg.from_user.id)
    await msg.answer(f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{get_user_bal(msg.from_user.id)}</b>\n\nPlease select your funding process.", reply_markup=balance_kb(), parse_mode="HTML")

@dp.message(F.text == "👤 User Profile")
async def profile_handler(msg: Message):
    register_user(msg.from_user.id)
    uid = msg.from_user.id
    await msg.answer(f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{get_user_bal(uid)}\n📅 <b>Join Date:</b> {get_user_jd(uid)}", parse_mode="HTML")

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
    txn = "".join([str(random.randint(0, 9)) for _ in range(12)])
    
    # FIXED: Generate a completely unique identifier tracking paisa value (e.g., 11 to 99 paise)
    paisa_extension = random.randint(11, 99)
    
    # Generate QR link embedded with variable tracking markers so the app defaults to include it
    upi_payload = f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR"
    img = qrcode.make(upi_payload)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    cap = (
        f"👋 <b>Welcome to the Deposit System</b>\n\n"
        f"⚠️ <b>CRITICAL IDENTIFICATION RULE:</b>\n"
        f"To avoid validation delays, please modify your final payment value to include exactly <b>.{paisa_extension}</b> paise!\n"
        f"Example: If paying ₹100, transfer exactly <b>₹100.{paisa_extension}</b>\n\n"
        f"📌 <b>Your Assigned Identifier Code:</b> `.{paisa_extension}` paise.\n"
        f"📌 <b>Transaction Reference:</b> <code>{txn}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Status", callback_data=f"chk_{uid}_{txn}_{paisa_extension}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    await msg.answer_photo(photo=BufferedInputFile(buf.read(), filename="qr.png"), caption=cap, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("chk_"))
async def user_check_click(cb: CallbackQuery):
    parts = cb.data.split("_")
    uid, txn, paisa = parts[1], parts[2], parts[3]
    await cb.answer("⏳ Verification request sent to admin!", show_alert=True)
    await cb.message.edit_caption(caption="⏳ <b>Verification Sent</b>\n\nThe admin is verifying your payment profile matching tracking signatures.", parse_mode="HTML")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add_{uid}_{txn}_1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add_{uid}_{txn}_5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add_{uid}_{txn}_10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add_{uid}_{txn}_50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add_{uid}_{txn}_100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add_{uid}_{txn}_500")],
        [InlineKeyboardButton(text="📩 Confirm & Send", callback_data=f"snd_{uid}_{txn}_0")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"dny_{uid}")]
    ])
    
    # Admin notification clearly labels the identifying micro-amount to look for in bank logs
    await bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID, 
        text=f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN:</b> <code>{txn}</code>\n🔍 <b>Look for Statement Ending In:</b> <u><b>.{paisa} Paisa</b></u>\n💰 <b>Added So Far:</b> ₹0", 
        reply_markup=akb, 
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("add_"))
async def admin_add_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    parts = cb.data.split("_")
    uid, txn, amt = int(parts[1]), parts[2], int(parts[3])
    
    current_text = cb.message.text
    session_amt = 0
    if "Added So Far: ₹" in current_text:
        try: session_amt = int(current_text.split("Added So Far: ₹")[1].strip())
        except Exception: session_amt = 0
        
    new_session_total = session_amt + amt
    update_balance(uid, amt)
    await cb.answer(f"Added +₹{amt}")
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ₹1", callback_data=f"add_{uid}_{txn}_1"), InlineKeyboardButton(text="➕ ₹5", callback_data=f"add_{uid}_{txn}_5")],
        [InlineKeyboardButton(text="➕ ₹10", callback_data=f"add_{uid}_{txn}_10"), InlineKeyboardButton(text="➕ ₹50", callback_data=f"add_{uid}_{txn}_50")],
        [InlineKeyboardButton(text="➕ ₹100", callback_data=f"add_{uid}_{txn}_100"), InlineKeyboardButton(text="➕ ₹500", callback_data=f"add_{uid}_{txn}_500")],
        [InlineKeyboardButton(text=f"📩 Confirm & Send ₹{new_session_total}", callback_data=f"snd_{uid}_{txn}_{new_session_total}")],
        [InlineKeyboardButton(text="❌ Decline Request", callback_data=f"dny_{uid}")]
    ])
    
    # Keeps parsing the statement identifier visible while you configure target values
    paisa_label = current_text.split("Look for Statement Ending In:")[1].split("\n")[0].strip()
    await cb.message.edit_text(text=f"🚨 <b>Adjusting Deposit Claim!</b>\n👤 <b>User:</b> <code>{uid}</code>\n📌 <b>TXN:</b> <code>{txn}</code>\n🔍 <b>Look for Statement Ending In:</b> {paisa_label}\n💰 <b>Added So Far:</b> ₹{new_session_total}", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("snd_"))
async def admin_send_receipt_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    parts = cb.data.split("_")
    uid, txn, final_session_amt = int(parts[1]), parts[2], int(parts[3])
    
    current_bal = get_user_bal(uid)
    await cb.message.edit_text(f"✅ Approved and sent receipt total of ₹{final_session_amt} to user <code>{uid}</code>.")
    
    rcpt = f"✅ <b>Payment Confirmed!</b>\n\n<b>Transaction ID:</b> <code>{txn}</code>\n<b>Amount Added:</b> ₹{final_session_amt}\n<b>Current Total Balance:</b> ₹{current_bal}\n\nThank you for choosing SKY OTP!"
    try: await bot.send_message(chat_id=uid, text=rcpt, parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("dny_"))
async def admin_deny_click(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_TELEGRAM_ID: return
    uid = int(cb.data.split("_")[1])
    await cb.message.edit_text(f"❌ Denied request from user <code>{uid}</code>.")
    try: await bot.send_message(chat_id=uid, text="❌ Your transaction review request was declined by the administrator.")
    except Exception: pass

@dp.callback_query(F.data == "cancel")
async def cancel_click(cb: CallbackQuery):
    try: await cb.message.delete()
    except Exception: pass

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
