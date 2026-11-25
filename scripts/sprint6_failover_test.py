#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import PyMongoError, AutoReconnect, ServerSelectionTimeoutError

MONGO_USER = 'news_app_user'
MONGO_PASS = urllib.parse.quote_plus('AppSuperPass2026!')
MONGO_URI = f'mongodb://{MONGO_USER}:{MONGO_PASS}@mongo1:27017,mongo2:27017,mongo3:27017/news_aggregator?replicaSet=rs0&authSource=news_aggregator&retryWrites=true&w=majority'

print("==================================================================")
print(" СПРИНТ 6: АВТОМАТИЗАЦИЯ ОТКАЗА PRIMARY И ВОССТАНОВЛЕНИЕ (ВОСХИТИТЕЛЬНО)")
print("==================================================================")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['news_aggregator']
client.admin.command('ping')

# 1. Определение текущего Primary
initial_primary = client.primary
print(f"1. Начальное состояние: Текущий Primary -> {initial_primary}")
assert initial_primary is not None, "Primary не обнаружен!"

# Контрольная запись до сбоя
probe_id = f"failover_probe_{int(time.time())}"
db.replication_probe.insert_one({
    "marker": probe_id,
    "createdAt": datetime.now(timezone.utc),
    "writer": "test_pre_failover"
})
print(f"   Контрольная запись '{probe_id}' успешно создана с w:majority")

# 2. Остановка текущего Primary узла через docker stop
primary_container = initial_primary[0]
print(f"\n2. Имитация аварии: останавливаем контейнер {primary_container}...")
t_stop = time.time()
subprocess.run(["docker", "stop", primary_container], check=True)
print(f"   Контейнер {primary_container} успешно остановлен.")

# 3. Мониторинг выборов и восстановление записи
print("\n3. Приложение пытается писать и отслеживает перевыборы Primary...")
new_primary = None
attempts = 0
write_recovered = False
failover_duration = 0.0

while attempts < 30:
    attempts += 1
    try:
        current_p = client.primary
        if current_p and current_p[0] != primary_container:
            new_primary = current_p
            post_probe_id = f"post_failover_{int(time.time())}_{attempts}"
            db.replication_probe.insert_one({
                "marker": post_probe_id,
                "createdAt": datetime.now(timezone.utc),
                "writer": f"writer_on_{new_primary[0]}"
            })
            failover_duration = time.time() - t_stop
            write_recovered = True
            print(f"   [ВЫБОРЫ ЗАВЕРШЕНЫ] Новый Primary: {new_primary}!")
            print(f"   [ЗАПИСЬ ВОССТАНОВЛЕНА] Запись '{post_probe_id}' сохранена через {failover_duration:.2f} сек.")
            break
        else:
            print(f"   [ОЖИДАНИЕ {attempts}] Идут выборы... (client.primary={current_p})")
    except (AutoReconnect, ServerSelectionTimeoutError, PyMongoError) as err:
        print(f"   [ОЖИДАНИЕ {attempts}] Ошибка переключения драйвера ({type(err).__name__}). Повтор...")
    
    time.sleep(1.0)

assert write_recovered, "Приложение не смогло восстановить запись после падения Primary!"

# 4. Восстановление исходного узла (возврат в кластер)
print(f"\n4. Возвращаем узел {primary_container} обратно в строй...")
subprocess.run(["docker", "start", primary_container], check=True)
print(f"   Контейнер {primary_container} запущен.")

time.sleep(5.0)

# 5. Проверяем топологию после возврата через root-пользователя
root_user = 'course_root'
root_pass = urllib.parse.quote_plus('SuperSecretRootPass2026!')
root_uri = f'mongodb://{root_user}:{root_pass}@mongo1:27017,mongo2:27017,mongo3:27017/admin?replicaSet=rs0'
root_client = MongoClient(root_uri, serverSelectionTimeoutMS=5000)
members = root_client.admin.command('replSetGetStatus')['members']
print("\n5. Итоговый статус Replica Set после восстановления:")
for m in members:
    print(f"   - {m['name']}: {m['stateStr']} (health={m['health']}, uptime={m.get('uptime', 0)}s)")

root_client.close()
client.close()
print("\n==================================================================")
print(f" ТЕСТ FAILOVER ЗАВЕРШЕН УСПЕШНО! Время перевыборов: {failover_duration:.2f}с")
print("==================================================================")
