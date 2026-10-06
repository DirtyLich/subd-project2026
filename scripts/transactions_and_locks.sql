BEGIN;

-- Шаг 1: Выключаем источник новостей
UPDATE sources SET is_active = false WHERE source_id = 5;

-- Шаг 2: Прячем все его активные новости в архив
UPDATE news SET status = 'archived' WHERE source_id = 5 AND status = 'active';

-- Шаг 3: Удаляем подписки пользователей на этот источник
DELETE FROM subscriptions WHERE source_id = 5;

-- Шаг 4: Подтверждаем транзакцию
COMMIT;