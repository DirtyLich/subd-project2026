#!/usr/bin/env python3
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pymongo import MongoClient, InsertOne, UpdateOne, DeleteOne
from pymongo.errors import BulkWriteError

MONGO_USER = 'news_app_user'
MONGO_PASS = urllib.parse.quote_plus('AppSuperPass2026!')
MONGO_URI = f'mongodb://{MONGO_USER}:{MONGO_PASS}@127.0.0.1:27017/news_aggregator?authSource=news_aggregator&directConnection=true'

client = MongoClient(MONGO_URI)
db = client['news_aggregator']

print("==================================================================")
print(" СПРИНТ 6: ПАКЕТНАЯ ОБРАБОТКА ЧЕРЕЗ BULK API С ДВУМЯ ТИПАМИ ОПЕРАЦИЙ")
print("==================================================================")

# Очистим тестовый диапазон
db.articles.delete_many({"legacy_id": {"$gte": 900000, "$lte": 905000}})

# -------------------------------------------------------------
# 1. Формирование разнородного пакета (InsertOne, UpdateOne, DeleteOne)
# -------------------------------------------------------------
operations = []

# А. InsertOne (1000 новых статей)
for i in range(900001, 901001):
    doc = {
        "legacy_id": i,
        "title": f"Срочная новость высоких технологий #{i}",
        "summary": "Краткое описание события...",
        "content": "Полный текст аналитической заметки...",
        "external_url": f"https://tech.example.com/item/{i}",
        "status": "active",
        "published_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "source": {
            "source_id": 99,
            "name": "Tech Daily News",
            "url": "https://tech.example.com",
            "type": "api"
        },
        "categories": [{"category_id": 1, "name": "IT"}],
        "tags": ["tech", "ai", "bulk"],
        "metrics": {"views_count": 0, "favorites_count": 0, "comments_count": 0},
        "schema_version": 1
    }
    operations.append(InsertOne(doc))

# Б. UpdateOne (атомарный инкремент счетчиков и выставление тега)
for i in range(900001, 900501):
    operations.append(
        UpdateOne(
            {"legacy_id": i},
            {"$inc": {"metrics.views_count": 10}, "$push": {"tags": "featured"}}
        )
    )

# В. DeleteOne (удаление некоторых устаревших/тестовых документов)
for i in range(900901, 901001):
    operations.append(DeleteOne({"legacy_id": i}))

print(f"Сформирован разнородный пакет операций: {len(operations)} шт.")
print(f" - InsertOne: 1000")
print(f" - UpdateOne: 500")
print(f" - DeleteOne: 100")

# -------------------------------------------------------------
# 2. Выполнение в режиме ordered=False (Unordered)
# -------------------------------------------------------------
t0 = time.perf_counter()
res = db.articles.bulk_write(operations, ordered=False)
t1 = time.perf_counter()

print("\n--- Результат выполнения Unordered Bulk Write ---")
print(f"  Время выполнения: {(t1 - t0)*1000.0:.2f} ms")
print(f"  Вставлено (inserted_count): {res.inserted_count}")
print(f"  Обновлено (modified_count): {res.modified_count}")
print(f"  Удалено (deleted_count): {res.deleted_count}")

# -------------------------------------------------------------
# 3. Обработка частичных ошибок и сравнение ordered vs unordered
# Желательно: Сравнить ordered и unordered bulk-операции при ошибке
# -------------------------------------------------------------
print("\n--- Сравнение поведения ordered vs unordered при частичной ошибке ---")

# Вставим эталонную запись для создания коллизии уникального индекса
db.articles.delete_many({"legacy_id": {"$in": [999010, 999011, 999012, 999013, 999014]}})
db.articles.insert_one({
    "legacy_id": 999012,
    "title": "Существующая статья с уникальным legacy_id",
    "status": "active",
    "published_at": datetime.now(timezone.utc),
    "source": {"source_id": 1, "name": "Default"},
    "schema_version": 1
})

# Формируем пакет из 5 операций, где 3-я (999012) гарантированно вызовет E11000 duplicate key
failing_batch = [
    InsertOne({"legacy_id": 999010, "title": "Корректная статья #1", "status": "active", "published_at": datetime.now(timezone.utc), "source": {"source_id": 1, "name": "Valid Source"}, "schema_version": 1}),
    InsertOne({"legacy_id": 999011, "title": "Корректная статья #2", "status": "active", "published_at": datetime.now(timezone.utc), "source": {"source_id": 1, "name": "Valid Source"}, "schema_version": 1}),
    InsertOne({"legacy_id": 999012, "title": "ДУБЛИКАТ статьи #3", "status": "active", "published_at": datetime.now(timezone.utc), "source": {"source_id": 1, "name": "Valid Source"}, "schema_version": 1}),
    InsertOne({"legacy_id": 999013, "title": "Корректная статья #4", "status": "active", "published_at": datetime.now(timezone.utc), "source": {"source_id": 1, "name": "Valid Source"}, "schema_version": 1}),
    InsertOne({"legacy_id": 999014, "title": "Корректная статья #5", "status": "active", "published_at": datetime.now(timezone.utc), "source": {"source_id": 1, "name": "Valid Source"}, "schema_version": 1}),
]

print("\nА. Эксперимент: ordered=True")
db.articles.delete_many({"legacy_id": {"$in": [999010, 999011, 999013, 999014]}})
try:
    db.articles.bulk_write(failing_batch, ordered=True)
except BulkWriteError as bwe:
    print(f"  [CATCH] BulkWriteError поймана:")
    print(f"  Успешно выполнено до ошибки: {bwe.details['nInserted']} вставок")
    print(f"  Число ошибок: {len(bwe.details['writeErrors'])}")
    print(f"  Статус статьи #4 (999013) в БД: {'найдена' if db.articles.find_one({'legacy_id': 999013}) else 'НЕ добавлена (выполнение прервалось)'}")

print("\nБ. Эксперимент: ordered=False")
db.articles.delete_many({"legacy_id": {"$in": [999010, 999011, 999013, 999014]}})
try:
    db.articles.bulk_write(failing_batch, ordered=False)
except BulkWriteError as bwe:
    print(f"  [CATCH] BulkWriteError поймана:")
    print(f"  Успешно выполнено всего: {bwe.details['nInserted']} вставок")
    print(f"  Число ошибок: {len(bwe.details['writeErrors'])}")
    print(f"  Статус статьи #4 (999013) в БД: {'УСПЕШНО добавлена (обработка продолжилась)' if db.articles.find_one({'legacy_id': 999013}) else 'не найдена'}")
    print(f"  Статус статьи #5 (999014) в БД: {'УСПЕШНО добавлена (обработка продолжилась)' if db.articles.find_one({'legacy_id': 999014}) else 'не найдена'}")

# Зачистка тестовых записей
db.articles.delete_many({"legacy_id": {"$gte": 900000, "$lte": 999999}})
client.close()

print("\n==================================================================")
print(" БЕНЧМАРК И ОБРАБОТКА ОШИБОК BULK API ЗАВЕРШЕНЫ УСПЕШНО!")
print("==================================================================")
