import spacy
import numpy as np
from typing import Dict, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

class NLPProcessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("ru_core_news_sm")
            self.vectorizer = TfidfVectorizer()
            self.field_patterns = {
                'date': [
                    'дата', 'число', 'день', 'месяц', 'год',
                    'срок', 'время', 'период'
                ],
                'address': [
                    'адрес', 'место', 'локация', 'город',
                    'улица', 'дом', 'квартира'
                ],
                'name': [
                    'имя', 'фамилия', 'отчество', 'фио',
                    'контактное лицо', 'представитель'
                ],
                'phone': [
                    'телефон', 'номер', 'контакт', 'мобильный',
                    'сотовый', 'звонить'
                ],
                'email': [
                    'почта', 'email', 'электронная почта',
                    'e-mail', 'контакт'
                ],
                'price': [
                    'цена', 'стоимость', 'сумма', 'оплата',
                    'рубль', 'доллар', 'евро'
                ]
            }
            self.field_embeddings = self._create_field_embeddings()
        except Exception as e:
            logger.error(f"Error initializing NLP processor: {e}")
            raise

    def _create_field_embeddings(self) -> Dict[str, np.ndarray]:
        """Создает векторные представления для каждого поля"""
        embeddings = {}
        for field, patterns in self.field_patterns.items():
            # Объединяем все паттерны в один текст
            text = ' '.join(patterns)
            doc = self.nlp(text)
            # Используем средний вектор всех токенов
            embeddings[field] = np.mean([token.vector for token in doc], axis=0)
        return embeddings

    def _get_text_embedding(self, text: str) -> np.ndarray:
        """Получает векторное представление текста"""
        doc = self.nlp(text)
        return np.mean([token.vector for token in doc], axis=0)

    def _calculate_similarity(self, text_embedding: np.ndarray, field: str) -> float:
        """Вычисляет косинусное сходство между текстом и полем"""
        field_embedding = self.field_embeddings[field]
        return cosine_similarity([text_embedding], [field_embedding])[0][0]

    def extract_data(self, text: str, confidence_threshold: float = 0.7) -> Dict[str, str]:
        """
        Извлекает данные из текста с использованием NLP
        :param text: Исходный текст
        :param confidence_threshold: Порог уверенности для определения поля
        :return: Словарь с извлеченными данными
        """
        try:
            doc = self.nlp(text)
            extracted_data = {}
            
            # Получаем векторное представление всего текста
            text_embedding = self._get_text_embedding(text)
            
            # Для каждого поля вычисляем сходство
            for field in self.field_patterns.keys():
                similarity = self._calculate_similarity(text_embedding, field)
                if similarity >= confidence_threshold:
                    # Ищем конкретные значения в тексте
                    value = self._find_field_value(doc, field)
                    if value:
                        extracted_data[field] = value
            
            return extracted_data
        except Exception as e:
            logger.error(f"Error extracting data with NLP: {e}")
            return {}

    def _find_field_value(self, doc, field: str) -> Optional[str]:
        """Находит конкретное значение для поля в тексте"""
        if field == 'date':
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    return ent.text
        elif field == 'address':
            for ent in doc.ents:
                if ent.label_ == "LOC":
                    return ent.text
        elif field == 'name':
            for ent in doc.ents:
                if ent.label_ == "PER":
                    return ent.text
        elif field == 'phone':
            # Поиск номеров телефонов с помощью регулярных выражений
            for token in doc:
                if token.like_num and len(token.text) >= 10:
                    return token.text
        elif field == 'email':
            for token in doc:
                if '@' in token.text:
                    return token.text
        elif field == 'price':
            for token in doc:
                if token.like_num and any(curr in token.text for curr in ['₽', '$', '€']):
                    return token.text
        return None

    def train_on_examples(self, examples: List[Dict[str, str]]):
        """
        Обучение на примерах для улучшения точности
        :param examples: Список примеров в формате {'text': 'исходный текст', 'field': 'значение'}
        """
        try:
            # Обновляем векторные представления полей на основе примеров
            for field in self.field_patterns.keys():
                field_examples = [ex['text'] for ex in examples if ex['field'] == field]
                if field_examples:
                    field_embeddings = [self._get_text_embedding(text) for text in field_examples]
                    self.field_embeddings[field] = np.mean(field_embeddings, axis=0)
        except Exception as e:
            logger.error(f"Error training on examples: {e}") 