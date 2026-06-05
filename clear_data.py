import os
import sqlite3
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("DELETE FROM submissions")
cur.execute("DELETE FROM labs")

cur.execute("DELETE FROM sqlite_sequence WHERE name = 'submissions'")
cur.execute("DELETE FROM sqlite_sequence WHERE name = 'labs'")

conn.commit()
conn.close()

if os.path.exists(UPLOAD_DIR):
    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

print("Все лабораторные работы, попытки и загруженные файлы удалены.")