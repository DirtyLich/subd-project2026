const appDbName = process.env.MONGO_APP_DATABASE || 'news_aggregator';
const appDb = db.getSiblingDB(appDbName);

print(`--- Инициализация доменной схемы в Replica Set: ${appDbName} ---`);

// 1. Коллекция articles
if (!appDb.getCollectionNames().includes('articles')) {
  appDb.createCollection('articles', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['title', 'source', 'status', 'published_at', 'schema_version'],
        properties: {
          _id: { bsonType: 'objectId' },
          legacy_id: { bsonType: ['int', 'long'] },
          title: { bsonType: 'string', minLength: 5, maxLength: 300 },
          summary: { bsonType: ['string', 'null'] },
          content: { bsonType: ['string', 'null'] },
          external_url: { bsonType: 'string', pattern: '^https?://.+' },
          status: { enum: ['active', 'hidden', 'duplicate', 'archived'] },
          published_at: { bsonType: 'date' },
          created_at: { bsonType: 'date' },
          source: {
            bsonType: 'object',
            required: ['source_id', 'name'],
            properties: {
              source_id: { bsonType: ['int', 'long'] },
              name: { bsonType: 'string', minLength: 2 },
              url: { bsonType: 'string' },
              type: { bsonType: 'string' }
            }
          },
          categories: {
            bsonType: 'array',
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
            items: { bsonType: 'string' }
          },
          metrics: {
            bsonType: 'object',
            properties: {
              views_count: { bsonType: ['int', 'long'] },
              favorites_count: { bsonType: ['int', 'long'] },
              comments_count: { bsonType: ['int', 'long'] }
            }
          },
          schema_version: { bsonType: 'int', minimum: 1 }
        }
      }
    }
  });
}

// 2. Коллекция user_profiles
if (!appDb.getCollectionNames().includes('user_profiles')) {
  appDb.createCollection('user_profiles', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['legacy_user_id', 'email', 'schema_version'],
        properties: {
          _id: { bsonType: 'objectId' },
          legacy_user_id: { bsonType: ['int', 'long'] },
          name: { bsonType: 'string' },
          email: { bsonType: 'string', pattern: '^.+@.+\\..+$' },
          role: { enum: ['admin', 'editor', 'user', 'moderator'] },
          preferences: { bsonType: 'object' },
          bookmarked_article_ids: {
            bsonType: 'array',
            items: { bsonType: 'objectId' }
          },
          schema_version: { bsonType: 'int', minimum: 1 }
        }
      }
    }
  });
}

// 3. Коллекция comments
if (!appDb.getCollectionNames().includes('comments')) {
  appDb.createCollection('comments', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['article_id', 'content', 'created_at', 'schema_version'],
        properties: {
          _id: { bsonType: 'objectId' },
          article_id: { bsonType: 'objectId' },
          author: {
            bsonType: 'object',
            properties: {
              user_id: { bsonType: ['int', 'long'] },
              name: { bsonType: 'string' }
            }
          },
          content: { bsonType: 'string', minLength: 1, maxLength: 5000 },
          created_at: { bsonType: 'date' },
          schema_version: { bsonType: 'int', minimum: 1 }
        }
      }
    }
  });
}

// 4. Коллекция sync_metadata
if (!appDb.getCollectionNames().includes('sync_metadata')) {
  appDb.createCollection('sync_metadata');
}

// Индексы
appDb.articles.createIndex({ legacy_id: 1 }, { unique: true, sparse: true, name: 'idx_articles_legacy_id_unique' });
appDb.articles.createIndex({ status: 1, published_at: -1 }, { name: 'idx_articles_status_published' });
appDb.articles.createIndex({ tags: 1 }, { name: 'idx_articles_tags' });
appDb.articles.createIndex({ 'source.source_id': 1 }, { name: 'idx_articles_source_id' });
appDb.user_profiles.createIndex({ legacy_user_id: 1 }, { unique: true, name: 'idx_user_profiles_legacy_id' });
appDb.user_profiles.createIndex({ email: 1 }, { unique: true, name: 'idx_user_profiles_email' });
appDb.comments.createIndex({ article_id: 1, created_at: -1 }, { name: 'idx_comments_article_date' });
appDb.sync_metadata.createIndex({ pipeline_name: 1 }, { unique: true, name: 'idx_sync_metadata_pipeline' });

print('--- Доменная схема и индексы успешно созданы в Replica Set! ---');
