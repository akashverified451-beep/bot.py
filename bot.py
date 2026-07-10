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
from aiogram.fsm.storage.memory import MemoryStorage
import qrcode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8761162220:AAEsp3UI6Iv5x4y8k4tW9z33LVYFcLEnqlc")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "8393210427"))
YOUR_UPI_ID = "skyotpprovider@axisbank"
DB_PATH = os.getenv("DATABASE_PATH", "bot.db")

class AdminStates(StatesGroup):
    waiting_for_admin_amount = State()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                uid INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                join_date TEXT
            )
        ''')
        conn.commit()

def get_user_data(uid):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, join_date FROM users WHERE uid = ?", (uid,))
        return cursor.fetchone()

def register_user(uid):
    if get_user_data(uid) is None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO users (uid, balance, join_date) VALUES (?, 0, ?)", (uid, now))
            conn.commit()

def update_balance(uid, amount):
    register_user(uid)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amount, uid))
        conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
    register_user(message.from_user.id)
    await message.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=get_main_keyboard())

# --- ADMIN INPUT CAPTURE (Placed strictly first to isolate text capture) ---
@dp.message(AdminStates.waiting_for_admin_amount)
async def process_admin_amount_entry(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        return
        
    text_input = message.text.strip()
    if not text_input.isdigit():
        await message.answer("❌ Invalid input. Please write numbers only (e.g., 50 or 500):")
        return
        
    credit_amount = int(text_input)
    if credit_amount <= 0:
        await message.answer("❌ The amount must be greater than 0. Enter a valid value:")
        return
        
    state_data = await state.get_data()
    target_uid = state_data.get("approve_target_uid")
    old_msg_id = state_data.get("admin_msg_id")
    txn_id = state_data.get("txn_id")
    await state.clear()
    
    user_data = get_user_data(target_uid)
    previous_balance = user_data[0] if user_data else 0
    new_balance = previous_balance + credit_amount
    
    update_balance(target_uid, credit_amount)
    
    await message.answer(f"✅ Successfully accredited ₹{credit_amount} to user <code>{target_uid}</code>.", parse_mode="HTML")
    
    try:
        await bot.edit_message_text(chat_id=ADMIN_TELEGRAM_ID, message_id=old_msg_id, text=f"✅ Approved & added ₹{credit_amount} for <code>{target_uid}</code>.", parse_mode="HTML")
    except Exception:
        pass
    
    customer_receipt = (
        f"✅ <b>Payment Confirmed!</b>\n\n"
        f"<b>Transaction ID:</b> <code>{txn_id}</code>\n"
        f"<b>Amount:</b> ₹{credit_amount}\n"
        f"<b>Previous Balance:</b> ₹{previous_balance}\n"
        f"<b>New Balance:</b> ₹{new_balance}\n\n"
        f"Thank you for your payment!"
    )
    
    try:
        await bot.send_message(chat_id=target_uid, text=customer_receipt, parse_mode="HTML")
    except Exception:
        pass

# --- STANDARD USER INTERFACE HANDLERS ---
@dp.message(StateFilter(None), F.text == "💼 Wallet")
async def balance_handler(message: Message):
    uid = message.from_user.id
    register_user(uid)
    user_data = get_user_data(uid)
    bal = user_data[0] if user_data else 0
    await message.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", reply_markup=get_balance_reply_keyboard(), parse_mode="HTML")

@dp.message(StateFilter(None), F.text == "👤 User Profile")
async def profile_handler(message: Message):
    uid = message.from_user.id
    register_user(uid)
    user_data = get_user_data(uid)
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

@dp.message(StateFilter(None), F.text == "➕ Add Funds")
async def process_add_funds_text(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    txn_id = "".join([str(random.randint(0, 9)) for _ in range(15)])
    
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
        [InlineKeyboardButton(text="✅ Check Payment Status", callback_data=f"req_{uid}_{txn_id}")],
        [InlineKeyboardButton(text="❌ Cancel Payment", callback_data="cancel_payment")]
    ])
    
    try:
        await message.answer_photo(photo=input_file, caption=pay_msg, parse_mode="HTML", reply_markup=kb)
    except Exception as err:
        logging.error(f"Failed to send QR: {err}")
        await message.answer("❌ System processing error. Please contact the administrator.")

# --- INLINE INTERACTIVE BUTTON CALLBACKS ---
@dp.callback_query(F.data.startswith("req_"))
async def handle_user_verification_request(callback: CallbackQuery):
    _, uid, txn_id = callback.data.split("_")
    await callback.answer("⏳ Verification request sent to admin! Please wait.", show_alert=True)
    await callback.message.edit_caption(
        caption=f"⏳ <b>Verification Request Sent</b>\n\nThe admin is verifying your transaction. Your balance updates automatically following verification.", 
        parse_mode="HTML"
    )
    
    akb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Enter Custom Amount", callback_data=f"adm_input_{uid}_{txn_id}")],
        [InlineKeyboardButton(text="❌ Reject Payment", callback_data=f"adm_deny_{uid}")]
    ])
    await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"🚨 <b>New Deposit Claim!</b>\n👤 <b>User ID:</b> <code>{uid}</code>\n📌 <b>TXN ID:</b> <code>{txn_id}</code>\n\nVerify your bank statements and click below to enter the exact received value.", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_"))
async def handle_admin_decision(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_TELEGRAM_ID:
        return
        
    data_parts = callback.data.split("_")
    action = data_parts[1]
    target_uid = int(data_parts[2])
    
    if action == "input":
        txn_id = data_parts[3]
        await state.set_state(AdminStates.waiting_for_admin_amount)
        await state.update_data(approve_target_uid=target_uid, admin_msg_id=callback.message.message_id, txn_id=txn_id)
        await callback.answer()
        await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"💬 Please type the exact amount (in whole numbers) to credit user <code>{target_uid}</code>:", parse_mode="HTML")
        
    elif action == "deny":
        await callback.message.edit_text(text=f"❌ Denied request from user <code>{target_uid}</code>.", parse_mode="HTML")
        try:
