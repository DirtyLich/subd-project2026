#!/usr/bin/env python3
import os
import sys
import time
import json
import statistics
import urllib.parse
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

MONGO_USER = 'news_app_user'
MONGO_PASS = urllib.parse.quote_plus('AppSuperPass2026!')
MONGO_URI = f'mongodb://{MONGO_USER}:{MONGO_PASS}@127.0.0.1:27017/news_aggregator?authSource=news_aggregator&directConnection=true'

client = MongoClient(MONGO_URI)
db = client['news_aggregator']

print("==================================================================")
print(" СПРИНТ 6: АНАЛИЗ И ОПТИМИЗАЦИЯ ДВУХ ЗАТРАТНЫХ ЗАПРОСОВ (MONGODB)")
print("==================================================================")

# -------------------------------------------------------------
# ЗАПРОС 1: Поиск популярных новостей по категории со сложной сортировкой
# Бизнес-сценарий: Выборка активных статей определенной категории, отсортированных по количеству просмотров
# Поля: categories.category_id, status, metrics.views_count
# -------------------------------------------------------------
filter_q1 = {
    "status": "active",
    "categories.category_id": 1,
    "metrics.views_count": {"$gte": 500}
}
sort_q1 = [("metrics.views_count", -1)]

# Сначала убедимся, что специфического индекса нет
try:
    db.articles.drop_index("idx_cat_status_views")
except Exception:
    pass

print("\n--- [ЗАПРОС 1] До оптимизации (COLLSCAN / неоптимальный индекс) ---")
runs_q1_before = []
explain_q1_before = None

for i in range(5):
    t0 = time.perf_counter()
    res = list(db.articles.find(filter_q1).sort(sort_q1).limit(20))
    t1 = time.perf_counter()
    runs_q1_before.append((t1 - t0) * 1000.0)

explain_q1_before = db.command('explain', {
    'find': 'articles',
    'filter': filter_q1,
    'sort': dict(sort_q1),
    'limit': 20
}, verbosity='executionStats')

stats_q1_before = explain_q1_before['executionStats']
med_time_q1_before = statistics.median(runs_q1_before)

print(f"  Медианное время (5 запусков): {med_time_q1_before:.3f} ms")
print(f"  executionTimeMillis (explain): {stats_q1_before['executionTimeMillis']} ms")
print(f"  totalDocsExamined: {stats_q1_before['totalDocsExamined']}")
print(f"  totalKeysExamined: {stats_q1_before['totalKeysExamined']}")
print(f"  nReturned: {stats_q1_before['nReturned']}")
winning_stage_1_before = stats_q1_before['executionStages']['stage']
print(f"  Stage: {winning_stage_1_before}")

# Создаем составной покрывающий/оптимизированный индекс по ESR-правилу:
# Equality: status, categories.category_id
# Sort: metrics.views_count (-1)
print("\n--- [ЗАПРОС 1] Создание оптимизированного индекса: idx_cat_status_views ---")
db.articles.create_index([
    ("status", 1),
    ("categories.category_id", 1),
    ("metrics.views_count", -1)
], name="idx_cat_status_views")

runs_q1_after = []
for i in range(5):
    t0 = time.perf_counter()
    res = list(db.articles.find(filter_q1).sort(sort_q1).limit(20))
    t1 = time.perf_counter()
    runs_q1_after.append((t1 - t0) * 1000.0)

explain_q1_after = db.command('explain', {
    'find': 'articles',
    'filter': filter_q1,
    'sort': dict(sort_q1),
    'limit': 20
}, verbosity='executionStats')

stats_q1_after = explain_q1_after['executionStats']
med_time_q1_after = statistics.median(runs_q1_after)

print(f"  Медианное время (5 запусков): {med_time_q1_after:.3f} ms")
print(f"  executionTimeMillis (explain): {stats_q1_after['executionTimeMillis']} ms")
print(f"  totalDocsExamined: {stats_q1_after['totalDocsExamined']}")
print(f"  totalKeysExamined: {stats_q1_after['totalKeysExamined']}")
print(f"  nReturned: {stats_q1_after['nReturned']}")
winning_stage_1_after = stats_q1_after['executionStages']['stage']
print(f"  Stage: {winning_stage_1_after}")

# -------------------------------------------------------------
# ЗАПРОС 2: Фильтрация по автору/источнику за интервал дат со статусом
# Бизнес-сценарий: Дайджест публикаций конкретного источника за определенный период дат
# -------------------------------------------------------------
filter_q2 = {
    "source.source_id": 84,
    "status": "active",
    "published_at": {
        "$gte": datetime(2020, 1, 1, tzinfo=timezone.utc),
        "$lte": datetime(2030, 1, 1, tzinfo=timezone.utc)
    }
}
sort_q2 = [("published_at", -1)]

try:
    db.articles.drop_index("idx_source_status_pubdate")
except Exception:
    pass

print("\n--- [ЗАПРОС 2] До оптимизации ---")
runs_q2_before = []
for i in range(5):
    t0 = time.perf_counter()
    res = list(db.articles.find(filter_q2).sort(sort_q2).limit(20))
    t1 = time.perf_counter()
    runs_q2_before.append((t1 - t0) * 1000.0)

explain_q2_before = db.command('explain', {
    'find': 'articles',
    'filter': filter_q2,
    'sort': dict(sort_q2),
    'limit': 20
}, verbosity='executionStats')

stats_q2_before = explain_q2_before['executionStats']
med_time_q2_before = statistics.median(runs_q2_before)

print(f"  Медианное время (5 запусков): {med_time_q2_before:.3f} ms")
print(f"  executionTimeMillis (explain): {stats_q2_before['executionTimeMillis']} ms")
print(f"  totalDocsExamined: {stats_q2_before['totalDocsExamined']}")
print(f"  totalKeysExamined: {stats_q2_before['totalKeysExamined']}")
print(f"  nReturned: {stats_q2_before['nReturned']}")
winning_stage_2_before = stats_q2_before['executionStages']['stage']
print(f"  Stage: {winning_stage_2_before}")

# Создаем составной индекс по ESR правилу:
# Equality: source.source_id, status
# Sort / Range: published_at (-1)
print("\n--- [ЗАПРОС 2] Создание оптимизированного индекса: idx_source_status_pubdate ---")
db.articles.create_index([
    ("source.source_id", 1),
    ("status", 1),
    ("published_at", -1)
], name="idx_source_status_pubdate")

runs_q2_after = []
for i in range(5):
    t0 = time.perf_counter()
    res = list(db.articles.find(filter_q2).sort(sort_q2).limit(20))
    t1 = time.perf_counter()
    runs_q2_after.append((t1 - t0) * 1000.0)

explain_q2_after = db.command('explain', {
    'find': 'articles',
    'filter': filter_q2,
    'sort': dict(sort_q2),
    'limit': 20
}, verbosity='executionStats')

stats_q2_after = explain_q2_after['executionStats']
med_time_q2_after = statistics.median(runs_q2_after)

print(f"  Медианное время (5 запусков): {med_time_q2_after:.3f} ms")
print(f"  executionTimeMillis (explain): {stats_q2_after['executionTimeMillis']} ms")
print(f"  totalDocsExamined: {stats_q2_after['totalDocsExamined']}")
print(f"  totalKeysExamined: {stats_q2_after['totalKeysExamined']}")
print(f"  nReturned: {stats_q2_after['nReturned']}")
winning_stage_2_after = stats_q2_after['executionStages']['stage']
print(f"  Stage: {winning_stage_2_after}")

print("\n==================================================================")
print(" СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ ОПТИМИЗАЦИИ")
print("==================================================================")
print("| Метрика | Запрос 1 ДО | Запрос 1 ПОСЛЕ | Запрос 2 ДО | Запрос 2 ПОСЛЕ |")
print("|---|---|---|---|---|")
print(f"| Индекс | Неоптимальный | idx_cat_status_views | Неоптимальный | idx_source_status_pubdate |")
print(f"| Stage | {winning_stage_1_before} | {winning_stage_1_after} | {winning_stage_2_before} | {winning_stage_2_after} |")
print(f"| executionTimeMillis | {stats_q1_before['executionTimeMillis']} ms | {stats_q1_after['executionTimeMillis']} ms | {stats_q2_before['executionTimeMillis']} ms | {stats_q2_after['executionTimeMillis']} ms |")
print(f"| Median Time (5 runs) | {med_time_q1_before:.3f} ms | {med_time_q1_after:.3f} ms | {med_time_q2_before:.3f} ms | {med_time_q2_after:.3f} ms |")
print(f"| totalDocsExamined | {stats_q1_before['totalDocsExamined']} | {stats_q1_after['totalDocsExamined']} | {stats_q2_before['totalDocsExamined']} | {stats_q2_after['totalDocsExamined']} |")
print(f"| totalKeysExamined | {stats_q1_before['totalKeysExamined']} | {stats_q1_after['totalKeysExamined']} | {stats_q2_before['totalKeysExamined']} | {stats_q2_after['totalKeysExamined']} |")
print(f"| nReturned | {stats_q1_before['nReturned']} | {stats_q1_after['nReturned']} | {stats_q2_before['nReturned']} | {stats_q2_after['nReturned']} |")

client.close()
