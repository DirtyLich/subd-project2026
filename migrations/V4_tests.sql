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