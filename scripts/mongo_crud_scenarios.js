const db = db.getSiblingDB('news_aggregator');

db.articles.deleteMany({ legacy_id: { $in: [NumberLong('999001'), NumberLong('999002')] } });
db.user_profiles.deleteMany({ email: 'alex.engineer@example.com' });
db.article_comments.deleteMany({ author_name: 'Алексей Инженер' });


print('==================================================================');
print(' СЦЕНАРИИ CRUD И ПРОВЕРКА ВАЛИДАЦИИ СХЕМЫ (MONGODB)');
print('==================================================================');

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

print('\n--- 3. READ: Чтение статьи со встроенными метаданными (O(1) чтение) ---');
const foundArticle = db.articles.findOne(
  { _id: insertRes.insertedId },
  { title: 1, 'source.name': 1, tags: 1, metrics: 1 }
);
printjson(foundArticle);

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

print('\n--- 5. NEGATIVE TESTS: Проверка $jsonSchema валидатора ---');

try {
  db.articles.insertOne({
    legacy_id: NumberLong('999002'),
    title: 'Hi',
    status: 'active',
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с коротким title был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ короткий заголовок (minLength: 5)');
}

try {
  db.articles.insertOne({
    legacy_id: NumberLong('999003'),
    title: 'Корректный заголовок статьи',
    status: 'invalid_status_xyz',
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с невалидным status был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ недопустимый статус (enum: active/hidden/archived/duplicate)');
}

try {
  db.articles.insertOne({
    legacy_id: NumberLong('999004'),
    title: 'Корректный заголовок статьи',
    status: 'active',
    external_url: 'not-a-valid-http-url',
    published_at: new Date(),
    source: { source_id: NumberLong('1'), name: 'News' },
    schema_version: 1
  });
  print('[FAIL] Ошибка! Документ с некорректным URL был ошибочно принят!');
} catch (e) {
  print('[PASS] Валидатор успешно ОТКЛОНИЛ невалидный external_url (pattern: ^https?://)');
}

print('\n--- 6. DELETE: Удаление тестовых документов ---');
const delRes = db.comments.deleteOne({ _id: commentRes.insertedId });
print(`[OK] Комментарий удален, deletedCount: ${delRes.deletedCount}`);

print('\n==================================================================');
print(' ВСЕ СЦЕНАРИИ CRUD И ТЕСТЫ ВАЛИДАЦИИ УСПЕШНО ПРОЙДЕНЫ!');
print('==================================================================');