#!/usr/bin/env python3
"""
scripts/test_mongo_crud.py
Автоматическое тестирование CRUD-сценариев и валидации схемы MongoDB ($jsonSchema)
КТ-05 · Спринт 5
"""
import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import OperationFailure, WriteError
from bson import ObjectId

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
DB_NAME = os.getenv("MONGO_DB", "news_aggregator")

passed_tests = 0
failed_tests = 0

def log_test(title, success, detail=""):
    global passed_tests, failed_tests
    if success:
        passed_tests += 1
        print(f"  [\033[92mPASS\033[0m] {title} {detail}")
    else:
        failed_tests += 1
        print(f"  [\033[91mFAIL\033[0m] {title} {detail}")

def run_tests():
    global passed_tests, failed_tests
    print("==================================================================")
    print(" АВТОМАТИЧЕСКАЯ ПРОВЕРКА MONGODB: CRUD И $jsonSchema ВАЛИДАЦИЯ")
    print(f" Подключение: {MONGO_URI}{DB_NAME}")
    print("==================================================================")

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]
        client.admin.command("ping")
        log_test("Подключение к MongoDB кластеру", True)
    except Exception as e:
        print(f"\033[91m[ERROR] Не удалось подключиться к MongoDB: {e}\033[0m")
        sys.exit(1)

    # Очистка тестовых записей перед тестом
    db.articles.delete_many({"legacy_id": {"$in": [999101, 999102, 999103, 999104]}})
    db.user_profiles.delete_many({"legacy_user_id": 999501})
    db.comments.delete_many({"author.user_id": 999501})

    # -------------------------------------------------------------
    # 1. CREATE: Валидная статья со встроенными тегами и источником (Embedding)
    # -------------------------------------------------------------
    print("\n--- 1. CREATE: Вставка валидной статьи (Embedding) ---")
    valid_doc = {
        "legacy_id": 999101,
        "title": "Тестирование документной модели данных в MongoDB 7.0",
        "summary": "Автоматизированная проверка создания и валидации BSON документов.",
        "content": "Полное руководство по переходу с реляционной схемы на документную...",
        "external_url": "https://database-weekly.example.com/mongo7",
        "status": "active",
        "published_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "source": {
            "source_id": 101,
            "name": "Database Weekly",
            "url": "https://database-weekly.example.com",
            "type": "api"
        },
        "categories": [
            {"category_id": 1, "name": "IT и технологии"},
            {"category_id": 3, "name": "Инженерия данных"}
        ],
        "tags": ["nosql", "mongodb", "architecture", "validation"],
        "metrics": {
            "views_count": 50,
            "favorites_count": 10,
            "comments_count": 0
        },
        "schema_version": 1
    }

    try:
        res = db.articles.insert_one(valid_doc)
        inserted_id = res.inserted_id
        log_test("Успешная вставка валидного документа в коллекцию articles", True, f"(_id: {inserted_id})")
    except Exception as e:
        log_test("Успешная вставка валидного документа в коллекцию articles", False, str(e))
        inserted_id = None

    # -------------------------------------------------------------
    # 2. CREATE: Профиль пользователя и комментарий (1:N Referencing)
    # -------------------------------------------------------------
    print("\n--- 2. CREATE: Профиль пользователя и связанный комментарий (Referencing) ---")
    try:
        user_doc = {
            "legacy_user_id": 999501,
            "name": "Дмитрий Архитектор",
            "email": "dmitry.arch@example.com",
            "role": "user",
            "preferences": {
                "ui_theme": "dark",
                "notifications_enabled": True
            },
            "bookmarked_article_ids": [inserted_id] if inserted_id else [],
            "reading_history": [
                {
                    "article_id": inserted_id if inserted_id else ObjectId(),
                    "read_at": datetime.now(timezone.utc),
                    "time_spent_seconds": 180
                }
            ],
            "schema_version": 1
        }
        user_res = db.user_profiles.insert_one(user_doc)
        log_test("Создание профиля пользователя (M:N Referencing закладки)", True, f"(_id: {user_res.inserted_id})")

        comment_doc = {
            "article_id": inserted_id if inserted_id else ObjectId(),
            "author": {
                "user_id": 999501,
                "name": "Дмитрий Архитектор"
            },
            "content": "Встраивание тегов и ссылочная модель для комментариев идеально подходят под SLA чтения.",
            "status": "published",
            "likes_count": 3,
            "created_at": datetime.now(timezone.utc),
            "schema_version": 1
        }
        comment_res = db.comments.insert_one(comment_doc)
        comment_id = comment_res.inserted_id
        log_test("Создание комментария (1:N Referencing к статье)", True, f"(_id: {comment_id})")
    except Exception as e:
        log_test("Создание профиля и комментария", False, str(e))

    # -------------------------------------------------------------
    # 3. READ: Быстрое чтение статьи и Aggregation Pipeline ($lookup)
    # -------------------------------------------------------------
    print("\n--- 3. READ: Выборка по индексу и агрегация ($lookup) ---")
    try:
        article_found = db.articles.find_one({"_id": inserted_id})
        log_test("Чтение статьи целиком со всеми тегами и источником без JOIN", article_found is not None and len(article_found["tags"]) == 4)

        # Проверка $lookup
        pipeline = [
            {"$match": {"_id": inserted_id}},
            {
                "$lookup": {
                    "from": "comments",
                    "localField": "_id",
                    "foreignField": "article_id",
                    "as": "comments_list"
                }
            }
        ]
        agg_result = list(db.articles.aggregate(pipeline))
        has_comments = len(agg_result) > 0 and len(agg_result[0].get("comments_list", [])) >= 1
        log_test("Агрегация $lookup: Успешное связывание статьи и комментариев", has_comments)
    except Exception as e:
        log_test("Чтение и агрегация", False, str(e))

    # -------------------------------------------------------------
    # 4. UPDATE: Атомарные операторы ($inc, $push, $set)
    # -------------------------------------------------------------
    print("\n--- 4. UPDATE: Модификация документа ($inc, $push, $set) ---")
    try:
        upd_res = db.articles.update_one(
            {"_id": inserted_id},
            {
                "$inc": {"metrics.views_count": 10, "metrics.comments_count": 1},
                "$push": {"tags": "benchmarking"},
                "$set": {"summary": "Обновленное резюме статьи после нагрузочных тестов."}
            }
        )
        updated_doc = db.articles.find_one({"_id": inserted_id})
        log_test("Атомарный инкремент $inc просмотров (было 50 -> стало 60)", updated_doc["metrics"]["views_count"] == 60)
        log_test("Добавление тега через $push (стало 5 тегов)", len(updated_doc["tags"]) == 5)
    except Exception as e:
        log_test("Атомарное обновление", False, str(e))

    # -------------------------------------------------------------
    # 5. NEGATIVE TESTS: Проверка отклонения нарушений схемы ($jsonSchema)
    # -------------------------------------------------------------
    print("\n--- 5. NEGATIVE TESTS: Валидация схемы ($jsonSchema) ---")

    # 5.1 Короткий заголовок (< 5 символов)
    title_rejected = False
    try:
        db.articles.insert_one({
            "legacy_id": 999102,
            "title": "Abc",  # < 5 символов!
            "status": "active",
            "published_at": datetime.now(timezone.utc),
            "source": {"source_id": 1, "name": "Src"},
            "schema_version": 1
        })
    except (OperationFailure, WriteError):
        title_rejected = True
    log_test("Валидатор отклонил заголовок короче 5 символов (minLength: 5)", title_rejected)

    # 5.2 Недопустимый статус (не в enum)
    status_rejected = False
    try:
        db.articles.insert_one({
            "legacy_id": 999103,
            "title": "Корректный длинный заголовок статьи",
            "status": "banned_fake_status",  # нет в enum!
            "published_at": datetime.now(timezone.utc),
            "source": {"source_id": 1, "name": "Src"},
            "schema_version": 1
        })
    except (OperationFailure, WriteError):
        status_rejected = True
    log_test("Валидатор отклонил статус вне допустимого enum (active/hidden/duplicate/archived)", status_rejected)

    # 5.3 Некорректный external_url
    url_rejected = False
    try:
        db.articles.insert_one({
            "legacy_id": 999104,
            "title": "Корректный длинный заголовок статьи",
            "status": "active",
            "external_url": "ftp://invalid-protocol.com/123",  # нарушает pattern: ^https?://
            "published_at": datetime.now(timezone.utc),
            "source": {"source_id": 1, "name": "Src"},
            "schema_version": 1
        })
    except (OperationFailure, WriteError):
        url_rejected = True
    log_test("Валидатор отклонил невалидный external_url (pattern: ^https?://)", url_rejected)

    # -------------------------------------------------------------
    # 6. DELETE: Удаление комментариев и закладок
    # -------------------------------------------------------------
    print("\n--- 6. DELETE: Удаление связанных документов ---")
    try:
        del_res = db.comments.delete_one({"_id": comment_id})
        log_test("Удаление комментария по _id", del_res.deleted_count == 1)

        # Удаление ссылки на статью из закладок пользователя ($pull)
        pull_res = db.user_profiles.update_one(
            {"legacy_user_id": 999501},
            {"$pull": {"bookmarked_article_ids": inserted_id}}
        )
        user_after_pull = db.user_profiles.find_one({"legacy_user_id": 999501})
        log_test("Удаление ссылки из массива закладок ($pull)", len(user_after_pull["bookmarked_article_ids"]) == 0)
    except Exception as e:
        log_test("Удаление", False, str(e))

    client.close()

    print("\n==================================================================")
    print(f" ИТОГО ПРОВЕРОК: Успешно: \033[92m{passed_tests}\033[0m / {passed_tests + failed_tests}")
    if failed_tests == 0:
        print(" \033[92mВСЕ CRUD СЦЕНАРИИ И ВАЛИДАЦИЯ MONGODB РАБОТАЮТ БЕЗУПРЕЧНО!\033[0m")
        sys.exit(0)
    else:
        print(f" \033[91mОБНАРУЖЕНЫ ОШИБКИ: {failed_tests}\033[0m")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
