/**
 * mongo/init/01-init-schema.js
 * Спринт 5: Инициализация документной модели MongoDB
 * Коллекции: articles, user_profiles, comments, sync_metadata
 * Включает: $jsonSchema валидацию типов, обязательных полей, бизнес-правил и индексы.
 */

const dbName = 'news_aggregator';
const db = db.getSiblingDB(dbName);

print(`--- Инициализация базы данных: ${dbName} ---`);

// ============================================================================
// 1. Коллекция: articles (Статьи / Витрина новостей)
// Решение: Embedding для источника (source), категорий и тегов (M:N).
// ============================================================================
db.createCollection('articles', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['title', 'source', 'status', 'published_at', 'schema_version'],
      properties: {
        _id: { bsonType: 'objectId' },
        legacy_id: {
          bsonType: ['int', 'long'],
          description: 'Идентификатор news_id из PostgreSQL для идемпотентного backfill'
        },
        title: {
          bsonType: 'string',
          minLength: 5,
          maxLength: 300,
          description: 'Бизнес-правило 1: Заголовок от 5 до 300 символов'
        },
        summary: {
          bsonType: ['string', 'null'],
          description: 'Краткое резюме статьи'
        },
        content: {
          bsonType: ['string', 'null'],
          description: 'Полный текст публикации'
        },
        external_url: {
          bsonType: 'string',
          pattern: '^https?://.+',
          description: 'Бизнес-правило 2: Валидный веб-URL источника'
        },
        status: {
          enum: ['active', 'hidden', 'duplicate', 'archived'],
          description: 'Бизнес-правило 3: Допустимый жизненный цикл статьи'
        },
        published_at: {
          bsonType: 'date',
          description: 'Дата и время публикации'
        },
        created_at: {
          bsonType: 'date',
          description: 'Дата добавления в агрегатор'
        },
        source: {
          bsonType: 'object',
          required: ['source_id', 'name'],
          description: 'Пример Embedding: Метаданные источника встроены в статью',
          properties: {
            source_id: { bsonType: ['int', 'long'] },
            name: { bsonType: 'string' },
            url: { bsonType: 'string' },
            type: { enum: ['rss', 'api', 'web_scraping'] }
          }
        },
        categories: {
          bsonType: 'array',
          description: 'Пример Embedding: Категории новости',
          items: {
            bsonType: 'object',
            required: ['category_id', 'name'],
            properties: {
              category_id: { bsonType: ['int', 'long'] },
              name: { bsonType: 'string' }
            }
          }
        },
        tags: {
          bsonType: 'array',
          maxItems: 20,
          description: 'Пример Embedding связи M:N: Список тегов статьи (не более 20)',
          items: {
            bsonType: 'string'
          }
        },
        metrics: {
          bsonType: 'object',
          properties: {
            views_count: { bsonType: ['int', 'long'], minimum: 0 },
            favorites_count: { bsonType: ['int', 'long'], minimum: 0 },
            comments_count: { bsonType: ['int', 'long'], minimum: 0 }
          }
        },
        schema_version: {
          bsonType: 'int',
          enum: [1],
          description: 'Версионирование схемы документа (паттерн Schema Versioning)'
        }
      }
    }
  },
  validationLevel: 'strict',
  validationAction: 'error'
});

// Индексы для articles
db.articles.createIndex({ legacy_id: 1 }, { unique: true, sparse: true, name: 'idx_articles_legacy_id_unique' });
db.articles.createIndex({ status: 1, published_at: -1 }, { name: 'idx_articles_status_published' });
db.articles.createIndex({ tags: 1 }, { name: 'idx_articles_tags' });
db.articles.createIndex({ 'source.source_id': 1 }, { name: 'idx_articles_source_id' });
db.articles.createIndex({ title: 'text', content: 'text' }, { name: 'idx_articles_text_search', default_language: 'russian' });


// ============================================================================
// 2. Коллекция: user_profiles (Профили пользователей и настройки)
// Решение: Referencing для закладок (M:N), Subset pattern для истории чтения.
// ============================================================================
db.createCollection('user_profiles', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'email', 'role', 'schema_version'],
      properties: {
        _id: { bsonType: 'objectId' },
        legacy_user_id: {
          bsonType: ['int', 'long'],
          description: 'Связь с primary key users в PostgreSQL'
        },
        name: {
          bsonType: 'string',
          minLength: 2,
          maxLength: 100
        },
        email: {
          bsonType: 'string',
          pattern: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$',
          description: 'Бизнес-правило: Валидный email'
        },
        role: {
          enum: ['user', 'editor', 'admin']
        },
        preferences: {
          bsonType: 'object',
          properties: {
            ui_theme: { enum: ['light', 'dark', 'system'] },
            notifications_enabled: { bsonType: 'bool' }
          }
        },
        bookmarked_article_ids: {
          bsonType: 'array',
          description: 'Пример Referencing связи M:N: Ссылки на сохраненные статьи',
          items: {
            bsonType: 'objectId'
          }
        },
        reading_history: {
          bsonType: 'array',
          maxItems: 50,
          description: 'Subset Pattern: Последние 50 прочитанных статей с метриками времени',
          items: {
            bsonType: 'object',
            required: ['article_id', 'read_at'],
            properties: {
              article_id: { bsonType: 'objectId' },
              read_at: { bsonType: 'date' },
              time_spent_seconds: { bsonType: 'int', minimum: 0 }
            }
          }
        },
        schema_version: {
          bsonType: 'int',
          enum: [1]
        }
      }
    }
  },
  validationLevel: 'strict',
  validationAction: 'error'
});

// Индексы для user_profiles
db.user_profiles.createIndex({ legacy_user_id: 1 }, { unique: true, sparse: true, name: 'idx_users_legacy_id_unique' });
db.user_profiles.createIndex({ email: 1 }, { unique: true, name: 'idx_users_email_unique' });


// ============================================================================
// 3. Коллекция: comments (Комментарии к статьям)
// Решение: Referencing (1:N) к статье через article_id.
// ============================================================================
db.createCollection('comments', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['article_id', 'author', 'content', 'status', 'created_at', 'schema_version'],
      properties: {
        _id: { bsonType: 'objectId' },
        article_id: {
          bsonType: 'objectId',
          description: 'Пример Referencing связи 1:N: Ссылка на родительскую статью'
        },
        author: {
          bsonType: 'object',
          required: ['user_id', 'name'],
          properties: {
            user_id: { bsonType: ['int', 'long'] },
            name: { bsonType: 'string' }
          }
        },
        content: {
          bsonType: 'string',
          minLength: 1,
          maxLength: 2000,
          description: 'Бизнес-правило: Комментарий от 1 до 2000 символов'
        },
        status: {
          enum: ['published', 'moderation', 'deleted'],
          description: 'Бизнес-правило: Статус модерации комментария'
        },
        likes_count: {
          bsonType: 'int',
          minimum: 0,
          description: 'Счетчик лайков'
        },
        created_at: {
          bsonType: 'date'
        },
        schema_version: {
          bsonType: 'int',
          enum: [1]
        }
      }
    }
  },
  validationLevel: 'strict',
  validationAction: 'error'
});

// Индексы для comments
db.comments.createIndex({ article_id: 1, created_at: -1 }, { name: 'idx_comments_article_date' });
db.comments.createIndex({ 'author.user_id': 1 }, { name: 'idx_comments_author' });


// ============================================================================
// 4. Коллекция: sync_metadata (Служебная коллекция для идемпотентного Backfill)
// Уровень "Восхитительно": Контроль повторного запуска и фиксация watermark
// ============================================================================
db.createCollection('sync_metadata');
db.sync_metadata.createIndex({ pipeline_name: 1 }, { unique: true });

print('--- Инициализация коллекций, валидаторов и индексов успешно завершена! ---');
