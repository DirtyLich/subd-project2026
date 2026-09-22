INSERT INTO users (name, email, password_hash, role, status) 
VALUES ('Сергей Смирнов', 'sergey_v3@example.com', 'hash_pass_4', 'user', 'active')
ON CONFLICT (email) DO NOTHING;

UPDATE users 
SET name = 'Сергей Николаевич Смирнов' 
WHERE email = 'sergey_v3@example.com';

SELECT * FROM users WHERE email = 'sergey_v3@example.com';


-- 2. Жизненный цикл сущности "Источник" (sources)
INSERT INTO sources (name, url, type, update_frequency_minutes) 
VALUES ('TechCrunch V3', 'https://techcrunch.com/feed_v3_final/', 'rss', 30);

UPDATE sources 
SET update_frequency_minutes = 10 
WHERE name = 'TechCrunch V3';

SELECT * FROM sources WHERE name = 'TechCrunch V3';


-- 3. Жизненный цикл сущности "Новость" (news)
INSERT INTO news (source_id, title, summary, content, external_url, published_at) 
VALUES (1, 'Новый стартап запустил ИИ V3', 'Краткое описание', 'Полный текст новости...', 'https://example.com/ai-startup-v3-final', NOW());

INSERT INTO news_categories (news_id, category_id) 
VALUES (1, 1) 
ON CONFLICT DO NOTHING;

SELECT n.title, s.name AS source 
FROM news n 
JOIN sources s ON n.source_id = s.source_id 
WHERE n.title = 'Новый стартап запустил ИИ V3';



-- НЕГАТИВНЫЕ ТЕСТЫ (5 ОГРАНИЧЕНИЙ ЦЕЛОСТНОСТИ)
-- Примечание: Закомментированы, так как вызывают намеренные ошибки в СУБД.

-- 1. Ограничение UNIQUE (дублирование уникального email)
-- INSERT INTO users (name, email, password_hash, role, status) VALUES ('Иван Клон', 'ivan@example.com', 'pass', 'user', 'active');

-- 2. Ограничение CHECK (указание недопустимой роли 'superadmin')
-- INSERT INTO users (name, email, password_hash, role, status) VALUES ('Петр', 'petr@example.com', 'pass', 'superadmin', 'active');

-- 3. Ограничение FOREIGN KEY (ссылка на несуществующий source_id = 9999)
-- INSERT INTO news (source_id, title, summary, content, external_url, published_at) VALUES (9999, 'Тест', 'Кратко', 'Текст', 'https://example.com/err', NOW());

-- 4. Ограничение NOT NULL (попытка вставить NULL в поле email)
-- INSERT INTO users (name, email, password_hash, role, status) VALUES ('Без почты', NULL, 'pass', 'user', 'active');

-- 5. Ограничение IDENTITY / PRIMARY KEY (попытка ручного ввода значенния в auto-increment поле)
-- INSERT INTO sources (source_id, name, url, type, update_frequency_minutes) VALUES (1, 'Дубликат', 'https://dup.com', 'rss', 15);