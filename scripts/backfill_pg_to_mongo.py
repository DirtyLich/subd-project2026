#!/usr/bin/env python3
"""
scripts/backfill_pg_to_mongo.py
Воспроизводимый Backfill данных из PostgreSQL в MongoDB с контролем повторного запуска
КТ-05 · Спринт 5 · Уровень "Восхитительно" (Пункт В-4)

Возможности:
1. Воспроизводимый перенос данных с обогащением (Embedding метаданных источника, категорий и тегов).
2. Контроль повторного запуска (Idempotency):
   - Уникальный индекс по legacy_id в MongoDB.
   - Механизм Upsert (UpdateOne с upsert=True) исключает появление дубликатов.
   - Фиксация watermark (last_synced_legacy_id) в служебной коллекции `sync_metadata`.
3. Поддержка дозагрузки (resume) и сброса (--reset).
4. Батчевая обработка (Bulk Write) для высокой скорости переноса.
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient, UpdateOne

# Параметры подключения по умолчанию
PG_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "mydb")
PG_USER = os.getenv("POSTGRES_USER", "flyway_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "flyway_password")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
MONGO_DB = os.getenv("MONGO_DB", "news_aggregator")

PIPELINE_NAME = "pg_to_mongo_articles_backfill"


def get_pg_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS
    )


def get_mongo_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
    return client, client[MONGO_DB]


def load_lookup_dictionaries(pg_conn):
    """
    Предзагрузка справочников источников, категорий и тегов в память
    для эффективного O(1) обогащения документов без тяжелых N-JOIN.
    """
    cur = pg_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Источники
    cur.execute("SELECT source_id, name, url, type FROM sources;")
    sources = {row["source_id"]: row for row in cur.fetchall()}

    # 2. Категории
    cur.execute("SELECT category_id, name FROM categories;")
    categories = {row["category_id"]: row for row in cur.fetchall()}

    # 3. Теги
    cur.execute("SELECT tag_id, name FROM tags;")
    tags = {row["tag_id"]: row["name"] for row in cur.fetchall()}

    cur.close()
    return sources, categories, tags


def get_watermark(mongo_db):
    """Чтение текущего состояния процесса миграции из коллекции sync_metadata."""
    meta = mongo_db.sync_metadata.find_one({"pipeline_name": PIPELINE_NAME})
    if meta:
        return meta.get("last_synced_legacy_id", 0), meta.get("total_synced_count", 0)
    return 0, 0


def update_watermark(mongo_db, last_id, batch_count, status="IN_PROGRESS"):
    """Атомарное обновление watermark в MongoDB."""
    mongo_db.sync_metadata.update_one(
        {"pipeline_name": PIPELINE_NAME},
        {
            "$set": {
                "last_synced_legacy_id": int(last_id),
                "last_run_timestamp": datetime.now(timezone.utc),
                "status": status
            },
            "$inc": {
                "total_synced_count": batch_count
            }
        },
        upsert=True
    )


def reset_watermark(mongo_db):
    """Сброс состояния миграции для чистого перезапуска."""
    mongo_db.sync_metadata.delete_one({"pipeline_name": PIPELINE_NAME})
    print(f"[\033[93mRESET\033[0m] Watermark для пайплайна '{PIPELINE_NAME}' успешно сброшен.")


def print_status(mongo_db):
    """Отображение текущего прогресса backfill."""
    meta = mongo_db.sync_metadata.find_one({"pipeline_name": PIPELINE_NAME})
    total_articles = mongo_db.articles.count_documents({})
    print("==================================================================")
    print(" ТЕКУЩИЙ СТАТУС ПАЙПЛАЙНА BACKFILL")
    print("==================================================================")
    if meta:
        print(f"  • Пайплайн:               {meta.get('pipeline_name')}")
        print(f"  • Статус:                 {meta.get('status')}")
        print(f"  • Последний перенесенный ID: {meta.get('last_synced_legacy_id')}")
        print(f"  • Всего обработано:       {meta.get('total_synced_count')}")
        print(f"  • Время последней пачки:  {meta.get('last_run_timestamp')}")
    else:
        print("  • Пайплайн еще не запускался.")
    print(f"  • Всего документов в articles: {total_articles}")
    print("==================================================================")


def run_backfill(limit=1000, batch_size=500, reset=False):
    mongo_client, mongo_db = get_mongo_db()

    if reset:
        reset_watermark(mongo_db)

    watermark, total_synced_so_far = get_watermark(mongo_db)
    print("==================================================================")
    print(" ВОСПРОИЗВОДИМЫЙ BACKFILL: POSTGRESQL -> MONGODB")
    print(f" Источник (PostgreSQL): {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}")
    print(f" Приемник (MongoDB):    {MONGO_URI}{MONGO_DB}")
    print(f" Текущий watermark:     news_id > {watermark}")
    print(f" Лимит на данный запуск: {limit} документов (батчи по {batch_size})")
    print("==================================================================")

    pg_conn = get_pg_connection()
    sources, categories, tags = load_lookup_dictionaries(pg_conn)
    print(f"[\033[92mINFO\033[0m] Справочники загружены: {len(sources)} источников, {len(categories)} категорий, {len(tags)} тегов.")

    start_time = time.time()
    processed_in_run = 0

    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)

    while processed_in_run < limit:
        current_limit = min(batch_size, limit - processed_in_run)
        
        # Выборка пачки новостей строго больше последнего watermark
        pg_cur.execute("""
            SELECT 
                news_id, source_id, title, summary, content, 
                external_url, status, published_at, created_at
            FROM news
            WHERE news_id > %s
            ORDER BY news_id ASC
            LIMIT %s;
        """, (watermark, current_limit))

        news_rows = pg_cur.fetchall()
        if not news_rows:
            print("[\033[92mINFO\033[0m] Все доступные новости из PostgreSQL перенесены!")
            break

        news_ids = [r["news_id"] for r in news_rows]

        # Загрузка связей с категориями для пачки
        pg_cur.execute("""
            SELECT news_id, category_id 
            FROM news_categories 
            WHERE news_id = ANY(%s);
        """, (news_ids,))
        news_cats_map = {}
        for row in pg_cur.fetchall():
            news_cats_map.setdefault(row["news_id"], []).append(row["category_id"])

        # Загрузка связей с тегами для пачки
        pg_cur.execute("""
            SELECT news_id, tag_id 
            FROM news_tags 
            WHERE news_id = ANY(%s);
        """, (news_ids,))
        news_tags_map = {}
        for row in pg_cur.fetchall():
            news_tags_map.setdefault(row["news_id"], []).append(row["tag_id"])

        # Формирование BSON документов и подготовка bulk upsert операций
        bulk_ops = []
        max_batch_id = watermark

        for row in news_rows:
            nid = row["news_id"]
            max_batch_id = max(max_batch_id, nid)

            # Получаем источник
            src_info = sources.get(row["source_id"], {
                "source_id": row["source_id"],
                "name": f"Source #{row['source_id']}",
                "url": "https://unknown.source.local",
                "type": "rss"
            })

            # Получаем категории (embedding)
            cat_list = []
            for cid in news_cats_map.get(nid, []):
                if cid in categories:
                    cat_list.append({
                        "category_id": cid,
                        "name": categories[cid]["name"]
                    })

            # Получаем теги (embedding M:N)
            tag_list = [tags[tid] for tid in news_tags_map.get(nid, []) if tid in tags][:20]

            # Валидация URL под pattern ^https?://
            url = row["external_url"]
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                url = f"https://news.archive.local/item/{nid}"

            # Формирование денормализованного документа
            doc = {
                "legacy_id": nid,
                "title": row["title"] if len(row["title"]) >= 5 else f"Статья: {row['title']}",
                "summary": row["summary"],
                "content": row["content"],
                "external_url": url,
                "status": row["status"] if row["status"] in ("active", "hidden", "duplicate", "archived") else "active",
                "published_at": row["published_at"] if row["published_at"] else datetime.now(timezone.utc),
                "created_at": row["created_at"] if row["created_at"] else datetime.now(timezone.utc),
                "source": {
                    "source_id": src_info["source_id"],
                    "name": src_info["name"],
                    "url": src_info.get("url", "https://source.local"),
                    "type": src_info.get("type", "rss")
                },
                "categories": cat_list,
                "tags": tag_list,
                "metrics": {
                    "views_count": 0,
                    "favorites_count": 0,
                    "comments_count": 0
                },
                "schema_version": 1
            }

            # Идемпотентная операция: поиск по уникальному legacy_id, обновление через $set, upsert
            bulk_ops.append(
                UpdateOne({"legacy_id": nid}, {"$set": doc}, upsert=True)
            )

        # Выполнение пакета в MongoDB
        bulk_res = mongo_db.articles.bulk_write(bulk_ops, ordered=False)
        watermark = max_batch_id
        processed_in_run += len(bulk_ops)

        # Сохранение watermark
        update_watermark(mongo_db, watermark, len(bulk_ops), "IN_PROGRESS")

        upserted = len(bulk_res.upserted_ids) if bulk_res.upserted_ids else 0
        matched = bulk_res.matched_count
        print(f"  [BATCH] Обработано: {len(bulk_ops)} | Добавлено (новых): {upserted} | Обновлено (matched): {matched} | Watermark: {watermark}")

    update_watermark(mongo_db, watermark, 0, "COMPLETED")

    elapsed = time.time() - start_time
    speed = processed_in_run / elapsed if elapsed > 0 else 0
    print("\n==================================================================")
    print(f" BACKFILL ЗАВЕРШЕН УСПЕШНО ЗА {elapsed:.2f} сек.")
    print(f"  • Обработано в этой сессии: \033[92m{processed_in_run}\033[0m документов")
    print(f"  • Скорость миграции:        \033[92m{speed:.1f}\033[0m док/сек")
    print(f"  • Актуальный watermark ID:  {watermark}")
    print("==================================================================")

    pg_cur.close()
    pg_conn.close()
    mongo_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Воспроизводимый Backfill из PostgreSQL в MongoDB")
    parser.add_argument("--limit", type=int, default=1000, help="Количество документов для переноса (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=500, help="Размер батча bulk_write (default: 500)")
    parser.add_argument("--reset", action="store_true", help="Сбросить watermark и начать миграцию заново")
    parser.add_argument("--status", action="store_true", help="Показать текущий статус пайплайна")

    args = parser.parse_args()

    if args.status:
        _, mdb = get_mongo_db()
        print_status(mdb)
    else:
        run_backfill(limit=args.limit, batch_size=args.batch_size, reset=args.reset)
