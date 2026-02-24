"""
Email Bot Admin Panel - Управление пользователями и подписками
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from datetime import datetime

from email_bot_database import EmailBotDatabase
import email_bot_config as config

logger = logging.getLogger(__name__)
admin_router = Router()

# Инициализация БД
db = EmailBotDatabase()


def is_admin(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    return telegram_id == config.ADMIN_TELEGRAM_ID or db.is_admin(telegram_id)


# ========== АДМИН КОМАНДЫ ==========

@admin_router.message(Command('admin'))
async def cmd_admin_menu(message: Message):
    """Меню администратора"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    await message.answer(
        "🔧 АДМИН-ПАНЕЛЬ\n\n"
        "👥 Пользователи:\n"
        "• /admin_users - список пользователей\n"
        "• /admin_user <id> - инфо о пользователе\n\n"
        "💳 Подписки:\n"
        "• /admin_sub <id> <месяцы> - продлить подписку\n"
        "• /sub <id> <месяцы> - быстрая команда\n\n"
        "📊 Статистика:\n"
        "• /admin_stats - общая статистика\n"
        "• /stats - быстрая команда\n\n"
        "🛠 Управление:\n"
        "• /admin_make <id> - дать права админа"
    )


@admin_router.message(Command('admin_users'))
async def cmd_admin_users(message: Message):
    """Список всех пользователей"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    users = db.get_all_users()

    if not users:
        await message.answer("👥 Нет пользователей")
        return

    text = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)}):\n\n"

    for user in users[:20]:  # Первые 20
        username = f"@{user['username']}" if user['username'] else f"ID{user['telegram_id']}"
        name = user['first_name'] or 'Без имени'

        # Проверка подписки
        if user['subscription_until']:
            sub_until = datetime.fromisoformat(user['subscription_until'])
            if sub_until > datetime.now():
                days_left = (sub_until - datetime.now()).days
                sub_status = f"✅ {days_left}д"
            else:
                sub_status = "❌ Истекла"
        else:
            sub_status = "❌ Нет"

        text += (
            f"{username} ({name})\n"
            f"  💳 Подписка: {sub_status}\n"
            f"  🆔 ID: `{user['telegram_id']}`\n\n"
        )

    if len(users) > 20:
        text += f"\n... и еще {len(users) - 20} пользователей"

    await message.answer(text)


@admin_router.message(Command('admin_user'))
async def cmd_admin_user(message: Message):
    """Информация о конкретном пользователе"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    # Парсим ID из команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `/admin_user <telegram_id>`")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    user = db.get_user(user_id)
    if not user:
        await message.answer(f"❌ Пользователь {user_id} не найден")
        return

    # Получаем данные
    smtp_configs = db.get_smtp_configs(user_id)
    templates = db.get_templates(user_id)
    campaigns = db.get_campaigns(user_id, limit=5)
    transactions = db.get_transactions(user_id, limit=5)

    # Подписка
    if user['subscription_until']:
        sub_until = datetime.fromisoformat(user['subscription_until'])
        if sub_until > datetime.now():
            days_left = (sub_until - datetime.now()).days
            sub_info = f"✅ До {sub_until.strftime('%d.%m.%Y')} ({days_left} дн.)"
        else:
            sub_info = f"❌ Истекла {sub_until.strftime('%d.%m.%Y')}"
    else:
        sub_info = "❌ Нет подписки"

    username = f"@{user['username']}" if user['username'] else f"ID{user_id}"
    name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()

    info = (
        f"👤 ПОЛЬЗОВАТЕЛЬ: {username}\n"
        f"📝 Имя: {name or 'Не указано'}\n"
        f"🆔 ID: `{user_id}`\n\n"
        f"💳 Подписка: {sub_info}\n\n"
        f"⚙️ SMTP конфигураций: {len(smtp_configs)}\n"
        f"📋 Шаблонов: {len(templates)}\n"
        f"📧 Рассылок: {len(campaigns)}\n"
        f"💰 Транзакций: {len(transactions)}\n\n"
        f"✅ Активен: {'Да' if user['is_active'] else 'Нет'}\n"
        f"🔧 Админ: {'Да' if user['is_admin'] else 'Нет'}\n\n"
        f"📅 Зарегистрирован: {user['created_at'][:10]}"
    )

    await message.answer(info)


@admin_router.message(Command('admin_sub'))
async def cmd_admin_subscribe(message: Message):
    """Продлить подписку пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    # Парсим: /admin_sub <user_id> <months>
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Использование:\n\n"
            "`/admin_sub <user_id> <месяцы>`\n\n"
            "Пример:\n"
            "`/admin_sub 123456789 1`"
        )
        return

    try:
        user_id = int(parts[1])
        months = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверный формат. ID и месяцы должны быть числами.")
        return

    if months <= 0:
        await message.answer("❌ Количество месяцев должно быть больше 0")
        return

    # Проверяем существует ли пользователь
    if not db.is_user_registered(user_id):
        await message.answer(f"❌ Пользователь {user_id} не найден")
        return

    # Продлеваем подписку
    new_until = db.extend_subscription(user_id, months=months)

    # Добавляем транзакцию
    amount = config.SUBSCRIPTION_PRICE * months
    db.add_transaction(
        telegram_id=user_id,
        amount=amount,
        transaction_type='subscription',
        description=f"Подписка на {months} мес. (администратор)",
        admin_id=message.from_user.id
    )

    await message.answer(
        f"✅ ПОДПИСКА ПРОДЛЕНА!\n\n"
        f"👤 Пользователь: `{user_id}`\n"
        f"📅 На срок: {months} мес.\n"
        f"💰 Сумма: {amount} ₽\n"
        f"📆 Действует до: {new_until.strftime('%d.%m.%Y')}"
    )


@admin_router.message(Command('admin_stats'))
async def cmd_admin_stats(message: Message):
    """Общая статистика"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    stats = db.get_stats()

    await message.answer(
        f"📊 СТАТИСТИКА БОТА\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"✅ Активных подписок: {stats['active_subscriptions']}\n\n"
        f"📧 Всего рассылок: {stats['total_campaigns']}\n"
        f"📨 Писем отправлено: {stats['total_emails_sent']}\n\n"
        f"💰 Выручка: {stats['total_revenue']:.2f} ₽"
    )


@admin_router.message(Command('admin_make'))
async def cmd_admin_make(message: Message):
    """Дать права администратора"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Недостаточно прав")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `/admin_make <user_id>`")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    if not db.is_user_registered(user_id):
        await message.answer(f"❌ Пользователь {user_id} не найден")
        return

    db.make_admin(user_id)

    await message.answer(
        f"✅ ПРАВА АДМИНА ВЫДАНЫ!\n\n"
        f"👤 Пользователь: `{user_id}`\n"
        f"🔧 Теперь может использовать админ-команды"
    )


# ========== БЫСТРЫЕ КОМАНДЫ ==========

@admin_router.message(Command('sub'))
async def cmd_sub_shortcut(message: Message):
    """Быстрое продление подписки (алиас для /admin_sub)"""
    if not is_admin(message.from_user.id):
        return
    await cmd_admin_subscribe(message)


@admin_router.message(Command('stats'))
async def cmd_stats_shortcut(message: Message):
    """Быстрая статистика"""
    if not is_admin(message.from_user.id):
        return
    await cmd_admin_stats(message)
