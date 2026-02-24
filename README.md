# Email Sender Bot

Telegram bot for managing email campaigns. Configure SMTP accounts, build contact lists, compose emails with templates, and send bulk campaigns, all through a Telegram chat interface.

## How it works

You interact with the bot in Telegram. It walks you through each step: connect your SMTP server (Gmail, Yandex, Mail.ru, or custom), upload contacts from a file or add them manually, write your email (subject, body, attachments), and hit send. The bot handles delivery with configurable delays between messages to avoid spam filters.

Contacts can be imported from text files or parsed from structured data. Email templates are saved and reusable. Campaign history is tracked so you can see what was sent and when.

## Features

- Multiple SMTP configurations per user (Gmail, Yandex, Mail.ru, custom)
- Contact list management with import from files
- Email templates with save/load
- Bulk sending with configurable delay between messages
- Campaign tracking and history
- Admin panel for user management
- Subscription-based access model

## Tech stack

- **Python 3** with asyncio
- **aiogram 3** for async Telegram bot interaction
- **SQLite** as local database for users, contacts, campaigns, SMTP configs
- **smtplib** for SMTP delivery

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your bot token and admin ID
python email_bot.py
```

## Environment variables

```env
TELEGRAM_BOT_TOKEN=your-bot-token
ADMIN_TELEGRAM_ID=your-telegram-id
DATABASE_PATH=email_bot.db
```

## Project structure

```
├── email_bot.py           # Bot entry point
├── email_bot_config.py    # Configuration
├── email_bot_database.py  # SQLite operations
├── email_bot_handlers.py  # Telegram message handlers
├── email_bot_admin.py     # Admin commands
├── email_sender.py        # SMTP sending logic
├── contacts_parser.py     # Contact import/parsing
└── requirements.txt
```

## License

MIT
