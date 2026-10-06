-- Миграция V4: Оптимизирующие покрывающие частичные индексы для аналитических запросов

-- Индекс для аналитики по активным публикациям (Запрос 2)
CREATE INDEX IF NOT EXISTS idx_news_active_covering 
ON news(source_id, news_id) 
WHERE status = 'active';

-- Индекс для мониторинга источников с дубликатами (Запрос 4)
CREATE INDEX IF NOT EXISTS idx_news_duplicate_covering 
ON news(source_id, news_id) 
WHERE status = 'duplicate';
