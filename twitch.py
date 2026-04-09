import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime
import logging

# ===== КОНФИГУРАЦИЯ =====
TELEGRAM_BOT_TOKEN = "8736801717:AAGeL6vFG3IViX2CjNmEPEYMYpiVRpjLwqw"  # Замени на свой токен от @BotFather
TWITCH_CLIENT_ID = "olpgrne5q1u1s9ixy8k1ozrqfa1rrd"      # Получить на dev.twitch.tv/console
TWITCH_ACCESS_TOKEN = "zwbmp4qiozuroqvtyn7t4p8zdmrpoa" # Твой токен Twitch
CHANNELS = ["zhenya4700", "costrulka"]           # Каналы для отслеживания
CHECK_INTERVAL = 1  # Секунд между проверками

# ===== НАСТРОЙКА ЛОГГИРОВАНИЯ =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Глобальная переменная для хранения ID сообщения
message_id_store = {"message_id": None, "chat_id": None}

# ===== ФУНКЦИЯ ПОЛУЧЕНИЯ СТРИМОВ ИЗ TWITCH API =====
async def get_streams_info():
    """Получает информацию о стримах для указанных каналов"""
    url = "https://api.twitch.tv/helix/streams"
    
    # Подготовка параметров запроса (логины каналов)
    params = []
    for channel in CHANNELS:
        params.append(("user_login", channel))
    
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
                    error_text = await response.text()
                    logger.error(f"Twitch API error {response.status}: {error_text}")
                    return {channel: {"is_live": False, "error": str(response.status)} 
                           for channel in CHANNELS}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {channel: {"is_live": False, "error": str(e)} 
                   for channel in CHANNELS}

def process_streams_data(streams_data):
    """Обрабатывает данные о стримах и создает словарь с результатами"""
    result = {}
    
    # Создаем словарь для быстрого доступа к стримам
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
                "started_at": stream["started_at"],
                "thumbnail": stream["thumbnail_url"].format(width=320, height=180)
            }
        else:
            result[channel] = {
                "is_live": False,
                "viewer_count": 0,
                "title": None,
                "game_name": None,
                "started_at": None,
                "thumbnail": None
            }
    
    return result

# ===== ФУНКЦИЯ ФОРМИРОВАНИЯ СООБЩЕНИЯ =====
def format_status_message(streams_info):
    """Формирует красивое сообщение со статусом стримеров"""
    current_time = datetime.now().strftime("%H:%M:%S")
    message = f"🎥 **СТАТУС СТРИМЕРОВ**\nОбновлено: {current_time}\n\n"
    
    for channel in CHANNELS:
        info = streams_info[channel]
        if info["is_live"]:
            message += f"🟢 **{channel}** - **В ЭФИРЕ!**\n"
            message += f"   👁️ Зрителей: **{info['viewer_count']:,}**\n"
            message += f"   🎮 Игра: {info['game_name']}\n"
            message += f"   📝 Тайтл: {info['title'][:50]}...\n"
        else:
            message += f"🔴 **{channel}** - Не стримит\n"
        
        message += "   ─────────────\n"
    
    message += "\n🔄 Обновляется каждые 5 секунд"
    return message

# ===== ФУНКЦИЯ ОБНОВЛЕНИЯ СООБЩЕНИЯ =====
async def update_message():
    """Основной цикл: получает данные и обновляет сообщение"""
    while True:
        try:
            # Получаем данные о стримах
            streams_info = await get_streams_info()
            
            # Формируем текст сообщения
            message_text = format_status_message(streams_info)
            
            # Обновляем или создаем сообщение
            if message_id_store["message_id"] and message_id_store["chat_id"]:
                try:
                    # Редактируем существующее сообщение
                    await bot.edit_message_text(
                        message_text,
                        chat_id=message_id_store["chat_id"],
                        message_id=message_id_store["message_id"],
                        parse_mode="Markdown"
                    )
                    logger.info(f"Message updated at {datetime.now()}")
                except Exception as e:
                    # Если не можем отредактировать (сообщение удалено и т.д.)
                    logger.warning(f"Can't edit message: {e}")
                    message_id_store["message_id"] = None
            else:
                # Если нет сохраненного сообщения, ждем команду /start
                logger.info("Waiting for /start command to initialize message")
        
        except Exception as e:
            logger.error(f"Update error: {e}")
        
        # Ждем 5 секунд перед следующей проверкой
        await asyncio.sleep(CHECK_INTERVAL)

# ===== КОМАНДЫ ТЕЛЕГРАМ БОТА =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start - создает новое сообщение со статусом"""
    streams_info = await get_streams_info()
    message_text = format_status_message(streams_info)
    
    # Отправляем новое сообщение
    sent_message = await message.answer(
        message_text,
        parse_mode="Markdown"
    )
    
    # Сохраняем ID сообщения для будущих обновлений
    message_id_store["message_id"] = sent_message.message_id
    message_id_store["chat_id"] = sent_message.chat.id
    
    logger.info(f"Started tracking for chat {message.chat.id}")

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Команда /stop - останавливает обновления"""
    message_id_store["message_id"] = None
    message_id_store["chat_id"] = None
    await message.answer("❌ Отслеживание остановлено. Напишите /start чтобы начать заново.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status - показывает текущий статус без обновлений"""
    streams_info = await get_streams_info()
    message_text = format_status_message(streams_info)
    await message.answer(message_text, parse_mode="Markdown")

# ===== ЗАПУСК БОТА =====
async def main():
    # Запускаем фоновую задачу для обновления сообщения
    asyncio.create_task(update_message())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
