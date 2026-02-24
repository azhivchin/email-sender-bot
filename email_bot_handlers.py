"""
Email Bot Handlers - Постоянные кнопки и вся логика
Подписка: 1000 ₽/мес без лимитов
"""

import logging
import asyncio
import csv
import io
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from email_bot_database import EmailBotDatabase
from email_sender import EmailSender, SMTP_PRESETS

logger = logging.getLogger(__name__)
router = Router()

# Инициализация БД
db = EmailBotDatabase()

# ========== ПОСТОЯННАЯ КЛАВИАТУРА ==========

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает постоянную клавиатуру с основными кнопками"""
    keyboard = [
        [KeyboardButton(text="📧 Новая рассылка"), KeyboardButton(text="📋 Мои шаблоны")],
        [KeyboardButton(text="📊 История"), KeyboardButton(text="⚙️ SMTP Настройки")],
        [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="📖 Помощь")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Выберите действие..."
    )


# ========== FSM STATES ==========

class SMTPSetup(StatesGroup):
    """Настройка SMTP"""
    waiting_for_provider = State()
    waiting_for_email = State()
    waiting_for_password = State()
    waiting_for_name = State()
    waiting_for_custom_host = State()
    waiting_for_custom_port = State()


class TemplateCreate(StatesGroup):
    """Создание шаблона"""
    waiting_for_name = State()
    waiting_for_subject = State()
    waiting_for_body = State()


class ContactsUpload(StatesGroup):
    """Загрузка контактов"""
    waiting_for_file_or_text = State()
    waiting_for_list_name = State()


class CampaignCreate(StatesGroup):
    """Создание рассылки"""
    waiting_for_smtp = State()
    waiting_for_contacts = State()
    waiting_for_template = State()
    confirming = State()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def has_active_subscription(telegram_id: int) -> tuple[bool, str]:
    """Проверка активной подписки"""
    if not db.has_active_subscription(telegram_id):
        user = db.get_user(telegram_id)
        if user and user['subscription_until']:
            return False, f"❌ Подписка истекла {user['subscription_until'][:10]}\n\nПродлите подписку: 💳 Подписка"
        return False, "❌ Нет активной подписки\n\nОформите подписку: 💳 Подписка"
    return True, ""


# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Приветствие и регистрация"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    # Регистрируем пользователя
    if not db.is_user_registered(telegram_id):
        db.register_user(telegram_id, username, first_name, last_name)
        is_new = True
    else:
        is_new = False

    if is_new:
        await message.answer(
            f"👋 Привет, {first_name}!\n\n"
            "🎉 Вы зарегистрированы в Email Рассылка Боте!\n\n"
            "📧 Что умеет бот:\n"
            "• Массовая отправка email\n"
            "• Безлимитные рассылки\n"
            "• Использование ВАШЕЙ почты (Gmail, Yandex, Mail.ru)\n"
            "• Шаблоны писем\n"
            "• История и статистика\n\n"
            "💰 Подписка: 1000 ₽/мес\n\n"
            "⚙️ Следующие шаги:\n"
            "1️⃣ Оформите подписку - 💳 Подписка\n"
            "2️⃣ Настройте SMTP - ⚙️ SMTP Настройки\n"
            "3️⃣ Создайте шаблон - 📋 Мои шаблоны\n"
            "4️⃣ Запустите рассылку - 📧 Новая рассылка\n\n"
            "📖 Подробная инструкция - 📖 Помощь",
            reply_markup=get_main_keyboard()
        )
    else:
        has_sub, msg = has_active_subscription(telegram_id)
        status = "✅ Подписка активна" if has_sub else msg

        await message.answer(
            f"👋 С возвращением, {first_name}!\n\n"
            f"{status}\n\n"
            "Используйте кнопки ниже для работы с ботом.",
            reply_markup=get_main_keyboard()
        )


@router.message(Command('help'))
@router.message(F.text == "📖 Помощь")
async def cmd_help(message: Message):
    """Помощь и инструкции"""
    await message.answer(
        "📖 ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ\n\n"
        "📧 Новая рассылка - Запустить рассылку email\n"
        "📋 Мои шаблоны - Создать/просмотреть шаблоны писем\n"
        "📊 История - Просмотр всех рассылок\n"
        "⚙️ SMTP Настройки - Настроить вашу почту\n"
        "💳 Подписка - Оформить/продлить подписку\n\n"
        "🔑 Настройка Gmail:\n"
        "1. Включите двухфакторную аутентификацию\n"
        "2. Создайте пароль приложения:\n"
        "   https://myaccount.google.com/apppasswords\n"
        "3. Используйте пароль приложения в боте\n\n"
        "🔑 Настройка Yandex:\n"
        "1. Включите IMAP:\n"
        "   https://mail.yandex.ru/#setup/client\n"
        "2. Создайте пароль приложения:\n"
        "   https://id.yandex.ru/security/app-passwords\n\n"
        "📋 Формат CSV файла:\n"
        "```\n"
        "email\n"
        "user1@example.com\n"
        "user2@example.com\n"
        "```\n\n"
        "❓ Вопросы? Пишите @LANA_AI_connection",
        reply_markup=get_main_keyboard()
    )


# ========== ПОДПИСКА ==========

@router.message(F.text == "💳 Подписка")
async def cmd_subscription(message: Message):
    """Управление подпиской"""
    telegram_id = message.from_user.id
    user = db.get_user(telegram_id)

    if user['subscription_until']:
        sub_until = datetime.fromisoformat(user['subscription_until'])
        if sub_until > datetime.now():
            days_left = (sub_until - datetime.now()).days
            await message.answer(
                f"✅ ПОДПИСКА АКТИВНА\n\n"
                f"📅 Действует до: {sub_until.strftime('%d.%m.%Y')}\n"
                f"⏳ Осталось дней: {days_left}\n\n"
                f"💰 Стоимость: 1000 ₽/мес\n\n"
                f"Для продления напишите:\n"
                f"👤 @LANA_AI_connection\n"
                f"🆔 Ваш ID: `{telegram_id}`",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                f"❌ ПОДПИСКА ИСТЕКЛА\n\n"
                f"📅 Была активна до: {sub_until.strftime('%d.%m.%Y')}\n\n"
                f"💰 Стоимость: 1000 ₽/мес\n\n"
                f"Для оформления напишите:\n"
                f"👤 @LANA_AI_connection\n"
                f"🆔 Ваш ID: `{telegram_id}`",
                reply_markup=get_main_keyboard()
            )
    else:
        await message.answer(
            f"💳 ОФОРМЛЕНИЕ ПОДПИСКИ\n\n"
            f"💰 Стоимость: 1000 ₽/мес\n"
            f"♾️ Безлимитные рассылки\n\n"
            f"Для оформления напишите:\n"
            f"👤 @LANA_AI_connection\n"
            f"🆔 Ваш ID: `{telegram_id}`\n\n"
            f"После оплаты администратор активирует подписку на 30 дней.",
            reply_markup=get_main_keyboard()
        )


# ========== SMTP НАСТРОЙКИ ==========

@router.message(F.text == "⚙️ SMTP Настройки")
async def cmd_smtp_settings(message: Message):
    """Меню SMTP настроек"""
    telegram_id = message.from_user.id
    configs = db.get_smtp_configs(telegram_id)

    if not configs:
        text = "⚙️ SMTP НАСТРОЙКИ\n\n❌ У вас нет настроенных SMTP конфигураций\n\n"
        text += "Добавьте вашу почту для отправки писем:"
    else:
        text = f"⚙️ SMTP НАСТРОЙКИ\n\n✅ Настроено конфигураций: {len(configs)}\n\n"
        for cfg in configs:
            default = "⭐ " if cfg['is_default'] else ""
            text += f"{default}{cfg['name']} ({cfg['from_email']})\n"
        text += "\nУправление:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить SMTP", callback_data="smtp_add")],
        [InlineKeyboardButton(text="📋 Список SMTP", callback_data="smtp_list")] if configs else [],
        [InlineKeyboardButton(text="📖 Инструкции", callback_data="smtp_instructions")]
    ])

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "smtp_add")
async def smtp_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления SMTP"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Gmail", callback_data="smtp_provider_gmail")],
        [InlineKeyboardButton(text="Yandex", callback_data="smtp_provider_yandex")],
        [InlineKeyboardButton(text="Mail.ru", callback_data="smtp_provider_mailru")],
        [InlineKeyboardButton(text="Другой SMTP", callback_data="smtp_provider_custom")]
    ])

    await callback.message.edit_text(
        "⚙️ ВЫБОР ПОЧТОВОГО СЕРВИСА\n\n"
        "Выберите ваш email провайдер:",
        reply_markup=keyboard
    )
    await state.set_state(SMTPSetup.waiting_for_provider)
    await callback.answer()


@router.callback_query(F.data.startswith("smtp_provider_"))
async def smtp_provider_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран провайдер SMTP"""
    provider = callback.data.replace("smtp_provider_", "")
    preset = SMTP_PRESETS.get(provider, SMTP_PRESETS['custom'])

    await state.update_data(
        provider=provider,
        smtp_host=preset['smtp_host'],
        smtp_port=preset['smtp_port']
    )

    if provider == 'custom':
        await callback.message.edit_text(
            "⚙️ CUSTOM SMTP\n\n"
            "Отправьте SMTP хост (например: smtp.example.com):"
        )
        await state.set_state(SMTPSetup.waiting_for_custom_host)
    else:
        instructions = preset.get('instructions', '')
        await callback.message.edit_text(
            f"⚙️ НАСТРОЙКА {preset['name'].upper()}\n\n"
            f"{instructions}\n\n"
            f"Отправьте ваш email адрес:"
        )
        await state.set_state(SMTPSetup.waiting_for_email)

    await callback.answer()


@router.message(SMTPSetup.waiting_for_email)
async def smtp_email_received(message: Message, state: FSMContext):
    """Получен email"""
    email = message.text.strip()

    if '@' not in email:
        await message.answer("❌ Неверный формат email. Попробуйте еще раз:")
        return

    await state.update_data(email=email, from_email=email)
    await message.answer(
        f"✅ Email: {email}\n\n"
        f"Теперь отправьте ПАРОЛЬ ПРИЛОЖЕНИЯ\n\n"
        f"⚠️ НЕ обычный пароль, а пароль приложения!"
    )
    await state.set_state(SMTPSetup.waiting_for_password)


@router.message(SMTPSetup.waiting_for_password)
async def smtp_password_received(message: Message, state: FSMContext):
    """Получен пароль"""
    password = message.text.strip().replace(' ', '')  # Убираем пробелы
    data = await state.get_data()

    # Проверяем подключение
    await message.answer("🔄 Проверяю подключение...")

    smtp_config = {
        'smtp_host': data['smtp_host'],
        'smtp_port': data['smtp_port'],
        'smtp_user': data['email'],
        'smtp_password': password,
        'from_email': data['email']
    }

    success, msg = EmailSender.test_smtp_connection(smtp_config)

    if not success:
        await message.answer(
            f"{msg}\n\n"
            f"Попробуйте отправить пароль еще раз или /cancel для отмены."
        )
        return

    # Сохраняем пароль
    await state.update_data(password=password)

    # Просим имя отправителя
    await message.answer(
        f"✅ Подключение успешно!\n\n"
        f"Укажите имя отправителя (будет показано получателям):\n"
        f"Например: Ваше Имя или Название Компании"
    )
    await state.set_state(SMTPSetup.waiting_for_name)


@router.message(SMTPSetup.waiting_for_name)
async def smtp_name_received(message: Message, state: FSMContext):
    """Получено имя отправителя"""
    from_name = message.text.strip()
    data = await state.get_data()

    # Сохраняем в БД
    config_id = db.add_smtp_config(
        telegram_id=message.from_user.id,
        name=f"{data['provider'].capitalize()} ({data['email']})",
        smtp_host=data['smtp_host'],
        smtp_port=data['smtp_port'],
        smtp_user=data['email'],
        smtp_password=data['password'],
        from_email=data['email'],
        from_name=from_name
    )

    await message.answer(
        f"✅ SMTP НАСТРОЕН!\n\n"
        f"📧 Email: {data['email']}\n"
        f"👤 Имя: {from_name}\n"
        f"🔧 Провайдер: {data['provider'].capitalize()}\n\n"
        f"Теперь можете запускать рассылки!",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


# ========== ШАБЛОНЫ ==========

@router.message(F.text == "📋 Мои шаблоны")
async def cmd_templates(message: Message):
    """Список шаблонов"""
    telegram_id = message.from_user.id
    templates = db.get_templates(telegram_id)

    if not templates:
        text = "📋 МОИ ШАБЛОНЫ\n\n❌ У вас нет созданных шаблонов\n\n"
    else:
        text = f"📋 МОИ ШАБЛОНЫ\n\n✅ Всего: {len(templates)}\n\n"
        for t in templates[:5]:
            text += f"📝 {t['name']}\n   Тема: {t['subject'][:30]}...\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="template_create")],
        [InlineKeyboardButton(text="📋 Все шаблоны", callback_data="template_list")] if templates else []
    ])

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "template_create")
async def template_create_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания шаблона"""
    await callback.message.edit_text(
        "📝 СОЗДАНИЕ ШАБЛОНА\n\n"
        "Шаг 1/3: Введите название шаблона\n"
        "(Например: Приветственное письмо)"
    )
    await state.set_state(TemplateCreate.waiting_for_name)
    await callback.answer()


@router.message(TemplateCreate.waiting_for_name)
async def template_name_received(message: Message, state: FSMContext):
    """Получено название шаблона"""
    name = message.text.strip()
    await state.update_data(name=name)

    await message.answer(
        f"✅ Название: {name}\n\n"
        f"Шаг 2/3: Введите ТЕМУ письма\n"
        f"(Например: Специальное предложение для вас!)"
    )
    await state.set_state(TemplateCreate.waiting_for_subject)


@router.message(TemplateCreate.waiting_for_subject)
async def template_subject_received(message: Message, state: FSMContext):
    """Получена тема письма"""
    subject = message.text.strip()
    await state.update_data(subject=subject)

    await message.answer(
        f"✅ Тема: {subject}\n\n"
        f"Шаг 3/3: Введите ТЕКСТ письма\n\n"
        f"Можно использовать:\n"
        f"• HTML для форматирования\n"
        f"• Переменные {{name}}, {{email}}, {{company}}\n\n"
        f"Пример:\n"
        f"Привет, {{name}}!\n\n"
        f"Мы рады предложить вам специальную скидку..."
    )
    await state.set_state(TemplateCreate.waiting_for_body)


@router.message(TemplateCreate.waiting_for_body)
async def template_body_received(message: Message, state: FSMContext):
    """Получен текст письма"""
    body = message.text.strip()
    data = await state.get_data()

    # Сохраняем шаблон
    template_id = db.add_template(
        telegram_id=message.from_user.id,
        name=data['name'],
        subject=data['subject'],
        body=body
    )

    await message.answer(
        f"✅ ШАБЛОН СОЗДАН!\n\n"
        f"📝 Название: {data['name']}\n"
        f"📧 Тема: {data['subject']}\n"
        f"📄 Длина текста: {len(body)} символов\n\n"
        f"Теперь можете использовать его в рассылках!",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


# ========== ИСТОРИЯ ==========

@router.message(F.text == "📊 История")
async def cmd_history(message: Message):
    """История рассылок"""
    telegram_id = message.from_user.id
    campaigns = db.get_campaigns(telegram_id, limit=10)

    if not campaigns:
        await message.answer(
            "📊 ИСТОРИЯ РАССЫЛОК\n\n"
            "❌ У вас пока нет рассылок\n\n"
            "Создайте первую рассылку: 📧 Новая рассылка",
            reply_markup=get_main_keyboard()
        )
        return

    text = f"📊 ИСТОРИЯ РАССЫЛОК\n\n✅ Всего: {len(campaigns)}\n\n"

    for c in campaigns:
        status_emoji = {
            'pending': '⏳',
            'running': '🔄',
            'completed': '✅',
            'failed': '❌'
        }.get(c['status'], '❓')

        text += (
            f"{status_emoji} {c['name']}\n"
            f"   Отправлено: {c['sent_count']}/{c['total_emails']}\n"
            f"   Дата: {c['created_at'][:16]}\n\n"
        )

    await message.answer(text, reply_markup=get_main_keyboard())


# ========== НОВАЯ РАССЫЛКА ==========

@router.message(F.text == "📧 Новая рассылка")
async def cmd_new_campaign(message: Message):
    """Создание новой рассылки"""
    telegram_id = message.from_user.id

    # Проверка подписки
    has_sub, msg = has_active_subscription(telegram_id)
    if not has_sub:
        await message.answer(msg, reply_markup=get_main_keyboard())
        return

    # Проверка SMTP
    smtp_configs = db.get_smtp_configs(telegram_id)
    if not smtp_configs:
        await message.answer(
            "❌ Сначала настройте SMTP!\n\n"
            "Нажмите: ⚙️ SMTP Настройки",
            reply_markup=get_main_keyboard()
        )
        return

    # Проверка шаблонов
    templates = db.get_templates(telegram_id)
    if not templates:
        await message.answer(
            "❌ Сначала создайте шаблон письма!\n\n"
            "Нажмите: 📋 Мои шаблоны",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        "📧 НОВАЯ РАССЫЛКА\n\n"
        "Сейчас настроим рассылку по шагам.\n\n"
        "Готовы начать?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Начать", callback_data="campaign_start")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="campaign_cancel")]
        ])
    )


# Продолжение в следующем сообщении из-за ограничения размера...
"""
Дополнительные handlers для Email Bot
Логика запуска рассылок и загрузки контактов
"""

import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from email_bot_database import EmailBotDatabase
from email_sender import EmailSender
from contacts_parser import ContactsParser
from email_bot_handlers import (
    router, ContactsUpload, CampaignCreate,
    get_main_keyboard, has_active_subscription
)

logger = logging.getLogger(__name__)

# БД уже инициализирована в email_bot_handlers
db = EmailBotDatabase()


# ========== ЗАГРУЗКА КОНТАКТОВ ==========

@router.callback_query(F.data == "campaign_start")
async def campaign_step1_smtp(callback: CallbackQuery, state: FSMContext):
    """Шаг 1: Выбор SMTP конфигурации"""
    telegram_id = callback.from_user.id
    smtp_configs = db.get_smtp_configs(telegram_id)

    if not smtp_configs:
        await callback.message.edit_text(
            "❌ Сначала настройте SMTP!\n\n"
            "Нажмите: ⚙️ SMTP Настройки"
        )
        await callback.answer()
        return

    # Создаем кнопки с SMTP конфигурациями
    keyboard = []
    for cfg in smtp_configs:
        default_mark = "⭐ " if cfg['is_default'] else ""
        button_text = f"{default_mark}{cfg['name']}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"campaign_smtp_{cfg['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="campaign_cancel")])

    await callback.message.edit_text(
        "📧 НОВАЯ РАССЫЛКА\n\n"
        "Шаг 1/4: Выберите SMTP конфигурацию\n"
        "(С какого email отправлять письма)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(CampaignCreate.waiting_for_smtp)
    await callback.answer()


@router.callback_query(F.data.startswith("campaign_smtp_"))
async def campaign_step2_contacts(callback: CallbackQuery, state: FSMContext):
    """Шаг 2: Загрузка контактов"""
    smtp_id = int(callback.data.replace("campaign_smtp_", ""))
    await state.update_data(smtp_config_id=smtp_id)

    # Проверяем есть ли сохраненные списки
    telegram_id = callback.from_user.id
    contact_lists = db.get_contact_lists(telegram_id)

    keyboard = [
        [InlineKeyboardButton(text="📤 Загрузить CSV/XLSX файл", callback_data="campaign_upload_file")],
        [InlineKeyboardButton(text="✍️ Ввести emails вручную", callback_data="campaign_enter_text")]
    ]

    if contact_lists:
        keyboard.insert(0, [InlineKeyboardButton(text="📋 Использовать сохраненный список", callback_data="campaign_use_saved")])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="campaign_cancel")])

    await callback.message.edit_text(
        "📧 НОВАЯ РАССЫЛКА\n\n"
        "Шаг 2/4: Загрузите контакты\n\n"
        "Выберите способ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(CampaignCreate.waiting_for_contacts)
    await callback.answer()


@router.callback_query(F.data == "campaign_upload_file")
async def campaign_contacts_upload_file(callback: CallbackQuery, state: FSMContext):
    """Загрузка CSV/XLSX файла"""
    await callback.message.edit_text(
        "📤 ЗАГРУЗКА ФАЙЛА\n\n"
        "Отправьте CSV или XLSX файл с контактами.\n\n"
        "Формат CSV:\n"
        "```\n"
        "email\n"
        "user1@example.com\n"
        "user2@example.com\n"
        "```\n\n"
        "Или просто список email по одному на строку."
    )
    await state.set_state(ContactsUpload.waiting_for_file_or_text)
    await callback.answer()


@router.callback_query(F.data == "campaign_enter_text")
async def campaign_contacts_enter_text(callback: CallbackQuery, state: FSMContext):
    """Ввод emails вручную"""
    await callback.message.edit_text(
        "✍️ ВВОД КОНТАКТОВ\n\n"
        "Отправьте список email адресов.\n\n"
        "Можно отправить:\n"
        "• По одному на строку\n"
        "• Через запятую\n"
        "• CSV формат\n\n"
        "Пример:\n"
        "```\n"
        "user1@example.com\n"
        "user2@example.com\n"
        "user3@example.com\n"
        "```"
    )
    await state.set_state(ContactsUpload.waiting_for_file_or_text)
    await callback.answer()


@router.message(ContactsUpload.waiting_for_file_or_text, F.document)
async def process_contacts_file(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    telegram_id = message.from_user.id

    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        filename = message.document.file_name

        # Парсим контакты
        await message.answer("🔄 Обрабатываю файл...")
        emails = await ContactsParser.parse_csv_file(file_bytes.read(), filename)

        if not emails:
            await message.answer(
                "❌ Не удалось найти email адреса в файле.\n\n"
                "Проверьте формат файла и попробуйте еще раз.",
                reply_markup=get_main_keyboard()
            )
            return

        # Сохраняем список
        list_name = f"Список {filename[:20]}"
        list_id = db.add_contact_list(telegram_id, list_name, emails)

        # Сохраняем в state для использования в кампании
        await state.update_data(contact_list_id=list_id)

        # Показываем превью
        preview = ContactsParser.format_contacts_preview(emails)
        await message.answer(
            f"✅ КОНТАКТЫ ЗАГРУЖЕНЫ!\n\n{preview}",
            reply_markup=get_main_keyboard()
        )

        # Переходим к следующему шагу
        await campaign_step3_template(message, state)

    except Exception as e:
        logger.error(f"File processing error: {e}")
        await message.answer(
            f"❌ Ошибка обработки файла: {str(e)}\n\n"
            f"Попробуйте другой файл или введите emails вручную.",
            reply_markup=get_main_keyboard()
        )


@router.message(ContactsUpload.waiting_for_file_or_text, F.text)
async def process_contacts_text(message: Message, state: FSMContext):
    """Обработка текстового ввода контактов"""
    telegram_id = message.from_user.id
    text = message.text

    try:
        # Парсим контакты из текста
        emails = ContactsParser.parse_csv_text(text)

        if not emails:
            await message.answer(
                "❌ Не удалось найти email адреса в тексте.\n\n"
                "Проверьте формат и попробуйте еще раз.",
                reply_markup=get_main_keyboard()
            )
            return

        # Сохраняем список
        list_name = f"Список от {message.date.strftime('%d.%m.%Y %H:%M')}"
        list_id = db.add_contact_list(telegram_id, list_name, emails)

        # Сохраняем в state
        await state.update_data(contact_list_id=list_id)

        # Показываем превью
        preview = ContactsParser.format_contacts_preview(emails)
        await message.answer(
            f"✅ КОНТАКТЫ ЗАГРУЖЕНЫ!\n\n{preview}",
            reply_markup=get_main_keyboard()
        )

        # Переходим к следующему шагу
        await campaign_step3_template(message, state)

    except Exception as e:
        logger.error(f"Text processing error: {e}")
        await message.answer(
            f"❌ Ошибка обработки: {str(e)}",
            reply_markup=get_main_keyboard()
        )


async def campaign_step3_template(message: Message, state: FSMContext):
    """Шаг 3: Выбор шаблона письма"""
    telegram_id = message.from_user.id
    templates = db.get_templates(telegram_id)

    if not templates:
        await message.answer(
            "❌ У вас нет шаблонов писем!\n\n"
            "Создайте шаблон: 📋 Мои шаблоны",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    # Создаем кнопки с шаблонами
    keyboard = []
    for tpl in templates:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📝 {tpl['name']}",
                callback_data=f"campaign_template_{tpl['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="campaign_cancel")])

    await message.answer(
        "📧 НОВАЯ РАССЫЛКА\n\n"
        "Шаг 3/4: Выберите шаблон письма",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(CampaignCreate.waiting_for_template)


@router.callback_query(F.data.startswith("campaign_template_"))
async def campaign_step4_confirm(callback: CallbackQuery, state: FSMContext):
    """Шаг 4: Подтверждение и запуск"""
    template_id = int(callback.data.replace("campaign_template_", ""))
    await state.update_data(template_id=template_id)

    # Получаем все данные
    data = await state.get_data()
    smtp_config = db.get_smtp_config(data['smtp_config_id'])
    contact_list = db.get_contact_list(data['contact_list_id'])
    template = db.get_template(template_id)

    # Формируем сводку
    summary = (
        "📧 ПОДТВЕРЖДЕНИЕ РАССЫЛКИ\n\n"
        f"📤 От кого: {smtp_config['from_name']} ({smtp_config['from_email']})\n"
        f"📨 Кому: {len(contact_list['contacts'])} получателей\n"
        f"📝 Тема: {template['subject']}\n\n"
        f"Запустить рассылку?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Запустить", callback_data="campaign_launch")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="campaign_cancel")]
    ])

    await callback.message.edit_text(summary, reply_markup=keyboard)
    await state.set_state(CampaignCreate.confirming)
    await callback.answer()


@router.callback_query(F.data == "campaign_launch")
async def campaign_launch(callback: CallbackQuery, state: FSMContext):
    """Запуск рассылки"""
    telegram_id = callback.from_user.id
    data = await state.get_data()

    # Проверка подписки
    has_sub, msg = has_active_subscription(telegram_id)
    if not has_sub:
        await callback.message.edit_text(msg)
        await callback.answer()
        await state.clear()
        return

    # Создаем кампанию в БД
    campaign_name = f"Рассылка от {callback.message.date.strftime('%d.%m.%Y %H:%M')}"
    campaign_id = db.create_campaign(
        telegram_id=telegram_id,
        name=campaign_name,
        smtp_config_id=data['smtp_config_id'],
        template_id=data['template_id'],
        contact_list_id=data['contact_list_id']
    )

    await callback.message.edit_text(
        "🚀 ЗАПУСК РАССЫЛКИ...\n\n"
        "⏳ Начинаю отправку писем\n"
        "Это может занять несколько минут"
    )
    await callback.answer()

    # Запускаем рассылку в фоне
    asyncio.create_task(run_campaign(telegram_id, campaign_id, callback.message))

    await state.clear()


async def run_campaign(telegram_id: int, campaign_id: str, message: Message):
    """
    Запуск рассылки в фоновом режиме
    """
    try:
        # Получаем данные кампании
        campaigns = db.get_campaigns(telegram_id)
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)

        if not campaign:
            await message.answer("❌ Ошибка: кампания не найдена", reply_markup=get_main_keyboard())
            return

        # Получаем SMTP, шаблон, контакты
        smtp_config = db.get_smtp_config(campaign['smtp_config_id'])
        template = db.get_template(campaign['template_id'])
        contact_list = db.get_contact_list(campaign['contact_list_id'])

        if not all([smtp_config, template, contact_list]):
            await message.answer("❌ Ошибка: не все данные найдены", reply_markup=get_main_keyboard())
            db.update_campaign_status(campaign_id, 'failed', 0, 0)
            return

        # Обновляем статус
        db.update_campaign_status(campaign_id, 'running')

        # Инициализируем EmailSender
        sender = EmailSender(smtp_config)

        # Callback для отслеживания прогресса
        sent_count = [0]
        failed_count = [0]

        async def progress_callback(current, total, email, success):
            if success:
                sent_count[0] += 1
            else:
                failed_count[0] += 1

            # Обновляем каждые 10 писем
            if current % 10 == 0 or current == total:
                await message.answer(
                    f"📧 Прогресс: {current}/{total}\n"
                    f"✅ Отправлено: {sent_count[0]}\n"
                    f"❌ Ошибок: {failed_count[0]}",
                    reply_markup=get_main_keyboard()
                )

        # Отправляем письма
        sent, failed, errors = await sender.send_bulk_emails(
            recipients=contact_list['contacts'],
            subject=template['subject'],
            body=template['body'],
            delay=1.0,  # 1 секунда между письмами
            callback=progress_callback
        )

        # Обновляем статус кампании
        db.update_campaign_status(campaign_id, 'completed', sent, failed)

        # Итоговое сообщение
        await message.answer(
            f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
            f"📨 Всего писем: {sent + failed}\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}\n\n"
            f"Проверьте историю: 📊 История",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logger.error(f"Campaign error: {e}", exc_info=True)
        db.update_campaign_status(campaign_id, 'failed', 0, 0)
        await message.answer(
            f"❌ ОШИБКА РАССЫЛКИ\n\n{str(e)}",
            reply_markup=get_main_keyboard()
        )


@router.callback_query(F.data == "campaign_cancel")
async def campaign_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания рассылки"""
    await callback.message.edit_text("❌ Рассылка отменена")
    await state.clear()
    await callback.answer()
