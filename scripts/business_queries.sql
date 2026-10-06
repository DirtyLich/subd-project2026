SELECT n.news_id, n.title, s.name AS source_name, n.published_at
FROM news n
JOIN sources s ON n.source_id = s.source_id
LEFT JOIN news_categories nc ON n.news_id = nc.news_id
JOIN subscriptions sub ON 
    (sub.source_id = n.source_id OR sub.category_id = nc.category_id)
WHERE sub.user_id = 3 AND n.status = 'active'
ORDER BY n.published_at DESC
LIMIT 20;

SELECT s.name AS source_name, COUNT(n.news_id) AS active_news_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'active'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 1000
ORDER BY active_news_count DESC;

SELECT t.name AS tag_name, COUNT(nt.news_id) AS usage_count
FROM tags t
JOIN news_tags nt ON t.tag_id = nt.tag_id
JOIN news n ON nt.news_id = n.news_id
WHERE n.status = 'active'
GROUP BY t.tag_id, t.name
ORDER BY usage_count DESC
LIMIT 10;

SELECT s.name AS source_name, COUNT(n.news_id) AS duplicate_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'duplicate'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 100
ORDER BY duplicate_count DESC;

SELECT u.name AS user_name, u.email, COUNT(f.favorite_id) AS favorites_count
FROM users u
JOIN favorites f ON u.user_id = f.user_id
GROUP BY u.user_id, u.name, u.email
ORDER BY favorites_count DESC
LIMIT 5;