#!/bin/bash

# Установка Python 3.11 venv
python3.11 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Установка необходимых пакетов
pip install spacy==3.7.2
python -m spacy download ru_core_news_sm

# Установка зависимостей из requirements.txt
pip install -r requirements.txt

# Создание .env файла с фиксированными значениями
cat <<EOF > .env
API_ID=ваш_api_id
API_HASH=ваш_api_hash
EOF

# Пауза — ожидание нажатия клавиши (необязательно)
read -n 1 -s -r -p "Нажмите любую клавишу для выхода..."
echo
