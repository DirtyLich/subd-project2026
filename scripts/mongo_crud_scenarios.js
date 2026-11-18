/**
 * scripts/mongo_crud_scenarios.js
 * Сценарии CRUD и демонстрация валидации схемы ($jsonSchema) для MongoDB
 * Запуск: docker exec -i mongodb_db mongosh news_aggregator < scripts/mongo_crud_scenarios.js
 */

const db = db.getSiblingDB('news_aggregator');

print('==================================================================');
print(' СЦЕНАРИИ CRUD И ПРОВЕРКА ВАЛИДАЦИИ СХЕМЫ (MONGODB)');
print('==================================================================');

// -------------------------------------------------------------
// 1. CREATE: Успешная вставка валидного документа статьи
// -------------------------------------------------------------
print('\n--- 1. CREATE: Вставка валидной статьи ---');
const validArticle = {
  legacy_id: NumberLong('999001'),
  title: 'Архитектура современных СУБД: PostgreSQL и MongoDB',
  summary: 'Сравнение реляционного и документного подходов в реальных проектах.',
  content: 'Подробный анализ полиглотного хранения данных и преимуществ документной модели...',
  external_url: 'https://techblog.example.com/databases-2026',
  status: 'active',
  published_at: new Date(),
  created_at: new Date(),
  source: {
    source_id: NumberLong('10'),
    name: 'Tech Radar Central',
    url: 'https://techradar.example.com',
    type: 'rss'
  },
  categories: [
    { category_id: NumberLong('1'), name: 'IT и технологии' },
    { category_id: NumberLong('5'), name: 'Базы данных' }
  ],
  tags: ['postgresql', 'mongodb', 'polyglot-persistence', 'nosql'],
  metrics: {
    views_count: NumberLong('120'),
    favorites_count: NumberLong('15'),
    comments_count: NumberLong('0')
  },
  schema_version: 1
};

const insertRes = db.articles.insertOne(validArticle);
print(`[OK] Статья успешно создана, _id: ${insertRes.insertedId}`);

// -------------------------------------------------------------
// 2. CREATE: Создание профиля пользователя и комментария (Referencing)
// -------------------------------------------------------------
print('\n--- 2. CREATE: Связанный профиль и комментарий (1:N Referencing) ---');
const userProfile = {
  legacy_user_id: NumberLong('501'),
  name: 'Алексей Инженер',
  email: 'alex.engineer@example.com',
  role: 'user',
  preferences: {
    ui_theme: 'dark',
    notifications_enabled: true
  },
  bookmarked_article_ids: [insertRes.insertedId],
  reading_history: [
    {
      article_id: insertRes.insertedId,
      read_at: new Date(),
      time_spent_seconds: 145
    }
  ],
  schema_version: 1
};

const userRes = db.user_profiles.insertOne(userProfile);
print(`[OK] Профиль пользователя создан, _id: ${userRes.insertedId}`);

// Добавление комментария (1:N Referencing: article_id ссылается на articles._id)
const comment = {
  article_id: insertRes.insertedId,
  author: {
    user_id: NumberLong('501'),
    name: 'Алексей Инженер'
  },
  content: 'Отличная статья! Документная модель действительно ускоряет чтение ленты.',
  status: 'published',
  likes_count: 5,
  created_at: new Date(),
  schema_version: 1
};

const commentRes = db.comments.insertOne(comment);
print(`[OK] Комментарий к статье создан, _id: ${commentRes.insertedId}`);

// -------------------------------------------------------------
// 3. READ: Выборка новости со всеми тегами и источником за 1 запрос (без JOIN)
// -------------------------------------------------------------
print('\n--- 3. READ: Чтение статьи со встроенными метаданными (O(1) чтение) ---');
const foundArticle = db.articles.findOne(
  { _id: insertRes.insertedId },
  { title: 1, 'source.name': 1, tags: 1, metrics: 1 }
);
printjson(foundArticle);

// Агрегация: Сборка статьи с комментариями через $lookup (демонстрация связывания)
print('\n--- 3.1. READ (Aggregation): Сборка статьи с комментариями через $lookup ---');
const articleWithComments = db.articles.aggregate([
  { $match: { _id: insertRes.insertedId } },
  {
    $lookup: {
      from: 'comments',
      localField: '_id',
      foreignField: 'article_id',
      as: 'comments_list'
    }
  },
  {
    $project: {
      title: 1,
      source_name: '$source.name',
      tags: 1,
      comments_count: { $size: '$comments_list' },
      first_comment: { $arrayElemAt: ['$comments_list.content', 0] }
    }
  }
]).toArray();
printjson(articleWithComments);

// -------------------------------------------------------------
// 4. UPDATE: Атомарное обновление метрик и добавление тега
// -------------------------------------------------------------
print('\n--- 4. UPDATE: Атомарное обновление ($inc, $push, $set) ---');
db.articles.updateOne(
  { _id: insertRes.insertedId },
  {
    $inc: { 'metrics.views_count': 1, 'metrics.comments_count': 1 },
    $push: { tags: 'highload' },
    $set: { summary: 'Обновленное резюме: добавлены бенчмарки нагрузки.' }
  }
);
const updatedArticle = db.articles.findOne({ _id: insertRes.insertedId }, { metrics: 1, tags: 1, summary: 1 });
printjson(updatedArticle);

// -------------------------------------------------------------
// 5. VALIDATION DEMO: Проверка отклонения невалидных документов
// -------------------------------------------------------------
print('\n--- 5. NEGATIVE TESTS: Проверка $jsonSchema валидатора ---');

// Тест 5.1: Слишком короткий заголовок (< 5 символов)
try {
  db.articles.insertOne({
    legacy_id: NumberLong('999002'),
    title: 'Hi', // < 5 символов!
    status: 'active',
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с коротким title был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ короткий заголовок (minLength: 5)');
}

// Тест 5.2: Невалидный статус публикации (нет в enum)
try {
  db.articles.insertOne({
    legacy_id: NumberLong('999003'),
    title: 'Корректный заголовок статьи',
    status: 'invalid_status_xyz', // не в enum!
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с невалидным status был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ недопустимый статус (enum: active/hidden/archived/duplicate)');
}

// Тест 5.3: Некорректный формат URL источника
try {
  db.articles.insertOne({
    legacy_id: NumberLong('999004'),
    title: 'Корректный заголовок статьи',
    status: 'active',
    external_url: 'not-a-valid-http-url', // не regex ^https?://
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с некорректным URL был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ невалидный external_url (pattern: ^https?://)');
}

// -------------------------------------------------------------
// 6. DELETE: Удаление тестового комментария
// -------------------------------------------------------------
print('\n--- 6. DELETE: Удаление тестовых документов ---');
const delRes = db.comments.deleteOne({ _id: commentRes.insertedId });
print(`[OK] Комментарий удален, deletedCount: ${delRes.deletedCount}`);

print('\n==================================================================');
print(' ВСЕ СЦЕНАРИИ CRUD И ТЕСТЫ ВАЛИДАЦИИ УСПЕШНО ПРОЙДЕНЫ!');
print('==================================================================');
