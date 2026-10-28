\pset pager off

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'app'
ORDER BY table_name;

SELECT news_id, title, status FROM app.news;
