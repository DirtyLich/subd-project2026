CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('guest', 'user', 'editor', 'admin')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sources (
    source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    url VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('rss', 'api', 'web_scraping')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    update_frequency_minutes INT NOT NULL DEFAULT 30 CHECK (update_frequency_minutes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE tags (
    tag_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE news (
    news_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    title VARCHAR(300) NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT,
    content TEXT,
    external_url VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'hidden', 'duplicate', 'archived')),
    published_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE news_categories (
    news_id BIGINT NOT NULL REFERENCES news(news_id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(category_id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, category_id)
);

CREATE TABLE news_tags (
    news_id BIGINT NOT NULL REFERENCES news(news_id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, tag_id)
);

CREATE TABLE favorites (
    favorite_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    news_id BIGINT NOT NULL REFERENCES news(news_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_favorite_news UNIQUE (user_id, news_id)
);

CREATE TABLE subscriptions (
    subscription_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id BIGINT REFERENCES categories(category_id) ON DELETE CASCADE,
    source_id BIGINT REFERENCES sources(source_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_subscription_target CHECK (
        (category_id IS NOT NULL AND source_id IS NULL) OR 
        (category_id IS NULL AND source_id IS NOT NULL)
    ),
    CONSTRAINT unique_user_category_sub UNIQUE (user_id, category_id),
    CONSTRAINT unique_user_source_sub UNIQUE (user_id, source_id)
);