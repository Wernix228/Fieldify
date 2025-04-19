from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

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

# Создаем движок базы данных
engine = create_engine('sqlite:///bot_database.db')

# Создаем все таблицы
Base.metadata.create_all(engine)

# Создаем сессию
Session = sessionmaker(bind=engine)
session = Session() 