-- ============================================================================
-- Запрос 1: Формирование персональной ленты новостей
-- Бизнес-вопрос: Какие последние 20 активных новостей показать пользователю на основе его подписок (на источники или категории)?
-- Параметры: sub.user_id (ID пользователя, например = 3), n.status (статус новости = 'active'), LIMIT 20
-- Пример результата:
-- news_id | title                         | source_name     | published_at
-- --------+-------------------------------+-----------------+------------------------
-- 10450   | В мире технологий...          | TechNews        | 2023-10-09 12:00:00+00
-- 9921    | Новые открытия в физике...    | ScienceDaily    | 2023-10-09 11:30:00+00
-- ============================================================================
SELECT n.news_id, n.title, s.name AS source_name, n.published_at
FROM news n
JOIN sources s ON n.source_id = s.source_id
LEFT JOIN news_categories nc ON n.news_id = nc.news_id
JOIN subscriptions sub ON 
    (sub.source_id = n.source_id OR sub.category_id = nc.category_id)
WHERE sub.user_id = 3 AND n.status = 'active'
ORDER BY n.published_at DESC
LIMIT 20;

-- ============================================================================
-- Запрос 2: Аналитика активности источников
-- Бизнес-вопрос: Какие источники публикуют больше всего активных новостей (более 1000)? (Выявление самых продуктивных партнеров)
-- Параметры: n.status (= 'active'), HAVING COUNT > 1000
-- Пример результата:
-- source_name       | active_news_count
-- ------------------+-------------------
-- РИА Новости       | 45030
-- Lenta.ru          | 32100
-- ============================================================================
SELECT s.name AS source_name, COUNT(n.news_id) AS active_news_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'active'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 1000
ORDER BY active_news_count DESC;

-- ============================================================================
-- Запрос 3: Популярные темы (теги)
-- Бизнес-вопрос: Какие 10 тегов чаще всего встречаются в активных новостях? (Для формирования облака тегов)
-- Параметры: n.status (= 'active'), LIMIT 10
-- Пример результата:
-- tag_name          | usage_count
-- ------------------+-------------
-- ИИ                | 15200
-- Экономика         | 14150
-- ============================================================================
SELECT t.name AS tag_name, COUNT(nt.news_id) AS usage_count
FROM tags t
JOIN news_tags nt ON t.tag_id = nt.tag_id
JOIN news n ON nt.news_id = n.news_id
WHERE n.status = 'active'
GROUP BY t.tag_id, t.name
ORDER BY usage_count DESC
LIMIT 10;

-- ============================================================================
-- Запрос 4: Мониторинг источников спама/дубликатов
-- Бизнес-вопрос: Какие источники часто (более 100 раз) публикуют дубликаты новостей? (Для понижения рейтинга источника)
-- Параметры: n.status (= 'duplicate'), HAVING COUNT > 100
-- Пример результата:
-- source_name       | duplicate_count
-- ------------------+-----------------
-- SpamNews24        | 1500
-- CopyPasteDaily    | 450
-- ============================================================================
SELECT s.name AS source_name, COUNT(n.news_id) AS duplicate_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'duplicate'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 100
ORDER BY duplicate_count DESC;

-- ============================================================================
-- Запрос 5: Рейтинг вовлеченности пользователей
-- Бизнес-вопрос: Топ-5 пользователей, которые добавили больше всего новостей в избранное? (Для выдачи бейджей "Самый активный")
-- Параметры: LIMIT 5
-- Пример результата:
-- user_name         | email               | favorites_count
-- ------------------+---------------------+-----------------
-- Иван Иванов       | ivan@example.com    | 45
-- Петр Петров       | petr@example.com    | 42
-- ============================================================================
SELECT u.name AS user_name, u.email, COUNT(f.favorite_id) AS favorites_count
FROM users u
JOIN favorites f ON u.user_id = f.user_id
GROUP BY u.user_id, u.name, u.email
ORDER BY favorites_count DESC
LIMIT 5;