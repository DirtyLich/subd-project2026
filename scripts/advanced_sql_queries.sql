SELECT 
    n.news_id, 
    n.title, 
    s.name AS source_name, 
    n.published_at
FROM news n
JOIN sources s ON n.source_id = s.source_id
LEFT JOIN news_categories nc ON n.news_id = nc.news_id
JOIN subscriptions sub ON 
    (sub.source_id = n.source_id OR sub.category_id = nc.category_id)
WHERE sub.user_id = 3 AND n.status = 'active'
ORDER BY n.published_at DESC
LIMIT 20;

SELECT 
    s.name AS source_name, 
    COUNT(n.news_id) AS active_news_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'active'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 1000
ORDER BY active_news_count DESC;

SELECT 
    t.name AS tag_name, 
    COUNT(nt.news_id) AS usage_count
FROM tags t
JOIN news_tags nt ON t.tag_id = nt.tag_id
JOIN news n ON nt.news_id = n.news_id
WHERE n.status = 'active'
GROUP BY t.tag_id, t.name
ORDER BY usage_count DESC
LIMIT 10;

SELECT 
    s.name AS source_name, 
    COUNT(n.news_id) AS duplicate_count
FROM sources s
JOIN news n ON s.source_id = n.source_id
WHERE n.status = 'duplicate'
GROUP BY s.source_id, s.name
HAVING COUNT(n.news_id) > 100
ORDER BY duplicate_count DESC;

SELECT 
    u.name AS user_name, 
    u.email, 
    COUNT(f.favorite_id) AS favorites_count
FROM users u
JOIN favorites f ON u.user_id = f.user_id
GROUP BY u.user_id, u.name, u.email
ORDER BY favorites_count DESC
LIMIT 5;

WITH ranked_news AS (
    SELECT 
        c.category_id,
        c.name AS category_name,
        n.news_id,
        n.title,
        n.published_at,
        DENSE_RANK() OVER (
            PARTITION BY c.category_id 
            ORDER BY n.published_at DESC
        ) AS rank_in_category
    FROM categories c
    JOIN news_categories nc ON c.category_id = nc.category_id
    JOIN news n ON nc.news_id = n.news_id
    WHERE n.status = 'active'
)
SELECT 
    category_name, 
    rank_in_category, 
    news_id, 
    title, 
    published_at
FROM ranked_news
WHERE rank_in_category <= 3
ORDER BY category_name, rank_in_category;

WITH source_publications AS (
    SELECT 
        s.source_id,
        s.name AS source_name,
        n.news_id,
        n.title,
        n.published_at,
        LAG(n.published_at) OVER (
            PARTITION BY s.source_id 
            ORDER BY n.published_at
        ) AS prev_published_at
    FROM sources s
    JOIN news n ON s.source_id = n.source_id
    WHERE s.source_id IN (1, 2, 3) AND n.status = 'active'
)
SELECT 
    source_name,
    news_id,
    published_at,
    prev_published_at,
    ROUND(EXTRACT(EPOCH FROM (published_at - prev_published_at)) / 60.0, 2) AS interval_minutes
FROM source_publications
WHERE prev_published_at IS NOT NULL
ORDER BY source_name, published_at DESC
LIMIT 20;

WITH daily_source_stats AS (
    SELECT 
        s.source_id,
        s.name AS source_name,
        date_trunc('day', n.published_at)::date AS publication_date,
        COUNT(n.news_id) AS daily_news_count
    FROM sources s
    JOIN news n ON s.source_id = n.source_id
    WHERE s.source_id IN (1, 2, 3) AND n.status = 'active'
    GROUP BY s.source_id, s.name, date_trunc('day', n.published_at)::date
)
SELECT 
    source_name,
    publication_date,
    daily_news_count,
    SUM(daily_news_count) OVER (
        PARTITION BY source_id 
        ORDER BY publication_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total_news,
    ROUND(AVG(daily_news_count) OVER (
        PARTITION BY source_id 
        ORDER BY publication_date
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS moving_avg_3d
FROM daily_source_stats
ORDER BY source_name, publication_date
LIMIT 25;
