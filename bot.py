import os
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message
import spacy
from pymongo import MongoClient
from pydantic import BaseModel
import threading
import queue

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load NLP model
nlp = spacy.load("ru_core_news_sm")

# MongoDB connection
client = MongoClient(os.getenv("MONGODB_URI"))
db = client.message_processor

class ChatConfig(BaseModel):
    chat_id: int
    tags: Dict[str, str]  # tag -> field mapping
    use_nlp: bool
    duplicate_threshold: float
    active: bool

class MessageProcessor:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.processing_threads = []
        self.chat_configs = {}
        self.client = None

    def set_client(self, client: TelegramClient):
        self.client = client

    async def process_message(self, event: events.NewMessage.Event):
        message: Message = event.message
        chat_id = message.chat_id
        message_text = message.text
        
        if not message_text:
            return

        # Get chat configuration
        config = self.get_chat_config(chat_id)
        if not config or not config.active:
            return

        # Add message to processing queue
        self.message_queue.put((chat_id, message_text, datetime.now()))

    def get_chat_config(self, chat_id: int) -> Optional[ChatConfig]:
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
        doc = nlp(text)
        extracted_data = {}
        
        # Extract dates
        for ent in doc.ents:
            if ent.label_ == "DATE":
                extracted_data["date"] = ent.text
            elif ent.label_ == "LOC":
                extracted_data["address"] = ent.text
        
        return extracted_data

    def check_duplicates(self, data: Dict, chat_id: int) -> bool:
        # Check for duplicates based on key fields
        existing = db.messages.find_one({
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

                # Extract data using tags
                extracted_data = self.extract_data_with_tags(message_text, config.tags)
                
                # Use NLP if enabled
                if config.use_nlp:
                    nlp_data = self.extract_data_with_nlp(message_text)
                    extracted_data.update(nlp_data)

                # Check for duplicates
                if self.check_duplicates(extracted_data, chat_id):
                    logger.info(f"Duplicate message detected in chat {chat_id}")
                    continue

                # Save to database
                db.messages.insert_one({
                    "chat_id": chat_id,
                    "timestamp": timestamp,
                    **extracted_data
                })

            except Exception as e:
                logger.error(f"Error processing message: {e}")

    def start_processing(self, num_threads: int = 3):
        for _ in range(num_threads):
            thread = threading.Thread(target=self.process_queue, daemon=True)
            thread.start()
            self.processing_threads.append(thread)

async def main():
    # Initialize the client
    client = TelegramClient(
        'message_processor',
        int(os.getenv("API_ID")),
        os.getenv("API_HASH")
    )
    
    # Initialize message processor
    processor = MessageProcessor()
    processor.set_client(client)
    processor.start_processing()

    @client.on(events.NewMessage())
    async def handler(event):
        await processor.process_message(event)

    # Start the client
    await client.start()
    logger.info("User bot started!")
    
    # Keep the client running
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main()) 