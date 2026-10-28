-- ============================================================================
-- 02-create-domain-schema-and-rls.sql
-- Инициализация доменной схемы новостного агрегатора и политик Row-Level Security (RLS)
-- ============================================================================

\connect course_app

SET search_path = app, public;

-- 1. Таблицы предметной области в схеме app
CREATE TABLE IF NOT EXISTS app.users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('guest', 'user', 'editor', 'admin')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.sources (
    source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    url VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('rss', 'api', 'web_scraping')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    update_frequency_minutes INT NOT NULL DEFAULT 30 CHECK (update_frequency_minutes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS app.tags (
    tag_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS app.news (
    news_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES app.sources(source_id) ON DELETE RESTRICT,
    title VARCHAR(300) NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT,
    content TEXT,
    external_url VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'hidden', 'duplicate', 'archived')),
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.news_categories (
    news_id BIGINT NOT NULL REFERENCES app.news(news_id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES app.categories(category_id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, category_id)
);

CREATE TABLE IF NOT EXISTS app.news_tags (
    news_id BIGINT NOT NULL REFERENCES app.news(news_id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES app.tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, tag_id)
);

CREATE TABLE IF NOT EXISTS app.favorites (
    favorite_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app.users(user_id) ON DELETE CASCADE,
    news_id BIGINT NOT NULL REFERENCES app.news(news_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_favorite_news UNIQUE (user_id, news_id)
);

CREATE TABLE IF NOT EXISTS app.subscriptions (
    subscription_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app.users(user_id) ON DELETE CASCADE,
    category_id BIGINT REFERENCES app.categories(category_id) ON DELETE CASCADE,
    source_id BIGINT REFERENCES app.sources(source_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_subscription_target CHECK (
        (category_id IS NOT NULL AND source_id IS NULL) OR 
        (category_id IS NULL AND source_id IS NOT NULL)
    ),
    CONSTRAINT unique_user_category_sub UNIQUE (user_id, category_id),
    CONSTRAINT unique_user_source_sub UNIQUE (user_id, source_id)
);

-- Индексы для ускорения
CREATE INDEX IF NOT EXISTS idx_news_status_published ON app.news(status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON app.favorites(user_id);

-- 2. Настройка прав для ролей приложения и аналитика
GRANT USAGE ON SCHEMA app TO course_app, course_analyst;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO course_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO course_app;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO course_analyst;

-- 3. Настройка Row-Level Security (RLS) — пункт "Желательно"
ALTER TABLE app.news ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.favorites ENABLE ROW LEVEL SECURITY;

-- Политика чтения для news:
-- 1) Обычные пользователи видят ТОЛЬКО опубликованные активные новости ('active').
-- 2) Если в сессии выставлена переменная `app.current_user_role = 'editor'` или `'admin'`,
--    видны ВСЕ новости (включая hidden, duplicate, archived).
CREATE POLICY news_select_policy ON app.news
FOR SELECT
USING (
    status = 'active'
    OR NULLIF(current_setting('app.current_user_role', true), '') IN ('editor', 'admin')
);

-- Политики модификации news для сервиса приложения и редакторов:
CREATE POLICY news_insert_policy ON app.news
FOR INSERT
WITH CHECK (
    current_user = 'course_app'
    OR NULLIF(current_setting('app.current_user_role', true), '') IN ('editor', 'admin')
);

CREATE POLICY news_update_policy ON app.news
FOR UPDATE
USING (
    current_user = 'course_app'
    OR NULLIF(current_setting('app.current_user_role', true), '') IN ('editor', 'admin')
);

CREATE POLICY news_delete_policy ON app.news
FOR DELETE
USING (
    current_user = 'course_app'
    OR NULLIF(current_setting('app.current_user_role', true), '') IN ('editor', 'admin')
);

-- Политика для favorites:
-- Пользователь может видеть и добавлять в избранное ТОЛЬКО свои записи:
CREATE POLICY favorites_isolation_policy ON app.favorites
FOR ALL
USING (
    user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint
    OR NULLIF(current_setting('app.current_user_role', true), '') = 'admin'
)
WITH CHECK (
    user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint
    OR NULLIF(current_setting('app.current_user_role', true), '') = 'admin'
);

-- 4. Заполнение базовыми данными предметной области
INSERT INTO app.sources (name, url, type, is_active, update_frequency_minutes) VALUES
('Tech Radar', 'https://techradar.com/rss', 'rss', true, 15),
('OpenNews API', 'https://api.opennews.org/v1', 'api', true, 30),
('SpamDaily', 'https://spamdaily.net/feed', 'rss', false, 120);

INSERT INTO app.categories (name, description) VALUES
('IT и технологии', 'Новости сферы высоких технологий и ПО'),
('Наука', 'Открытия и научные исследования');

INSERT INTO app.users (name, email, password_hash, role, status) VALUES
('Иван Пользователь', 'ivan@user.local', 'hash_ivan', 'user', 'active'),
('Мария Редактор', 'maria@editor.local', 'hash_maria', 'editor', 'active'),
('Алексей Заблокирован', 'alex@user.local', 'hash_alex', 'user', 'blocked');

INSERT INTO app.news (source_id, title, summary, external_url, status, published_at) VALUES
(1, 'Релиз PostgreSQL 17', 'Вышла новая стабильная версия СУБД с улучшениями вакуума и репликации', 'https://postgresql.org/news/17', 'active', now() - interval '1 hour'),
(1, 'Черновик: будущие тренды СУБД', 'Внутренний черновик статьи, пока не опубликован', 'https://draft.local/1', 'hidden', now()),
(2, 'Дубликат новости об ИИ', 'Повторяющаяся публикация', 'https://dup.local/2', 'duplicate', now() - interval '2 days'),
(1, 'Архивная статья 2024 года', 'Старая новость в архиве', 'https://archive.local/3', 'archived', now() - interval '1 year');

INSERT INTO app.favorites (user_id, news_id) VALUES
(1, 1);
