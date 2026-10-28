# 📖 Runbook: Эксплуатация, диагностика и восстановление PostgreSQL

Данный документ регламентирует действия дежурного инженера при возникновении сбоев в работе кластера PostgreSQL (Спринт 4).

---

## 1. Сценарий: Отставание или остановка репликации (Replication Lag / Down)

### Признаки проблемы
- На реплике отсутствуют свежие данные, записанные на primary.
- Мониторинг сообщает о росте `replication_lag_bytes` или `time_since_last_replayed_transaction > 60s`.
- В логах primary сообщение: `terminating connection due to administrator command` или отсутствие процесса `walsender`.

### Диагностические действия
1. **Проверить статус процессов репликации на Primary:**
   ```bash
   docker exec -i sprint-04-postgresql-primary-1 psql -U course_admin -d course_app -c "
   SELECT application_name, client_addr, state, sync_state, 
          pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
   FROM pg_stat_replication;"
   ```
   *Норма:* `state = streaming`, `lag_bytes ≈ 0`.

2. **Проверить статус приемника на Replica:**
   ```bash
   docker exec -i sprint-04-postgresql-replica-1 psql -U course_admin -d course_app -c "
   SELECT status, sender_host, latest_end_lsn, latest_end_time 
   FROM pg_stat_wal_receiver;"
   ```
   *Если 0 строк:* реплика отключена от мастера.

3. **Проверить логи контейнеров:**
   ```bash
   docker compose logs --tail=50 replica
   ```

### Действия по восстановлению
1. **Если контейнер реплики остановлен:**
   ```bash
   docker compose start replica
   ```
2. **Если нарушена сетевая связность или пароль:**
   Проверить сетевой пинг из реплики:
   ```bash
   docker exec -i sprint-04-postgresql-replica-1 pg_isready -h primary -p 5432
   ```
   Убедиться в совпадении `REPLICATION_PASSWORD` в `.env`.

3. **Если реплика безнадёжно отстала (WAL удален на мастере):**
   Пересоздать реплику через `pg_basebackup`:
   ```bash
   docker compose stop replica
   docker volume rm sprint04_replica_data
   docker compose up -d replica
   ```

### Проверка целостности
```bash
docker exec -i sprint-04-postgresql-primary-1 psql -U course_admin -d course_app -f /course/sql/02-create-probe.sql
docker exec -i sprint-04-postgresql-replica-1 psql -U course_admin -d course_app -f /course/sql/04-read-probes.sql
```
Маркер зонда должен появиться на реплике в течение 1 секунды.

---

## 2. Сценарий: Отказ Primary узла (Master Down / Failover)

### Признаки проблемы
- Приложение получает ошибки: `could not connect to server: Connection refused`.
- Запросы на запись (`INSERT`, `UPDATE`, `DELETE`) падают с 500 ошибкой.
- Read-only запросы к реплике (порт 55433) продолжают отвечать.

### Диагностические действия
1. **Проверить статус контейнера primary:**
   ```bash
   docker compose ps primary
   ```
2. **Проверить системный лог primary на наличие OOM-killer или паники ядра:**
   ```bash
   docker compose logs --tail=100 primary
   ```

### Действия по восстановлению
#### Вариант А: Быстрый перезапуск упавшего Primary (Soft Recovery)
```bash
docker compose start primary
docker exec -i sprint-04-postgresql-primary-1 pg_isready -U course_admin -d course_app
```

#### Вариант Б: Продвижение Replica до нового Primary (Failover)
Если мастер скомпрометирован или диск повреждён:
1. **Повысить реплику до мастера:**
   ```bash
   docker exec -i sprint-04-postgresql-replica-1 pg_ctl promote -D /var/lib/postgresql/data
   ```
2. **Проверить, что узел вышел из recovery:**
   ```bash
   docker exec -i sprint-04-postgresql-replica-1 psql -U course_admin -d course_app -c "SELECT pg_is_in_recovery();"
   ```
   *Результат:* должен вернуть `f` (false — теперь это мастер).
3. **Переключить строку подключения приложения:**
   Направить `DATABASE_URL` приложения на порт нового мастера (55433).

---

## 3. Сценарий: Восстановление из резервной копии (Disaster Recovery / Point in Time)

### Признаки необходимости
- Случайное повреждение схемы, выполнение неквалифицированного `DROP/TRUNCATE`, компрометация данных.

### Пошаговая процедура восстановления в чистый инстанс
1. **Экспорт глобальных ролей (на мастере):**
   ```bash
   docker exec -i sprint-04-postgresql-primary-1 pg_dumpall -U course_admin --globals-only > globals.sql
   ```
2. **Создание полного дампа БД:**
   ```bash
   docker exec -i sprint-04-postgresql-primary-1 pg_dump -U course_admin -d course_app -Fc -f /tmp/course_app.dump
   docker cp sprint-04-postgresql-primary-1:/tmp/course_app.dump ./course_app.dump
   ```
3. **Запуск чистого изолированного экземпляра `restore`:**
   ```bash
   docker compose --profile restore up -d restore
   ```
4. **Импорт ролей и данных в чистый узел:**
   ```bash
   # Импортируем роли:
   cat globals.sql | docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d postgres
   
   # Восстанавливаем саму БД:
   docker cp ./course_app.dump sprint-04-postgresql-restore-1:/tmp/course_app.dump
   docker exec -i sprint-04-postgresql-restore-1 pg_restore -U course_admin -d course_app_restored --clean --if-exists /tmp/course_app.dump
   ```

### Проверка целостности восстановленных данных
Выполнить тестовые наборы:
```bash
docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d course_app_restored -f /course/sql/05-integrity-check.sql
docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d course_app_restored -f /course/sql/06-verify-domain-schema.sql
docker exec -i sprint-04-postgresql-restore-1 psql -U course_admin -d course_app_restored -f /course/sql/07-roles-and-permissions-demo.sql
```
*Критерий успеха:* все таблицы на месте, RLS-политики активны, роли работают корректно.
