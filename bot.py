import os
import random
import logging
import asyncio
import io
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
)
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import qrcode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"

# Database Configuration (Ensures user data survives service restarts)
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            join_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, join_date FROM users WHERE uid = ?", (uid,))
    row = cursor.fetchone()
    conn.close()
    return row

def register_user(uid):
    if not get_user(uid):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, ?, ?)", (uid, 0, now))
        conn.commit()
        conn.close()

def update_balance(uid, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amount, uid))
    conn.commit()
    conn.close()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛍️ Buy Telegram Account")],
        [KeyboardButton(text="🗨️ Buy Whatsapp OTP")],
        [KeyboardButton(text="💼 Wallet"), KeyboardButton(text="👤 User Profile")]
    ], resize_keyboard=True)

def get_balance_reply_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Funds")],
        [KeyboardButton(text="🔙 Back to Main Menu")]
    ], resize_keyboard=True)

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    uid = message.from_user.id
    register_user(uid)
    await message.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=get_main_keyboard())

@dp.message(StateFilter(None), F.text == "💼 Wallet")
async def balance_handler(message: Message):
    uid = message.from_user.id
    register_user(uid)
    user_data = get_user(uid)
    bal = user_data[0] if user_data else 0
    await message.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", reply_markup=get_balance_reply_keyboard(), parse_mode="HTML")

@dp.message(StateFilter(None), F.text == "👤 User Profile")
async def profile_handler(message: Message):
    uid = message.from_user.id
    register_user(uid)
    user_data = get_user(uid)
    bal = user_data[0] if user_data else 0
    jd = user_data[1] if user_data else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await message.answer(text=f"👤 <b>Your Profile Summary</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💰 <b>Balance:</b> ₹{bal}\n📅 <b>Join Date:</b> {jd}", parse_mode="HTML")

@dp.message(F.text == "🔙 Back to Main Menu")
async def process_back_to_main_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(text="👋 Welcome to SKY OTP BOT.", reply_markup=get_main_keyboard())

@dp.message(StateFilter(None), F.text == "🛍️ Buy Telegram Account")
async def buy_telegram_account_handler(message: Message):
    await message.answer("🔄 <b>Live Telegram OTP Activation Enabled</b>\n\nPlease request your code from your app now.", parse_mode="HTML")

# FIXED: Instant QR code response allowing custom payment amounts
@dp.message(StateFilter(None), F.text == "➕ Add Funds")
async def process_add_funds_text(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    
    txn_id = "".join([str(random.randint(0, 9)) for _ in range(15)])
    
    # UPI URI payload without specific target amount parameter allows variable payment input 
    upi_payload = f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    input_file = BufferedInputFile(img_byte_arr.read(), filename="payment_qr.png")
    
    pay_msg = (
        f"👋 <b>Welcome to the Deposit System</b>\n\n"
        f"Scan the QR code below and pay <b>any amount</b> you wish to add to your wallet.\n\n"
        f"📌 <b>Transaction Reference:</b>\n<code>{txn_id}</code>\n\n"
        f"After making the payment, click <b>'Check Payment Status'</b> below to notify the admin."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"req_{uid}_any")],
        [InlineKeyboardButton(text="❌ Cancel Payment", callback_data="cancel_payment")]
    ])
    
    try:
        await message.answer_photo(photo=input_file, caption=pay_msg, parse_mode="HTML", reply_markup=kb)
    except Exception as err:
        logging.error(f"Failed to send QR: {err}")
        await message.answer("❌ System processing error. Please contact the administrator.")

@dp.callback_query(F.data.startswith("req_"))
async def handle_user_verification_request(callback: CallbackQuery):
    _, uid, amt = callback.data.split("_")
    await callback.answer("⏳ Verification request sent to admin! Please wait.", show_alert=True)
    await callback.message.edit_caption(
        caption=f"⏳ <b>Verification Request Sent</b>\n\nThe admin is verifying your custom payment transaction. Your profile will update upon review.", 
        parse_mode="HTML"
    )
    # Admin must enter the approved value manually later or confirm validation
    akb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Accept (Default ₹100)", callback_data=f"adm_approve_{uid}_100"),
        InlineKeyboardButton(text="❌ Reject Payment", callback_data=f"adm_deny_{uid}_0")
    ]])
    await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"🚨 <b>New Custom Request!</b>\n👤 <b>User:</b> <code>{uid}</code>\n💰 <b>Amount paid:</b> Open Amount", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_"))
async def handle_admin_decision(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, action, uid, amt = callback.data.split("_")
    uid, amt = int(uid), int(amt)
    
    if action == "approve":
        update_balance(uid, amt)
        await callback.message.edit_text(text=f"✅ Approved ₹{amt} for <code>{uid}</code>.", parse_mode="HTML")
        try:
            await bot.send_message(chat_id=uid, text=f"🎉 Your deposit was verified and balance was updated!", parse_mode="HTML")
        except Exception: pass
    elif action == "deny":
        await callback.message.edit_text(text=f"❌ Denied request from <code>{uid}</code>.", parse_mode="HTML")
        try:
            await bot.send_message(chat_id=uid, text="❌ Your transaction review request was declined.", parse_mode="HTML")
        except Exception: pass

@dp.callback_query(F.data == "cancel_payment")
async def handle_cancel_payment(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception: pass

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
