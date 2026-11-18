\pset pager off

\echo '========================================================'
\echo '1. ПРОВЕРКА АТРИБУТОВ РОЛЕЙ В КАТАЛОГЕ PG_ROLES'
\echo '========================================================'
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication
FROM pg_roles
WHERE rolname IN ('course_admin', 'course_app', 'course_analyst', 'replicator')
ORDER BY rolname;

\echo ''
\echo '========================================================'
\echo '2. ДЕМОНСТРАЦИЯ: РОЛЬ ПРИЛОЖЕНИЯ (course_app)'
\echo '========================================================'
SET ROLE course_app;
SELECT current_user AS active_role;

\echo '-- 2.1. Разрешено: чтение данных'
SELECT news_id, title, status FROM app.news ORDER BY news_id LIMIT 3;

\echo '-- 2.2. Разрешено: добавление данных (INSERT)'
INSERT INTO app.news (source_id, title, summary, external_url, status)
VALUES (1, 'Новость от course_app', 'Тест прав приложения', 'https://test.local/app1', 'active')
RETURNING news_id, title, status;

\echo '-- 2.3. Запрещено: DDL (создание таблицы)'
CREATE TABLE app.illegal_table (id int);

\echo '-- 2.4. Запрещено: создание ролей (администрирование)'
CREATE ROLE hacker WITH LOGIN PASSWORD '123';

\echo '-- 2.5. Запрещено: чтение системных хэшей паролей'
SELECT * FROM pg_shadow;

RESET ROLE;

\echo ''
\echo '========================================================'
\echo '3. ДЕМОНСТРАЦИЯ: РОЛЬ АНАЛИТИКА (course_analyst)'
\echo '========================================================'
SET ROLE course_analyst;
SELECT current_user AS active_role;

\echo '-- 3.1. Разрешено: аналитические запросы (SELECT)'
SELECT s.name, count(n.news_id) AS total_news
FROM app.sources s
LEFT JOIN app.news n ON s.source_id = n.source_id
GROUP BY s.name;

\echo '-- 3.2. Запрещено: изменение данных (INSERT)'
INSERT INTO app.news (source_id, title, external_url)
VALUES (1, 'Попытка аналитика', 'https://test.local');

\echo '-- 3.3. Запрещено: удаление данных (DELETE)'
DELETE FROM app.news WHERE news_id = 1;

RESET ROLE;

\echo ''
\echo '========================================================'
\echo '4. ДЕМОНСТРАЦИЯ: ROW-LEVEL SECURITY (RLS)'
\echo '========================================================'
SET ROLE course_app;

\echo '-- 4.1. Обычный пользователь (видит ТОЛЬКО active новости)'
SET app.current_user_role = 'user';
SELECT news_id, title, status FROM app.news ORDER BY news_id;

\echo '-- 4.2. Редактор (видит ВСЕ новости: active, hidden, duplicate, archived)'
SET app.current_user_role = 'editor';
SELECT news_id, title, status FROM app.news ORDER BY news_id;

\echo '-- 4.3. Изоляция избранного (favorites) по user_id'
SET app.current_user_id = '1';
SELECT favorite_id, user_id, news_id FROM app.favorites;

\echo '-- 4.4. Другой пользователь (user_id = 2) не видит чужие закладки'
SET app.current_user_id = '2';
SELECT favorite_id, user_id, news_id FROM app.favorites;

RESET ROLE;
RESET app.current_user_role;
RESET app.current_user_id;
