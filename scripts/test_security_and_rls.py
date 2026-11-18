#!/usr/bin/env python3
import os
import sys
import time
import psycopg2
from psycopg2 import errors

def load_env(env_path=".env"):
    config = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config

ENV = load_env()
DB_NAME = ENV.get("POSTGRES_DB", "course_app")
HOST = "127.0.0.1"
PRIMARY_PORT = int(ENV.get("PRIMARY_PORT", 55432))
REPLICA_PORT = int(ENV.get("REPLICA_PORT", 55433))

ADMIN_USER = ENV.get("POSTGRES_ADMIN_USER", "course_admin")
ADMIN_PASS = ENV.get("POSTGRES_ADMIN_PASSWORD", "SecureAdminPass2026!")

APP_USER = ENV.get("APPLICATION_USER", "course_app")
APP_PASS = ENV.get("APPLICATION_PASSWORD", "SecureAppPass2026!")

ANALYST_USER = ENV.get("ANALYST_USER", "course_analyst")
ANALYST_PASS = ENV.get("ANALYST_PASSWORD", "SecureAnalystPass2026!")

passed_tests = 0
failed_tests = 0

def log_test(title, success, detail=""):
    global passed_tests, failed_tests
    if success:
        passed_tests += 1
        print(f"  [\033[92mPASS\033[0m] {title} {detail}")
    else:
        failed_tests += 1
        print(f"  [\033[91mFAIL\033[0m] {title} {detail}")

def test_admin_role():
    print("\n--- 1. Тестирование роли Администратора (course_admin) ---")
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=ADMIN_USER, password=ADMIN_PASS, host=HOST, port=PRIMARY_PORT)
        cur = conn.cursor()
        cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s;", (ADMIN_USER,))
        is_super = cur.fetchone()[0]
        log_test("Администратор имеет права superuser", is_super)
        
        cur.execute("SELECT count(*) FROM app.news;")
        cnt = cur.fetchone()[0]
        log_test("Администратор имеет доступ к схеме app", cnt >= 0, f"(новостей: {cnt})")
        conn.close()
    except Exception as e:
        log_test("Подключение администратора", False, str(e))

def test_application_role():
    print("\n--- 2. Тестирование роли Приложения (course_app) ---")
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=APP_USER, password=APP_PASS, host=HOST, port=PRIMARY_PORT)
        cur = conn.cursor()
        
        # 2.1 Проверка NOSUPERUSER
        cur.execute("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = %s;", (APP_USER,))
        super_flag, createrole_flag = cur.fetchone()
        log_test("Приложение НЕ является superuser", not super_flag and not createrole_flag)
        
        # 2.2 Разрешено: SELECT
        cur.execute("SELECT count(*) FROM app.news;")
        log_test("Приложение: Разрешено чтение (SELECT) новостей", True)
        
        # 2.3 Разрешено: INSERT
        test_title = f"Автотест новости {int(time.time())}"
        cur.execute("""
            INSERT INTO app.news (source_id, title, summary, external_url, status)
            VALUES (1, %s, 'Summary autotest', 'https://autotest.local', 'active')
            RETURNING news_id;
        """, (test_title,))
        new_id = cur.fetchone()[0]
        conn.commit()
        log_test("Приложение: Разрешена вставка (INSERT) новостей", True, f"(news_id={new_id})")
        
        # 2.4 Запрещено: DDL (CREATE TABLE)
        ddl_blocked = False
        try:
            cur.execute("CREATE TABLE app.should_fail (id int);")
        except errors.InsufficientPrivilege:
            ddl_blocked = True
            conn.rollback()
        log_test("Приложение: ЗАПРЕЩЕНО DDL (CREATE TABLE)", ddl_blocked, "(Код: InsufficientPrivilege)")
        
        # 2.5 Запрещено: создание ролей
        role_blocked = False
        try:
            cur.execute("CREATE ROLE malicious_user WITH PASSWORD '123';")
        except errors.InsufficientPrivilege:
            role_blocked = True
            conn.rollback()
        log_test("Приложение: ЗАПРЕЩЕНО администрирование (CREATE ROLE)", role_blocked)

        # 2.6 Запрещено: чтение секретов pg_shadow
        shadow_blocked = False
        try:
            cur.execute("SELECT * FROM pg_shadow;")
        except errors.InsufficientPrivilege:
            shadow_blocked = True
            conn.rollback()
        log_test("Приложение: ЗАПРЕЩЕН доступ к системным паролям pg_shadow", shadow_blocked)

        conn.close()
    except Exception as e:
        log_test("Тест приложения", False, str(e))

def test_analyst_role():
    print("\n--- 3. Тестирование роли Аналитика (course_analyst) ---")
    try:
        # Подключение к primary
        conn = psycopg2.connect(dbname=DB_NAME, user=ANALYST_USER, password=ANALYST_PASS, host=HOST, port=PRIMARY_PORT)
        cur = conn.cursor()
        
        # 3.1 Разрешено: чтение агрегатов
        cur.execute("SELECT count(*) FROM app.news;")
        cnt = cur.fetchone()[0]
        log_test("Аналитик: Разрешено чтение аналитики (SELECT)", True, f"(записей: {cnt})")
        
        # 3.2 Запрещено: INSERT
        ins_blocked = False
        try:
            cur.execute("INSERT INTO app.news (source_id, title, external_url) VALUES (1, 'X', 'Y');")
        except errors.InsufficientPrivilege:
            ins_blocked = True
            conn.rollback()
        log_test("Аналитик: ЗАПРЕЩЕНА вставка (INSERT)", ins_blocked, "(Read-only роль)")
        
        # 3.3 Запрещено: DELETE
        del_blocked = False
        try:
            cur.execute("DELETE FROM app.news WHERE news_id = 1;")
        except errors.InsufficientPrivilege:
            del_blocked = True
            conn.rollback()
        log_test("Аналитик: ЗАПРЕЩЕНО удаление (DELETE)", del_blocked)
        conn.close()
        
        # 3.4 Чтение аналитиком с Read-Replica (порт 55433)
        conn_rep = psycopg2.connect(dbname=DB_NAME, user=ANALYST_USER, password=ANALYST_PASS, host=HOST, port=REPLICA_PORT)
        cur_rep = conn_rep.cursor()
        cur_rep.execute("SELECT count(*) FROM app.news;")
        rep_cnt = cur_rep.fetchone()[0]
        log_test("Аналитик: Безопасные запросы на Read Replica (порт 55433)", True, f"(записей на реплике: {rep_cnt})")
        conn_rep.close()
        
    except Exception as e:
        log_test("Тест аналитика", False, str(e))

def test_row_level_security():
    print("\n--- 4. Тестирование политик Row-Level Security (RLS) ---")
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=APP_USER, password=APP_PASS, host=HOST, port=PRIMARY_PORT)
        cur = conn.cursor()
        
        # 4.1 Контекст обычного читателя: видит только active
        cur.execute("SET app.current_user_role = 'user';")
        cur.execute("SELECT DISTINCT status FROM app.news;")
        statuses = [r[0] for r in cur.fetchall()]
        only_active = (statuses == ['active'])
        log_test("RLS news: Обычный пользователь видит ТОЛЬКО active новости", only_active, f"(статусы: {statuses})")
        
        # 4.2 Контекст редактора: видит скрытые/черновики/архивы
        cur.execute("SET app.current_user_role = 'editor';")
        cur.execute("SELECT count(DISTINCT status) FROM app.news;")
        distinct_statuses = cur.fetchone()[0]
        log_test("RLS news: Редактор (editor) видит скрытые/архивные новости", distinct_statuses > 1, f"(всего статусов: {distinct_statuses})")
        
        # 4.3 Изоляция favorites: пользователь 1 видит свою запись
        cur.execute("SET app.current_user_id = '1';")
        cur.execute("SELECT count(*) FROM app.favorites;")
        user1_favs = cur.fetchone()[0]
        log_test("RLS favorites: Пользователь 1 видит свои избранные новости", user1_favs >= 1, f"(записей: {user1_favs})")
        
        # 4.4 Пользователь 2 НЕ видит записи пользователя 1
        cur.execute("SET app.current_user_id = '2';")
        cur.execute("SELECT count(*) FROM app.favorites;")
        user2_favs = cur.fetchone()[0]
        log_test("RLS favorites: Пользователь 2 НЕ видит чужие закладки", user2_favs == 0, f"(записей: {user2_favs})")
        
        # 4.5 Попытка пользователя 2 добавить закладку за пользователя 1 (WITH CHECK нарушение)
        cur.execute("SET app.current_user_id = '2';")
        tamper_blocked = False
        try:
            cur.execute("INSERT INTO app.favorites (user_id, news_id) VALUES (1, 1);")
        except errors.InsufficientPrivilege:
            tamper_blocked = True
            conn.rollback()
        log_test("RLS favorites: ЗАПРЕЩЕНО внедрение записи под чужим user_id", tamper_blocked, "(WITH CHECK policy)")
        
        conn.close()
    except Exception as e:
        log_test("Тест RLS", False, str(e))

def test_replication_pipeline():
    print("\n--- 5. Тестирование цепочки репликации Primary -> Replica ---")
    try:
        # Вставка на Primary от имени приложения
        conn_p = psycopg2.connect(dbname=DB_NAME, user=APP_USER, password=APP_PASS, host=HOST, port=PRIMARY_PORT)
        cur_p = conn_p.cursor()
        marker = f"pipeline-test-{int(time.time())}"
        cur_p.execute("INSERT INTO app.replication_probe (marker) VALUES (%s) RETURNING id;", (marker,))
        probe_id = cur_p.fetchone()[0]
        conn_p.commit()
        conn_p.close()
        
        # Ожидание передачи WAL (обычно < 100 мс)
        time.sleep(0.5)
        
        # Чтение на Replica
        conn_r = psycopg2.connect(dbname=DB_NAME, user=ANALYST_USER, password=ANALYST_PASS, host=HOST, port=REPLICA_PORT)
        cur_r = conn_r.cursor()
        cur_r.execute("SELECT count(*) FROM app.replication_probe WHERE marker = %s;", (marker,))
        replicated = cur_r.fetchone()[0] == 1
        conn_r.close()
        
        log_test("Потоковая репликация: запись с primary мгновенно доступна на replica", replicated, f"(probe_id={probe_id}, marker={marker})")
    except Exception as e:
        log_test("Тест репликации", False, str(e))

if __name__ == "__main__":
    print("==================================================================")
    print(" АВТОМАТИЧЕСКИЙ ТЕСТ: БЕЗОПАСНОСТЬ, РОЛИ, RLS И РЕПЛИКАЦИЯ")
    print("==================================================================")
    test_admin_role()
    test_application_role()
    test_analyst_role()
    test_row_level_security()
    test_replication_pipeline()
    print("\n==================================================================")
    print(f" ИТОГ: Пройдено тестов: \033[92m{passed_tests}\033[0m / {passed_tests + failed_tests}")
    if failed_tests == 0:
        print(" \033[92mВСЕ ПРОВЕРКИ УСПЕШНО ПРОЙДЕНЫ!\033[0m")
        sys.exit(0)
    else:
        print(f" \033[91mОБНАРУЖЕНО ОШИБОК: {failed_tests}\033[0m")
        sys.exit(1)
