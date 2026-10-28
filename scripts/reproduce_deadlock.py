import psycopg2
import time
import threading

def session1():
    try:
        conn = psycopg2.connect("dbname=mydb user=flyway_user password=flyway_password host=localhost port=5432")
        cur = conn.cursor()
        print("[Сессия 1] Транзакция началась")
        cur.execute("BEGIN;")
        print("[Сессия 1] Обновляем news_id = 1 (захватываем строку 1)")
        cur.execute("UPDATE news SET title = 'Title A' WHERE news_id = 1;")
        time.sleep(2)
        print("[Сессия 1] Пытаемся обновить news_id = 2...")
        cur.execute("UPDATE news SET title = 'Title B' WHERE news_id = 2;")
        cur.execute("COMMIT;")
        print("[Сессия 1] Успешный COMMIT")
    except Exception as e:
        print(f"\n[Сессия 1] Ошибка/Deadlock: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def session2():
    try:
        conn = psycopg2.connect("dbname=mydb user=flyway_user password=flyway_password host=localhost port=5432")
        cur = conn.cursor()
        print("[Сессия 2] Транзакция началась")
        cur.execute("BEGIN;")
        
        print("[Сессия 2] Обновляем news_id = 1...")
        cur.execute("UPDATE news SET title = 'Title A - Session 2' WHERE news_id = 1;")
        time.sleep(2)
        
        print("[Сессия 2] Обновляем news_id = 2...")
        cur.execute("UPDATE news SET title = 'Title B - Session 2' WHERE news_id = 2;")
        
        cur.execute("COMMIT;")
        print("[Сессия 2] Успешный COMMIT")
    except Exception as e:
        print(f"\n[Сессия 2] Ошибка/Deadlock: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    print("Запуск воспроизведения взаимной блокировки (Deadlock)...")
    t1 = threading.Thread(target=session1)
    t2 = threading.Thread(target=session2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("\nЭксперимент завершён.")
