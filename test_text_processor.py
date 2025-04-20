import asyncio
from text_processor import TextProcessor
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Initialize the text processor with your API key
    api_key = os.getenv("NOVITA_API_KEY")
    if not api_key:
        print("Please set NOVITA_API_KEY in your .env file")
        return

    processor = TextProcessor(api_key)

    # Test cases
    test_cases = [
        "16 мая 2008 года по адрсу ул. Ленина, д. 10, кв. 5. Телефон: +7 (999) 123-45-67",
        "Запись на 25 янвая 2023, адрс: проспкт Мира, дом 15, квтира 3. Конткт: 899912уу3456цфыс7",
        "Встреча назначена на 2023-12-25 по адресу: улица Пушкина, дом 20",
        "Номер телефона: 8-999-123-45-67, дата: 16/05/2008"
    ]

    print("Testing text processing...")
    for text in test_cases:
        print(f"\nProcessing text: {text}")
        
        # Test phone number extraction
        print("\nExtracted phone numbers:")
        phones = processor.extract_phone_numbers(text)
        print(phones)

        # Test address extraction
        print("\nExtracted addresses:")
        addresses = processor.extract_addresses(text)
        print(addresses)

        # Test AI processing
        print("\nAI processing results:")
        ai_data = await processor.process_text_with_ai(text)
        print(ai_data)

if __name__ == "__main__":
    asyncio.run(main()) 