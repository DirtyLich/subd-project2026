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
- [Спринт 4: Безопасность, репликация и восстановление](#-спринт-4-безопасность-репликация-и-восстановление)
- [Спринт 5: Расширенный SQL и документная модель MongoDB](#-спринт-5-расширенный-sql-и-документная-модель-mongodb)

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

## 🛡️ Спринт 4: Безопасность, репликация и восстановление

В рамках 4-го спринта развернут отказоустойчивый кластер PostgreSQL 17 с потоковой асинхронной репликацией, политиками Row-Level Security (RLS), разграничением прав по принципу наименьших привилегий и регламентом аварийного восстановления.

---

### 📦 Артефакты сдачи

1. **SQL-настройки ролей и политик:**
   - [`primary/init/01-initialize-cluster.sh`](primary/init/01-initialize-cluster.sh) — создание ролей `course_admin`, `course_app`, `course_analyst`, `replicator`, гранты и `ALTER DEFAULT PRIVILEGES`.
   - [`primary/init/02-create-domain-schema-and-rls.sql`](primary/init/02-create-domain-schema-and-rls.sql) — схема `app`, таблицы, индексы и политики Row-Level Security (RLS).
   - [`sql/07-roles-and-permissions-demo.sql`](sql/07-roles-and-permissions-demo.sql) — демонстрация разрешенных и запрещенных операций.
2. **Инструкция работы с секретами:**
   - Раздел [2. Работа с секретами](#2-работа-с-секретами) ниже.
   - [`.env.example`](.env.example) — безопасный шаблон переменных окружения.
   - [`.gitignore`](.gitignore) — изоляция `.env` и дампов БД от системы контроля версий.
3. **Команды backup и restore:**
   - Раздел [5. Резервное копирование и восстановление](#5-резервное-копирование-и-восстановление-backup--restore) ниже.
   - Раздел 3 в регламенте [`RUNBOOK.md`](RUNBOOK.md).
4. **Конфигурация репликации:**
   - [`compose.yaml`](compose.yaml) — конфигурация контейнеров `primary`, `replica`, `restore`.
   - [`replica/replica-entrypoint.sh`](replica/replica-entrypoint.sh) — скрипт инициализации реплики через `pg_basebackup`.
5. **Журнал экспериментов с отказами:**
   - [`EXPERIMENT-LOG.md`](EXPERIMENT-LOG.md) — 4 подробных эксперимента (репликация, остановка replica, остановка primary, backup/restore) с замерами LSN.
6. **Runbook восстановления:**
   - [`RUNBOOK.md`](RUNBOOK.md) — регламент дежурного инженера при сбоях (признаки проблемы, диагностика, восстановление, проверка целостности).

---

### 🎯 Выполненный объём требований ТЗ

- [x] **Обязательная часть (8 баллов):** выполнена в полном объеме (роли, запрет superuser для app, демонстрация прав, секреты вне git, backup & restore в чистый инстанс, primary + replica, 2 эксперимента с остановкой узлов, runbook).
- [x] **Желательная часть (2 выбранных пункта):**
  1. *Настроить RLS для естественного сценария предметной области* — политики для `app.news` (фильтрация по статусам active/editor) и `app.favorites` (персональная изоляция закладок по `user_id` с `WITH CHECK`).
  2. *Направить безопасные аналитические запросы на read replica* — запросы роли `course_analyst` направляются на порт реплики `55433` (hot standby).
- [x] **Восхитительная часть (1 выбранный пункт):**
  1. *Разработать автоматический тест набора ролей и политик RLS* — скрипт [`scripts/test_security_and_rls.py`](scripts/test_security_and_rls.py), покрывающий 18 проверок.

---

### 1. Архитектура ролей и привилегий

| Роль | Назначение | Права доступа | Ограничения безопасности |
|---|---|---|---|
| `course_admin` | Администратор кластера | Владелец схемы `app`, `SUPERUSER` | Полный административный доступ |
| `course_app` | Бэкенд приложения | `SELECT`, `INSERT`, `UPDATE`, `DELETE` на таблицы `app.*`, `USAGE` на sequences | `NOSUPERUSER`, `NOCREATEROLE`, запрет DDL (`CREATE/DROP TABLE`), запрет доступа к `pg_shadow` |
| `course_analyst` | BI и аналитика | Только `SELECT` на `app.*` | `NOSUPERUSER`, запрещены любые `INSERT/UPDATE/DELETE`, безопасное чтение с реплики |
| `replicator` | Сервис потоковой репликации | `REPLICATION`, `LOGIN` | `NOSUPERUSER`, `NOCREATEDB`, разрешено только чтение WAL-потока |

---

### 2. Работа с секретами

- **Изоляция:** Пароли и параметры подключения хранятся исключительно в файле `.env`, который добавлен в `.gitignore` и никогда не попадает в репозиторий.
- **Шаблон:** Для развертывания предоставлен безопасный файл `.env.example` с плейсхолдерами.
- **Инициализация:** Для старта скопируйте `.env.example` в `.env` и задайте надежные пароли:
  ```bash
  cp .env.example .env
  ```

---

### 3. Запуск стенда репликации

Инфраструктура описана в `compose.yaml`:
```bash
# Запуск Primary и Read-Replica узлов
docker compose -f compose.yaml up -d primary replica

# Проверка статуса (оба узла должны быть healthy)
docker compose -f compose.yaml ps
```

- **Primary:** `127.0.0.1:55432`
- **Replica:** `127.0.0.1:55433` (read-only, hot standby)
- **Restore Node:** `127.0.0.1:55434` (профиль `restore`)

---

### 4. Политики Row-Level Security (RLS) — Пункт "Желательно" №1

В схеме `app` включен механизм RLS для двух сущностей предметной области:
1. **`app.news` (видимость новостей):**
   - Обычный читатель (`app.current_user_role = 'user'`) видит исключительно опубликованные новости со статусом `active`.
   - Редакторы и администраторы (`app.current_user_role = 'editor'`) имеют доступ ко всем новостям, включая черновики (`hidden`), дубликаты (`duplicate`) и архивные статьи (`archived`).
2. **`app.favorites` (изоляция персональных закладок):**
   - Пользователь видит и может добавлять только свои закладки (`WHERE user_id = current_setting('app.current_user_id')`). Попытка прочесть или вставить чужой `user_id` блокируется политикой `WITH CHECK`.

---

### 5. Безопасные аналитические запросы на Read Replica — Пункт "Желательно" №2

- Аналитическая роль `course_analyst` обладает правами исключительно на чтение (`SELECT`).
- Все ресурсоемкие аналитические запросы направляются на выделенный узел Read Replica (`127.0.0.1:55433`), что полностью изолирует мастер-узел от аналитической нагрузки.
- Любые попытки записи или модификации схемы на реплике физически блокируются ядром PostgreSQL (`ERROR: cannot execute INSERT in a read-only transaction`).

---

### 6. Резервное копирование и восстановление (Backup & Restore)

```bash
# 1. Дамп ролей кластера
docker exec sprint-04-postgresql-primary-1 pg_dumpall -U course_admin --globals-only > globals.sql

# 2. Создание бинарного дампа базы данных (Custom Format)
docker exec sprint-04-postgresql-primary-1 pg_dump -U course_admin -d course_app -Fc -f /tmp/course_app.dump
docker cp sprint-04-postgresql-primary-1:/tmp/course_app.dump ./course_app.dump

# 3. Запуск чистого узла восстановления
docker compose -f compose.yaml --profile restore up -d restore

# 4. Восстановление в чистый инстанс
cat globals.sql | docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d postgres
docker cp ./course_app.dump sprint-04-postgresql-restore-1:/tmp/course_app.dump
docker exec -i sprint-04-postgresql-restore-1 pg_restore -U course_admin -d course_app_restored --clean /tmp/course_app.dump
```

---

### 7. Автоматическое тестирование — Пункт "Восхитительно" №1

В проекте разработан комплексный автоматический скрипт тестирования ролей, ограничений и RLS:
```bash
.venv/bin/python3 scripts/test_security_and_rls.py
# либо через активированное окружение:
# source .venv/bin/activate && python scripts/test_security_and_rls.py
```
Скрипт проверяет **18 утверждений безопасности**:
- [x] Проверка прав superuser для `course_admin`
- [x] Запрет суперпользовательских операций для `course_app` (DDL, `pg_shadow`, `CREATE ROLE`)
- [x] Read-only ограничения аналитика `course_analyst`
- [x] Направление аналитических запросов на Read-Replica (порт 55433)
- [x] Фильтрацию строк RLS для читателей и редакторов
- [x] Изоляцию персональных данных избранного и защиту от подделки `user_id`
- [x] Сквозную доставку транзакций через потоковую репликацию

---

### 🎬 Демонстрация и критерии приёмки

Быстрые команды для проверки при приёмке проекта:

1. **Запрет административной операции от имени приложения:**
   ```bash
   docker exec -i sprint-04-postgresql-primary-1 psql -U course_admin -d course_app -f /course/sql/07-roles-and-permissions-demo.sql
   ```
   *(Демонстрирует отказ при попытке DDL, CREATE ROLE и чтении `pg_shadow` от имени `course_app`)*.

2. **Поступление новой записи на Replica:**
   ```bash
   # Запись на Primary:
   docker exec -i sprint-04-postgresql-primary-1 psql -U course_admin -d course_app -f /course/sql/02-create-probe.sql
   # Чтение на Replica (запись появляется мгновенно):
   docker exec -i sprint-04-postgresql-replica-1 psql -U course_admin -d course_app -f /course/sql/04-read-probes.sql
   ```

3. **Восстановление базы из резервной копии в чистый инстанс:**
   ```bash
   docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d course_app_restored -f /course/sql/05-integrity-check.sql
   docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d course_app_restored -f /course/sql/06-verify-domain-schema.sql
   ```

4. **Полный сквозной автотест (все 18 проверок):**
   ```bash
   .venv/bin/python3 scripts/test_security_and_rls.py
   ```

---

*PostgreSQL 17 · Docker Compose · Streaming Replication · Row-Level Security · Python 3*

---

## 🍃 Спринт 5: Расширенный SQL и документная модель MongoDB

В рамках 5-го спринта расширена аналитическая часть реляционного ядра PostgreSQL (оконные функции, ранжирование, LAG, скользящие агрегаты, CTE) и спроектирована высокопроизводительная документная модель MongoDB 7.0 с гибридной архитектурой хранения (**Polyglot Persistence**).

### 📦 Артефакты сдачи Спринта 5

1. **Полный каталог SQL-запросов:**
   - [`scripts/advanced_sql_queries.sql`](scripts/advanced_sql_queries.sql) (и дубликат в [`scripts/business_queries.sql`](scripts/business_queries.sql)) — 8 содержательных аналитических запросов с полным покрытием требований ТЗ.
2. **Модель владения данными и SSOT:**
   - Раздел 2 в архитектурном журнале [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md). PostgreSQL — транзакционный источник истины (Single Source of Truth), MongoDB — денормализованная витрина быстрого чтения и интерактивности.
3. **Диаграмма и описание коллекций:**
   - Раздел 4 в [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md) — Mermaid-диаграмма сущностей, связь 1:N (комментарии) и связь M:N (теги и закладки).
4. **Решение Embedding vs Referencing:**
   - Раздел 5 в [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md) — обоснование выбора через характер чтения, обновлений и размер документа BSON (лимит 16 MB).
5. **Словарь коллекций и полей (Data Dictionary) — Пункт "Желательно" №2:**
   - Раздел 6 в [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md) — спецификация типов, индексов и бизнес-правил для `articles`, `user_profiles`, `comments`.
6. **Полнотекстовый поиск (FTS) в PostgreSQL и его ограничения — Пункт "Желательно" №3:**
   - [`scripts/postgres_fulltext_search.sql`](scripts/postgres_fulltext_search.sql) и раздел 11 в [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md) — функциональный GIN-индекс, стемминг русской морфологии, ранжирование `ts_rank`, подсветка `ts_headline` и анализ ограничений (Write Amplification, отсутствие опечаточного Fuzzy Search, многоязычность).
7. **Настройки Schema Validation ($jsonSchema):**
   - [`mongo/init/01-init-schema.js`](mongo/init/01-init-schema.js) — строгая валидация типов, обязательных полей и бизнес-правил (длина заголовка, regex URL, enum статусов).
7. **CRUD-сценарии с проверкой валидации:**
   - [`scripts/mongo_crud_scenarios.js`](scripts/mongo_crud_scenarios.js) — скрипт для `mongosh`.
   - [`scripts/test_mongo_crud.py`](scripts/test_mongo_crud.py) — автоматический автотест на Python (**13 проверок PASS**).
8. **Воспроизводимый Backfill данных с контролем повторного запуска — Пункт "Восхитительно" №1:**
   - [`scripts/backfill_pg_to_mongo.py`](scripts/backfill_pg_to_mongo.py) — потоковый перенос данных из PostgreSQL в MongoDB со встроенным кэшем справочников, batch upsert и фиксацией watermark в `sync_metadata`.
9. **Автоматическая проверка результатов SQL-запросов — Пункт "Желательно" №1:**
   - [`scripts/test_advanced_sql.py`](scripts/test_advanced_sql.py) — автотест на Python для всех 8 SQL-запросов (**21 проверка PASS**).
10. **Журнал архитектурных решений:**
    - [`ADR-SPRINT-05.md`](ADR-SPRINT-05.md) — полный документ с обоснованиями, сравнением с JSONB и стратегией Schema Versioning.

---

### 📊 Каталог 8 SQL-запросов (PostgreSQL)

| № | Бизнес-сценарий | Обязательное требование ТЗ | Конструкции SQL |
|---|---|---|---|
| **1** | Персональная лента по подпискам | Соединение нескольких таблиц (JOIN 4 таблиц) | `JOIN`, `WHERE`, `ORDER BY`, `LIMIT` |
| **2** | Аналитика активности источников | Агрегатная функция + фильтр | `JOIN`, `COUNT`, `GROUP BY`, `HAVING` |
| **3** | Топ-10 популярных тегов статьи | Агрегатная функция + JOIN 3 таблиц | `JOIN`, `COUNT`, `GROUP BY`, `ORDER BY` |
| **4** | Выявление спам-источников дубликатов | Агрегатная функция + фильтр | `JOIN`, `COUNT`, `GROUP BY`, `HAVING` |
| **5** | Топ-5 вовлеченных читателей | Агрегатная функция | `JOIN`, `COUNT`, `GROUP BY`, `ORDER BY` |
| **6** | Топ-3 свежих новости в каждой категории | **Оконная: Ранжирование (DENSE_RANK) + CTE** | `DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)`, `CTE` |
| **7** | Периодичность публикаций источников | **Оконная: Функция смещения (LAG) + CTE** | `LAG() OVER (PARTITION BY ... ORDER BY ...)`, `CTE`, `EPOCH` |
| **8** | Накопительный итог и скользящее среднее | **Накопительный и скользящий агрегат + CTE** | `SUM(...) OVER (ROWS UNBOUNDED PRECEDING)`, `AVG(...) OVER (ROWS 2 PRECEDING)`, `CTE` |

---

### 🚀 Быстрый запуск и демонстрация на защите (Спринт 5)

#### 1. Запуск инфраструктуры (PostgreSQL + MongoDB)
```bash
docker compose -f docker-compose.yml up -d
```

#### 2. Запуск автотеста всех 8 SQL-запросов (Пункт "Желательно" №1)
```bash
.venv/bin/python3 scripts/test_advanced_sql.py
```

#### 2.1. Демонстрация полнотекстового поиска FTS в PostgreSQL (Пункт "Желательно" №3)
```bash
docker exec -i postgres_db psql -U flyway_user -d mydb < scripts/postgres_fulltext_search.sql
```
*(Проверяет синтаксис, структуру колонок, диапазоны рангов `DENSE_RANK <= 3`, положительность интервалов `LAG` и монотонность накопительного итога — **21 из 21 PASS**)*.

#### 3. Демонстрация CRUD и валидации схемы MongoDB ($jsonSchema)
```bash
# Вариант А: Запуск в консоли mongosh
docker exec -i mongodb_db mongosh news_aggregator < scripts/mongo_crud_scenarios.js

# Вариант Б: Автоматический Python-тест (13 из 13 проверок PASS)
.venv/bin/python3 scripts/test_mongo_crud.py
```

#### 4. Запуск и проверка идемпотентного Backfill (Пункт "Восхитительно")
```bash
# 1. Потоковый перенос первой 1000 документов (со скоростью > 6000 док/сек):
.venv/bin/python3 scripts/backfill_pg_to_mongo.py --limit 1000

# 2. Проверка текущего статуса и watermark в коллекции sync_metadata:
.venv/bin/python3 scripts/backfill_pg_to_mongo.py --status

# 3. Дозагрузка следующей партии с сохраненного места:
.venv/bin/python3 scripts/backfill_pg_to_mongo.py --limit 1000

# 4. Доказательство идемпотентности (повторный накат существующих записей не плодит дубликаты):
.venv/bin/python3 scripts/backfill_pg_to_mongo.py --reset --limit 500
# (Выведет: Обработано: 500 | Добавлено: 0 | Обновлено (matched): 500)
```

---

*PostgreSQL 15/17 · MongoDB 7.0 · PyMongo · Docker Compose · JSON Schema Validation*
