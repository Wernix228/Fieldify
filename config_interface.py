from typing import Dict, List
from pydantic import BaseModel
from telethon import TelegramClient, events
from telethon.tl.types import Message

class TagConfig(BaseModel):
    tag: str
    field: str
    is_active: bool

class ChatSettings:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.tag_configs: Dict[int, List[TagConfig]] = {}
        self.default_tags = {
            "Дата:": "date",
            "Адрес:": "address",
            "Имя:": "name",
            "Телефон:": "phone"
        }

    async def handle_config_command(self, event: events.NewMessage.Event):
        message: Message = event.message
        chat_id = message.chat_id
        
        if not message.text.startswith('/config'):
            return

        # Show configuration menu
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

    async def handle_tag_management(self, event: events.CallbackQuery.Event):
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

    async def toggle_tag(self, event: events.CallbackQuery.Event, tag: str):
        chat_id = event.chat_id
        
        for tag_config in self.tag_configs[chat_id]:
            if tag_config.tag == tag:
                tag_config.is_active = not tag_config.is_active
                break
        
        await self.handle_tag_management(event)

    async def add_tag(self, event: events.CallbackQuery.Event):
        await event.edit(
            "Введите новую метку в формате:\n"
            "метка:поле\n"
            "Например: Дата:date"
        )
        # Set state to wait for new tag
        self.waiting_for_tag = True

    async def process_new_tag(self, event: events.NewMessage.Event):
        chat_id = event.chat_id
        text = event.message.text
        
        try:
            tag, field = text.split(":")
            new_config = TagConfig(tag=tag.strip(), field=field.strip(), is_active=True)
            
            if chat_id not in self.tag_configs:
                self.tag_configs[chat_id] = []
            
            self.tag_configs[chat_id].append(new_config)
            self.waiting_for_tag = False
            
            await event.reply(f"Метка {tag} успешно добавлена!")
            await self.handle_tag_management(event)
            
        except ValueError:
            await event.reply(
                "Неверный формат. Используйте формат:\n"
                "метка:поле\n"
                "Например: Дата:date"
            )

    def get_active_tags(self, chat_id: int) -> Dict[str, str]:
        if chat_id not in self.tag_configs:
            return self.default_tags
        
        return {
            config.tag: config.field
            for config in self.tag_configs[chat_id]
            if config.is_active
        } 