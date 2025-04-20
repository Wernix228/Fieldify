import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import MessageNotModifiedError
import spacy
from pydantic import BaseModel
import threading
import queue
from nlp_processor import NLPProcessor
from database import session, Message as DBMessage, ChatConfig as DBChatConfig
from text_processor import TextProcessor
import json
from pathlib import Path

# Определяем базовые пути
BASE_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = BASE_DIR / 'configs'
DATA_DIR = BASE_DIR / 'data'

# Создаем необходимые директории
os.makedirs(CONFIGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Загружаем переменные окружения из configs/.env
env_path = CONFIGS_DIR / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load NLP model
try:
    nlp_processor = NLPProcessor()
except Exception as e:
    logger.error(f"Failed to initialize NLP processor: {e}")
    nlp_processor = None

class TagConfig(BaseModel):
    tag: str
    field: str
    is_active: bool

class ChatConfig(BaseModel):
    chat_id: int
    tags: Dict[str, str]  # tag -> field mapping
    use_nlp: bool
    duplicate_threshold: float
    active: bool

class ChatManager:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.tag_configs: Dict[int, List[TagConfig]] = {}
        self.chat_configs: Dict[int, ChatConfig] = {}
        self.default_tags = {
            "Дата:": "date",
            "Адрес:": "address",
            "Имя:": "name",
            "Телефон:": "phone"
        }
        self.waiting_for_tag: Dict[int, bool] = {}
        self.load_chat_configs()

    def load_chat_configs(self):
        """Загружает конфигурации чатов из базы данных"""
        try:
            configs = session.query(DBChatConfig).all()
            for config in configs:
                chat_id = config.chat_id
                self.tag_configs[chat_id] = [
                    TagConfig(tag=tag, field=field, is_active=True)
                    for tag, field in config.tags.items()
                ]
        except Exception as e:
            logger.error(f"Error loading chat configs: {e}")

    def save_chat_config(self, chat_id: int):
        """Сохраняет конфигурацию чата в базу данных"""
        try:
            config = session.query(DBChatConfig).filter_by(chat_id=chat_id).first()
            if not config:
                config = DBChatConfig(chat_id=chat_id)
                session.add(config)
            
            config.tags = {tag.tag: tag.field for tag in self.tag_configs.get(chat_id, [])}
            session.commit()
        except Exception as e:
            logger.error(f"Error saving chat config: {e}")
            session.rollback()

    def save_tags_to_json(self, chat_id: int):
        """Сохраняет метки в JSON файлы"""
        try:
            # Сохраняем метки в tags.json
            tags_data = {}
            tags_file = DATA_DIR / 'tags.json'
            if tags_file.exists():
                with open(tags_file, 'r', encoding='utf-8') as f:
                    tags_data = json.load(f)
            
            if chat_id in self.tag_configs:
                tags_data[str(chat_id)] = {
                    tag.tag: tag.field 
                    for tag in self.tag_configs[chat_id]
                }
            
            with open(tags_file, 'w', encoding='utf-8') as f:
                json.dump(tags_data, f, ensure_ascii=False, indent=2)
                
            # Для tag_values.json не создаем пустые списки
            tag_values_file = DATA_DIR / 'tag_values.json'
            if tag_values_file.exists():
                with open(tag_values_file, 'r', encoding='utf-8') as f:
                    tag_values = json.load(f)
            else:
                tag_values = {}
                
            if str(chat_id) not in tag_values:
                tag_values[str(chat_id)] = {}
                
            with open(tag_values_file, 'w', encoding='utf-8') as f:
                json.dump(tag_values, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving tags to JSON: {e}")

    async def handle_config_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /config"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/config'):
                return

            help_text = (
                "Доступные команды:\n"
                "/config - показать это сообщение\n"
                "/tags - управление метками\n"
                "/add_tag метка:поле - добавить новую метку\n"
                "/toggle_tag метка - включить/выключить метку\n"
                "/show_tags - показать все метки\n"
                "/show_values - показать все значения меток\n"
                "/show_tag_values метка - показать значения конкретной метки\n"
                "/nlp on/off - включить/выключить NLP\n"
                "/threshold 0.7 - установить порог дубликатов\n"
                "/status - показать статус бота\n"
                "/data [limit] - показать последние извлеченные данные\n"
                "/data_chat chat_id [limit] - показать данные для конкретного чата\n"
                "/export - экспортировать все данные в CSV файл"
            )
            
            await event.reply(help_text)
        except Exception as e:
            logger.error(f"Error in handle_config_command: {e}")
            await event.reply("Произошла ошибка при обработке команды. Попробуйте позже.")

    async def handle_tags_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /tags"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/tags'):
                return
                
            if chat_id not in self.tag_configs:
                self.tag_configs[chat_id] = [
                    TagConfig(tag=tag, field=field, is_active=True)
                    for tag, field in self.default_tags.items()
                ]

            tags_text = "Управление метками:\n✅ - активна\n❌ - неактивна\n\n"
            for tag_config in self.tag_configs[chat_id]:
                status = "✅" if tag_config.is_active else "❌"
                tags_text += f"{status} {tag_config.tag} -> {tag_config.field}\n"
            
            tags_text += "\nИспользуйте /toggle_tag метка для включения/выключения метки"
            tags_text += "\nИспользуйте /add_tag метка:поле для добавления новой метки"
            
            await event.reply(tags_text)
        except Exception as e:
            logger.error(f"Error in handle_tags_command: {e}")
            await event.reply("Произошла ошибка. Попробуйте позже.")

    async def handle_add_tag_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /add_tag"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/add_tag'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/add_tag метка:поле\n"
                    "Например: /add_tag Дата:date"
                )
                return
                
            tag_param = parts[1]
            
            try:
                tag, field = tag_param.split(":")
                new_config = TagConfig(tag=tag.strip(), field=field.strip(), is_active=True)
                
                if chat_id not in self.tag_configs:
                    self.tag_configs[chat_id] = []
                
                # Проверка на дубликаты
                if any(tc.tag == new_config.tag for tc in self.tag_configs[chat_id]):
                    await event.reply(f"Метка '{tag}' уже существует")
                    return
                
                self.tag_configs[chat_id].append(new_config)
                self.save_chat_config(chat_id)
                self.save_tags_to_json(chat_id)  # Сохраняем в JSON
                
                await event.reply(f"Метка {tag} успешно добавлена!")
                
            except ValueError:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/add_tag метка:поле\n"
                    "Например: /add_tag Дата:date"
                )
        except Exception as e:
            logger.error(f"Error in handle_add_tag_command: {e}")
            await event.reply("Произошла ошибка при добавлении метки")

    async def handle_toggle_tag_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /toggle_tag"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/toggle_tag'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/toggle_tag метка\n"
                    "Например: /toggle_tag Дата:"
                )
                return
                
            tag = parts[1].strip()
            
            if chat_id not in self.tag_configs:
                await event.reply("Конфигурация чата не найдена")
                return
                
            tag_found = False
            for tag_config in self.tag_configs[chat_id]:
                if tag_config.tag == tag:
                    tag_config.is_active = not tag_config.is_active
                    tag_found = True
                    status = "включена" if tag_config.is_active else "выключена"
                    await event.reply(f"Метка '{tag}' {status}")
                    break
            
            if not tag_found:
                await event.reply(f"Метка '{tag}' не найдена")
                return
                
            self.save_chat_config(chat_id)
        except Exception as e:
            logger.error(f"Error in handle_toggle_tag_command: {e}")
            await event.reply("Произошла ошибка при переключении метки")

    async def handle_nlp_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /nlp"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/nlp'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/nlp on или /nlp off"
                )
                return
                
            param = parts[1].strip().lower()
            
            if param not in ['on', 'off']:
                await event.reply(
                    "Неверный параметр. Используйте 'on' или 'off'"
                )
                return
                
            # Получаем конфигурацию чата
            config = self.get_chat_config(chat_id)
            if not config:
                config = ChatConfig(
                    chat_id=chat_id,
                    tags=self.get_active_tags(chat_id),
                    use_nlp=True,
                    duplicate_threshold=0.7,
                    active=True
                )
                self.chat_configs[chat_id] = config
                
            config.use_nlp = (param == 'on')
            self.update_chat_config(chat_id, config)
            
            status = "включен" if config.use_nlp else "выключен"
            await event.reply(f"NLP {status}")
        except Exception as e:
            logger.error(f"Error in handle_nlp_command: {e}")
            await event.reply("Произошла ошибка при изменении настройки NLP")

    async def handle_threshold_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /threshold"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/threshold'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/threshold 0.7"
                )
                return
                
            try:
                threshold = float(parts[1].strip())
                if threshold < 0 or threshold > 1:
                    await event.reply(
                        "Порог должен быть числом от 0 до 1"
                    )
                    return
                    
                # Получаем конфигурацию чата
                config = self.get_chat_config(chat_id)
                if not config:
                    config = ChatConfig(
                        chat_id=chat_id,
                        tags=self.get_active_tags(chat_id),
                        use_nlp=True,
                        duplicate_threshold=threshold,
                        active=True
                    )
                    self.chat_configs[chat_id] = config
                else:
                    config.duplicate_threshold = threshold
                    self.update_chat_config(chat_id, config)
                    
                await event.reply(f"Порог дубликатов установлен на {threshold}")
            except ValueError:
                await event.reply(
                    "Неверный формат. Используйте число от 0 до 1"
                )
        except Exception as e:
            logger.error(f"Error in handle_threshold_command: {e}")
            await event.reply("Произошла ошибка при установке порога дубликатов")

    async def handle_status_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /status"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/status'):
                return
                
            # Получаем конфигурацию чата
            config = self.get_chat_config(chat_id)
            if not config:
                config = ChatConfig(
                    chat_id=chat_id,
                    tags=self.get_active_tags(chat_id),
                    use_nlp=True,
                    duplicate_threshold=0.7,
                    active=True
                )
                self.chat_configs[chat_id] = config
                
            # Получаем активные метки
            active_tags = self.get_active_tags(chat_id)
            
            status_text = (
                f"Статус бота:\n"
                f"NLP: {'включен' if config.use_nlp else 'выключен'}\n"
                f"Порог дубликатов: {config.duplicate_threshold}\n"
                f"Активные метки: {len(active_tags)}\n\n"
                f"Список активных меток:\n"
            )
            
            for tag, field in active_tags.items():
                status_text += f"{tag} -> {field}\n"
                
            await event.reply(status_text)
        except Exception as e:
            logger.error(f"Error in handle_status_command: {e}")
            await event.reply("Произошла ошибка при получении статуса")

    async def handle_data_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /data для просмотра данных из базы"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/data'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=1)
            limit = 10  # По умолчанию показываем 10 записей
            
            if len(parts) > 1:
                try:
                    limit = int(parts[1].strip())
                    if limit <= 0:
                        limit = 10
                    if limit > 50:  # Ограничиваем максимальное количество записей
                        limit = 50
                except ValueError:
                    await event.reply(
                        "Неверный формат. Используйте число, например: /data 20"
                    )
                    return
            
            # Получаем данные из базы
            messages = session.query(DBMessage).order_by(DBMessage.timestamp.desc()).limit(limit).all()
            
            if not messages:
                await event.reply("В базе данных нет записей.")
                return
                
            # Формируем сообщение с данными
            data_text = f"Последние {len(messages)} записей из базы данных:\n\n"
            
            for i, msg in enumerate(messages, 1):
                data_text += f"Запись #{i} (ID: {msg.id}):\n"
                data_text += f"Чат: {msg.chat_id}\n"
                data_text += f"Время: {msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                
                # Добавляем извлеченные данные
                if msg.date:
                    data_text += f"Дата: {msg.date}\n"
                if msg.address:
                    data_text += f"Адрес: {msg.address}\n"
                if msg.name:
                    data_text += f"Имя: {msg.name}\n"
                if msg.phone:
                    data_text += f"Телефон: {msg.phone}\n"
                
                # Добавляем исходный текст сообщения (сокращенный)
                if msg.message_text:
                    text_preview = msg.message_text[:100] + "..." if len(msg.message_text) > 100 else msg.message_text
                    data_text += f"Текст: {text_preview}\n"
                
                data_text += "\n" + "-" * 30 + "\n\n"
            
            # Отправляем данные частями, если они слишком длинные
            if len(data_text) > 4000:
                parts = [data_text[i:i+4000] for i in range(0, len(data_text), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await event.reply(part)
                    else:
                        await self.client.send_message(chat_id, part)
            else:
                await event.reply(data_text)
                
        except Exception as e:
            logger.error(f"Error in handle_data_command: {e}")
            await event.reply("Произошла ошибка при получении данных из базы.")

    async def handle_data_chat_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /data_chat для просмотра данных из базы для конкретного чата"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/data_chat'):
                return
                
            # Извлекаем параметры команды
            parts = message.text.split(maxsplit=2)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "/data_chat chat_id [limit]\n"
                    "Например: /data_chat 123456789 20"
                )
                return
                
            try:
                target_chat_id = int(parts[1].strip())
                limit = 10  # По умолчанию показываем 10 записей
                
                if len(parts) > 2:
                    try:
                        limit = int(parts[2].strip())
                        if limit <= 0:
                            limit = 10
                        if limit > 50:  # Ограничиваем максимальное количество записей
                            limit = 50
                    except ValueError:
                        await event.reply(
                            "Неверный формат лимита. Используйте число, например: /data_chat 123456789 20"
                        )
                        return
                
                # Получаем данные из базы для конкретного чата
                messages = session.query(DBMessage).filter_by(chat_id=target_chat_id).order_by(DBMessage.timestamp.desc()).limit(limit).all()
                
                if not messages:
                    await event.reply(f"В базе данных нет записей для чата {target_chat_id}.")
                    return
                    
                # Формируем сообщение с данными
                data_text = f"Последние {len(messages)} записей из базы данных для чата {target_chat_id}:\n\n"
                
                for i, msg in enumerate(messages, 1):
                    data_text += f"Запись #{i} (ID: {msg.id}):\n"
                    data_text += f"Время: {msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    # Добавляем извлеченные данные
                    if msg.date:
                        data_text += f"Дата: {msg.date}\n"
                    if msg.address:
                        data_text += f"Адрес: {msg.address}\n"
                    if msg.name:
                        data_text += f"Имя: {msg.name}\n"
                    if msg.phone:
                        data_text += f"Телефон: {msg.phone}\n"
                    
                    # Добавляем исходный текст сообщения (сокращенный)
                    if msg.message_text:
                        text_preview = msg.message_text[:100] + "..." if len(msg.message_text) > 100 else msg.message_text
                        data_text += f"Текст: {text_preview}\n"
                    
                    data_text += "\n" + "-" * 30 + "\n\n"
                
                # Отправляем данные частями, если они слишком длинные
                if len(data_text) > 4000:
                    parts = [data_text[i:i+4000] for i in range(0, len(data_text), 4000)]
                    for i, part in enumerate(parts):
                        if i == 0:
                            await event.reply(part)
                        else:
                            await self.client.send_message(chat_id, part)
                else:
                    await event.reply(data_text)
                    
            except ValueError:
                await event.reply(
                    "Неверный формат ID чата. Используйте число, например: /data_chat 123456789"
                )
                
        except Exception as e:
            logger.error(f"Error in handle_data_chat_command: {e}")
            await event.reply("Произошла ошибка при получении данных из базы.")

    async def handle_export_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /export для экспорта данных в CSV файл"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/export'):
                return
                
            # Получаем все данные из базы
            messages = session.query(DBMessage).order_by(DBMessage.timestamp.desc()).all()
            
            if not messages:
                await event.reply("В базе данных нет записей для экспорта.")
                return
                
            # Создаем временный CSV файл
            import csv
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as temp_file:
                writer = csv.writer(temp_file)
                
                # Записываем заголовки
                writer.writerow(['ID', 'Chat ID', 'Timestamp', 'Date', 'Address', 'Name', 'Phone', 'Message Text'])
                
                # Записываем данные
                for msg in messages:
                    writer.writerow([
                        msg.id,
                        msg.chat_id,
                        msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        msg.date or '',
                        msg.address or '',
                        msg.name or '',
                        msg.phone or '',
                        msg.message_text or ''
                    ])
                
                temp_file_path = temp_file.name
            
            # Отправляем файл
            await event.reply(f"Экспортировано {len(messages)} записей в CSV файл.")
            await self.client.send_file(chat_id, temp_file_path, comment="Данные из базы")
            
            # Удаляем временный файл
            os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Error in handle_export_command: {e}")
            await event.reply("Произошла ошибка при экспорте данных в CSV файл.")

    async def handle_show_tags_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /show_tags - показывает содержимое tags.json"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/show_tags'):
                return

            tags_file = DATA_DIR / 'tags.json'
            if not tags_file.exists():
                await event.reply("Файл с метками пуст или не существует.")
                return

            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)

            # Форматируем данные для текущего чата
            if str(chat_id) in tags_data:
                chat_tags = tags_data[str(chat_id)]
                response = "Список меток:\n\n"
                for tag, field in chat_tags.items():
                    response += f"Метка: {tag}\nПоле: {field}\n\n"
            else:
                response = "Для этого чата нет сохраненных меток."

            # Отправляем ответ
            await event.reply(response)

            # Отправляем файл JSON с правильным параметром comment
            with open(tags_file, 'rb') as f:
                await event.reply(file=f, comment="Файл со всеми метками (tags.json)")

        except Exception as e:
            logger.error(f"Error in handle_show_tags_command: {e}")
            await event.reply("Произошла ошибка при получении меток.")

    async def handle_show_values_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /show_values - показывает содержимое tag_values.json"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/show_values'):
                return

            values_file = DATA_DIR / 'tag_values.json'
            if not values_file.exists():
                await event.reply("Файл со значениями меток пуст или не существует.")
                return

            with open(values_file, 'r', encoding='utf-8') as f:
                values_data = json.load(f)

            # Форматируем данные для текущего чата
            if str(chat_id) in values_data:
                chat_values = values_data[str(chat_id)]
                response = "Значения меток:\n\n"
                for field, values in chat_values.items():
                    response += f"Поле: {field}\nЗначения:\n"
                    for value in values:
                        response += f"- {value}\n"
                    response += "\n"
            else:
                response = "Для этого чата нет сохраненных значений."

            # Отправляем ответ
            await event.reply(response)

            # Отправляем файл JSON с правильным параметром comment
            with open(values_file, 'rb') as f:
                await event.reply(file=f, comment="Файл со всеми значениями (tag_values.json)")

        except Exception as e:
            logger.error(f"Error in handle_show_values_command: {e}")
            await event.reply("Произошла ошибка при получении значений меток.")

    async def handle_show_tag_values_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /show_tag_values tag - показывает значения конкретной метки"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/show_tag_values'):
                return

            # Получаем имя метки из команды
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(
                    "Неверный формат. Используйте:\n"
                    "/show_tag_values метка\n"
                    "Например: /show_tag_values password"
                )
                return

            tag_name = parts[1].strip()

            # Загружаем оба файла для поиска
            tags_file = DATA_DIR / 'tags.json'
            values_file = DATA_DIR / 'tag_values.json'

            if not tags_file.exists() or not values_file.exists():
                await event.reply("Файлы с метками или значениями не существуют.")
                return

            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)

            with open(values_file, 'r', encoding='utf-8') as f:
                values_data = json.load(f)

            # Ищем поле для указанной метки
            field = None
            if str(chat_id) in tags_data:
                chat_tags = tags_data[str(chat_id)]
                for tag, tag_field in chat_tags.items():
                    if tag == tag_name:
                        field = tag_field
                        break

            if not field:
                await event.reply(f"Метка '{tag_name}' не найдена в конфигурации чата.")
                return

            # Получаем значения для найденного поля
            if str(chat_id) in values_data and field in values_data[str(chat_id)]:
                values = values_data[str(chat_id)][field]
                
                # Создаем временный JSON файл с значениями конкретной метки
                temp_data = {
                    "tag": tag_name,
                    "field": field,
                    "values": values
                }
                
                temp_file = DATA_DIR / f'temp_{field}_values.json'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(temp_data, f, ensure_ascii=False, indent=2)

                # Формируем текстовый ответ
                response = f"Значения для метки '{tag_name}' (поле: {field}):\n\n"
                for value in values:
                    response += f"- {value}\n"

                # Отправляем ответ
                await event.reply(response)

                # Отправляем файл JSON с правильным параметром comment
                with open(temp_file, 'rb') as f:
                    await event.reply(file=f, comment=f"Значения метки {tag_name}")

                # Удаляем временный файл
                temp_file.unlink()
            else:
                await event.reply(f"Для метки '{tag_name}' нет сохраненных значений.")

        except Exception as e:
            logger.error(f"Error in handle_show_tag_values_command: {e}")
            await event.reply("Произошла ошибка при получении значений метки.")

    def get_chat_config(self, chat_id: int) -> Optional[ChatConfig]:
        """Получает конфигурацию чата"""
        if chat_id not in self.chat_configs:
            # Создаем новую конфигурацию с активными метками
            active_tags = self.get_active_tags(chat_id)
            self.chat_configs[chat_id] = ChatConfig(
                chat_id=chat_id,
                tags=active_tags,
                use_nlp=True,
                duplicate_threshold=0.7,
                active=True
            )
        return self.chat_configs.get(chat_id)

    def update_chat_config(self, chat_id: int, config: ChatConfig):
        """Обновляет конфигурацию чата"""
        self.chat_configs[chat_id] = config

    def get_active_tags(self, chat_id: int) -> Dict[str, str]:
        """Возвращает активные метки для чата"""
        if chat_id not in self.tag_configs:
            return self.default_tags
        
        return {
            config.tag: config.field
            for config in self.tag_configs[chat_id]
            if config.is_active
        }

class MessageProcessor:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.processing_threads = []
        self.client = None
        self.chat_manager = None
        self.text_processor = TextProcessor(os.getenv("NOVITA_API_KEY"))

    def set_client(self, client: TelegramClient):
        self.client = client
        self.chat_manager = ChatManager(client)

    async def process_message(self, event: events.NewMessage.Event):
        try:
            message: Message = event.message
            chat_id = message.chat_id
            message_text = message.text
            
            if not message_text:
                return

            # Обработка команд
            if message_text.startswith('/'):
                if message_text.startswith('/show_tags'):
                    await self.chat_manager.handle_show_tags_command(event)
                elif message_text.startswith('/show_values'):
                    await self.chat_manager.handle_show_values_command(event)
                elif message_text.startswith('/show_tag_values'):
                    await self.chat_manager.handle_show_tag_values_command(event)
                elif message_text.startswith('/config'):
                    await self.chat_manager.handle_config_command(event)
                elif message_text.startswith('/tags'):
                    await self.chat_manager.handle_tags_command(event)
                elif message_text.startswith('/add_tag'):
                    await self.chat_manager.handle_add_tag_command(event)
                elif message_text.startswith('/toggle_tag'):
                    await self.chat_manager.handle_toggle_tag_command(event)
                elif message_text.startswith('/nlp'):
                    await self.chat_manager.handle_nlp_command(event)
                elif message_text.startswith('/threshold'):
                    await self.chat_manager.handle_threshold_command(event)
                elif message_text.startswith('/status'):
                    await self.chat_manager.handle_status_command(event)
                elif message_text.startswith('/data'):
                    await self.chat_manager.handle_data_command(event)
                elif message_text.startswith('/data_chat'):
                    await self.chat_manager.handle_data_chat_command(event)
                elif message_text.startswith('/export'):
                    await self.chat_manager.handle_export_command(event)
                return

            # Получение конфигурации чата
            config = self.chat_manager.get_chat_config(chat_id)
            if not config:
                logger.info(f"No config found for chat {chat_id}")
                return
            if not config.active:
                logger.info(f"Chat {chat_id} is not active")
                return

            # Добавление сообщения в очередь обработки
            logger.info(f"Adding message to queue from chat {chat_id}: {message_text[:100]}...")
            self.message_queue.put((chat_id, message_text, datetime.now()))

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def process_queue(self):
        while True:
            try:
                chat_id, message_text, timestamp = self.message_queue.get()
                logger.info(f"Processing message from chat {chat_id}: {message_text[:100]}...")
                
                # Получаем конфигурацию чата
                config = self.chat_manager.get_chat_config(chat_id)
                if not config:
                    logger.warning(f"No config found for chat {chat_id} during processing")
                    continue
                if not config.active:
                    logger.info(f"Chat {chat_id} is not active")
                    continue

                extracted_data = {}
                
                # Получаем активные метки
                active_tags = self.chat_manager.get_active_tags(chat_id)
                if active_tags:
                    # Извлекаем данные с помощью меток
                    tag_data = self.extract_data_with_tags(message_text, active_tags, chat_id)
                    if tag_data:
                        extracted_data.update(tag_data)
                        logger.info(f"Tags extracted data: {tag_data}")
                
                # Используем AI для обработки текста
                if config.use_nlp:
                    ai_data = asyncio.run(self.text_processor.process_text_with_ai(message_text))
                    if ai_data:
                        extracted_data.update(ai_data)
                        logger.info(f"AI extracted data: {ai_data}")

                # Проверяем дубликаты с помощью Levenshtein distance
                if self.check_duplicates_with_levenshtein(message_text, chat_id, config.duplicate_threshold):
                    logger.info(f"Duplicate message detected in chat {chat_id} using Levenshtein distance")
                    continue

                # Сохраняем в базу данных
                message = DBMessage(
                    chat_id=chat_id,
                    message_text=message_text,
                    timestamp=timestamp,
                    **extracted_data
                )
                session.add(message)
                session.commit()
                logger.info(f"Successfully saved message from chat {chat_id} with data: {extracted_data}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                session.rollback()

    def check_duplicates_with_levenshtein(self, text: str, chat_id: int, threshold: float) -> bool:
        """Проверяет наличие дубликатов с помощью расстояния Левенштейна"""
        try:
            # Получаем последние N сообщений из базы данных
            recent_messages = session.query(DBMessage).filter_by(chat_id=chat_id).order_by(DBMessage.timestamp.desc()).limit(10).all()
            
            for msg in recent_messages:
                if self.text_processor.is_similar(text, msg.message_text, threshold):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking duplicates with Levenshtein: {e}")
            return False

    def extract_data_with_tags(self, text: str, tags: Dict[str, str], chat_id: int) -> Dict:
        """
        Извлекает данные из текста с помощью меток
        
        Args:
            text (str): Текст для обработки
            tags (Dict[str, str]): Словарь меток и их полей
            chat_id (int): ID чата
        """
        extracted_data = {}
        for tag, field in tags.items():
            if tag in text:
                # Extract data after the tag
                start_idx = text.find(tag) + len(tag)
                end_idx = text.find('\n', start_idx)
                if end_idx == -1:
                    end_idx = len(text)
                value = text[start_idx:end_idx].strip()
                
                if value:  # Проверяем, что значение не пустое
                    extracted_data[field] = value
                    
                    # Сохраняем значение метки в tag_values.json
                    try:
                        tag_values = {}
                        tag_values_file = DATA_DIR / 'tag_values.json'
                        if tag_values_file.exists():
                            with open(tag_values_file, 'r', encoding='utf-8') as f:
                                tag_values = json.load(f)
                        
                        chat_id_str = str(chat_id)
                        if chat_id_str not in tag_values:
                            tag_values[chat_id_str] = {}
                        if field not in tag_values[chat_id_str]:
                            tag_values[chat_id_str][field] = []
                        
                        # Добавляем новое значение, если его еще нет
                        if value not in tag_values[chat_id_str][field]:
                            tag_values[chat_id_str][field].append(value)
                        
                        with open(tag_values_file, 'w', encoding='utf-8') as f:
                            json.dump(tag_values, f, ensure_ascii=False, indent=2)
                            
                    except Exception as e:
                        logger.error(f"Error saving tag value to JSON: {e}")
                
        return extracted_data

    def extract_data_with_nlp(self, text: str) -> Dict:
        """Извлекает данные из текста с помощью NLP"""
        try:
            if not nlp_processor:
                logger.warning("NLP processor not initialized")
                return {}
                
            doc = nlp_processor.extract_data(text)
            logger.info(f"NLP extracted data from text '{text[:100]}...': {doc}")
            return doc
        except Exception as e:
            logger.error(f"Error in NLP extraction: {e}")
            return {}

    def check_duplicates(self, data: Dict, chat_id: int) -> bool:
        """Проверяет наличие дубликатов в базе данных"""
        # Создаем базовый запрос
        query = session.query(DBMessage).filter_by(chat_id=chat_id)
        
        # Добавляем условия только для непустых полей
        if data.get("date"):
            query = query.filter_by(date=data["date"])
        if data.get("address"):
            query = query.filter_by(address=data["address"])
        if data.get("name"):
            query = query.filter_by(name=data["name"])
        if data.get("phone"):
            query = query.filter_by(phone=data["phone"])
            
        # Проверяем наличие дубликатов
        existing = query.first()
        return existing is not None

    def start_processing(self, num_threads: int = 3):
        for _ in range(num_threads):
            thread = threading.Thread(target=self.process_queue, daemon=True)
            thread.start()
            self.processing_threads.append(thread)

async def main():
    try:
        # Initialize the client
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        
        if not api_id or not api_hash:
            raise ValueError("API_ID and API_HASH environment variables must be set")
            
        # Путь к файлу сессии в папке configs
        session_file = CONFIGS_DIR / 'message_processor'
            
        client = TelegramClient(
            str(session_file),  # Преобразуем Path в строку
            int(api_id),
            api_hash
        )
        
        # Initialize message processor
        processor = MessageProcessor()
        processor.set_client(client)
        processor.start_processing()

        @client.on(events.NewMessage())
        async def handler(event):
            try:
                await processor.process_message(event)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        # Start the client
        await client.start()
        logger.info("User bot started!")
        
        # Keep the client running
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Cleanup
        if 'client' in locals():
            await client.disconnect()
        if 'processor' in locals():
            for thread in processor.processing_threads:
                thread.join(timeout=1.0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 