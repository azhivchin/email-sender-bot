"""
Email Sender Bot - Главный файл
Массовая email рассылка через Telegram бота
Подписка: 1000 ₽/мес - безлимит
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Импорты наших модулей
import email_bot_config as config
from email_bot_handlers import router
# from email_bot_admin import admin_router  # TODO: Создать админ-панель

# Загрузка .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/email-sender-bot/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("Starting Email Sender Bot...")
    logger.info(f"Admin ID: {config.ADMIN_TELEGRAM_ID}")
    logger.info(f"Subscription: {config.SUBSCRIPTION_PRICE} ₽/месяц")
    logger.info("=" * 50)

    # Инициализация бота
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(router)
    # dp.include_router(admin_router)  # TODO

    try:
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
