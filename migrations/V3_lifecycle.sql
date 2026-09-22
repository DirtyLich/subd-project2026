INSERT INTO users (name, email, password_hash, role, status) 
VALUES ('Сергей Смирнов', 'sergey_v3@example.com', 'hash_pass_4', 'user', 'active')
ON CONFLICT (email) DO NOTHING;

UPDATE users 
SET name = 'Сергей Николаевич Смирнов' 
WHERE email = 'sergey_v3@example.com';

SELECT * FROM users WHERE email = 'sergey_v3@example.com';


INSERT INTO sources (name, url, type, update_frequency_minutes) 
VALUES ('TechCrunch V3', 'https://techcrunch.com/feed_v3_final/', 'rss', 30);

UPDATE sources 
SET update_frequency_minutes = 10 
WHERE name = 'TechCrunch V3';

SELECT * FROM sources WHERE name = 'TechCrunch V3';


INSERT INTO news (source_id, title, summary, content, external_url, published_at) 
VALUES (1, 'Новый стартап запустил ИИ V3', 'Краткое описание', 'Полный текст новости...', 'https://example.com/ai-startup-v3-final', NOW());

INSERT INTO news_categories (news_id, category_id) 
VALUES (1, 1) 
ON CONFLICT DO NOTHING;

SELECT n.title, s.name AS source 
FROM news n 
JOIN sources s ON n.source_id = s.source_id 
WHERE n.title = 'Новый стартап запустил ИИ V3';