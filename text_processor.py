import re
from typing import Dict, Optional
from openai import OpenAI
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.novita.ai/v3/openai"
        )
        self.model = "deepseek/deepseek-v3-turbo"

    async def process_text_with_ai(self, text: str) -> Dict:
        """Process text using DeepSeek to extract structured information"""
        try:
            system_prompt = """Extract the following information from the text:
            - Date (convert to format YYYY-MM-DD)
            - Phone numbers
            - Addresses
            - Names
            Return the information in JSON format with these keys: date, phone, address, name.
            If any information is not found, use null for that field.Answer without registration"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                stream=False,
                max_tokens=512
            )

            result = response.choices[0].message.content
            # Clean the response from ```json prefix and ``` suffix
            result = result.replace('```json', '').replace('```', '').strip()
            # Parse the JSON response
            import json
            try:
                data = json.loads(result)
                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response: {result}")
                return {}

        except Exception as e:
            logger.error(f"Error processing text with AI: {e}")
            return {}

    def extract_phone_numbers(self, text: str) -> list:
        """Extract phone numbers from text using regex"""
        phone_pattern = r'\+?[\d\s\-\(\)]{10,}'
        phones = re.findall(phone_pattern, text)
        return [re.sub(r'\D', '', phone) for phone in phones]

    def extract_addresses(self, text: str) -> list:
        """Extract addresses from text using regex"""
        # This is a simple pattern and might need adjustment based on your needs
        address_pattern = r'[А-Яа-я\s\d\.,\-]+(?:ул\.|улица|пр\.|проспект|д\.|дом|кв\.|квартира)[А-Яа-я\s\d\.,\-]+'
        return re.findall(address_pattern, text)

    def normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to YYYY-MM-DD format"""
        try:
            # Try different date formats
            formats = [
                '%d %B %Y',  # 16 мая 2008
                '%d.%m.%Y',  # 16.05.2008
                '%Y-%m-%d',  # 2008-05-16
                '%d/%m/%Y'   # 16/05/2008
            ]
            
            for fmt in formats:
                try:
                    date = datetime.strptime(date_str, fmt)
                    return date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return None
        except Exception as e:
            logger.error(f"Error normalizing date {date_str}: {e}")
            return None 