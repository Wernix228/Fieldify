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
from pymongo import MongoClient
from pymongo.errors import ConnectionError as MongoConnectionError
from pydantic import BaseModel
import threading
import queue
from nlp_processor import NLPProcessor

# Load environment variables
load_dotenv()

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

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    # Test the connection
    client.server_info()
    db = client.telegram_bot
    messages_collection = db.messages
    chat_configs_collection = db.chat_configs
    logger.info("Successfully connected to MongoDB")
except MongoConnectionError as e:
    logger.error(f"MongoDB connection error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error connecting to MongoDB: {e}")
    raise

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
            configs = chat_configs_collection.find({})
            for config in configs:
                chat_id = config['chat_id']
                self.tag_configs[chat_id] = [
                    TagConfig(**tag_config) for tag_config in config.get('tag_configs', [])
                ]
        except Exception as e:
            logger.error(f"Error loading chat configs: {e}")

    def save_chat_config(self, chat_id: int):
        """Сохраняет конфигурацию чата в базу данных"""
        try:
            chat_configs_collection.update_one(
                {'chat_id': chat_id},
                {'$set': {
                    'chat_id': chat_id,
                    'tag_configs': [tag.dict() for tag in self.tag_configs.get(chat_id, [])]
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving chat config: {e}")

    async def handle_config_command(self, event: events.NewMessage.Event):
        """Обрабатывает команду /config"""
        try:
            message: Message = event.message
            chat_id = message.chat_id
            
            if not message.text.startswith('/config'):
                return

            # Показываем меню конфигурации
            keyboard = [
                [
                    {"text": "Управление метками", "callback_data": "manage_tags"},
                    {"text": "Настройки NLP", "callback_data": "nlp_settings"}
                ],
                [
                    {"text": "Порог дубликатов", "callback_data": "duplicate_threshold"},
                    {"text": "Статус бота", "callback_data": "bot_status"}
                ]
            ]
            
            await self.client.send_message(
                chat_id,
                "Выберите настройку для изменения:",
                buttons=keyboard
            )
        except Exception as e:
            logger.error(f"Error in handle_config_command: {e}")
            await event.reply("Произошла ошибка при обработке команды. Попробуйте позже.")

    async def handle_tag_management(self, event: events.CallbackQuery.Event):
        """Обрабатывает управление метками"""
        try:
            chat_id = event.chat_id
            
            if chat_id not in self.tag_configs:
                self.tag_configs[chat_id] = [
                    TagConfig(tag=tag, field=field, is_active=True)
                    for tag, field in self.default_tags.items()
                ]

            buttons = []
            for tag_config in self.tag_configs[chat_id]:
                status = "✅" if tag_config.is_active else "❌"
                buttons.append([
                    {"text": f"{status} {tag_config.tag} -> {tag_config.field}", 
                     "callback_data": f"toggle_tag_{tag_config.tag}"}
                ])
            
            buttons.append([
                {"text": "Добавить метку", "callback_data": "add_tag"},
                {"text": "Назад", "callback_data": "back_to_main"}
            ])
            
            await event.edit(
                "Управление метками:\n✅ - активна\n❌ - неактивна",
                buttons=buttons
            )
        except MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error(f"Error in handle_tag_management: {e}")
            await event.answer("Произошла ошибка. Попробуйте позже.")

    async def toggle_tag(self, event: events.CallbackQuery.Event, tag: str):
        """Переключает состояние метки"""
        try:
            chat_id = event.chat_id
            
            if chat_id not in self.tag_configs:
                await event.answer("Конфигурация чата не найдена")
                return
                
            tag_found = False
            for tag_config in self.tag_configs[chat_id]:
                if tag_config.tag == tag:
                    tag_config.is_active = not tag_config.is_active
                    tag_found = True
                    break
            
            if not tag_found:
                await event.answer("Метка не найдена")
                return
                
            self.save_chat_config(chat_id)
            await self.handle_tag_management(event)
        except Exception as e:
            logger.error(f"Error in toggle_tag: {e}")
            await event.answer("Произошла ошибка при переключении метки")

    async def add_tag(self, event: events.CallbackQuery.Event):
        """Начинает процесс добавления новой метки"""
        try:
            chat_id = event.chat_id
            self.waiting_for_tag[chat_id] = True
            
            await event.edit(
                "Введите новую метку в формате:\n"
                "метка:поле\n"
                "Например: Дата:date"
            )
        except Exception as e:
            logger.error(f"Error in add_tag: {e}")
            await event.answer("Произошла ошибка при добавлении метки")

    async def process_new_tag(self, event: events.NewMessage.Event):
        """Обрабатывает новую метку"""
        try:
            chat_id = event.chat_id
            
            if not self.waiting_for_tag.get(chat_id, False):
                return
                
            text = event.message.text
            
            try:
                tag, field = text.split(":")
                new_config = TagConfig(tag=tag.strip(), field=field.strip(), is_active=True)
                
                if chat_id not in self.tag_configs:
                    self.tag_configs[chat_id] = []
                
                # Проверка на дубликаты
                if any(tc.tag == new_config.tag for tc in self.tag_configs[chat_id]):
                    await event.reply(f"Метка '{tag}' уже существует")
                    return
                
                self.tag_configs[chat_id].append(new_config)
                self.waiting_for_tag[chat_id] = False
                self.save_chat_config(chat_id)
                
                await event.reply(f"Метка {tag} успешно добавлена!")
                await self.handle_tag_management(event)
                
            except ValueError:
                await event.reply(
                    "Неверный формат. Используйте формат:\n"
                    "метка:поле\n"
                    "Например: Дата:date"
                )
        except Exception as e:
            logger.error(f"Error in process_new_tag: {e}")
            await event.reply("Произошла ошибка при обработке новой метки")

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
        self.chat_configs = {}
        self.client = None
        self.chat_manager = None

    def set_client(self, client: TelegramClient):
        self.client = client
        self.chat_manager = ChatManager(client)

    async def process_message(self, event: events.NewMessage.Event):
        message: Message = event.message
        chat_id = message.chat_id
        message_text = message.text
        
        if not message_text:
            return

        # Обработка команды /config
        if message_text.startswith('/config'):
            await self.chat_manager.handle_config_command(event)
            return

        # Обработка новой метки
        if self.chat_manager.waiting_for_tag.get(chat_id, False):
            await self.chat_manager.process_new_tag(event)
            return

        # Получение конфигурации чата
        config = self.get_chat_config(chat_id)
        if not config or not config.active:
            return

        # Добавление сообщения в очередь обработки
        self.message_queue.put((chat_id, message_text, datetime.now()))

    def get_chat_config(self, chat_id: int) -> Optional[ChatConfig]:
        """Получает конфигурацию чата"""
        if chat_id not in self.chat_configs:
            # Создаем новую конфигурацию с активными метками
            active_tags = self.chat_manager.get_active_tags(chat_id)
            self.chat_configs[chat_id] = ChatConfig(
                chat_id=chat_id,
                tags=active_tags,
                use_nlp=True,
                duplicate_threshold=0.7,
                active=True
            )
        return self.chat_configs.get(chat_id)

    def update_chat_config(self, chat_id: int, config: ChatConfig):
        self.chat_configs[chat_id] = config

    def extract_data_with_tags(self, text: str, tags: Dict[str, str]) -> Dict:
        extracted_data = {}
        for tag, field in tags.items():
            if tag in text:
                # Extract data after the tag
                start_idx = text.find(tag) + len(tag)
                end_idx = text.find('\n', start_idx)
                if end_idx == -1:
                    end_idx = len(text)
                value = text[start_idx:end_idx].strip()
                extracted_data[field] = value
        return extracted_data

    def extract_data_with_nlp(self, text: str) -> Dict:
        doc = nlp_processor.extract_data(text)
        return doc

    def check_duplicates(self, data: Dict, chat_id: int) -> bool:
        # Check for duplicates based on key fields
        existing = messages_collection.find_one({
            "chat_id": chat_id,
            "date": data.get("date"),
            "address": data.get("address")
        })
        return existing is not None

    def process_queue(self):
        while True:
            try:
                chat_id, message_text, timestamp = self.message_queue.get()
                config = self.get_chat_config(chat_id)
                
                if not config:
                    continue

                extracted_data = {}
                
                # Сначала используем NLP для извлечения данных
                if config.use_nlp:
                    nlp_data = self.extract_data_with_nlp(message_text)
                    extracted_data.update(nlp_data)
                
                # Затем используем метки только для полей, которые не были определены NLP
                if config.tags:
                    tag_data = self.extract_data_with_tags(message_text, config.tags)
                    for field, value in tag_data.items():
                        if field not in extracted_data:
                            extracted_data[field] = value

                # Check for duplicates
                if self.check_duplicates(extracted_data, chat_id):
                    logger.info(f"Duplicate message detected in chat {chat_id}")
                    continue

                # Save to database
                message_data = {
                    "chat_id": chat_id,
                    "timestamp": timestamp,
                    **extracted_data
                }
                messages_collection.insert_one(message_data)
                logger.info(f"Processed message from chat {chat_id}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")

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
            
        client = TelegramClient(
            'message_processor',
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

        @client.on(events.CallbackQuery())
        async def callback_handler(event):
            try:
                data = event.data.decode('utf-8')
                if data == "manage_tags":
                    await processor.chat_manager.handle_tag_management(event)
                elif data.startswith("toggle_tag_"):
                    tag = data.replace("toggle_tag_", "")
                    await processor.chat_manager.toggle_tag(event, tag)
                elif data == "add_tag":
                    await processor.chat_manager.add_tag(event)
                elif data == "back_to_main":
                    await processor.chat_manager.handle_config_command(event)
            except Exception as e:
                logger.error(f"Error handling callback: {e}")
                await event.answer("Произошла ошибка при обработке команды")

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