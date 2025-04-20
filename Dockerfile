# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download ru_core_news_sm

# Copy the rest of the application
COPY . .

# Create necessary directories if they don't exist
RUN mkdir -p data configs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "bot.py"] 