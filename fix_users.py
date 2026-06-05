import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# На всякий случай добавляем новые поля, если их нет
columns = cur.execute("PRAGMA table_info(users)").fetchall()
column_names = [column[1] for column in columns]

if "full_name" not in column_names:
    cur.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")

if "student_group" not in column_names:
    cur.execute("ALTER TABLE users ADD COLUMN student_group TEXT DEFAULT ''")

# Создаём или обновляем студента
cur.execute("""
    INSERT OR IGNORE INTO users (username, password, role, full_name, student_group)
    VALUES (?, ?, ?, ?, ?)
""", ("student", "student123", "student", "Иванов Иван Иванович", "ІПЗ-5.01"))

cur.execute("""
    UPDATE users
    SET password = ?, role = ?, full_name = ?, student_group = ?
    WHERE username = ?
""", ("student123", "student", "Иванов Иван Иванович", "ІПЗ-5.01", "student"))

# Создаём или обновляем преподавателя
cur.execute("""
    INSERT OR IGNORE INTO users (username, password, role, full_name, student_group)
    VALUES (?, ?, ?, ?, ?)
""", ("teacher", "teacher123", "teacher", "Преподаватель", ""))

cur.execute("""
    UPDATE users
    SET password = ?, role = ?, full_name = ?, student_group = ?
    WHERE username = ?
""", ("teacher123", "teacher", "Преподаватель", "", "teacher"))

conn.commit()
conn.close()

print("Пользователи student и teacher созданы или обновлены.")