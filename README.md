# Fieldify - Telegram Message Processing Bot
# Fieldify - Telegram бот для обработки сообщений

[English](#english) | [Русский](#russian)

<a name="english"></a>
## English

Fieldify is a powerful Telegram bot that automatically extracts structured data from messages in your chats. It's perfect for processing applications, forms, and any messages with a specific structure.

### 🚀 Key Features

- ✨ Automatic data extraction from messages using tags
- 🤖 Smart data recognition using NLP (names, dates, addresses, phone numbers)
- 🔄 Duplicate message protection
- ⚙️ Simple configuration through Telegram commands
- 💾 Reliable data storage in SQLite
- 📊 Data export to CSV
- 🔍 Advanced text processing with spaCy
- 🌐 Multi-language support (English/Russian)

### 📋 Requirements

- Python 3.10 or higher
- Windows/Linux/MacOS
- Telegram API access (API ID and API Hash)
- OpenAI API key (for advanced NLP features)

### 🔧 Installation

#### Automatic Installation (Recommended)

1. **Ensure Python 3.10+ is installed**
   - Download Python from [official website](https://www.python.org/downloads/)
   - Check "Add Python to PATH" during installation

2. **Run the installer**
   - Double-click `setup.bat`
   - Or open command prompt in project directory and run:
   ```cmd
   setup.bat
   ```

3. **Follow the installer instructions**
   - Wait for all components to install
   - Enter Telegram API credentials when prompted

#### Manual Installation

1. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file with:
   ```
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   OPENAI_API_KEY=your_openai_key
   ```

### 🎯 Usage

1. **Start the bot:**
   ```bash
   # Windows
   start.bat

   # Linux/macOS
   source venv/bin/activate
   python bot.py
   ```

2. **First-time setup:**
   - Enter your phone number
   - Enter Telegram verification code
   - Enter 2FA password if enabled

3. **Available Commands:**
   - `/config` - show all available commands
   - `/tags` - manage data extraction tags
   - `/add_tag tag:field` - add new tag
   - `/toggle_tag tag` - enable/disable tag
   - `/nlp on/off` - enable/disable smart recognition
   - `/threshold 0.7` - set duplicate detection threshold
   - `/status` - show current settings
   - `/data [limit]` - show recent extracted data
   - `/export` - export all data to CSV

### 📊 Visualization

Run the visualization tool to analyze extracted data:
```bash
# Windows
visual.bat

# Linux/macOS
python visualization.py
```

### 🐳 Docker Support

Build and run with Docker:
```bash
docker build -t fieldify .
docker run -d --name fieldify fieldify
```

---

<a name="russian"></a>
## Русский

Fieldify - это мощный Telegram бот, который автоматически извлекает структурированные данные из сообщений в ваших чатах. Идеально подходит для обработки заявок, анкет и любых сообщений с определенной структурой.

### 🚀 Основные возможности

- ✨ Автоматическое извлечение данных из сообщений по меткам
- 🤖 Умное распознавание данных с помощью NLP (имена, даты, адреса, телефоны)
- 🔄 Защита от дубликатов сообщений
- ⚙️ Простая настройка через команды в Telegram
- 💾 Надежное хранение данных в базе SQLite
- 📊 Экспорт данных в CSV
- 🔍 Продвинутая обработка текста с помощью spaCy
- 🌐 Поддержка нескольких языков (Английский/Русский)

### 📋 Требования

- Python 3.10 или выше
- Windows/Linux/MacOS
- Доступ к Telegram API (API ID и API Hash)
- Ключ OpenAI API (для расширенных функций NLP)

### 🔧 Установка

#### Автоматическая установка (рекомендуется)

1. **Убедитесь, что Python 3.10+ установлен**
   - Скачайте Python с [официального сайта](https://www.python.org/downloads/)
   - При установке отметьте "Add Python to PATH"

2. **Запустите установщик**
   - Дважды кликните на `setup.bat`
   - Или откройте командную строку в папке проекта и выполните:
   ```cmd
   setup.bat
   ```

3. **Следуйте инструкциям установщика**
   - Дождитесь завершения установки всех компонентов
   - Введите данные Telegram API при запросе

#### Ручная установка

1. **Создайте и активируйте виртуальное окружение**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

2. **Установите зависимости**
   ```bash
   pip install -r requirements.txt
   ```

3. **Настройте переменные окружения**
   Создайте файл `.env` со следующим содержимым:
   ```
   TELEGRAM_API_ID=ваш_api_id
   TELEGRAM_API_HASH=ваш_api_hash
   OPENAI_API_KEY=ваш_openai_key
   ```

### 🎯 Использование

1. **Запустите бота:**
   ```bash
   # Windows
   start.bat

   # Linux/macOS
   source venv/bin/activate
   python bot.py
   ```

2. **При первом запуске:**
   - Введите свой номер телефона
   - Введите код подтверждения из Telegram
   - Введите пароль 2FA, если включен

3. **Доступные команды:**
   - `/config` - показать все доступные команды
   - `/tags` - управление метками для извлечения данных
   - `/add_tag метка:поле` - добавить новую метку
   - `/toggle_tag метка` - включить/выключить метку
   - `/nlp on/off` - включить/выключить умное распознавание
   - `/threshold 0.7` - установить порог определения дубликатов
   - `/status` - показать текущие настройки
   - `/data [limit]` - показать последние извлеченные данные
   - `/export` - выгрузить все данные в CSV файл

### 📊 Визуализация

Запустите инструмент визуализации для анализа извлеченных данных:
```bash
# Windows
visual.bat

# Linux/macOS
python visualization.py
```

### 🐳 Поддержка Docker

Сборка и запуск с помощью Docker:
```bash
docker build -t fieldify .
docker run -d --name fieldify fieldify
```

## 📝 Примеры использования

### Стандартные метки
Бот по умолчанию распознает следующие метки в сообщениях:
```
Дата: 15.04.2024
Адрес: ул. Пушкина, д. 10
Имя: Иван Петров
Телефон: +7 (999) 123-45-67
```

### Пользовательские метки
Вы можете добавить свои метки через команду `/add_tag`:
```
Должность: менеджер
Зарплата: 80000
Опыт работы: 3 года
```

## 🔍 Умное распознавание (NLP)

При включенном NLP (`/nlp on`) бот автоматически находит в тексте:
- 📅 Даты в любом формате
- 📍 Адреса и местоположения
- 👤 Имена и ФИО
- 📞 Номера телефонов
- 💰 Цены и суммы
- ✉️ Email адреса

## ⚠️ Важные замечания

- Храните файл `.env` в безопасном месте
- Не передавайте API ID и API Hash посторонним
- Регулярно делайте резервные копии базы данных
- При возникновении ошибок проверьте логи
