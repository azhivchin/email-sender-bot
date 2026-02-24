"""
База данных для Email Рассылка Бота
Подписка: 1000 ₽/мес без лимитов
"""

import logging
import sqlite3
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class EmailBotDatabase:
    """База данных для multi-user email рассылки"""

    def __init__(self, db_path: str = '/opt/email-sender-bot/email_bot.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализирует БД и создает таблицы"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Таблица пользователей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    subscription_until TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица SMTP конфигураций
            conn.execute('''
                CREATE TABLE IF NOT EXISTS smtp_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    smtp_host TEXT NOT NULL,
                    smtp_port INTEGER NOT NULL,
                    smtp_user TEXT NOT NULL,
                    smtp_password TEXT NOT NULL,
                    from_email TEXT NOT NULL,
                    from_name TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
                )
            ''')

            # Таблица списков контактов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS contact_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    contacts TEXT NOT NULL,
                    total_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
                )
            ''')

            # Таблица шаблонов писем
            conn.execute('''
                CREATE TABLE IF NOT EXISTS email_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
                )
            ''')

            # Таблица рассылок (кампаний)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    user_telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    smtp_config_id INTEGER NOT NULL,
                    template_id INTEGER NOT NULL,
                    contact_list_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    total_emails INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (smtp_config_id) REFERENCES smtp_configs(id),
                    FOREIGN KEY (template_id) REFERENCES email_templates(id),
                    FOREIGN KEY (contact_list_id) REFERENCES contact_lists(id)
                )
            ''')

            # Таблица отправленных писем
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sent_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    sent_at TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            ''')

            # Таблица транзакций (подписки)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    description TEXT,
                    admin_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
                )
            ''')

            conn.commit()
            logger.info("Email Bot Database initialized")

    # ========== USERS ==========

    def register_user(self, telegram_id: int, username: str = None,
                     first_name: str = None, last_name: str = None):
        """Регистрация нового пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name))
            conn.commit()
        logger.info(f"User {telegram_id} registered")

    def is_user_registered(self, telegram_id: int) -> bool:
        """Проверка регистрации пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT 1 FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            return cursor.fetchone() is not None

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def has_active_subscription(self, telegram_id: int) -> bool:
        """Проверка активной подписки"""
        user = self.get_user(telegram_id)
        if not user or not user['subscription_until']:
            return False

        sub_until = datetime.fromisoformat(user['subscription_until'])
        return sub_until > datetime.now()

    def extend_subscription(self, telegram_id: int, months: int = 1):
        """Продлить подписку на N месяцев"""
        user = self.get_user(telegram_id)

        # Если подписка еще активна - продлеваем от текущей даты окончания
        if user['subscription_until']:
            sub_until = datetime.fromisoformat(user['subscription_until'])
            if sub_until > datetime.now():
                new_until = sub_until + timedelta(days=30 * months)
            else:
                new_until = datetime.now() + timedelta(days=30 * months)
        else:
            new_until = datetime.now() + timedelta(days=30 * months)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users
                SET subscription_until = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (new_until.isoformat(), telegram_id))
            conn.commit()

        logger.info(f"Subscription extended for user {telegram_id} until {new_until}")
        return new_until

    # ========== SMTP CONFIGS ==========

    def add_smtp_config(self, telegram_id: int, name: str, smtp_host: str,
                       smtp_port: int, smtp_user: str, smtp_password: str,
                       from_email: str, from_name: str = None) -> int:
        """Добавить SMTP конфигурацию"""
        with sqlite3.connect(self.db_path) as conn:
            # Если это первая конфигурация - делаем ее default
            cursor = conn.execute(
                'SELECT COUNT(*) FROM smtp_configs WHERE user_telegram_id = ?',
                (telegram_id,)
            )
            is_first = cursor.fetchone()[0] == 0

            cursor = conn.execute('''
                INSERT INTO smtp_configs
                (user_telegram_id, name, smtp_host, smtp_port, smtp_user,
                 smtp_password, from_email, from_name, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (telegram_id, name, smtp_host, smtp_port, smtp_user,
                  smtp_password, from_email, from_name, is_first))
            conn.commit()
            return cursor.lastrowid

    def get_smtp_configs(self, telegram_id: int) -> List[Dict]:
        """Получить все SMTP конфигурации пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM smtp_configs WHERE user_telegram_id = ? ORDER BY created_at DESC',
                (telegram_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_smtp_config(self, config_id: int) -> Optional[Dict]:
        """Получить SMTP конфигурацию по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM smtp_configs WHERE id = ?',
                (config_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_smtp_config(self, config_id: int):
        """Удалить SMTP конфигурацию"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM smtp_configs WHERE id = ?', (config_id,))
            conn.commit()

    # ========== CONTACT LISTS ==========

    def add_contact_list(self, telegram_id: int, name: str, contacts: List[str]) -> int:
        """Добавить список контактов"""
        contacts_json = json.dumps(contacts)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO contact_lists
                (user_telegram_id, name, contacts, total_count)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, name, contacts_json, len(contacts)))
            conn.commit()
            return cursor.lastrowid

    def get_contact_lists(self, telegram_id: int) -> List[Dict]:
        """Получить все списки контактов пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT id, name, total_count, created_at FROM contact_lists WHERE user_telegram_id = ? ORDER BY created_at DESC',
                (telegram_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_contact_list(self, list_id: int) -> Optional[Dict]:
        """Получить список контактов по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM contact_lists WHERE id = ?',
                (list_id,)
            )
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data['contacts'] = json.loads(data['contacts'])
                return data
            return None

    # ========== EMAIL TEMPLATES ==========

    def add_template(self, telegram_id: int, name: str, subject: str, body: str) -> int:
        """Добавить шаблон письма"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO email_templates
                (user_telegram_id, name, subject, body)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, name, subject, body))
            conn.commit()
            return cursor.lastrowid

    def get_templates(self, telegram_id: int) -> List[Dict]:
        """Получить все шаблоны пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM email_templates WHERE user_telegram_id = ? ORDER BY created_at DESC',
                (telegram_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_template(self, template_id: int) -> Optional[Dict]:
        """Получить шаблон по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM email_templates WHERE id = ?',
                (template_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # ========== CAMPAIGNS ==========

    def create_campaign(self, telegram_id: int, name: str, smtp_config_id: int,
                       template_id: int, contact_list_id: int) -> str:
        """Создать новую рассылку"""
        campaign_id = str(uuid.uuid4())

        # Получаем количество контактов
        contact_list = self.get_contact_list(contact_list_id)
        total_emails = len(contact_list['contacts']) if contact_list else 0

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO campaigns
                (id, user_telegram_id, name, smtp_config_id, template_id,
                 contact_list_id, total_emails, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (campaign_id, telegram_id, name, smtp_config_id,
                  template_id, contact_list_id, total_emails))
            conn.commit()

        return campaign_id

    def get_campaigns(self, telegram_id: int, limit: int = 20) -> List[Dict]:
        """Получить рассылки пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM campaigns WHERE user_telegram_id = ? ORDER BY created_at DESC LIMIT ?',
                (telegram_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_campaign_status(self, campaign_id: str, status: str,
                              sent_count: int = None, failed_count: int = None):
        """Обновить статус рассылки"""
        with sqlite3.connect(self.db_path) as conn:
            if sent_count is not None and failed_count is not None:
                conn.execute('''
                    UPDATE campaigns
                    SET status = ?, sent_count = ?, failed_count = ?,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, sent_count, failed_count, campaign_id))
            else:
                conn.execute('''
                    UPDATE campaigns
                    SET status = ?, started_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, campaign_id))
            conn.commit()

    # ========== TRANSACTIONS ==========

    def add_transaction(self, telegram_id: int, amount: float,
                       transaction_type: str, description: str = None,
                       admin_id: int = None):
        """Добавить транзакцию"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO transactions
                (user_telegram_id, amount, type, description, admin_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, amount, transaction_type, description, admin_id))
            conn.commit()

    def get_transactions(self, telegram_id: int, limit: int = 20) -> List[Dict]:
        """Получить транзакции пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM transactions WHERE user_telegram_id = ? ORDER BY created_at DESC LIMIT ?',
                (telegram_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    # ========== ADMIN ==========

    def is_admin(self, telegram_id: int) -> bool:
        """Проверка прав администратора"""
        user = self.get_user(telegram_id)
        return user and user['is_admin']

    def make_admin(self, telegram_id: int):
        """Дать права администратора"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE users SET is_admin = 1 WHERE telegram_id = ?',
                (telegram_id,)
            )
            conn.commit()

    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """Получить статистику бота"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
            active_subs = conn.execute(
                'SELECT COUNT(*) as count FROM users WHERE subscription_until > datetime("now")'
            ).fetchone()['count']

            total_campaigns = conn.execute('SELECT COUNT(*) as count FROM campaigns').fetchone()['count']
            total_sent = conn.execute('SELECT SUM(sent_count) as total FROM campaigns').fetchone()['total'] or 0

            total_revenue = conn.execute(
                'SELECT SUM(amount) as total FROM transactions WHERE type = "subscription"'
            ).fetchone()['total'] or 0

            return {
                'total_users': total_users,
                'active_subscriptions': active_subs,
                'total_campaigns': total_campaigns,
                'total_emails_sent': total_sent,
                'total_revenue': total_revenue
            }
