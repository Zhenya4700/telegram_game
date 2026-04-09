import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime
import logging

# ===== КОНФИГУРАЦИЯ =====
TELEGRAM_BOT_TOKEN = "8736801717:AAGeL6vFG3IViX2CjNmEPEYMYpiVRpjLwqw"
TWITCH_CLIENT_ID = "olpgrne5q1u1s9ixy8k1ozrqfa1rrd"
TWITCH_ACCESS_TOKEN = "zwbmp4qiozuroqvtyn7t4p8zdmrpoa"
CHANNELS = ["zhenya4700", "costrulka"]
CHECK_INTERVAL = 1  # Секунд между проверками

# 👇 ЗАМЕНИ НА СВОЙ ID КАНАЛА (отрицательное число)
CHANNEL_ID = -1003781568680  # ⚠️ ВСТАВЬ СВОЙ ID СЮДА!

# ===== НАСТРОЙКА ЛОГГИРОВАНИЯ =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Глобальная переменная для хранения ID сообщения в канале
message_id_store = {"message_id": None}

# ===== ФУНКЦИЯ ПОЛУЧЕНИЯ СТРИМОВ =====
async def get_streams_info():
    url = "https://api.twitch.tv/helix/streams"
    params = [("user_login", channel) for channel in CHANNELS]
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {TWITCH_ACCESS_TOKEN}"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return process_streams_data(data.get("data", []))
                else:
                    logger.error(f"Twitch API error {response.status}")
                    return {channel: {"is_live": False} for channel in CHANNELS}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {channel: {"is_live": False} for channel in CHANNELS}

def process_streams_data(streams_data):
    result = {}
    streams_dict = {stream["user_login"].lower(): stream for stream in streams_data}
    
    for channel in CHANNELS:
        channel_lower = channel.lower()
        if channel_lower in streams_dict:
            stream = streams_dict[channel_lower]
            result[channel] = {
                "is_live": True,
                "viewer_count": stream["viewer_count"],
                "title": stream["title"],
                "game_name": stream["game_name"],
            }
        else:
            result[channel] = {
                "is_live": False,
                "viewer_count": 0,
                "title": None,
                "game_name": None,
            }
    return result

def format_status_message(streams_info):
    current_time = datetime.now().strftime("%H:%M:%S")
    message = f"**СТРИМ**\nОбновлено: {current_time}\n\n"
    
    for channel in CHANNELS:
        info = streams_info[channel]
        if info["is_live"]:
            message += f"V **{channel}** - **В ЭФИРЕ!**\n"
            message += f"   cмотрят: **{info['viewer_count']:,}**\n"
            message += f"   гей-м: {info['game_name']}\n"
            if info['title']:
                message += f"   название: {info['title'][:50]}...\n"
        else:
            message += f"X **{channel}** - Не стримит\n"
        message += "   ─────────────\n"
    
    
    return message

# ===== ФУНКЦИЯ ОБНОВЛЕНИЯ СООБЩЕНИЯ В КАНАЛЕ =====
async def update_message():
    """Основной цикл: получает данные и обновляет сообщение в канале"""
    last_text = ""
    
    # Отправляем первое сообщение при запуске
    streams_info = await get_streams_info()
    message_text = format_status_message(streams_info)
    
    try:
        sent_message = await bot.send_message(
            CHANNEL_ID,
            message_text,
            parse_mode="Markdown"
        )
        message_id_store["message_id"] = sent_message.message_id
        last_text = message_text
        logger.info(f"✅ Первое сообщение отправлено в канал {CHANNEL_ID}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить сообщение в канал: {e}")
        return
    
    while True:
        try:
            streams_info = await get_streams_info()
            message_text = format_status_message(streams_info)
            
            if message_text != last_text and message_id_store["message_id"]:
                try:
                    await bot.edit_message_text(
                        message_text,
                        chat_id=CHANNEL_ID,
                        message_id=message_id_store["message_id"],
                        parse_mode="Markdown"
                    )
                    last_text = message_text
                    logger.info(f"✅ Сообщение обновлено в {datetime.now()}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить: {e}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка обновления: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)

# ===== КОМАНДЫ (для лички, опционально) =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("✅ Бот работает и отправляет статусы в канал!")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    streams_info = await get_streams_info()
    message_text = format_status_message(streams_info)
    await message.answer(message_text, parse_mode="Markdown")

# ===== ЗАПУСК БОТА =====
async def main():
    asyncio.create_task(update_message())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
