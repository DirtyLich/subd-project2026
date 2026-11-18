# Журнал экспериментов спринта 4

## Окружение

- **Дата и время:** 2026-10-27 13:30 
- **Участники:** Студент курса по базам данных PostgreSQL
- **Версия Docker:** Docker version 29.1.3 (Compose v2.40.3)
- **Версия PostgreSQL:** PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2)
- **Commit проекта:** sprint-04-security-replication
- **Особенности конфигурации:**
  - `wal_level = replica`, `max_wal_senders = 10`, `wal_keep_size = 256MB`, `hot_standby = on`
  - Авторизация: `scram-sha-256`
  - Сеть: общая Docker-сеть `sprint04_database_network`
  - Персистентные тома: `sprint04_primary_data`, `sprint04_replica_data`, `sprint04_restore_data`

---

## Эксперимент 1. Репликация primary → replica

| Шаг | Команда или действие | Ожидаемый результат | Фактический результат | Доказательство |
|---:|---|---|---|---|
| 1 | Запуск стенда: `docker compose up -d primary replica` | Оба узла healthy | Узлы запущены, primary и replica в состоянии healthy | `sprint-04-postgresql-primary-1 Up (healthy)`<br>`sprint-04-postgresql-replica-1 Up (healthy)` |
| 2 | Проверка ролей через `01-primary-status.sql` и `03-replica-status.sql` | Primary: `is_in_recovery = false`; replica: `true` | Primary вернул `f`, Replica вернула `t`; статус репликации `streaming` | `pg_stat_replication: state = streaming, sync_state = async`<br>`pg_stat_wal_receiver: status = streaming, sender_host = primary` |
| 3 | Запись на primary: `02-create-probe.sql` | Запись создана, сгенерирован LSN | Запись успешно создана в `app.replication_probe`, `primary_wal_lsn = 0/3056880` | `INSERT 0 1`, `marker = probe-20261027-132527-196-189` |
| 4 | Чтение на replica: `04-read-probes.sql` | Та же запись найдена | Запись сгенерированная на primary сразу доступна на реплике | Запрос вернул `id = 1, marker = probe-20261027-132527-196-189` |
| 5 | Запись на replica: `02-create-probe.sql` | Операция отклонена | СУБД отклонила транзакцию модификации | `ERROR: cannot execute INSERT in a read-only transaction`<br>`ERROR: recovery is in progress` |

---

## Эксперимент 2. Остановка replica

| Шаг | Команда или действие | Наблюдение приложения | Наблюдение БД |
|---:|---|---|---|
| 1 | `docker compose stop replica` | Приложение, пишущее на primary, не испытывает сбоев и задержек; read-only запросы к реплике прерываются (`connection refused`) | `pg_stat_replication` на primary показывает 0 строк (клиент репликации отключился). Primary продолжает работать в штатном режиме. |
| 2 | Выполнить запись на primary: `INSERT INTO app.replication_probe` (маркер probe-2) | Запись создана успешно без задержек (т.к. репликация асинхронная) | WAL продвинулся: `current_wal_lsn` изменился с `0/3069E78` на `0/306A148`. Изменения накапливаются в локальном WAL primary (`wal_keep_size = 256MB`). |
| 3 | Запустить replica: `docker compose start replica` | Подключение приложения к read replica восстанавливается | Процесс `walreceiver` подключается к primary, запрашивает недостающий сегмент WAL. В `pg_stat_replication` статус снова переходит в `streaming`. |
| 4 | Проверить догон реплики: `04-read-probes.sql` | Приложение видит запись probe-2 на реплике | `last_replayed_lsn` на реплике догнал `0/306A180`. В таблице присутствуют обе записи (`id = 1` и `id = 2`). Lag равен 0. |

---

## Эксперимент 3. Остановка primary

| Шаг | Команда или действие | Наблюдение приложения | Наблюдение БД |
|---:|---|---|---|
| 1 | `docker compose stop primary` | Попытки записи приложением завершаются ошибкой недоступности мастера (`connection refused` на порт 55432) | Контейнер primary остановлен. На реплике в логах фиксируется потеря соединения с `sender_host=primary:5432`. |
| 2 | Проверить запись: попытка `INSERT` на replica | Приложение получает отказ при попытке записи | `ERROR: cannot execute INSERT in a read-only transaction` (реплика остаётся в режиме `read-only hot_standby`). |
| 3 | Проверить чтение replica: `SELECT * FROM app.news` | Аналитические и поисковые запросы чтения работают штатно без сбоев | Реплика доступна для чтения; данные согласованы на момент последней реплицированной транзакции. |
| 4 | Восстановить primary: `docker compose start primary` | Доступность мастера на запись восстанавливается | Primary успешно стартовал, перешёл в статус healthy, готов принимать входящие транзакции. |
| 5 | Проверить репликацию: `01-primary-status.sql` | Запись и чтение на обоих узлах функционируют в полном объёме | Реплика автоматически повторно подключилась к primary: `state = streaming`, `sent_lsn == replay_lsn = 0/306A1F8`. |

---

## Эксперимент 4. Backup и restore

| Шаг | Команда или действие | Ожидаемый результат | Фактический результат |
|---:|---|---|---|
| 1 | Создать backup: `pg_dump -U course_admin -d course_app -Fc -f /tmp/course_app.dump` и глобальные роли `pg_dumpall --globals-only` | Архивы созданы, ошибок нет | Создан бинарный сжатый кастомный дамп `course_app.dump` (TOC: 100 entries) и дамп ролей `globals.sql`. |
| 2 | Проверить архив: `pg_restore -l /tmp/course_app.dump` | Список объектов читается корректно | Список содержит метаданные схемы `app`, таблиц `news`, `users`, `favorites`, ограничений целостности и прав доступа `GRANT`. |
| 3 | Запустить чистый restore-узел: `docker compose --profile restore up -d restore` | Узел healthy на порту 55434 | Поднят независимый чистый экземпляр PostgreSQL 17 с пустой БД `course_app_restored`. |
| 4 | Восстановить архив: применение `globals.sql` + `pg_restore -d course_app_restored --clean /tmp/course_app.dump` | Ошибок нет | Роли и все объекты БД развернуты в целевой базе с кодом возврата 0. |
| 5 | Проверить данные и ограничения: `05-integrity-check.sql` и `06-verify-domain-schema.sql` | Проверки пройдены | Все 10 доменных таблиц схемы `app`, первичные и внешние ключи, уникальные ограничения и RLS-политики восстановлены в полном объёме. |

---

## Итоги и обнаруженные ограничения

1. **Асинхронная потоковая репликация:**
   - Обеспечивает максимальную производительность записи на primary (отсутствует блокировка транзакций в ожидании подтверждения от реплики).
   - При внезапном сбое primary возможен минимальный replication lag (RPO > 0), поэтому для аналитических задач рекомендуется направить тяжелые запросы на реплику (`port 55433`), разгружая мастер.
2. **Безопасность ролей и принцип наименьших привилегий:**
   - Роль `course_app` изолирована от схемы `public` и системных представлений (`pg_shadow`), лишена прав суперпользователя и DDL, что исключает возможность деструктивных изменений структуры БД через приложение.
   - Роль `course_analyst` строго ограничена правами `SELECT` и может безопасно использоваться для BI-систем и аналитики.
3. **Восстановление в чистый инстанс:**
   - При использовании `pg_dump` дампается только содержимое конкретной базы. Для гарантированного восстановления в чистый кластер требуется предварительный перенос глобальных ролей кластера через `pg_dumpall --globals-only`.
