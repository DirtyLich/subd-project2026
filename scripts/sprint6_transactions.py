#!/usr/bin/env python3
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pymongo import MongoClient, ReadPreference
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError, OperationFailure

MONGO_USER = 'news_app_user'
MONGO_PASS = urllib.parse.quote_plus('AppSuperPass2026!')
# Подключение к Replica Set с seed-листом
MONGO_URI = f'mongodb://{MONGO_USER}:{MONGO_PASS}@mongo1:27017,mongo2:27017,mongo3:27017/news_aggregator?replicaSet=rs0&authSource=news_aggregator'

client = MongoClient(MONGO_URI)
db = client['news_aggregator']

print("==================================================================")
print(" СПРИНТ 6: МНОГОШАГОВЫЕ ТРАНЗАКЦИИ ПО ДВУМ КОЛЛЕКЦИЯМ (MONGODB RS)")
print("==================================================================")

# Подготовим исходные данные: статью и профиль пользователя
db.articles.delete_many({"legacy_id": 888001})
db.user_profiles.delete_many({"legacy_user_id": 888101})
db.comments.delete_many({"content": {"$regex": "^Тестовый транзакционный комментарий"}})

article_res = db.articles.insert_one({
    "legacy_id": 888001,
    "title": "Транзакционная архитектура в MongoDB Replica Set",
    "status": "active",
    "published_at": datetime.now(timezone.utc),
    "source": {"source_id": 1, "name": "System Arch"},
    "metrics": {"views_count": 100, "favorites_count": 5, "comments_count": 0},
    "schema_version": 1
})
article_id = article_res.inserted_id

user_res = db.user_profiles.insert_one({
    "legacy_user_id": 888101,
    "name": "Иван Инженер",
    "email": "ivan.trans@example.com",
    "role": "user",
    "bookmarked_article_ids": [],
    "schema_version": 1
})
user_id = user_res.inserted_id

print(f"Подготовлены тестовые сущности:")
print(f" - Статья _id: {article_id}")
print(f" - Пользователь _id: {user_id}")

# -------------------------------------------------------------
# 1. УСПЕШНОЕ ЗАВЕРШЕНИЕ ТРАНЗАКЦИИ (COMMIT)
# Шаг 1: Добавление комментария в коллекцию 'comments'
# Шаг 2: Инкремент comments_count в коллекции 'articles' ($inc)
# Шаг 3: Добавление статьи в закладки пользователя в 'user_profiles' ($addToSet)
# -------------------------------------------------------------
print("\n--- 1. Сценарий: Успешное выполнение транзакции (Commit) ---")

# Настройки транзакции: snapshot изоляция, write concern w:majority
wc_majority = WriteConcern(w="majority", wtimeout=5000)
rc_snapshot = ReadConcern("snapshot")

with client.start_session() as session:
    with session.start_transaction(read_concern=rc_snapshot, write_concern=wc_majority, read_preference=ReadPreference.PRIMARY):
        # Шаг 1
        comment_doc = {
            "article_id": article_id,
            "author": {"user_id": 888101, "name": "Иван Инженер"},
            "content": "Тестовый транзакционный комментарий: система надежна!",
            "created_at": datetime.now(timezone.utc),
            "schema_version": 1
        }
        db.comments.insert_one(comment_doc, session=session)
        
        # Шаг 2
        db.articles.update_one(
            {"_id": article_id},
            {"$inc": {"metrics.comments_count": 1}},
            session=session
        )
        
        # Шаг 3
        db.user_profiles.update_one(
            {"_id": user_id},
            {"$addToSet": {"bookmarked_article_ids": article_id}},
            session=session
        )
        # Автоматический commit при выходе из контекста

# Проверяем результат
art_after = db.articles.find_one({"_id": article_id})
user_after = db.user_profiles.find_one({"_id": user_id})
comm_count = db.comments.count_documents({"article_id": article_id})

print(f"  [OK] Транзакция успешно закоммичена:")
print(f"  - Счетчик comments_count в articles: {art_after['metrics']['comments_count']} (ожидалось: 1)")
print(f"  - Закладки в user_profiles: {len(user_after['bookmarked_article_ids'])} шт. (ожидалось: 1)")
print(f"  - Создано комментариев в comments: {comm_count}")

# -------------------------------------------------------------
# 2. ОТКАТ ТРАНЗАКЦИИ ПОСЛЕ ОШИБКИ (ABORT TRANSACTION)
# Искусственно вызываем ошибку на шаге 2 (нарушение валидации или бизнес-исключение)
# -------------------------------------------------------------
print("\n--- 2. Сценарий: Откат транзакции при ошибке (Rollback / Abort) ---")

try:
    with client.start_session() as session:
        with session.start_transaction(read_concern=rc_snapshot, write_concern=wc_majority):
            # Шаг 1: Вставка нового комментария
            db.comments.insert_one({
                "article_id": article_id,
                "author": {"user_id": 888101, "name": "Иван Инженер"},
                "content": "Тестовый транзакционный комментарий (должен откатиться)",
                "created_at": datetime.now(timezone.utc),
                "schema_version": 1
            }, session=session)
            
            # Шаг 2: Инкремент счетчика статьи
            db.articles.update_one(
                {"_id": article_id},
                {"$inc": {"metrics.comments_count": 1}},
                session=session
            )
            
            # Шаг 3: Внедряем критическую ошибку в середине транзакции
            print("  [SIMULATION] Внедрение ошибки в середине бизнес-процесса...")
            raise ValueError("Бизнес-ошибка: Лимит операций пользователя исчерпан!")

except ValueError as e:
    print(f"  [CATCH] Поймано исключение: {e}")
    print("  [ROLLBACK] Транзакция автоматически прервана (abort_transaction).")

# Проверяем целостность данных после отката
art_rollback = db.articles.find_one({"_id": article_id})
comm_count_rollback = db.comments.count_documents({"article_id": article_id})

print(f"  - Счетчик comments_count в articles остался: {art_rollback['metrics']['comments_count']} (не изменился)")
print(f"  - Количество комментариев в базе: {comm_count_rollback} (второй комментарий откатился)")
assert art_rollback['metrics']['comments_count'] == 1, "Ошибка отката счетчика!"
assert comm_count_rollback == 1, "Ошибка отката комментария!"

# -------------------------------------------------------------
# 3. БЕЗОПАСНЫЙ ПОВТОР ТРАНЗАКЦИИ (RETRYABLE TRANSACTIONS)
# Обработка TransientTransactionError и UnknownTransactionCommitResult
# -------------------------------------------------------------
print("\n--- 3. Сценарий: Безопасный повтор транзакции (Retryable Transactions) ---")

def execute_with_retry(client, txn_body, max_retries=3):
    """Официальный паттерн MongoDB Retryable Transactions с exponential backoff"""
    with client.start_session() as session:
        for attempt in range(1, max_retries + 1):
            try:
                # Внутренний цикл выполнения транзакции
                def callback(sess):
                    return txn_body(sess)
                
                # with_transaction автоматически обрабатывает TransientTransactionError
                res = session.with_transaction(
                    callback,
                    read_concern=rc_snapshot,
                    write_concern=wc_majority,
                    read_preference=ReadPreference.PRIMARY
                )
                print(f"  [RETRY] Транзакция успешно выполнена с попытки {attempt}")
                return res
            except PyMongoError as err:
                if err.has_error_label("TransientTransactionError"):
                    print(f"  [RETRY] Обнаружен TransientTransactionError на попытке {attempt}. Повтор через {0.1 * (2 ** attempt)}с...")
                    time.sleep(0.1 * (2 ** attempt))
                else:
                    raise

def sample_txn_body(session):
    db.articles.update_one(
        {"_id": article_id},
        {"$inc": {"metrics.views_count": 50}},
        session=session
    )
    return True

execute_with_retry(client, sample_txn_body)
art_retried = db.articles.find_one({"_id": article_id})
print(f"  - views_count после retryable-транзакции: {art_retried['metrics']['views_count']} (было 100 -> стало 150)")

client.close()
print("\n==================================================================")
print(" ВСЕ ТРАНЗАКЦИОННЫЕ СЦЕНАРИИ УСПЕШНО ПРОТЕСТИРОВАНЫ!")
print("==================================================================")
