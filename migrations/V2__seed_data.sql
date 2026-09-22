-- V2__seed_data.sql: Заполнение тестовыми данными

INSERT INTO users (name, email, password_hash, role, status) VALUES
('Иван Иванов', 'ivan@example.com', 'hash_pass_1', 'admin', 'active'),
('Петр Петров', 'petr@example.com', 'hash_pass_2', 'editor', 'active'),
('Алексей Сидоров', 'alex@example.com', 'hash_pass_3', 'user', 'active');

INSERT INTO sources (name, url, type, update_frequency_minutes) VALUES
('Хабр Новости', 'https://habr.com/ru/rss/all/all/', 'rss', 15),
('TechCrunch API', 'https://api.techcrunch.com/v1/news', 'api', 30);

INSERT INTO categories (name, description) VALUES
('IT и Технологии', 'Новости из мира IT и высоких технологий'),
('Бизнес', 'Финансы, стартапы и рынки');

INSERT INTO tags (name) VALUES
('PostgreSQL'),
('Docker'),
('AI');

INSERT INTO news (source_id, title, summary, content, external_url, published_at) VALUES
(1, 'Релиз PostgreSQL 16', 'Вышла новая версия популярной СУБД', 'Полный текст новости о PostgreSQL...', 'https://habr.com/post/1', NOW()),
(2, 'Обзор трендов AI 2026', 'Основные тренды искусственного интеллекта', 'Полный текст об AI...', 'https://techcrunch.com/post/2', NOW());

INSERT INTO news_categories (news_id, category_id) VALUES
(1, 1),
(2, 1),
(2, 2);

INSERT INTO news_tags (news_id, tag_id) VALUES
(1, 1),
(1, 2),
(2, 3);

INSERT INTO favorites (user_id, news_id) VALUES
(3, 1);

INSERT INTO subscriptions (user_id, category_id) VALUES
(3, 1);