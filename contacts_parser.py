"""
Парсер контактов из CSV/XLSX файлов
"""

import logging
import csv
import io
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContactsParser:
    """Парсинг контактов из различных форматов"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """Проверка валидности email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None

    @staticmethod
    def parse_csv_text(text: str) -> List[str]:
        """
        Парсинг CSV из текста

        Поддерживаемые форматы:
        1. Простой список email (по одному на строку)
        2. CSV с колонкой email
        3. CSV с множественными колонками

        Returns:
            List[str]: Список email адресов
        """
        emails = []
        lines = text.strip().split('\n')

        # Проверяем первую строку - возможно это CSV с заголовками
        first_line = lines[0].strip()

        # Проверяем наличие запятых/точек с запятой
        if ',' in first_line or ';' in first_line:
            # Это CSV файл
            delimiter = ',' if ',' in first_line else ';'

            try:
                reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

                # Ищем колонку с email
                email_column = None
                for field in reader.fieldnames or []:
                    field_lower = field.lower().strip()
                    if field_lower in ['email', 'e-mail', 'mail', 'emails']:
                        email_column = field
                        break

                if not email_column:
                    # Если нет заголовка email, берем первую колонку
                    email_column = reader.fieldnames[0] if reader.fieldnames else None

                if email_column:
                    for row in reader:
                        email = row.get(email_column, '').strip()
                        if email and ContactsParser.validate_email(email):
                            emails.append(email.lower())

            except Exception as e:
                logger.error(f"CSV parsing error: {e}")
                # Fallback - парсим как простой текст
                pass

        # Если CSV не сработал или это простой список
        if not emails:
            for line in lines:
                line = line.strip()
                if not line or line.lower().startswith(('email', 'e-mail')):
                    continue

                # Извлекаем все email из строки
                found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line)
                for email in found_emails:
                    email = email.lower().strip()
                    if ContactsParser.validate_email(email):
                        emails.append(email)

        # Убираем дубликаты
        emails = list(set(emails))
        logger.info(f"Parsed {len(emails)} unique emails")
        return emails

    @staticmethod
    async def parse_csv_file(file_bytes: bytes, filename: str) -> List[str]:
        """
        Парсинг CSV/XLSX файла

        Args:
            file_bytes: Содержимое файла
            filename: Имя файла (для определения типа)

        Returns:
            List[str]: Список email адресов
        """
        emails = []

        try:
            # Определяем формат по расширению
            file_ext = filename.lower().split('.')[-1]

            if file_ext in ['csv', 'txt']:
                # CSV файл
                text = file_bytes.decode('utf-8', errors='ignore')
                emails = ContactsParser.parse_csv_text(text)

            elif file_ext in ['xlsx', 'xls']:
                # Excel файл - требует openpyxl
                try:
                    import openpyxl
                    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes))
                    sheet = workbook.active

                    # Пытаемся найти колонку с email
                    email_col = None
                    header_row = 1

                    for col_idx, cell in enumerate(sheet[header_row], 1):
                        if cell.value and str(cell.value).lower().strip() in ['email', 'e-mail', 'mail']:
                            email_col = col_idx
                            break

                    # Если не нашли заголовок, берем первую колонку
                    if not email_col:
                        email_col = 1
                        header_row = 0  # Нет заголовка

                    # Читаем emails
                    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
                        if row and len(row) >= email_col:
                            email = str(row[email_col - 1] or '').strip()
                            if email and ContactsParser.validate_email(email):
                                emails.append(email.lower())

                    # Убираем дубликаты
                    emails = list(set(emails))

                except ImportError:
                    logger.warning("openpyxl not installed, cannot parse XLSX files")
                    raise Exception("Установите библиотеку для работы с XLSX: pip install openpyxl")

            else:
                raise Exception(f"Неподдерживаемый формат файла: {file_ext}")

            logger.info(f"Parsed {len(emails)} emails from {filename}")
            return emails

        except Exception as e:
            logger.error(f"File parsing error: {e}")
            raise

    @staticmethod
    def format_contacts_preview(emails: List[str], max_show: int = 5) -> str:
        """
        Форматирование предпросмотра контактов

        Args:
            emails: Список email
            max_show: Сколько показывать

        Returns:
            str: Форматированная строка
        """
        total = len(emails)
        preview = emails[:max_show]

        text = f"📧 Всего контактов: {total}\n\n"
        text += "Примеры:\n"
        for i, email in enumerate(preview, 1):
            text += f"{i}. {email}\n"

        if total > max_show:
            text += f"\n... и еще {total - max_show} контактов"

        return text
