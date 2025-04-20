import numpy as np
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from mpl_toolkits.mplot3d import Axes3D
from nlp_processor import NLPProcessor

def visualize_embeddings_3d(texts, title="3D представление векторов текста и полей"):
    """
    Создает 3D визуализацию векторных представлений текстов и полей с помощью t-SNE
    
    Args:
        texts (list): Список текстов для визуализации
        title (str): Заголовок графика
    """
    # Инициализируем NLP процессор
    nlp = NLPProcessor()
    
    # Получаем эмбеддинги для текстов
    text_embeddings = []
    for text in texts:
        embedding = nlp._get_text_embedding(text)
        text_embeddings.append(embedding)
    text_embeddings = np.array(text_embeddings)
    
    # Получаем эмбеддинги полей
    field_embeddings = []
    field_names = []
    for field, embedding in nlp.field_embeddings.items():
        field_embeddings.append(embedding)
        field_names.append(field)
    field_embeddings = np.array(field_embeddings)
    
    # Объединяем все векторы
    all_embeddings = np.vstack([text_embeddings, field_embeddings])
    
    # Уменьшаем размерность до 3D с помощью t-SNE
    tsne = TSNE(n_components=3, random_state=42, perplexity=min(30, len(all_embeddings)-1))
    embeddings_3d = tsne.fit_transform(all_embeddings)
    
    # Разделяем обратно на тексты и поля
    texts_3d = embeddings_3d[:len(text_embeddings)]
    fields_3d = embeddings_3d[len(text_embeddings):]
    
    # Создаем 3D график
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Визуализируем тексты
    ax.scatter(texts_3d[:, 0], texts_3d[:, 1], texts_3d[:, 2],
              c='blue', marker='o', label='Тексты')
    
    # Визуализируем поля
    ax.scatter(fields_3d[:, 0], fields_3d[:, 1], fields_3d[:, 2],
              c='red', marker='^', label='Поля')
    
    # Добавляем подписи для полей
    for i, field in enumerate(field_names):
        ax.text(fields_3d[i, 0], fields_3d[i, 1], fields_3d[i, 2],
                field, color='darkred')
    
    # Настраиваем внешний вид
    ax.set_title(title)
    ax.set_xlabel('Компонента 1')
    ax.set_ylabel('Компонента 2')
    ax.set_zlabel('Компонента 3')
    ax.legend()
    
    # Добавляем возможность вращения графика
    plt.show()

def demo_visualization():
    """
    Демонстрация работы визуализации на тестовых данных
    """
    # Примеры текстов для визуализации
    test_texts = [
        "Позвоните мне по телефону 8-999-123-45-67",
        "Встреча состоится 25 мая 2024 года",
        "Адрес доставки: ул. Пушкина, д. 10",
        "Контактное лицо: Иван Петров",
        "Стоимость заказа 1500 рублей",
        "Email для связи: example@mail.com",
        "Срочная доставка по адресу Ленина 15",
        "Менеджер Анна, тел. +7-900-555-44-33"
    ]
    
    visualize_embeddings_3d(test_texts)

if __name__ == "__main__":
    demo_visualization() 