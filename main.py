import os
import asyncio
import shutil
from datetime import datetime
import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from telethon import TelegramClient, events

# --- KONFIGURATSIYA ---
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
PORT = int(os.getenv('PORT', 8080))
ADMIN_ID = int(os.getenv('ADMIN_ID', 0)) # Botni boshqarish uchun

# Keshni tozalash (Diskni 200MB dan kam saqlash uchun)
def clean_cache():
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))

clean_cache()

# --- WEB SERVER (Render Health Check uchun) ---
async def handle(request):
    return web.Response(text="Venx App is Running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

# --- GLOBAL O'ZGARUVCHILAR ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient('venx_session', API_ID, API_HASH)
muted_users = {} # {user_id: mute_until_timestamp}

# --- USERBOT MANTIQI (Telethon) ---
UZB_TZ = pytz.timezone('Asia/Tashkent')

def get_auto_reply_message():
    now = datetime.now(UZB_TZ).hour
    if 0 <= now < 9:
        return 'Venx is resting. Contact after 09:00.'
    elif 9 <= now < 11:
        return 'Venx is preparing for work. Contact after 13:00.'
    elif 11 <= now < 13:
        return 'Venx is at work/school. Contact after 13:00.'
    else:
        return 'Venx will reply in 15-20 minutes✓.'

@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if not event.is_private: return
    sender_id = event.sender_id
    
    # Agar foydalanuvchi "Smart Mute" holatida bo'lsa
    now = datetime.now().timestamp()
    if sender_id in muted_users and now < muted_users[sender_id]:
        return

    await event.reply(get_auto_reply_message())

@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing(event):
    if event.is_private:
        # Agar biz o'zimiz javob bersak, 1 soatga avto-javobni o'chiramiz
        muted_users[event.to_id.user_id] = datetime.now().timestamp() + 3600

# --- BOT MANTIQI (Aiogram - Auth Workflow) ---
phone_number = None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Salom Venx! Userbotni faollashtirish uchun telefon raqamingizni yuboring (masalan: +998901234567)")

@dp.message()
async def process_auth(message: types.Message):
    global phone_number
    if message.from_user.id != ADMIN_ID: return

    text = message.text
    if text.startswith('+'):
        phone_number = text
        await client.connect()
        res = await client.send_code_request(phone_number)
        await message.answer("SMS kodni yuboring:")
    elif text.isdigit() and phone_number:
        try:
            await client.sign_in(phone_number, text)
            await message.answer("Userbot muvaffaqiyatli ishga tushdi! ✅")
            asyncio.create_task(client.run_until_disconnected())
        except Exception as e:
            await message.answer(f"Xatolik: {str(e)}")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # Web server, Bot va Userbotni birgalikda ishga tushiramiz
    await asyncio.gather(
        start_web_server(),
        dp.start_polling(bot),
        # Telethon connect qilingan bo'lsa ham, loop to'xtab qolmasligi uchun
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
