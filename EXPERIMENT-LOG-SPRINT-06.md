# Журнал экспериментов MongoDB Replica Set (Спринт 6)

## Окружение

- **Дата и время проведения:** 2026-11-23 17:15 UTC+7
- **Участники Replica Set:**
  - `mongo1:27017` (priority 2, voting member)
  - `mongo2:27017` (priority 1, voting member)
  - `mongo3:27017` (priority 1, voting member)
- **Версия Docker:** 26.1 / Linux WSL2
- **Версия MongoDB:** 7.0 (WiredTiger Engine)
- **Replica Set name:** `rs0`
- **Клиентский драйвер:** Python `PyMongo 4.20.1`

---

## 1. Исходное состояние топологии

| Участник | Роль | Health | Priority | Состояние синхронизации |
|---|---|---:|---:|---|
| `mongo1:27017` | **PRIMARY** | 1.0 | 2 | Primary (Writable, oplog source) |
| `mongo2:27017` | **SECONDARY** | 1.0 | 1 | Replicating from mongo1 |
| `mongo3:27017` | **SECONDARY** | 1.0 | 1 | Replicating from mongo1 |

---

## 2. Контрольная запись и проверка репликации

- **Команда:** `db.replication_probe.insertOne({ marker: "failover_probe_...", createdAt: new Date(), writer: "test_pre_failover" }, { writeConcern: { w: "majority", j: true, wtimeout: 5000 } })`
- **Write Concern:** `{ w: "majority", j: true, wtimeout: 5000 }`
- **Результат:** Запись успешно зафиксирована в журнал Primary и размножена на большинство (кворум = 2 узла).
- **Чтение с Primary:** Мгновенный доступ $O(1)$.
- **Чтение с Secondary:** Через `secondaryPreferred` подтверждено наличие документа на `mongo2` и `mongo3`.

---

## 3. Остановка текущего Primary (Автоматизированный Failover)

Скрипт выполнения: [`scripts/sprint6_failover_test.py`](file:///mnt/c/Users/PC/OneDrive/Desktop/SQL/scripts/sprint6_failover_test.py)

| Время от старта | Действие или наблюдение | Доказательство в логе / статус |
|---|---|---|
| `00:00` | Зафиксирован текущий Primary | `client.primary -> ('mongo1', 27017)` |
| `00:00.1` | Выполнена остановка контейнера Primary | `docker stop mongo1` |
| `00:02.0` | Heartbeat таймаут (2 сек). Потеря связи с mongo1 | Оставшиеся узлы `mongo2` и `mongo3` фиксируют недоступность лидера |
| `00:05.0` | Начало выборов нового лидера (Election) | Узлы `mongo2` и `mongo3` образуют кворум (2/3). Голосование за новый term |
| `00:10.2` | **Выбран новый Primary** | `New Primary -> ('mongo2', 27017)` |
| `00:10.22` | **Приложение восстановило запись** | Запись `post_failover_...` сохранена драйвером без ручного вмешательства |

- **Продолжительность отсутствия Primary:** **10.22 секунды**.
- **Новый Primary:** `mongo2:27017`.
- **Поведение retryable writes:** Запросы от приложения во время смены лидера буферизовались драйвером, после чего запись была направлена новому Primary без потери транзакций.

---

## 4. Возврат остановленного участника в строй

- **Команда запуска:** `docker start mongo1`
- **Роль после возврата:** `SECONDARY` (синхронизируется по oplog с нового лидера `mongo2`).
- **Состояние кластера:**
  - `mongo1:27017`: `SECONDARY` (Health 1.0, uptime 3s)
  - `mongo2:27017`: `PRIMARY` (Health 1.0)
  - `mongo3:27017`: `SECONDARY` (Health 1.0)
- **Итоговая проверка:** Документы, созданные в период изоляции `mongo1`, автоматически реплицированы на `mongo1` через catch-up механизм oplog.

---

## 5. Итоги архитектурных тестов

1. **Отказоустойчивость:** Кворумная модель $N=3$, Majority $=2$ успешно защищает систему от выхода из строя любого одного сервера.
2. **Время сходимости:** Полное переключение приложения и выборы занимают $\approx 10$ секунд, что полностью укладывается в production SLA.
3. **Целостность данных:** Ни одна запись, подтвержденная с `w: "majority"`, не была потеряна или подвергнута откату (Zero Rollback).
