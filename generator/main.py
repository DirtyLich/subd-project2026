import argparse
import random
import psycopg2
from psycopg2.extras import execute_values
from faker import Faker
import time

# 1. ФИКСИРУЕМ SEED ДЛЯ ВОСПРОИЗВОДИМОСТИ
SEED = 42
random.seed(SEED)
fake = Faker('ru_RU')
Faker.seed(SEED)

def generate_data(mode):
    # 2. НАСТРОЙКА РЕЖИМОВ (Разработка vs Нагрузка)
    if mode == 'dev':
        users_count, sources_count, news_count = 1000, 50, 100_000
    else:  # load
        users_count, sources_count, news_count = 10_000, 500, 3_000_000
    
    batch_size = 10_000

    print(f"Подключение к БД... Режим: {mode}")
    # Параметры из вашего docker-compose.yml
    conn = psycopg2.connect("dbname=mydb user=flyway_user password=flyway_password host=localhost port=5432")
    cur = conn.cursor()

    # Очищаем базу перед генерацией, чтобы данные не наслаивались, сбрасывая ID
    print("Очистка старых данных...")
    cur.execute("TRUNCATE users, sources, categories, tags, news RESTART IDENTITY CASCADE;")
    conn.commit()

    start_time = time.time()

    # 3. ГЕНЕРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ (Соблюдаем роли и статусы)
    print(f"Генерация {users_count} пользователей...")
    users_data = []
    for _ in range(users_count):
        # Неравномерное распределение ролей и статусов, соответствующих вашей схеме
        role = random.choices(['user', 'editor', 'admin'], weights=[90, 8, 2])[0]
        status = random.choices(['active', 'blocked', 'deleted'], weights=[85, 10, 5])[0]
        users_data.append((fake.name(), fake.unique.email(), 'hash123', role, status))
    
    execute_values(cur, "INSERT INTO users (name, email, password_hash, role, status) VALUES %s", users_data)

    # 4. ГЕНЕРАЦИЯ ИСТОЧНИКОВ (Соблюдаем типы и частоту)
    print(f"Генерация {sources_count} источников...")
    sources_data = []
    for _ in range(sources_count):
        s_type = random.choices(['rss', 'api', 'web_scraping'], weights=[60, 30, 10])[0]
        s_active = random.choices([True, False], weights=[95, 5])[0]
        freq = random.randint(5, 120) # CHECK > 0
        sources_data.append((fake.unique.company(), fake.unique.url(), s_type, s_active, freq))
    
    execute_values(cur, "INSERT INTO sources (name, url, type, is_active, update_frequency_minutes) VALUES %s", sources_data)

    # Генерируем категории и теги для связей
    categories_data = [(f"Категория {i}", fake.sentence()) for i in range(1, 21)]
    execute_values(cur, "INSERT INTO categories (name, description) VALUES %s", categories_data)
    
    tags_data = [(f"Тег {i}",) for i in range(1, 101)]
    execute_values(cur, "INSERT INTO tags (name) VALUES %s", tags_data)

    # 5. ГЕНЕРАЦИЯ НОВОСТЕЙ (Самая крупная таблица)
    print(f"Генерация {news_count} новостей батчами по {batch_size}...")
    
    # Создаем неравномерное распределение для источников (Закон Ципфа/Парето)
    # Источник №1 будет выбираться намного чаще, чем источник №500
    source_ids = list(range(1, sources_count + 1))
    source_weights = [1.0 / i for i in range(1, sources_count + 1)]

    for offset in range(0, news_count, batch_size):
        news_batch = []
        for _ in range(batch_size):
            src_id = random.choices(source_ids, weights=source_weights)[0]
            # Статусы из вашей концепции: active, hidden, duplicate, archived
            n_status = random.choices(['active', 'hidden', 'duplicate', 'archived'], weights=[70, 5, 15, 10])[0]
            
            # Генерация дат от начала 2025 года до текущего момента
            pub_date = fake.date_time_between(start_date='-2y', end_date='now')
            
            news_batch.append((
                src_id, 
                fake.sentence(nb_words=6), 
                fake.text(max_nb_chars=100), 
                fake.url(), 
                n_status, 
                pub_date
            ))
        
        execute_values(cur, """
            INSERT INTO news (source_id, title, summary, external_url, status, published_at) 
            VALUES %s
        """, news_batch)
        print(f"  Вставлено {offset + batch_size} / {news_count} ...")

    # 6. ГЕНЕРАЦИЯ СВЯЗЕЙ (ПОДПИСКИ, ИЗБРАННОЕ, ТЕГИ, КАТЕГОРИИ)
    print("Генерация подписок и избранного...")
    
    # Подписки (subscriptions)
    subs_data = []
    for u_id in range(1, users_count + 1):
        if random.random() < 0.4:  # 40% пользователей оформляют подписку
            if random.random() < 0.5:
                subs_data.append((u_id, random.randint(1, 20), None)) # на категорию
            else:
                subs_data.append((u_id, None, random.randint(1, sources_count))) # на источник
    execute_values(cur, "INSERT INTO subscriptions (user_id, category_id, source_id) VALUES %s ON CONFLICT DO NOTHING", list(set(subs_data)))

    # Избранное (favorites)
    favs_data = []
    for u_id in range(1, users_count + 1):
        for _ in range(random.randint(0, 8)): # от 0 до 8 новостей в закладках
            favs_data.append((u_id, random.randint(1, news_count)))
    execute_values(cur, "INSERT INTO favorites (user_id, news_id) VALUES %s ON CONFLICT DO NOTHING", list(set(favs_data)))

    print("Привязка новостей к тегам и категориям (батчами)...")
    for offset in range(0, news_count, batch_size):
        news_cats_data = []
        news_tags_data = []
        for n_id in range(offset + 1, offset + batch_size + 1):
            # 50% новостей получают категорию
            if random.random() < 0.5: 
                news_cats_data.append((n_id, random.randint(1, 20)))
            # 30% новостей получают тег
            if random.random() < 0.3: 
                news_tags_data.append((n_id, random.randint(1, 100)))

        execute_values(cur, "INSERT INTO news_categories (news_id, category_id) VALUES %s ON CONFLICT DO NOTHING", list(set(news_cats_data)))
        execute_values(cur, "INSERT INTO news_tags (news_id, tag_id) VALUES %s ON CONFLICT DO NOTHING", list(set(news_tags_data)))
    
    conn.commit()
    cur.close()
    conn.close()
    
    elapsed = round(time.time() - start_time, 2)
    print(f"✅ Генерация успешно завершена за {elapsed} секунд!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Генератор данных для БД новостного агрегатора')
    parser.add_argument('--mode', choices=['dev', 'load'], required=True, help='Режим генерации: dev (100k) или load (3M)')
    args = parser.parse_args()
    
    generate_data(args.mode)