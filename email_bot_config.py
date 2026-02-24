"""
Конфигурация Email Bot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Admin Telegram ID
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Database path
DATABASE_PATH = os.getenv("DATABASE_PATH", "email_bot.db")

# Стоимость подписки
SUBSCRIPTION_PRICE = 1000  # руб/мес
SUBSCRIPTION_DAYS = 30

# Настройки рассылки
EMAIL_SEND_DELAY = 1.0  # секунды между письмами
MAX_EMAILS_PER_BATCH = 1000  # максимум писем за раз
