"""
SMTP Email Sender - асинхронная отправка email
Поддерживает Gmail, Yandex, Mail.ru и другие SMTP серверы
"""

import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailSender:
    """Асинхронная отправка email через SMTP"""

    def __init__(self, smtp_config: Dict):
        """
        Args:
            smtp_config: Словарь с настройками SMTP
                {
                    'smtp_host': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'smtp_user': 'user@gmail.com',
                    'smtp_password': 'app_password',
                    'from_email': 'user@gmail.com',
                    'from_name': 'Sender Name'
                }
        """
        self.smtp_host = smtp_config['smtp_host']
        self.smtp_port = smtp_config['smtp_port']
        self.smtp_user = smtp_config['smtp_user']
        self.smtp_password = smtp_config['smtp_password']
        self.from_email = smtp_config['from_email']
        self.from_name = smtp_config.get('from_name', smtp_config['from_email'])

    def send_email(self, to_email: str, subject: str, body: str) -> Tuple[bool, str]:
        """
        Отправка одного email

        Args:
            to_email: Email получателя
            subject: Тема письма
            body: Текст письма (HTML поддерживается)

        Returns:
            Tuple[bool, str]: (успех, сообщение об ошибке)
        """
        try:
            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Добавляем тело письма (поддержка HTML)
            if '<html>' in body.lower() or '<p>' in body.lower():
                part = MIMEText(body, 'html', 'utf-8')
            else:
                part = MIMEText(body, 'plain', 'utf-8')

            msg.attach(part)

            # Подключаемся к SMTP серверу
            if self.smtp_port == 465:
                # SSL
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                # TLS (587) или обычный (25)
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                if self.smtp_port == 587:
                    server.starttls()

            # Авторизация
            server.login(self.smtp_user, self.smtp_password)

            # Отправка
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent to {to_email}")
            return True, ""

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Ошибка авторизации SMTP: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"Получатель отклонен: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except smtplib.SMTPException as e:
            error_msg = f"SMTP ошибка: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Неизвестная ошибка: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def send_bulk_emails(self, recipients: List[str], subject: str,
                              body: str, delay: float = 1.0,
                              callback=None) -> Tuple[int, int, List[str]]:
        """
        Массовая отправка email с задержкой между письмами

        Args:
            recipients: Список email получателей
            subject: Тема письма
            body: Текст письма
            delay: Задержка между письмами в секундах (защита от спама)
            callback: Опциональная callback функция для отслеживания прогресса
                      callback(current, total, email, success)

        Returns:
            Tuple[int, int, List[str]]: (успешно, ошибок, список ошибок)
        """
        sent_count = 0
        failed_count = 0
        errors = []
        total = len(recipients)

        for i, email in enumerate(recipients, 1):
            # Отправка письма (синхронная операция в executor)
            loop = asyncio.get_event_loop()
            success, error_msg = await loop.run_in_executor(
                None,
                self.send_email,
                email,
                subject,
                body
            )

            if success:
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"{email}: {error_msg}")

            # Callback для отслеживания прогресса
            if callback:
                try:
                    await callback(i, total, email, success)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            # Задержка между письмами (кроме последнего)
            if i < total:
                await asyncio.sleep(delay)

        logger.info(f"Bulk send completed: {sent_count} sent, {failed_count} failed")
        return sent_count, failed_count, errors

    @staticmethod
    def test_smtp_connection(smtp_config: Dict) -> Tuple[bool, str]:
        """
        Тест SMTP подключения

        Args:
            smtp_config: Настройки SMTP

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            smtp_host = smtp_config['smtp_host']
            smtp_port = smtp_config['smtp_port']
            smtp_user = smtp_config['smtp_user']
            smtp_password = smtp_config['smtp_password']

            # Подключение
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                if smtp_port == 587:
                    server.starttls()

            # Авторизация
            server.login(smtp_user, smtp_password)
            server.quit()

            return True, "✅ Подключение успешно!"

        except smtplib.SMTPAuthenticationError:
            return False, "❌ Ошибка авторизации. Проверьте логин и пароль."

        except smtplib.SMTPConnectError:
            return False, "❌ Не удалось подключиться к SMTP серверу."

        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"


# ========== ПРЕДУСТАНОВЛЕННЫЕ SMTP КОНФИГУРАЦИИ ==========

SMTP_PRESETS = {
    'gmail': {
        'name': 'Gmail',
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'instructions': '''
📧 Настройка Gmail:

1. Включите двухфакторную аутентификацию:
   https://myaccount.google.com/security

2. Создайте пароль приложения:
   https://myaccount.google.com/apppasswords

3. Выберите "Почта" и "Другое устройство"

4. Скопируйте сгенерированный пароль (16 символов)

5. Используйте:
   • Email: ваш.email@gmail.com
   • Пароль: пароль приложения из шага 4
'''
    },
    'yandex': {
        'name': 'Yandex',
        'smtp_host': 'smtp.yandex.ru',
        'smtp_port': 587,
        'instructions': '''
📧 Настройка Yandex:

1. Включите IMAP в настройках:
   https://mail.yandex.ru/#setup/client

2. Создайте пароль приложения:
   https://id.yandex.ru/security/app-passwords

3. Нажмите "Создать пароль приложения"

4. Выберите "Почта" → введите название

5. Скопируйте пароль

6. Используйте:
   • Email: ваш.email@yandex.ru
   • Пароль: пароль приложения из шага 5
'''
    },
    'mailru': {
        'name': 'Mail.ru',
        'smtp_host': 'smtp.mail.ru',
        'smtp_port': 587,
        'instructions': '''
📧 Настройка Mail.ru:

1. Включите IMAP/SMTP:
   https://e.mail.ru/settings/security

2. Создайте пароль для внешнего приложения:
   Настройки → Пароль и безопасность →
   Пароли для внешних приложений

3. Введите название и создайте пароль

4. Скопируйте пароль

5. Используйте:
   • Email: ваш.email@mail.ru
   • Пароль: пароль приложения из шага 4
'''
    },
    'custom': {
        'name': 'Другой SMTP',
        'smtp_host': '',
        'smtp_port': 587,
        'instructions': '''
📧 Настройка корпоративной/другой почты:

Узнайте у вашего провайдера:
1. SMTP сервер (например: smtp.example.com)
2. SMTP порт (обычно 587 или 465)
3. Требуется ли SSL/TLS

Стандартные порты:
• 587 - TLS (рекомендуется)
• 465 - SSL
• 25 - без шифрования (не рекомендуется)

Используйте ваши обычные данные для входа в почту.
'''
    }
}
