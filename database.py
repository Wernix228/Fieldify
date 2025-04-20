from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from pathlib import Path

# Определяем базовые пути
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'

# Создаем папку data, если её нет
os.makedirs(DATA_DIR, exist_ok=True)

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    message_text = Column(String)
    date = Column(String)
    address = Column(String)
    name = Column(String)
    phone = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ChatConfig(Base):
    __tablename__ = 'chat_configs'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True)
    use_nlp = Column(Boolean, default=True)
    duplicate_threshold = Column(Float, default=0.7)
    active = Column(Boolean, default=True)

# Изменяем путь к базе данных
db_path = DATA_DIR / 'bot_database.db'
engine = create_engine(f'sqlite:///{db_path}')

# Создаем все таблицы
Base.metadata.create_all(engine)

# Создаем сессию
Session = sessionmaker(bind=engine)
session = Session() 