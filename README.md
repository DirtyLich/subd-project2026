# 📰 Новостной агрегатор — PostgreSQL

> **Спринт 3:** Данные, транзакции и базовая оптимизация PostgreSQL

---

## 📋 Содержание

- [Структура проекта](#структура-проекта)
- [Схема базы данных](#схема-базы-данных)
- [Быстрый старт](#быстрый-старт)
- [Генератор данных](#генератор-данных)
- [Бизнес-запросы](#бизнес-запросы)
- [Транзакции и блокировки](#транзакции-и-блокировки)
- [Оптимизация запросов](#оптимизация-запросов)
- [Словарь таблиц](#словарь-таблиц)

---

## 📁 Структура проекта

```
SQL/
├── generator/
│   └── main.py                    # Воспроизводимый генератор данных (seed=42)
├── migrations/
│   ├── V1__init_schema.sql        # Схема БД: таблицы, ключи, ограничения
│   ├── V2__seed_data.sql          # Базовые справочные данные
│   ├── V3__crud.sql               # CRUD-операции
│   └── V4__add_covering_indexes.sql # Оптимизирующие частичные индексы
├── scripts/
│   ├── business_queries.sql       # 5 бизнес-запросов с описанием
│   ├── transactions_and_locks.sql # Транзакции, COMMIT/ROLLBACK, блокировки
│   └── negative_tests.sql         # Тесты нарушения ограничений
└── README.md
```

---

## 🗄️ Схема базы данных

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│    users     │       │      news        │       │   sources    │
├──────────────┤   ┌──▶├──────────────────┤◀──┐   ├──────────────┤
│ user_id  PK  │   │   │ news_id      PK  │   │   │ source_id PK │
│ name         │   │   │ source_id    FK  │───┘   │ name         │
│ email UNIQUE │   │   │ title            │       │ url          │
│ password_hash│   │   │ summary          │       │ type         │
│ role  CHECK  │   │   │ external_url     │       │ is_active    │
│ status CHECK │   │   │ status   CHECK   │       │ update_freq  │
└──────────────┘   │   │ published_at     │       └──────────────┘
       │           │   └──────────────────┘
       │           │          │         │
       ▼           │          ▼         ▼
┌──────────────┐   │  ┌──────────┐ ┌──────────┐
│ subscriptions│   │  │news_cats │ │news_tags │
├──────────────┤   │  ├──────────┤ ├──────────┤
│ user_id  FK  │   │  │ news_id  │ │ news_id  │
│ category_id  │   │  │category_id│ │ tag_id   │
│ source_id    │   │  └──────────┘ └──────────┘
└──────────────┘   │         │            │
       │           │         ▼            ▼
       ▼           │  ┌──────────┐ ┌──────────┐
┌──────────────┐   │  │categories│ │   tags   │
│  favorites   │   │  ├──────────┤ ├──────────┤
├──────────────┤   │  │category_id│ │ tag_id   │
│ user_id  FK  │   │  │ name     │ │ name     │
│ news_id  FK ─┘   │  └──────────┘ └──────────┘
│ UNIQUE(u,n)  │   └─────────────────────────────
└──────────────┘
```

**Бизнес-ограничения в схеме:**
- `CHECK (role IN ('guest', 'user', 'editor', 'admin'))` — допустимые роли
- `CHECK (status IN ('active', 'hidden', 'duplicate', 'archived'))` — статусы новостей
- `CHECK (update_frequency_minutes > 0)` — частота обновления > 0
- `CHECK (length(trim(title)) > 0)` — заголовок новости не пустой
- `UNIQUE (user_id, news_id)` в `favorites` — нет повторных закладок
- `CHECK` в `subscriptions` — подписка ровно на одну цель (категория **или** источник)

---

## ⚡ Быстрый старт

### Требования
- Docker + Docker Compose
- Python 3.10+ с виртуальным окружением (`.venv`)

### 1. Запуск базы данных

```bash
docker compose up -d
```

### 2. Применение миграций

```bash
# Flyway автоматически применяет миграции V1 → V4 при старте
```

### 3. Заполнение данными

```bash
# Активировать окружение
source .venv/bin/activate   # Linux / macOS / WSL
# или
.venv\Scripts\activate      # Windows CMD

# Режим разработки — 100 000 новостей
python generator/main.py --mode dev

# Режим нагрузки — 3 000 000 новостей
python generator/main.py --mode load
```

---

## 🔧 Генератор данных

Файл: [`generator/main.py`](generator/main.py)

### Воспроизводимость

Генератор использует **фиксированный seed** `42` для обоих источников случайности:

```python
SEED = 42
random.seed(SEED)
Faker.seed(SEED)
```

Это гарантирует, что повторный запуск создаёт **идентичный** набор данных.

### Режимы генерации

| Параметр | `--mode dev` | `--mode load` |
|---|---|---|
| Пользователи | 1 000 | 10 000 |
| Источники | 50 | 500 |
| **Новости (крупнейшая таблица)** | **100 000** | **3 000 000** |
| Категории | 20 | 20 |
| Теги | 100 | 100 |

### Распределение данных

Данные генерируются **неравномерно**, как в реальных системах:

| Сущность | Параметр | Распределение |
|---|---|---|
| Пользователи | роль | `user` 90% · `editor` 8% · `admin` 2% |
| Пользователи | статус | `active` 85% · `blocked` 10% · `deleted` 5% |
| Источники | тип | `rss` 60% · `api` 30% · `web_scraping` 10% |
| Источники | активность | активен 95% · неактивен 5% |
| Новости | статус | `active` 70% · `hidden` 5% · `duplicate` 15% · `archived` 10% |
| Новости | дата | равномерно за последние 2 года |
| Новости → Источник | популярность | **Закон Ципфа** — `weight = 1/rank` |
| Подписки | охват | 40% пользователей имеют хотя бы одну |
| Избранное | количество | от 0 до 8 новостей на пользователя |

> **Закон Ципфа** означает, что первый источник в рейтинге получает в 2 раза больше новостей, чем второй, в 3 раза больше, чем третий, и т.д. Это точно моделирует реальное поведение медиарынка.

---

## 🔍 Бизнес-запросы

Файл: [`scripts/business_queries.sql`](scripts/business_queries.sql)

Реализованы **5 бизнес-запросов**. Каждый сопровождён описанием задачи, параметрами и примером результата.

| № | Название | Таблиц в JOIN | Агрегат | HAVING |
|---|---|:---:|:---:|:---:|
| 1 | Персональная лента новостей | 4 | — | — |
| 2 | Аналитика активности источников | 2 | `COUNT` | ✅ `> 1000` |
| 3 | Популярные теги (облако тегов) | 3 | `COUNT` | — |
| 4 | Мониторинг источников-дубликатов | 2 | `COUNT` | ✅ `> 100` |
| 5 | Рейтинг вовлечённости пользователей | 2 | `COUNT` | — |

**Покрытие требований:** ≥3 запроса с JOIN ✅ · ≥2 с GROUP BY ✅ · ≥1 с HAVING ✅

---

## 🔐 Транзакции и блокировки

Файл: [`scripts/transactions_and_locks.sql`](scripts/transactions_and_locks.sql)

### Сценарий 1 — Многошаговая транзакция (COMMIT / ROLLBACK)

**Бизнес-задача:** Деактивация источника — атомарно изменяет 3 таблицы.

```
BEGIN
  ├── UPDATE sources SET is_active = false    (таблица 1)
  ├── UPDATE news    SET status = 'archived'  (таблица 2)
  └── DELETE FROM subscriptions               (таблица 3)
COMMIT  ←── всё применяется атомарно
```

**Контролируемый ROLLBACK:** попытка установить `update_frequency_minutes = -10` нарушает `CHECK > 0`, что автоматически откатывает все предшествующие изменения.

### Сценарий 2 — Race Condition (SELECT FOR UPDATE)

**Бизнес-задача:** Два модератора не могут одновременно взять одну новость на проверку.

```
Сессия 1:  BEGIN → SELECT ... FOR UPDATE → UPDATE → COMMIT
                              ↓
Сессия 2:  BEGIN → SELECT ... FOR UPDATE  ← ЗАБЛОКИРОВАНА, ждёт Сессию 1
```

### Сценарий 3 — Уровень изоляции REPEATABLE READ

Защищает аналитический отчёт от фантомных изменений: повторный `SELECT COUNT(*)` внутри одной транзакции всегда возвращает одно и то же значение, даже если параллельная сессия в это время вставляет строки.

---

## 📈 Оптимизация запросов

Файл: [`migrations/V4__add_covering_indexes.sql`](migrations/V4__add_covering_indexes.sql)

Для Запросов 2 и 4 созданы **частичные покрывающие индексы**:

```sql
-- Для запроса 2: только активные новости
CREATE INDEX idx_news_active_covering
    ON news(source_id, news_id) WHERE status = 'active';

-- Для запроса 4: только новости-дубликаты
CREATE INDEX idx_news_duplicate_covering
    ON news(source_id, news_id) WHERE status = 'duplicate';
```

### Результаты измерений (медиана 5 прогонов, 3 млн строк)

| Запрос | До оптимизации | После оптимизации | Улучшение |
|---|---|---|---|
| Запрос 2 (`active`) | 378 ms | 369 ms | −2.4% |
| Запрос 4 (`duplicate`) | 221 ms | 217 ms | −1.8% |

**Размер индексов** (дополнительные расходы на диск):
- Таблица `news`: **973 MB**
- Индекс `idx_news_active_covering`: **62 MB** (~6.4% от таблицы)

> **Почему "частичный"?** Индекс содержит только строки с определённым статусом, а не всю таблицу. Это уменьшает его размер и ускоряет обновление индекса при вставке новостей с другими статусами.

---

## 📚 Словарь таблиц

<details>
<summary>Развернуть полный словарь атрибутов</summary>

| Таблица | Атрибут | Тип | Ограничения |
|---|---|---|---|
| `users` | `user_id` | BIGINT | PK, GENERATED ALWAYS AS IDENTITY |
| | `name` | VARCHAR(100) | NOT NULL |
| | `email` | VARCHAR(255) | NOT NULL, UNIQUE |
| | `password_hash` | VARCHAR(255) | NOT NULL |
| | `role` | VARCHAR(20) | NOT NULL, DEFAULT 'user', CHECK |
| | `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK |
| | `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `sources` | `source_id` | BIGINT | PK, GENERATED ALWAYS AS IDENTITY |
| | `name` | VARCHAR(150) | NOT NULL, UNIQUE |
| | `url` | VARCHAR(500) | NOT NULL |
| | `type` | VARCHAR(50) | NOT NULL, CHECK |
| | `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| | `update_frequency_minutes` | INT | NOT NULL, DEFAULT 30, CHECK > 0 |
| `news` | `news_id` | BIGINT | PK, GENERATED ALWAYS AS IDENTITY |
| | `source_id` | BIGINT | NOT NULL, FK → sources, ON DELETE RESTRICT |
| | `title` | VARCHAR(300) | NOT NULL, CHECK length > 0 |
| | `status` | VARCHAR(20) | NOT NULL, CHECK |
| | `published_at` | TIMESTAMPTZ | NOT NULL |
| `news_categories` | `(news_id, category_id)` | — | Составной PK, оба FK с CASCADE |
| `news_tags` | `(news_id, tag_id)` | — | Составной PK, оба FK с CASCADE |
| `favorites` | `favorite_id` | BIGINT | PK |
| | `(user_id, news_id)` | — | UNIQUE — нет повторных закладок |
| `subscriptions` | `subscription_id` | BIGINT | PK |
| | `category_id / source_id` | BIGINT | CHECK: ровно одно NOT NULL |

</details>

---

## 🔬 Дополнительные эксперименты

### Исследование блокировок

Моделирование `FOR UPDATE`-конкуренции + диагностика через `pg_locks` и `pg_stat_activity`:

```sql
SELECT blocked_locks.pid     AS blocked_pid,
       blocking_locks.pid    AS blocking_pid,
       blocked_activity.query AS blocked_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON ...
WHERE NOT blocked_locks.granted;
```

**Результат:** Зафиксированы заблокированный PID, блокирующий PID и текст ожидающего запроса.

### Воспроизведение и устранение Deadlock

Классический deadlock: Сессия 1 блокирует строку 1 и ждёт строку 2; Сессия 2 — наоборот.

**Сообщение PostgreSQL:**
```
deadlock detected
DETAIL: Process 37 waits for ShareLock on transaction 789; blocked by process 36.
        Process 36 waits for ShareLock on transaction 788; blocked by process 37.
```

**Решение:** Всегда обновлять строки в едином порядке (`ORDER BY news_id ASC`), чтобы исключить цикличность захвата ресурсов.

---

*PostgreSQL · Python 3.14 · psycopg2 · Faker · Flyway*
