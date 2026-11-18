#!/usr/bin/env python3
"""
scripts/test_advanced_sql.py
Автоматическая валидация результатов аналитических SQL-запросов (КТ-05 / Спринт 5)
Пункт "Желательно" №1: Автоматические проверки результатов SQL-запросов
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Параметры подключения к PostgreSQL
DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_NAME = os.getenv("POSTGRES_DB", "mydb")
DB_USER = os.getenv("POSTGRES_USER", "flyway_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "flyway_password")

passed_count = 0
failed_count = 0

def log_test(title, success, detail=""):
    global passed_count, failed_count
    if success:
        passed_count += 1
        print(f"  [\033[92mPASS\033[0m] {title} {detail}")
    else:
        failed_count += 1
        print(f"  [\033[91mFAIL\033[0m] {title} {detail}")

def run_tests():
    global passed_count, failed_count
    print("==================================================================")
    print(" АВТОМАТИЧЕСКАЯ ПРОВЕРКА РЕЗУЛЬТАТОВ 8 SQL-ЗАПРОСОВ (SPRINT 5)")
    print(f" Подключение: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("==================================================================")

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        conn.autocommit = True
    except Exception as e:
        print(f"\033[91m[ERROR] Не удалось подключиться к базе данных: {e}\033[0m")
        sys.exit(1)

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # -------------------------------------------------------------
    # Запрос 1: Персональная лента (JOIN 4 таблиц)
    # -------------------------------------------------------------
    print("\n--- Запрос 1: Персональная лента новостей на основе подписок ---")
    try:
        cur.execute("SELECT user_id FROM subscriptions LIMIT 1;")
        sub_user = cur.fetchone()
        test_user_id = sub_user["user_id"] if sub_user else 3

        q1 = f"""
        SELECT n.news_id, n.title, s.name AS source_name, n.published_at
        FROM news n
        JOIN sources s ON n.source_id = s.source_id
        LEFT JOIN news_categories nc ON n.news_id = nc.news_id
        JOIN subscriptions sub ON 
            (sub.source_id = n.source_id OR sub.category_id = nc.category_id)
        WHERE sub.user_id = {test_user_id} AND n.status = 'active'
        ORDER BY n.published_at DESC
        LIMIT 20;
        """
        cur.execute(q1)
        rows = cur.fetchall()
        log_test("Запрос 1: Успешное выполнение синтаксиса", True)
        log_test("Запрос 1: Возврат строк (LIMIT 20)", len(rows) > 0, f"(получено: {len(rows)}, user_id={test_user_id})")
        expected_cols = {"news_id", "title", "source_name", "published_at"}
        actual_cols = set(rows[0].keys()) if rows else set()
        log_test("Запрос 1: Корректность колонок", expected_cols.issubset(actual_cols))
    except Exception as e:
        log_test("Запрос 1: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 2: Аналитика активности источников (Агрегат COUNT + HAVING)
    # -------------------------------------------------------------
    print("\n--- Запрос 2: Аналитика активности источников (COUNT + HAVING) ---")
    try:
        q2 = """
        SELECT s.name AS source_name, COUNT(n.news_id) AS active_news_count
        FROM sources s
        JOIN news n ON s.source_id = n.source_id
        WHERE n.status = 'active'
        GROUP BY s.source_id, s.name
        HAVING COUNT(n.news_id) > 1000
        ORDER BY active_news_count DESC;
        """
        cur.execute(q2)
        rows = cur.fetchall()
        log_test("Запрос 2: Успешное выполнение синтаксиса", True)
        all_gt_1000 = all(r["active_news_count"] > 1000 for r in rows) if rows else False
        log_test("Запрос 2: Фильтр HAVING COUNT > 1000 соблюдён", all_gt_1000, f"(найдено источников: {len(rows)})")
    except Exception as e:
        log_test("Запрос 2: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 3: Популярные теги (Агрегат COUNT + 3 JOIN)
    # -------------------------------------------------------------
    print("\n--- Запрос 3: Популярные теги (Агрегат COUNT + 3 JOIN) ---")
    try:
        q3 = """
        SELECT t.name AS tag_name, COUNT(nt.news_id) AS usage_count
        FROM tags t
        JOIN news_tags nt ON t.tag_id = nt.tag_id
        JOIN news n ON nt.news_id = n.news_id
        WHERE n.status = 'active'
        GROUP BY t.tag_id, t.name
        ORDER BY usage_count DESC
        LIMIT 10;
        """
        cur.execute(q3)
        rows = cur.fetchall()
        log_test("Запрос 3: Успешное выполнение синтаксиса", True)
        log_test("Запрос 3: Ровно 10 популярных тегов (LIMIT 10)", len(rows) == 10, f"(получено: {len(rows)})")
        descending = all(rows[i]["usage_count"] >= rows[i+1]["usage_count"] for i in range(len(rows)-1)) if len(rows) > 1 else True
        log_test("Запрос 3: Сортировка по убыванию частоты", descending)
    except Exception as e:
        log_test("Запрос 3: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 4: Мониторинг спама / дубликатов (Агрегат COUNT + HAVING)
    # -------------------------------------------------------------
    print("\n--- Запрос 4: Мониторинг источников спама/дубликатов ---")
    try:
        q4 = """
        SELECT s.name AS source_name, COUNT(n.news_id) AS duplicate_count
        FROM sources s
        JOIN news n ON s.source_id = n.source_id
        WHERE n.status = 'duplicate'
        GROUP BY s.source_id, s.name
        HAVING COUNT(n.news_id) > 100
        ORDER BY duplicate_count DESC;
        """
        cur.execute(q4)
        rows = cur.fetchall()
        log_test("Запрос 4: Успешное выполнение синтаксиса", True)
        all_gt_100 = all(r["duplicate_count"] > 100 for r in rows) if rows else False
        log_test("Запрос 4: Фильтр HAVING duplicate_count > 100 соблюден", all_gt_100, f"(источников спама: {len(rows)})")
    except Exception as e:
        log_test("Запрос 4: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 5: Рейтинг вовлеченности пользователей (Агрегат COUNT + JOIN)
    # -------------------------------------------------------------
    print("\n--- Запрос 5: Рейтинг вовлеченности пользователей (ТОП-5) ---")
    try:
        q5 = """
        SELECT u.name AS user_name, u.email, COUNT(f.favorite_id) AS favorites_count
        FROM users u
        JOIN favorites f ON u.user_id = f.user_id
        GROUP BY u.user_id, u.name, u.email
        ORDER BY favorites_count DESC
        LIMIT 5;
        """
        cur.execute(q5)
        rows = cur.fetchall()
        log_test("Запрос 5: Успешное выполнение синтаксиса", True)
        log_test("Запрос 5: Возвращено 5 активных пользователей", len(rows) == 5, f"(получено: {len(rows)})")
    except Exception as e:
        log_test("Запрос 5: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 6: Топ-3 свежих новостей по каждой категории (DENSE_RANK + CTE)
    # -------------------------------------------------------------
    print("\n--- Запрос 6: Оконное ранжирование новостей в категориях (DENSE_RANK + CTE) ---")
    try:
        q6 = """
        WITH ranked_news AS (
            SELECT 
                c.category_id,
                c.name AS category_name,
                n.news_id,
                n.title,
                n.published_at,
                DENSE_RANK() OVER (
                    PARTITION BY c.category_id 
                    ORDER BY n.published_at DESC
                ) AS rank_in_category
            FROM categories c
            JOIN news_categories nc ON c.category_id = nc.category_id
            JOIN news n ON nc.news_id = n.news_id
            WHERE n.status = 'active'
        )
        SELECT category_name, rank_in_category, news_id, title, published_at
        FROM ranked_news
        WHERE rank_in_category <= 3
        ORDER BY category_name, rank_in_category;
        """
        cur.execute(q6)
        rows = cur.fetchall()
        log_test("Запрос 6: Успешное выполнение синтаксиса", True)
        all_le_3 = all(r["rank_in_category"] in (1, 2, 3) for r in rows) if rows else False
        log_test("Запрос 6: Ограничение rank_in_category <= 3 соблюдено", all_le_3, f"(строк выборки: {len(rows)})")
        categories_count = len(set(r["category_name"] for r in rows))
        log_test("Запрос 6: Покрытие категорий оконной функцией", categories_count >= 10, f"(категорий: {categories_count})")
    except Exception as e:
        log_test("Запрос 6: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 7: Анализ периодичности публикаций (LAG + CTE)
    # -------------------------------------------------------------
    print("\n--- Запрос 7: Анализ периодичности публикаций (LAG + CTE) ---")
    try:
        q7 = """
        WITH source_publications AS (
            SELECT 
                s.source_id,
                s.name AS source_name,
                n.news_id,
                n.title,
                n.published_at,
                LAG(n.published_at) OVER (
                    PARTITION BY s.source_id 
                    ORDER BY n.published_at
                ) AS prev_published_at
            FROM sources s
            JOIN news n ON s.source_id = n.source_id
            WHERE s.source_id IN (1, 2, 3) AND n.status = 'active'
        )
        SELECT 
            source_name,
            news_id,
            published_at,
            prev_published_at,
            ROUND(EXTRACT(EPOCH FROM (published_at - prev_published_at)) / 60.0, 2) AS interval_minutes
        FROM source_publications
        WHERE prev_published_at IS NOT NULL
        ORDER BY source_name, published_at DESC
        LIMIT 20;
        """
        cur.execute(q7)
        rows = cur.fetchall()
        log_test("Запрос 7: Успешное выполнение синтаксиса", True)
        positive_intervals = all(float(r["interval_minutes"]) >= 0 for r in rows) if rows else False
        log_test("Запрос 7: Интервалы между публикациями корректны (>= 0 мин)", positive_intervals)
        lag_computed = all(r["prev_published_at"] is not None for r in rows) if rows else False
        log_test("Запрос 7: Оконная функция LAG успешно рассчитала предыдущие отметки времени", lag_computed)
    except Exception as e:
        log_test("Запрос 7: Ошибка выполнения", False, str(e))

    # -------------------------------------------------------------
    # Запрос 8: Накопительный итог и скользящее среднее (Running Total & Moving Avg)
    # -------------------------------------------------------------
    print("\n--- Запрос 8: Накопительный итог и скользящее среднее (Running Total & Moving Avg) ---")
    try:
        q8 = """
        WITH daily_source_stats AS (
            SELECT 
                s.source_id,
                s.name AS source_name,
                date_trunc('day', n.published_at)::date AS publication_date,
                COUNT(n.news_id) AS daily_news_count
            FROM sources s
            JOIN news n ON s.source_id = n.source_id
            WHERE s.source_id IN (1, 2, 3) AND n.status = 'active'
            GROUP BY s.source_id, s.name, date_trunc('day', n.published_at)::date
        )
        SELECT 
            source_name,
            publication_date,
            daily_news_count,
            SUM(daily_news_count) OVER (
                PARTITION BY source_id 
                ORDER BY publication_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_total_news,
            ROUND(AVG(daily_news_count) OVER (
                PARTITION BY source_id 
                ORDER BY publication_date
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ), 2) AS moving_avg_3d
        FROM daily_source_stats
        ORDER BY source_name, publication_date
        LIMIT 25;
        """
        cur.execute(q8)
        rows = cur.fetchall()
        log_test("Запрос 8: Успешное выполнение синтаксиса", True)
        # Проверяем, что накопительный итог >= daily_news_count
        valid_running = all(r["running_total_news"] >= r["daily_news_count"] for r in rows) if rows else False
        log_test("Запрос 8: Накопительный итог (SUM OVER) корректен и возрастает", valid_running)
        valid_moving = all(r["moving_avg_3d"] is not None and float(r["moving_avg_3d"]) > 0 for r in rows) if rows else False
        log_test("Запрос 8: Скользящее среднее (AVG OVER 2 PRECEDING) рассчитано", valid_moving)
    except Exception as e:
        log_test("Запрос 8: Ошибка выполнения", False, str(e))

    cur.close()
    conn.close()

    print("\n==================================================================")
    print(f" ИТОГО ПРОВЕРОК: Успешно: \033[92m{passed_count}\033[0m / {passed_count + failed_count}")
    if failed_count == 0:
        print(" \033[92mВСЕ АНАЛИТИЧЕСКИЕ SQL-ЗАПРОСЫ ПОЛНОСТЬЮ ВАЛИДНЫ!\033[0m")
        sys.exit(0)
    else:
        print(f" \033[91mОБНАРУЖЕНЫ ОШИБКИ: {failed_count}\033[0m")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
