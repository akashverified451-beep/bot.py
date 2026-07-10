import os
import random
import logging
import asyncio
import io
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

user_balances = {}  
user_join_dates = {}  

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class DepositStates(StatesGroup):
    waiting_for_amount = State()

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
    user_balances.setdefault(uid, 0)
    user_join_dates.setdefault(uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    await message.answer("👋 Welcome to SKY OTP BOT.\n✨ Use the menu panels below to navigate our services.", reply_markup=get_main_keyboard())

@dp.message(StateFilter(None), F.text == "💼 Wallet")
async def balance_handler(message: Message):
    uid = message.from_user.id
    bal = user_balances.get(uid, 0)
    await message.answer(text=f"💼 <b>Wallet Dashboard</b>\n\n💰 Balance: <b>₹{bal}</b>\n\nPlease select your funding process.", reply_markup=get_balance_reply_keyboard(), parse_mode="HTML")

@dp.message(StateFilter(None), F.text == "👤 User Profile")
async def profile_handler(message: Message):
    uid = message.from_user.id
    bal = user_balances.get(uid, 0)
    jd = user_join_dates.get(uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
    await state.set_state(DepositStates.waiting_for_amount)
    await message.answer("➕ <b>Deposit System</b>\n\nPlease enter the exact amount you want to add to your wallet in INR:", parse_mode="HTML")

@dp.message(DepositStates.waiting_for_amount, F.text.regexp(r'^\d+$'))
async def process_amount_input(message: Message, state: FSMContext):
    txt = message.text.strip()
    amt = int(txt)
    if amt <= 0:
        await message.answer("❌ Invalid amount. Please enter a valid number greater than 0:")
        return
        
    await state.clear()
    uid = message.from_user.id
    txn_id = "".join([str(random.randint(0, 9)) for _ in range(15)])
    upi_payload = f"upi://pay?pa={YOUR_UPI_ID}&pn=SKY_OTP&am={amt}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    input_file = BufferedInputFile(img_byte_arr.read(), filename="payment_qr.png")
    
    pay_msg = (
        f"Scan the QR and pay any amount\n\n"
        f"Transaction ID:\n"
        f"{txn_id}\n\n"
        f"After the deposit, please check your balance and click 'Check Payment Status.'"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅Check Payment Status", callback_data=f"req_{uid}_{amt}")],
        [InlineKeyboardButton(text="❌Cancel Payment", callback_data="cancel_payment")]
    ])
    
    try:
        await message.answer_photo(photo=input_file, caption=pay_msg, parse_mode="HTML", reply_markup=kb)
    except Exception as err:
        logging.error(f"Failed to send QR: {err}")
        await message.answer("❌ System processing error. Please contact the administrator.")

@dp.message(DepositStates.waiting_for_amount)
async def process_amount_invalid(message: Message):
    await message.answer("❌ Invalid format. Please write only numbers (e.g., 100):")

@dp.callback_query(F.data.startswith("req_"))
async def handle_user_verification_request(callback: CallbackQuery):
    _, uid, amt = callback.data.split("_")
    await callback.answer("⏳ Verification request sent to admin! Please wait.", show_alert=True)
    await callback.message.edit_caption(
        caption=f"⏳ <b>Verification Request Sent</b>\n💰 <b>Amount:</b> ₹{amt}\n\nThe admin is verifying your payment.", 
        parse_mode="HTML"
    )
    akb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Accept Payment", callback_data=f"adm_approve_{uid}_{amt}"),
        InlineKeyboardButton(text="❌ Reject Payment", callback_data=f"adm_deny_{uid}_{amt}")
    ]])
    await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"🚨 <b>New Request!</b>\n👤 <b>User:</b> <code>{uid}</code>\n💰 <b>Amount:</b> ₹{amt}", reply_markup=akb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_"))
async def handle_admin_decision(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_TELEGRAM_ID:
        return
    _, action, uid, amt = callback.data.split("_")
    uid, amt = int(uid), int(amt)
    
    if action == "approve":
        user_balances[uid] = user_balances.get(uid, 0) + amt
        await callback.message.edit_text(text=f"✅ Approved ₹{amt} for <code>{uid}</code>.", parse_mode="HTML")
        try:
            await bot.send_message(chat_id=uid, text=f"🎉 Your deposit of <b>₹{amt}</b> was verified!", parse_mode="HTML")
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
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
