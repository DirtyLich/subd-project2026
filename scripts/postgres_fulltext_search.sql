\pset pager off

\echo '=================================================================='
\echo ' 1. СОЗДАНИЕ ОПТИМИЗИРОВАННОГО GIN-ИНДЕКСА ДЛЯ ПОЛНОТЕКСТОВОГО ПОИСКА'
\echo '=================================================================='

CREATE INDEX IF NOT EXISTS idx_news_fts_gin 
ON news USING gin (
    to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(summary, ''))
);

\echo '[OK] GIN-индекс idx_news_fts_gin готов к поиску.'

\echo ''
\echo '=================================================================='
\echo ' 2. ПОЛНОТЕКСТОВЫЙ ПОИСК С МОРФОЛОГИЕЙ, РАНЖИРОВАНИЕМ И ПОДСВЕТКОЙ'
\echo '=================================================================='

WITH search_query AS (
    SELECT to_tsquery('russian', 'торговля | военный | технология') AS query
)
SELECT 
    n.news_id,
    n.title,
    ROUND(ts_rank(
        to_tsvector('russian', coalesce(n.title, '') || ' ' || coalesce(n.summary, '')), 
        sq.query
    )::numeric, 4) AS relevance_rank,
    ts_headline(
        'russian', 
        coalesce(n.summary, n.title), 
        sq.query, 
        'StartSel=<b>, StopSel=</b>, MinWords=5, MaxWords=25'
    ) AS snippet_highlight
FROM news n, search_query sq
WHERE to_tsvector('russian', coalesce(n.title, '') || ' ' || coalesce(n.summary, '')) @@ sq.query
ORDER BY relevance_rank DESC, n.published_at DESC
LIMIT 5;

\echo ''
\echo '=================================================================='
\echo ' 3. ПЛАН ВЫПОЛНЕНИЯ ЗАПРОСА (EXPLAIN ANALYZE)'
\echo '=================================================================='

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    n.news_id,
    n.title,
    ts_rank(
        to_tsvector('russian', coalesce(n.title, '') || ' ' || coalesce(n.summary, '')), 
        to_tsquery('russian', 'торговля')
    ) AS rank
FROM news n
WHERE to_tsvector('russian', coalesce(n.title, '') || ' ' || coalesce(n.summary, '')) @@ to_tsquery('russian', 'торговля')
ORDER BY rank DESC
LIMIT 5;

\echo ''
\echo '=================================================================='
\echo ' 4. АРХИТЕКТУРНЫЙ АНАЛИЗ: ОГРАНИЧЕНИЯ FTS В POSTGRESQL ДЛЯ ПРОЕКТА'
\echo '=================================================================='
