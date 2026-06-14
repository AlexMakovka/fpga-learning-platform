# Модуль os потрібний для роботи з шляхами, папками та файлами в операційній системі
import os

# sqlite3 потрібний для роботи з базою даних SQLite
# SQLite - це проста файлова база даних, яка зберігається в одному .db файлі
import sqlite3

# subprocess дозволяє запускати зовнішні команди та програми з Python
# Наприклад, можна запускати перевірку коду через Docker або через термінал
import subprocess

# tempfile потрібний для створення тимчасових файлів та папок
# Це зручно, коли потрібно тимчасово зберегти код студента для перевірки
import tempfile

# shutil використовується для роботи з файлами та папками:
# копіювання, видалення папок, переміщення файлів і т.д.
import shutil

# re - модуль регулярних виразів
# Він потрібний для пошуку та перевірки тексту за шаблонами
import re

# sys дозволяє працювати з параметрами та налаштуваннями Python-інтерпретатора
# Наприклад, можна отримувати аргументи запуску програми або завершувати програму
import sys

# ast використовується для аналізу Python-коду як структури
# Може застосовуватись для безпечної перевірки коду без його прямого виконання
import ast

# datetime потрібен для роботи з датою та часом
# Наприклад, щоб зберегти дату спроби, дату завантаження файлу або час перевірки
from datetime import datetime

# wraps потрібен при створенні декораторів
# Він допомагає зберегти ім'я та опис вихідної функції
from functools import wraps

# Завантажує змінні оточення з файлу .env
# Наприклад, секретні ключі та налаштування, які не варто зберігати прямо в коді
from dotenv import load_dotenv

# Включає OAuth-авторизацію у Flask
# Потрібна для входу через зовнішні сервіси, наприклад Google
from authlib.integrations.flask_client import OAuth


# Імпортуємо основні інструменти Flask

# Flask - основний клас програми
# request — об'єкт, через який отримуємо дані з форм та запитів
# redirect — перенаправляє користувача на іншу сторінку
# url_for — будує посилання на маршрути Flask на ім'я функції
# session — зберігає дані користувача між запитами, наприклад ID користувача
# render_template - відображає HTML-шаблони
# flash — показує одноразові повідомлення користувачу
# send_from_directory — дозволяє віддавати файл із папки
# abort - примусово завершує запит з помилкою, наприклад 404 або 403
from flask import Flask, request, redirect, url_for, session, render_template, flash, send_from_directory, abort


# secure_filename безпечно обробляє ім'я файлу, що завантажується
# Це захищає від небезпечних імен файлів та шляхів
from werkzeug.utils import secure_filename


# Створюємо екземпляр Flask-додатки
app = Flask(__name__)
# Реєструємо Google як зовнішній сервіс для авторизації
oauth = OAuth(app)

# ID і секрет клієнта беруться з файлу .env
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
# Адреса з налаштуваннями Google OAuth/OpenID Connect
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
# Запитуємо у Google базові дані користувача: email та профіль
    client_kwargs={
        "scope": "openid email profile"
    }
)
# Секретний ключ необхідний роботи сесій.
# У реальному проекті його краще зберігати в змінних оточення, а не прямо в коді.
app.secret_key = "change_this_secret_key"


# Абсолютний шлях до папки, де лежить поточний файл програми
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Шлях до файлу бази даних SQLite
DB_PATH = os.path.join(BASE_DIR, "database.db")
# Папка для зберігання завантажених користувачами файлів
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
WAVEFORM_DIR = os.path.join(BASE_DIR, "waveforms")
# Завантажує налаштування з файлу .env, який знаходиться в папці проекту
load_dotenv(os.path.join(BASE_DIR, ".env"))


# Назва Docker-образу, в якому запускатиметься перевірка Python-коду
PYTHON_DOCKER_IMAGE = "fpga-python-checker:latest"
# Максимальний час перевірки Python-коду 
PYTHON_CHECK_TIMEOUT_SECONDS = 15


# Створюємо папку uploads, якщо її ще немає
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(WAVEFORM_DIR, exist_ok=True)

# =========================
# 1. Робота з базою даних
# =========================

# Функція для отримання з'єднання з базою даних SQLite.
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Функція для ініціалізації бази даних. Вона створює необхідні таблиці, додає відсутні стовпці та вставляє початкові дані.
def init_db():
    conn = get_db()
    cur = conn.cursor()

# Таблиця користувачів: зберігає дані студентів, викладачів та адміністраторів
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            student_group TEXT DEFAULT '',
            email TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT '',
            approved_by TEXT DEFAULT ''
        )
    """)

# Отримуємо список вже існуючих стовпців у таблиці users
# Це потрібно, щоб безпечно додавати нові поля до старої бази даних
    user_columns = cur.execute("PRAGMA table_info(users)").fetchall()
    user_column_names = [column["name"] for column in user_columns]

# google_id зберігає унікальний ідентифікатор користувача з Google
    if "google_id" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN google_id TEXT DEFAULT ''")

# auth_provider показує, як користувач зареєструвався: через звичайний логін або через Google
    if "auth_provider" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local'")

# Додаємо поля, що бракують, якщо база була створена раніше і в ній їх ще немає
    if "email" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")

    if "status" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")

    if "created_at" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT ''")

    if "approved_by" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN approved_by TEXT DEFAULT ''")

    if "full_name" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")

    if "student_group" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN student_group TEXT DEFAULT ''")


# Таблиця лабораторних робіт:
# зберігає опис завдання, тестбенч, параметри перевірки та налаштування оцінювання
    cur.execute("""
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            testbench TEXT NOT NULL,

            discipline TEXT DEFAULT 'FPGA-проектирование',
            programming_language TEXT DEFAULT 'Verilog',
            checker_type TEXT DEFAULT 'hdl_testbench',
            topic TEXT DEFAULT '',
            difficulty TEXT DEFAULT 'basic',
            concepts TEXT DEFAULT '',
            grading_policy TEXT DEFAULT '',
            starter_code TEXT DEFAULT '',

            max_attempts INTEGER DEFAULT 3,
            allow_extra_questions INTEGER DEFAULT 1,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """)

# Отримуємо список стовпців таблиці labs
# Це дозволяє оновлювати структуру таблиці без видалення старих даних та без помилок, якщо база була створена раніше.
    columns = cur.execute("PRAGMA table_info(labs)").fetchall()
    column_names = [column["name"] for column in columns]

# Додаємо нові поля лабораторних робіт, якщо вони відсутні у старій версії бази даних
    if "discipline" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN discipline TEXT DEFAULT 'FPGA-проектирование'")

    if "programming_language" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN programming_language TEXT DEFAULT 'Verilog'")

    if "checker_type" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN checker_type TEXT DEFAULT 'hdl_testbench'")

    if "topic" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN topic TEXT DEFAULT ''")

    if "difficulty" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN difficulty TEXT DEFAULT 'basic'")

    if "concepts" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN concepts TEXT DEFAULT ''")

    if "grading_policy" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN grading_policy TEXT DEFAULT ''")

    if "starter_code" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN starter_code TEXT DEFAULT ''")

    if "created_by" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN created_by TEXT DEFAULT ''")


# Для старих лабораторних робіт вказуємо автора за замовчуванням як "teacher", щоб не було порожніх значень.
    cur.execute("""
        UPDATE labs
        SET created_by = 'teacher'
        WHERE created_by IS NULL OR created_by = ''
    """)

# Таблиця відправлених рішень студентів з лабораторних робіт
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
            waveform_filename TEXT DEFAULT '',
            status TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            passed_tests INTEGER DEFAULT 0,
            total_tests INTEGER DEFAULT 0,
            error_type TEXT DEFAULT '',
            error_title TEXT DEFAULT '',
            error_details TEXT DEFAULT '',
            recommendation TEXT DEFAULT '',
            error_confidence INTEGER DEFAULT 0,
            output TEXT NOT NULL,
            created_at TEXT NOT NULL,
            attempt_number INTEGER DEFAULT 1,
            file_deleted INTEGER DEFAULT 0,
            file_hidden_for_student INTEGER DEFAULT 0,
            FOREIGN KEY (lab_id) REFERENCES labs(id)
        )
    """)

# Отримуємо список стовпців таблиці submissions
# Це потрібно для безпечного оновлення старої версії бази даних без втрати даних та без помилок, якщо база була створена раніше.
    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]

# Поля для зберігання типу помилки та пояснень за результатами перевірки рішення студента. 
# Вони можуть бути заповнені після автоматичної класифікації помилки.
    if "error_type" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN error_type TEXT DEFAULT ''")

    if "error_title" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN error_title TEXT DEFAULT ''")

    if "error_details" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN error_details TEXT DEFAULT ''")

    if "recommendation" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN recommendation TEXT DEFAULT ''")

    if "error_confidence" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN error_confidence INTEGER DEFAULT 0")

# Номер спроби потрібен для обмеження кількості відправок по одній лабораторній роботі та для відображення історії спроб студенту і викладачу.
    if "attempt_number" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN attempt_number INTEGER DEFAULT 1")

# Поля для м'якого видалення або приховування файлу без видалення запису з бази даних. Це дозволяє зберігати історію спроб та їх результати, навіть якщо студент видаляє файл або хоче його приховати від себе.
    if "file_deleted" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN file_deleted INTEGER DEFAULT 0")

    if "file_hidden_for_student" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN file_hidden_for_student INTEGER DEFAULT 0")

    if "waveform_filename" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN waveform_filename TEXT DEFAULT ''")


# Таблиця спроб відповідей на додаткові питання після перевірки лабораторної
    cur.execute("""
        CREATE TABLE IF NOT EXISTS extra_task_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            answer_1 TEXT NOT NULL,
            answer_2 TEXT NOT NULL,
            answer_3 TEXT NOT NULL,
            correct_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 3,
            bonus INTEGER DEFAULT 0,
            score_before INTEGER DEFAULT 0,
            score_after INTEGER DEFAULT 0,
            feedback TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (submission_id) REFERENCES submissions(id)
        )
    """)

# Повторно перевіряємо структуру submissions, щоб додати поля оцінки, якщо база була створена раніше
    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]


# Поля для зберігання результату перевірки: підсумковий бал та кількість пройдених тестів. 
# Вони будуть заповнені після автоматичної перевірки рішення студента.
    if "score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN score INTEGER DEFAULT 0")

    if "passed_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN passed_tests INTEGER DEFAULT 0")

    if "total_tests" not in column_names:
         cur.execute("ALTER TABLE submissions ADD COLUMN total_tests INTEGER DEFAULT 0")


# Таблиця зв'язків між викладачами, дисциплінами та навчальними групами 
# Потрібно, щоб розуміти, який викладач веде яку дисципліну у якої групи студентів, 
# і показувати йому лише відповідні лабораторні роботи та рішення.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teacher_subject_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_username TEXT NOT NULL,
            discipline TEXT NOT NULL,
            student_group TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT DEFAULT '',
            UNIQUE(teacher_username, discipline, student_group),
            FOREIGN KEY (teacher_username) REFERENCES users(username)
        )
    """)

# Таблиця навчальних груп
# Потрібна для зберігання списку груп студентів
    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT DEFAULT ''
        )
    """)

# Таблиця дисциплін
# Потрібна для зберігання списку навчальних предметів у системі
    cur.execute("""
        CREATE TABLE IF NOT EXISTS disciplines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT DEFAULT ''
        )
    """)

# Таблиця ручної зміни оцінки за конкретну лабораторну роботу
# Дозволяє викладачеві виправити підсумковий бал студента за необхідності
    cur.execute("""
        CREATE TABLE IF NOT EXISTS grade_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            lab_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            edited_by TEXT NOT NULL,
            edited_at TEXT NOT NULL,
            UNIQUE(username, lab_id),
            FOREIGN KEY (username) REFERENCES users(username),
            FOREIGN KEY (lab_id) REFERENCES labs(id)
        )
    """)

# Таблиця підсумкових оцінок студентів з дисциплін
# Використовується, якщо викладач вручну виставляє фінальний бал на предмет
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subject_final_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            discipline TEXT NOT NULL,
            final_score INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            edited_by TEXT NOT NULL,
            edited_at TEXT NOT NULL,
            UNIQUE(username, discipline),
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)

# Щоб уже існуючі групи та предмети не загубилися
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        """
        INSERT OR IGNORE INTO study_groups (name, description, created_at, created_by)
        SELECT DISTINCT student_group, '', ?, 'system'
        FROM users
        WHERE student_group IS NOT NULL
        AND student_group != ''
        """,
        (now,)
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO disciplines (name, description, created_at, created_by)
        SELECT DISTINCT discipline, '', ?, 'system'
        FROM labs
        WHERE discipline IS NOT NULL
        AND discipline != ''
        """,
        (now,)
    )

# Перевіряємо, чи є користувачі в базі
# Якщо база порожня, створюємо тестового студента та викладача
    cur.execute("SELECT COUNT(*) AS count FROM users")
    if cur.fetchone()["count"] == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Тестовий студент для першого входу та перевірки роботи системи
        cur.execute(
            """
            INSERT INTO users (
                username,
                password,
                role,
                full_name,
                student_group,
                email,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "student1",
                "student123",
                "student",
                "Иван Иванов",
                "Группа 101",
                "",
                "active",
                now
            )
        )

# Тестовий викладач для першого входу та перевірки роботи системи
        cur.execute(
            """
            INSERT INTO users (
                username,
                password,
                role,
                full_name,
                student_group,
                email,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "teacher",
                "teacher123",
                "teacher",
                "Преподаватель",
                "",
                "",
                "active",
                now
            )
        )
        

# Створюємо адміністратора, якщо його ще немає. Це потрібно для можливості керування системою та лабораторними роботами.
    admin_exists = cur.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

# Якщо адміністратора немає, створюємо його з базовими правами та паролем. 
# В реальному застосуванні пароль потрібно змінити на більш складний та зберігати в безпечному місці.
    if not admin_exists:
        cur.execute(
            """
            INSERT INTO users (username, password, role, full_name, student_group, email, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "admin",
                "admin123",
                "admin",
                "Администратор системы",
                "",
                "",
                "active",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

# Перевіряємо, чи є лабораторні роботи в базі. 
# Якщо їх немає, створюємо тестову лабораторну роботу для демонстрації та перевірки роботи системи.
    cur.execute("SELECT COUNT(*) AS count FROM labs")
    cur.fetchone()

# Якщо лабораторних робіт немає, створюємо тестову лабораторну роботу з базовим описом та тестбенчем.
    conn.commit()
    conn.close()


# =========================
# 2. Декоратори доступу
# =========================

# Декоратор для захисту маршрутів, які вимагають авторизації. 
# Якщо користувач не увійшов, його перенаправляє на сторінку входу.
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# Декоратор для захисту маршрутів, які вимагають ролі викладача.
def teacher_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "teacher":
            flash("Доступ разрешён только преподавателю.")
            return redirect(url_for("index"))
        return func(*args, **kwargs)
    return wrapper


# Декоратор для захисту маршрутів, які вимагають ролі адміністратора.
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Доступ разрешён только администратору.")
            return redirect(url_for("index"))
        return func(*args, **kwargs)
    return wrapper


# =========================
# 3. Допоміжні функції для користувачів
# =========================

def build_unique_username(conn, base_username):
    base_username = str(base_username or "user").strip().lower()
    base_username = re.sub(r"[^a-zA-Z0-9_]+", "_", base_username)
    base_username = base_username.strip("_")

    if not base_username:
        base_username = "user"

    username = base_username
    counter = 1

    while True:
        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if not existing:
            return username

        counter += 1
        username = f"{base_username}_{counter}"


# =========================
# 4. Допоміжні функції для файлів та завантажень
# =========================

# Функція для транслітерації російських букв у латиницю, щоб формувати безпечні імена файлів, 
# які не містять кирилиці та спеціальних символів, що може викликати проблеми при збереженні файлів на сервері.
def transliterate_ru_to_en(text):

    symbols = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
        "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch",
        "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya"
    }

    result = []

    for char in str(text):
        lower_char = char.lower()

        if lower_char in symbols:
            value = symbols[lower_char]

            if char.isupper():
                value = value.capitalize()

            result.append(value)
        else:
            result.append(char)

    return "".join(result)


# Функція для формування безпечної частини імені файлу, яка містить лише латинські літери, цифри, дефіси та підкреслення, 
# щоб уникнути проблем з збереженням файлів на сервері та забезпечити зрозумілі імена файлів для вчителів при перегляді відправок студентів.
def make_safe_filename_part(text, default="item", max_length=30):

    text = transliterate_ru_to_en(text)
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-_")

    if not text:
        text = default

    return text[:max_length]


# Функція для формування короткого імені студента для файлу, яка використовує прізвище та ініціали студента, або ім'я користувача, 
# якщо повне ім'я не доступне, щоб створювати зрозумілі імена файлів для вчителів при перегляді відправок студентів.
def build_student_short_name(student):

    if not student:
        return "student"

    full_name = student["full_name"] if "full_name" in student.keys() else ""
    username = student["username"] if "username" in student.keys() else "student"

    full_name = str(full_name or "").strip()

    if not full_name:
        return make_safe_filename_part(username, "student", 24)

    parts = full_name.split()

    if len(parts) >= 2:
        surname = parts[0]
        initials = ""

        for part in parts[1:]:
            if part:
                initials += part[0]

        return make_safe_filename_part(surname + initials, username, 24)

    return make_safe_filename_part(full_name, username, 24)


# Функція для формування короткого префікса для імені файлу на основі типу лабораторної роботи та мови програмування, 
# щоб створювати зрозумілі імена файлів для вчителів при перегляді відправок студентів 
# та швидко визначати тип лабораторної роботи за ім'ям файлу.
def get_checker_prefix_for_filename(lab):

    checker_type = lab["checker_type"] or "hdl_testbench"
    programming_language = lab["programming_language"] or ""

    checker_type = checker_type.lower()
    programming_language = programming_language.lower()

    if checker_type == "python_unit_tests" or programming_language == "python":
        return "PY"

    if checker_type == "hdl_testbench" or programming_language == "verilog":
        return "FPGA"

    if checker_type == "sql_query" or programming_language == "sql":
        return "SQL"

    if checker_type == "cpp_tests" or programming_language == "c++":
        return "CPP"

    return "LAB"


# Функція для формування короткої теми лабораторної роботи для імені файлу на основі поля topic з паспорта лабораторної роботи 
# або за замовчуванням, щоб створювати зрозумілі імена файлів для вчителів при перегляді відправок студентів 
# та швидко визначати тему лабораторної роботи за ім'ям файлу.
def get_lab_topic_for_filename(lab):

    topic = ""

    if "topic" in lab.keys():
        topic = lab["topic"] or ""

    if not topic:
        topic = f"lab{lab['id']}"

    return make_safe_filename_part(topic, f"lab{lab['id']}", 24)


# Функція для отримання списку дозволених розширень файлів для конкретної лабораторної роботи на основі типу перевірки, 
# щоб забезпечити, що студенти завантажують файли з правильними розширеннями для кожної лабораторної роботи 
# та уникнути проблем з перевіркою рішень через неправильні формати файлів.
def get_allowed_extensions_for_lab(lab):

    checker_type = lab["checker_type"] or "hdl_testbench"

    if checker_type == "hdl_testbench":
        return [".v"]

    if checker_type == "python_unit_tests":
        return [".py"]

    if checker_type == "sql_query":
        return [".sql"]

    if checker_type == "cpp_tests":
        return [".cpp", ".cc", ".cxx"]

    return [".txt"]


# Функція для перевірки, чи є завантажений файл рішення студента дозволеним для конкретної лабораторної роботи на основі його розширення,
# щоб забезпечити, що студенти завантажують файли з правильними розширеннями для кожної лабораторної роботи 
# та уникнути проблем з перевіркою рішень через неправильні формати файлів.   
def is_allowed_solution_file(filename, lab):
    extension = os.path.splitext(filename)[1].lower()
    allowed_extensions = get_allowed_extensions_for_lab(lab)

    return extension in allowed_extensions




# Функція для формування імені файлу відправки рішення студента, яка включає тип лабораторної роботи, тему, 
# коротке ім'я студента, групу, номер спроби та дату відправки, щоб створювати зрозумілі імена файлів для вчителів 
# при перегляді відправок студентів та швидко визначати інформацію про відправку за ім'ям файлу.
def build_submission_filename(lab, student, attempt_number, original_filename):

    prefix = get_checker_prefix_for_filename(lab)
    lab_id_part = f"L{lab['id']}"
    topic_part = get_lab_topic_for_filename(lab)

    student_part = build_student_short_name(student)

    if student and "student_group" in student.keys():
        group_raw = student["student_group"] or "group"
    else:
        group_raw = "group"

    group_part = make_safe_filename_part(group_raw, "group", 20)

    try:
        attempt_part = f"A{int(attempt_number):02d}"
    except ValueError:
        attempt_part = "A01"

    datetime_part = datetime.now().strftime("%Y%m%d_%H%M%S")

    extension = os.path.splitext(original_filename)[1].lower()

    if not extension:
        extension = get_allowed_extensions_for_lab(lab)[0]

    return (
        f"{prefix}_"
        f"{lab_id_part}_"
        f"{topic_part}_"
        f"{student_part}_"
        f"{group_part}_"
        f"{attempt_part}_"
        f"{datetime_part}"
        f"{extension}"
    )


def build_waveform_filename(submission_filename):
    base_name = os.path.splitext(submission_filename)[0]
    safe_base_name = make_safe_filename_part(base_name, "waveform", 120)
    return f"{safe_base_name}.vcd"


# Функція для читання HDL-коду з файлу, завантаженого студентом, з обробкою можливих помилок кодування та відсутності файлу.
def read_submission_code(filename):

    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        return ""

    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


# Функція для видалення фізичного файлу, завантаженого студентом, з сервера. 
# Використовується при видаленні спроби або приховуванні файлу від студента.
def delete_uploaded_file(filename):
    if not filename:
        return

    file_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(file_path):
        os.remove(file_path)


# Функція для позначення файлу спроби як видаленого. Файл фізично видаляється з сервера, 
# а в базі даних встановлюється прапорець file_deleted, щоб викладач знав, що файл більше недоступний.
def mark_submission_file_deleted(submission_id):
    conn = get_db()

    submission = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    ).fetchone()

    if not submission:
        conn.close()
        return

    delete_uploaded_file(submission["filename"])

    conn.execute(
        """
        UPDATE submissions
        SET file_deleted = 1
        WHERE id = ?
        """,
        (submission_id,)
    )

    conn.commit()
    conn.close()


# Функція для приховування файлу спроби від студента. Файл фізично не видаляється з сервера, 
# але в базі даних встановлюється прапорець file_hidden_for_student, щоб студент не міг його бачити або завантажувати. 
# Викладач при цьому зможе скачати файл для перевірки.
def hide_submission_file_from_student(submission_id):

    conn = get_db()

    conn.execute(
        """
        UPDATE submissions
        SET file_hidden_for_student = 1
        WHERE id = ?
        """,
        (submission_id,)
    )

    conn.commit()
    conn.close()
    

# ============================================================
# 5. Допоміжні функції для спроб та відправок
# ============================================================

# Функція для отримання спроби студента разом з інформацією про лабораторну роботу. Студент може бачити тільки свої спроби, а викладач може бачити всі спроби.
def get_submission_for_current_user(submission_id):

    conn = get_db()

# Виконуємо SQL-запит для отримання інформації про спробу та пов'язану лабораторну роботу.
    submission = conn.execute(
        """
        SELECT 
            submissions.*,

            labs.title AS lab_title,
            labs.description AS lab_description,
            labs.testbench AS lab_testbench,

            labs.discipline AS lab_discipline,
            labs.programming_language AS lab_programming_language,
            labs.checker_type AS lab_checker_type,
            labs.topic AS lab_topic,
            labs.difficulty AS lab_difficulty,
            labs.concepts AS concepts,
            labs.grading_policy AS lab_grading_policy,
            labs.starter_code AS lab_starter_code,

            labs.allow_extra_questions,
            labs.max_attempts

        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        WHERE submissions.id = ?
        """,
        (submission_id,)
    ).fetchone()

    conn.close()

    if not submission:
        abort(404)

    if session.get("role") != "teacher" and submission["username"] != session["username"]:
        abort(403)

    return submission


# Функція для отримання кількості спроб студента по конкретній лабораторній роботі.
def get_student_attempts_count(username, lab_id):

    conn = get_db()

    result = conn.execute(
        """
        SELECT COUNT(*) AS attempts_count
        FROM submissions
        WHERE username = ? AND lab_id = ?
        """,
        (username, lab_id)
    ).fetchone()

    conn.close()

    return result["attempts_count"] if result else 0


# Функція для визначення номера наступної спроби студента по конкретній лабораторній роботі.
def get_next_attempt_number(username, lab_id):
    return get_student_attempts_count(username, lab_id) + 1


# Функція для отримання кількості спроб виконання додаткових завдань (extra tasks) по конкретній спробі.
def get_extra_task_attempt_count(submission_id):
    conn = get_db()

    result = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM extra_task_attempts
        WHERE submission_id = ?
        """,
        (submission_id,)
    ).fetchone()

    conn.close()

    return result["count"] if result else 0


# Функція для отримання історії помилок студента по конкретній лабораторній роботі.
def get_student_error_history(username, lab_id):
    
    conn = get_db()

    rows = conn.execute(
        """
        SELECT error_type, error_title, COUNT(*) AS count
        FROM submissions
        WHERE username = ?
          AND lab_id = ?
          AND error_type IS NOT NULL
          AND error_type != ''
          AND error_type != 'NO_ERROR'
        GROUP BY error_type, error_title
        ORDER BY count DESC
        """,
        (username, lab_id)
    ).fetchall()

    conn.close()

    return rows


# Формує SQL-умову, яка перевіряє доступ викладача до лабораторної роботи 
def get_teacher_access_condition():

    return """
        (
            labs.created_by = ?
            OR EXISTS (
                SELECT 1
                FROM teacher_subject_groups tsg
                WHERE tsg.teacher_username = ?
                  AND tsg.discipline = labs.discipline
                  AND tsg.student_group = users.student_group
            )
        )
    """


# Перевіряє, чи може користувач редагувати оцінку студента за лабораторною. 
# Адміністратор може редагувати усі оцінки.
#    Викладач може редагувати оцінку, якщо:
#    1. він створив лабораторну;
#    2. йому призначено предмет лабораторної та групу студента.
def can_edit_lab_grade(conn, current_username, current_role, student_username, lab_id):

    if current_role == "admin":
        return True

    if current_role != "teacher":
        return False

    access = conn.execute(
        """
        SELECT 1
        FROM labs
        JOIN users AS student ON student.username = ?
        WHERE labs.id = ?
          AND (
              labs.created_by = ?
              OR EXISTS (
                  SELECT 1
                  FROM teacher_subject_groups tsg
                  WHERE tsg.teacher_username = ?
                    AND tsg.discipline = labs.discipline
                    AND tsg.student_group = student.student_group
              )
          )
        """,
        (
            student_username,
            lab_id,
            current_username,
            current_username
        )
    ).fetchone()

    return access is not None


# =========================
# 6. Перевірка HDL / Verilog-рішень
# =========================

# Функція для форматування сирого виводу з перевірки HDL-коду у зрозумілий звіт для студента.
def format_hdl_report(raw_output):
    lines = raw_output.splitlines()
    test_cases = []

# Парсим вивід, шукаючи рядки, які починаються з "CASE|", і розбиваємо їх на частини для отримання інформації про кожен тест.
    for line in lines:
        line = line.strip()

        if line.startswith("CASE|"):
            parts = line.split("|")

            if len(parts) == 6:
                test_number = parts[1]
                inputs = parts[2]
                expected = parts[3]
                actual = parts[4]
                result = parts[5]

                test_cases.append({
                    "number": test_number,
                    "inputs": inputs,
                    "expected": expected,
                    "actual": actual,
                    "result": result
                })

# Якщо тестів не знайдено, повертаємо сирий вивід та нульові значення для балів і кількості тестів.
    if not test_cases:
        return raw_output, 0, 0, 0

# Рахуємо кількість пройдених тестів та загальну кількість тестів для обчислення підсумкового балу.
    passed_count = sum(1 for test in test_cases if test["result"] == "PASS")
    total_count = len(test_cases)

# Обчислюємо підсумковий бал як відношення пройдених тестів до загальної кількості, 
# помножене на 100, і округлюємо до цілих чисел.
    if total_count > 0:
        score = round((passed_count / total_count) * 100)
    else:
        score = 0

# Формуємо звіт для студента, включаючи загальний результат, кількість пройдених тестів та деталі кожного тесту.
    report_lines = []

# Додаємо загальний результат та кількість пройдених тестів у звіт.
    report_lines.append(f"Результат: {score} / 100 баллов")
    report_lines.append(f"Пройдено тестов: {passed_count} из {total_count}")
    report_lines.append("")

# Додаємо деталі кожного тесту у звіт, включаючи номер тесту, вхідні дані, очікуваний результат, фактичний результат та статус (пройдено або ошибка).
    for test in test_cases:
        if test["result"] == "PASS":
            status_text = "пройден"
        else:
            status_text = "ошибка"

        report_lines.append(
            f"Тест {test['number']}: {test['inputs']} — {status_text}"
        )
        report_lines.append(f"Ожидалось: {test['expected']}")
        report_lines.append(f"Получено:   {test['actual']}")
        report_lines.append("")

# Додаємо підсумковий статус у звіт на основі кількості пройдених тестів: якщо всі тести пройдені, 
# якщо частина тестів пройдена, або якщо тести не пройдені.
    if passed_count == total_count:
        report_lines.append("Итоговый статус: все тесты успешно пройдены.")
    elif passed_count > 0:
        report_lines.append("Итоговый статус: часть тестов пройдена, решение требует доработки.")
    else:
        report_lines.append("Итоговый статус: тесты не пройдены.")

    return "\n".join(report_lines), score, passed_count, total_count


# Функція для автоматичної перевірки HDL-коду студента за допомогою Icarus Verilog та тестбенча викладача.
def run_hdl_check(user_code_path, testbench_text, waveform_save_path=None):
# Створюємо тимчасову папку для зберігання файлу рішення студента, тестбенча та результатів симуляції.
    with tempfile.TemporaryDirectory() as temp_dir:
        solution_path = os.path.join(temp_dir, "solution.v")
        testbench_path = os.path.join(temp_dir, "testbench.v")
        output_path = os.path.join(temp_dir, "simulation.out")
        waveform_temp_path = os.path.join(temp_dir, "wave.vcd")

        shutil.copy(user_code_path, solution_path)

# Записуємо тестбенч викладача у тимчасовий файл для подальшої компіляції та симуляції.
        with open(testbench_path, "w", encoding="utf-8") as file:
            file.write(testbench_text)

# Команда для компіляції HDL-коду студента разом з тестбенчем викладача за допомогою Icarus Verilog.
        compile_command = [
            "iverilog",
            "-o",
            output_path,
            solution_path,
            testbench_path
        ]

# Запускаємо компіляцію та симуляцію, обробляючи можливі помилки, такі як відсутність Icarus Verilog 
# або перевищення часу виконання.
        try:
            compile_result = subprocess.run(
                compile_command,
                capture_output=True,
                text=True,
                timeout=10
            )
        except FileNotFoundError:
            return (
                "SYSTEM_ERROR",
                "Ошибка: Icarus Verilog не установлен или команда iverilog не добавлена в PATH.",
                0,
                0,
                0,
                False
            )
        except subprocess.TimeoutExpired:
            return (
                "TIMEOUT",
                "Ошибка: компиляция выполнялась слишком долго.",
                0,
                0,
                0,
                False
            )

# Якщо компіляція завершилася з помилкою, повертаємо статус COMPILE_ERROR та виведення компілятора для діагностики студенту.
        if compile_result.returncode != 0:
            return (
                "COMPILE_ERROR",
                compile_result.stderr or compile_result.stdout,
                0,
                0,
                0,
                False
            )
        
# Команда для запуску симуляції зкомпільованого HDL-коду за допомогою Icarus Verilog. 
# Вона виконує симуляцію та збирає вивід для подальшої обробки та формування звіту для студента.
        run_command = ["vvp", output_path]
        try:
            run_result = subprocess.run(
                run_command,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=temp_dir
            )
        except subprocess.TimeoutExpired:
            return (
                "TIMEOUT",
                "Ошибка: симуляция выполнялась слишком долго.",
                0,
                0,
                0
            )

        full_output = run_result.stdout + run_result.stderr

        waveform_created = False

        if waveform_save_path:
            vcd_files = [
                file_name
                for file_name in os.listdir(temp_dir)
                if file_name.lower().endswith(".vcd")
            ]

            if vcd_files:
                source_vcd_path = os.path.join(temp_dir, vcd_files[0])
                shutil.copy(source_vcd_path, waveform_save_path)
                waveform_created = True

        if run_result.returncode != 0:
            return (
                "SIMULATION_ERROR",
                full_output,
                0,
                0,
                0,
                False
            )

# Обробляємо вивід симуляції, шукаючи рядки, які починаються з "CASE|", 
# щоб визначити результати кожного тесту та сформувати звіт для студента.
        if "CASE|" in full_output:
            formatted_report, score, passed_tests, total_tests = format_hdl_report(full_output)

            if passed_tests == total_tests:
                status = "PASSED"
            elif passed_tests > 0:
                status = "PARTIAL"
            else:
                status = "FAILED"

            return (
                status,
                formatted_report,
                score,
                passed_tests,
                total_tests, 
                waveform_created
            )

        if "ALL_TESTS_PASSED" in full_output:
            return (
                "PASSED",
                full_output,
                100,
                1,
                1,
                waveform_created
            )

        return (
            "FAILED",
            full_output or "Тесты не пройдены или testbench не вывел результат проверки.",
            0,
            0,
            0,
            waveform_created
        )


# =========================
# 7. Перевірка Python-рішень
# =========================

# Функція для перевірки доступності Docker на комп'ютері. 
# Вона намагається виконати команду "docker --version" і перевіряє, чи вона виконується успішно, 
# щоб визначити, чи встановлений та доступний Docker для запуску перевірки Python-коду в контейнері.
def is_docker_available():
    """
    Проверяет, доступен ли Docker на компьютере.
    """

    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except Exception:
        return False


# Функція для перевірки наявності необхідного Docker-образу для перевірки Python-коду.
def is_python_checker_image_available():
    """
    Проверяет, собран ли Docker-образ для Python-проверки.
    """

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", PYTHON_DOCKER_IMAGE],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except Exception:
        return False


# Функція для первинної перевірки потенційно небезпечних конструкцій у Python-коді студента.
def contains_dangerous_python_code(code):
    forbidden_imports = {
        "os",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "requests",
        "urllib",
        "ftplib",
        "http",
        "multiprocessing"
    }

    forbidden_calls = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input"
    }

    try:
        tree = ast.parse(code)

    except SyntaxError:
        return False, ""

# Проходимо по всіх вузлах абстрактного синтаксичного дерева та шукаємо заборонені імпорти, виклики функцій та конструкції. 
# Якщо знаходимо, повертаємо статус небезпеки та фрагмент коду,
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]

                if module_name in forbidden_imports:
                    return True, f"import {module_name}"

        if isinstance(node, ast.ImportFrom):
            module_name = (node.module or "").split(".")[0]

            if module_name in forbidden_imports:
                return True, f"from {module_name} import ..."

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                function_name = node.func.id

                if function_name in forbidden_calls:
                    return True, f"{function_name}(...)"

        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                return True, "while True"

    return False, ""


# Функція для парсингу результатів виконання pytest та визначення кількості пройдених тестів та загальної кількості тестів.
def parse_pytest_result(output):
    output_lower = output.lower()

# Використовуємо регулярні вирази для пошуку рядків, які містять інформацію про кількість пройдених, 
# провалених тестів та помилок.
    passed = 0
    failed = 0
    errors = 0

    passed_match = re.search(r"(\d+)\s+passed", output_lower)
    failed_match = re.search(r"(\d+)\s+failed", output_lower)
    error_match = re.search(r"(\d+)\s+error", output_lower)

    if passed_match:
        passed = int(passed_match.group(1))

    if failed_match:
        failed = int(failed_match.group(1))

    if error_match:
        errors = int(error_match.group(1))

    total = passed + failed + errors

    return passed, total


# Функція для формування зрозумілого звіту для студента на основі сирого виводу pytest та кількості пройдених тестів.
def format_python_report(raw_output, passed_tests, total_tests):

    if total_tests > 0:
        score = round((passed_tests / total_tests) * 100)
    else:
        score = 0

    report = []
    report.append(f"Результат: {score} / 100 баллов")
    report.append(f"Пройдено тестов: {passed_tests} из {total_tests}")
    report.append("")
    report.append("Отчет pytest:")
    report.append(raw_output.strip())

    return "\n".join(report)


# Основна функція для перевірки Python-розв'язку студента в Docker-контейнері 
# з використанням тестів викладача та формування результату перевірки.
def run_python_unit_tests_check(solution_path, lab):

# Перед запуском перевірки коду в Docker-контейнері, спочатку перевіряємо, 
# чи доступний Docker та чи є необхідний образ для перевірки Python-коду.
    if not is_docker_available():
        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Docker недоступен.\n\n"
                "Проверьте, что Docker Desktop установлен и запущен."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

# Перевіряємо, чи є необхідний Docker-образ для перевірки Python-коду. 
# Якщо його немає, повертаємо інструкції для викладача щодо його створення.
    if not is_python_checker_image_available():
        return {
            "status": "SYSTEM_ERROR",
            "output": (
                f"Docker-образ {PYTHON_DOCKER_IMAGE} не найден.\n\n"
                "Соберите его командой:\n"
                "docker build -t fpga-python-checker:latest docker/python-checker"
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

    temp_dir = tempfile.mkdtemp(prefix="python_check_")

    try:
        with open(solution_path, "r", encoding="utf-8", errors="replace") as file:
            student_code = file.read()

        is_dangerous, dangerous_fragment = contains_dangerous_python_code(student_code)

# Якщо код містить потенційно небезпечні конструкції, не запускаємо його в Docker-контейнері та 
# повертаємо відповідний статус і пояснення для студента.
        if is_dangerous:
            return {
                "status": "SECURITY_BLOCK",
                "output": (
                    "Код не был запущен, так как система обнаружила потенциально опасную конструкцию.\n\n"
                    f"Обнаруженный фрагмент: {dangerous_fragment}\n\n"
                    "В учебной среде запрещены операции с файловой системой, системными командами, "
                    "сетью и динамическим выполнением кода."
                ),
                "score": 0,
                "passed_tests": 0,
                "total_tests": 0
            }

        solution_file = os.path.join(temp_dir, "solution.py")
        test_file = os.path.join(temp_dir, "test_solution.py")

        shutil.copy(solution_path, solution_file)

        with open(test_file, "w", encoding="utf-8") as file:
            file.write(lab["testbench"])

        host_workspace = os.path.abspath(temp_dir)

# Команда для запуску Docker-контейнера з обмеженнями ресурсів та без мережі.
        docker_command = [
            "docker",
            "run",
            "--rm",

            "--network",
            "none",

            "--cpus",
            "0.5",

            "--memory",
            "128m",

            "--pids-limit",
            "64",

            "--read-only",

            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",

            "--security-opt",
            "no-new-privileges",

            "--cap-drop",
            "ALL",

            "-e",
            "PYTHONDONTWRITEBYTECODE=1",

            "-e",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",

            "-v",
            f"{host_workspace}:/workspace:rw",

            "-w",
            "/workspace",

            PYTHON_DOCKER_IMAGE,

            "python",
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "test_solution.py"
        ]

# Запускаємо Docker-контейнер з тестами та обробляємо можливі помилки, такі як перевищення часу виконання.
        result = subprocess.run(
            docker_command,
            capture_output=True,
            text=True,
            timeout=PYTHON_CHECK_TIMEOUT_SECONDS
        )

        output = result.stdout + "\n" + result.stderr

        passed_tests, total_tests = parse_pytest_result(output)

# Якщо вивід містить помилки синтаксису або відступів, повертаємо статус COMPILE_ERROR та виведення для діагностики студенту.
        if "syntaxerror" in output.lower() or "indentationerror" in output.lower():
            return {
                "status": "COMPILE_ERROR",
                "output": format_python_report(output, 0, total_tests),
                "score": 0,
                "passed_tests": 0,
                "total_tests": total_tests
                
            }

# Якщо не вдалося визначити кількість тестів, повертаємо статус FAILED та відповідне повідомлення для студента.
        if total_tests == 0:
            return {
                "status": "FAILED",
                "output": format_python_report(
                    output + "\n\nНе удалось определить количество тестов.",
                    0,
                    0
                ),
                "score": 0,
                "passed_tests": 0,
                "total_tests": 0
            }

        score = round((passed_tests / total_tests) * 100)

# Визначаємо підсумковий статус на основі кількості пройдених тестів: 
# якщо всі тести пройдені, 
# якщо частина тестів пройдена, 
# або якщо тести не пройдені.
        if result.returncode == 0:
            status = "PASSED"
        elif passed_tests > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"

        return {
            "status": status,
            "output": format_python_report(output, passed_tests, total_tests),
            "score": score,
            "passed_tests": passed_tests,
            "total_tests": total_tests
        }

# Обробляємо перевищення часу виконання та повертаємо відповідний статус і пояснення для студента.
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "output": (
                "Превышено время выполнения Python-кода.\n\n"
                "Возможна ошибка в цикле, рекурсии или слишком тяжелый алгоритм."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

# Обробляємо інші можливі помилки, які можуть виникнути під час перевірки Python-коду, 
# та повертаємо відповідний статус і пояснення для студента.
    except Exception as error:
        return {
            "status": "SYSTEM_ERROR",
            "output": f"Ошибка системы проверки Python-задания: {str(error)}",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Функція для запуску перевірки рішення студента для завдань з Python, яка виконує юніт-тести та повертає результат у стандартному форматі, 
# щоб забезпечити єдиний формат результатів перевірки для всіх типів лабораторних робіт 
# та полегшити формування адаптивного навчального плану на основі результатів перевірки.
def run_sql_query_check(solution_path, lab):
    return {
        "status": "SYSTEM_ERROR",
        "output": "Проверка SQL-заданий пока не реализована.",
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0
    }


# Функція для запуску перевірки рішення студента для завдань з C++, яка компілює та виконує код та повертає результат у стандартному форматі,
# щоб забезпечити єдиний формат результатів перевірки для всіх типів лабораторних робіт 
# та полегшити формування адаптивного навчального плану на основі результатів перевірки.
def run_cpp_tests_check(solution_path, lab):
    return {
        "status": "SYSTEM_ERROR",
        "output": "Проверка C++-заданий пока не реализована.",
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0
    }


# Функція для запуску перевірки рішення студента на основі типу перевірки, визначеного в лабораторній роботі, 
# та повернення результату перевірки у стандартному форматі, щоб забезпечити єдиний формат результатів перевірки 
# для всіх типів лабораторних робіт та полегшити формування адаптивного навчального плану на основі результатів перевірки.
def run_solution_check(solution_path, lab, waveform_save_path=None):

    checker_type = lab["checker_type"] or "hdl_testbench"

    if checker_type == "hdl_testbench":
        status, output, score, passed_tests, total_tests, waveform_created = run_hdl_check(
            solution_path,
            lab["testbench"],
            waveform_save_path
        )

        return {
            "status": status,
            "output": output,
            "score": score,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "waveform_created": waveform_created
        }

    if checker_type == "python_unit_tests":
        return run_python_unit_tests_check(solution_path, lab)

    if checker_type == "sql_query":
        return {
            "status": "SYSTEM_ERROR",
            "output": "Проверка SQL-заданий пока не реализована.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
            "waveform_created": False
        }

    if checker_type == "cpp_tests":
        return {
            "status": "SYSTEM_ERROR",
            "output": "Проверка C++-заданий пока не реализована.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
            "waveform_created": False
        }

    return {
        "status": "SYSTEM_ERROR",
        "output": f"Неизвестный тип проверки: {checker_type}",
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0,
        "waveform_created": False
    }


# =========================
# 8. Діагностика помилок рішень
# =========================

# Функція для визначення теми лабораторної роботи на основі її назви, опису, тестбенча та коду студента.
def detect_lab_topic_for_diagnostics(lab, code):
    text = (
        str(lab["title"]) + " " +
        str(lab["description"]) + " " +
        str(lab["testbench"]) + " " +
        str(code)
    ).lower()

# На основі ключових слів у тексті визначаємо тему лабораторної роботи для подальшої діагностики 
# та формування рекомендацій для студента.
    if "mux" in text or "мультиплексор" in text or "селектор" in text:
        return "mux"

    if "adder" in text or "сумматор" in text or "sum" in text or "carry" in text:
        return "adder"

    if "counter" in text or "счетчик" in text or "счётчик" in text or "count" in text:
        return "counter"

    if "register" in text or "регистр" in text:
        return "register"

    if "fsm" in text or "автомат" in text or "state" in text:
        return "fsm"

    return "general"


# Функція для перевірки, чи містить текст хоча б одне з ключових слів.
def has_any(text, keywords):
    text = text.lower()

    for keyword in keywords:
        if keyword.lower() in text:
            return True

    return False


# Функція для примітивного виявлення ризику неповного опису умов у комбінаційній логіці, 
# наприклад, якщо є if, але немає else, або якщо є case, але немає default.
def code_has_incomplete_condition(code):

    code_lower = code.lower()

    has_if = "if" in code_lower
    has_else = "else" in code_lower

    has_case = "case" in code_lower
    has_default = "default" in code_lower

    if has_if and not has_else:
        return True

    if has_case and not has_default:
        return True

    return False


# Функція для витягування блоків з виводу перевірки, які містять інформацію про помилкові тести, 
# щоб потім використовувати їх для формування детальних рекомендацій для студента.
def get_failed_test_blocks(output):

    lines = output.splitlines()
    failed_blocks = []

    for index, line in enumerate(lines):
        line_lower = line.lower()

        if "ошибка" in line_lower and line_lower.strip().startswith("тест"):
            block = [line]

            if index + 1 < len(lines):
                block.append(lines[index + 1])

            if index + 2 < len(lines):
                block.append(lines[index + 2])

            failed_blocks.append("\n".join(block))

    return failed_blocks


# Функція для класифікації помилок у HDL-розв'язках студентів на основі статусу перевірки, виводу та теми лабораторної роботи.
def classify_hdl_error(status, output, lab, code):

    output_lower = str(output).lower()
    code_lower = str(code).lower()
    topic = detect_lab_topic_for_diagnostics(lab, code)
    failed_blocks = get_failed_test_blocks(output)
    failed_text = "\n".join(failed_blocks).lower()

    # Якщо всі тести пройдені, повертаємо статус без помилок та рекомендації для студента.
    if status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Ошибок не обнаружено",
            "error_details": "HDL-решение успешно прошло все тесты.",
            "recommendation": "Дополнительные действия не требуются.",
            "error_confidence": 100
        }

# Розбіжність імені модуля 
    if status == "COMPILE_ERROR" and has_any(output_lower, [
        "unknown module",
        "module not found",
        "unable to bind",
        "unknown module type",
        "root module"
    ]):
        return {
            "error_type": "MODULE_NAME_MISMATCH",
            "error_title": "Несовпадение имени модуля",
            "error_details": (
                "Testbench не смог подключить модуль студента. "
                "Чаще всего это происходит, когда имя модуля в HDL-файле не совпадает с именем, ожидаемым в задании."
            ),
            "recommendation": (
                "Проверьте, что имя после ключевого слова module полностью совпадает с именем, указанным в лабораторной работе."
            ),
            "error_confidence": 95
        }

# Розбіжність портів модуля
    if status == "COMPILE_ERROR" and has_any(output_lower, [
        "port",
        "is not a port",
        "cannot bind",
        "failed to elaborate port",
        "no port named"
    ]):
        return {
            "error_type": "PORT_MISMATCH",
            "error_title": "Несовпадение портов модуля",
            "error_details": (
                "Testbench ожидает определённые входы и выходы, но в модуле студента они названы иначе "
                "или отсутствуют."
            ),
            "recommendation": (
                "Сравните список портов в задании и в вашем Verilog-модуле. "
                "Имена входов и выходов должны совпадать с testbench."
            ),
            "error_confidence": 90
        }

# Помилка компіляції HDL-коду
    if status == "COMPILE_ERROR":
        return {
            "error_type": "COMPILE_ERROR",
            "error_title": "Ошибка компиляции HDL-кода",
            "error_details": (
                "Код не был скомпилирован. Возможны синтаксические ошибки, пропущенные точки с запятой, "
                "неверные объявления сигналов или ошибки структуры module/endmodule."
            ),
            "recommendation": (
                "Проверьте синтаксис Verilog: точки с запятой, объявления input/output, assign, always, begin/end и endmodule."
            ),
            "error_confidence": 85
        }

# Помилка reset/clock для послідовних схем
    if topic in ["counter", "register", "fsm"] and has_any(failed_text + output_lower, [
        "reset", "rst", "clock", "clk", "posedge", "negedge", "сброс", "такт"
    ]):
        return {
            "error_type": "RESET_CLOCK_ERROR",
            "error_title": "Ошибка reset/clock в последовательностной логике",
            "error_details": (
                "Ошибка связана с поведением схемы при тактовом сигнале или сигнале сброса. "
                "Для последовательностных схем важно корректно описать clock, reset и изменение состояния."
            ),
            "recommendation": (
                "Проверьте блок always, чувствительность к clock/reset и начальное значение после сброса."
            ),
            "error_confidence": 88
        }

# Помилка сигналу керування для мультиплексора
    if topic == "mux" and has_any(failed_text + output_lower, [
        "sel", "select", "выбор", "управля"
    ]):
        return {
            "error_type": "CONTROL_SIGNAL_ERROR",
            "error_title": "Ошибка выбора управляющего сигнала",
            "error_details": (
                "В ошибочных тестах видно, что выходной сигнал выбирает не тот вход при одном из значений управляющего сигнала."
            ),
            "recommendation": (
                "Проверьте, что при sel = 0 на выход передаётся d0, а при sel = 1 — d1."
            ),
            "error_confidence": 92
        }

# Неповний опис умов
    if code_has_incomplete_condition(code) or has_any(output_lower, [
        "x", "z", "latch", "undefined"
    ]):
        return {
            "error_type": "INCOMPLETE_CONDITION",
            "error_title": "Неполное описание условий",
            "error_details": (
                "В коде может быть не описана часть вариантов входных сигналов. "
                "Из-за этого выход может получать неопределённое значение или сохранять старое состояние."
            ),
            "recommendation": (
                "Проверьте наличие ветки else для if-условий или default для case-конструкций."
            ),
            "error_confidence": 80
        }

# Неправильна комбінаційна логіка
    if topic in ["mux", "adder", "general"] and status in ["FAILED", "PARTIAL"]:
        return {
            "error_type": "WRONG_COMBINATIONAL_LOGIC",
            "error_title": "Неверная комбинационная логика",
            "error_details": (
                "Код компилируется, но результаты работы схемы не совпадают с ожидаемыми значениями testbench."
            ),
            "recommendation": (
                "Составьте таблицу истинности для задания и сравните её с выражениями assign или always в вашем коде."
            ),
            "error_confidence": 78
        }

    # Не пройдено граничних тестів
    if status in ["FAILED", "PARTIAL"] and has_any(failed_text, [
        "1, b=1", "111", "max", "min", "0", "гранич"
    ]):
        return {
            "error_type": "BOUNDARY_TEST_FAILED",
            "error_title": "Не пройдены граничные тесты",
            "error_details": (
                "Решение работает для части входных данных, но ошибается на предельных или важных комбинациях сигналов."
            ),
            "recommendation": (
                "Отдельно проверьте случаи со всеми нулями, всеми единицами, reset и переходными состояниями."
            ),
            "error_confidence": 70
        }

    # Загальна помилка поведінки
    return {
        "error_type": "FUNCTIONAL_ERROR",
        "error_title": "Функциональная ошибка HDL-решения",
        "error_details": (
            "Решение не прошло часть тестов. Ошибка связана не с компиляцией, а с поведением HDL-модуля."
        ),
        "recommendation": (
            "Проанализируйте строки 'Ожидалось' и 'Получено' в отчёте testbench и найдите, для каких входов логика работает неверно."
        ),
        "error_confidence": 60
    }


# Функція для класифікації помилок у Python-розв'язках студентів на основі статусу перевірки, виводу та теми лабораторної роботи.
def classify_python_error(status, output, lab, code):
    output_lower = str(output).lower()

# Якщо всі тести пройдені, повертаємо статус без помилок та рекомендації для студента.
    if status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Ошибок не обнаружено",
            "error_details": "Решение прошло все unit-тесты.",
            "recommendation": "Дополнительные действия не требуются.",
            "error_confidence": 100
        }

# Якщо вивід містить синтаксичні помилки, повертаємо відповідний статус та рекомендації для студента щодо виправлення синтаксису Python.
    if "syntaxerror" in output_lower:
        return {
            "error_type": "PYTHON_SYNTAX_ERROR",
            "error_title": "Синтаксическая ошибка Python",
            "error_details": "Код не был выполнен из-за синтаксической ошибки.",
            "recommendation": "Проверьте двоеточия, отступы, скобки и написание ключевых слов Python.",
            "error_confidence": 95
        }

# Якщо вивід містить помилки логіки, коли код запускається, але результати не співпадають з очікуваними, повертаємо відповідний статус та рекомендації для студента щодо перевірки логіки рішення.
    if "assertionerror" in output_lower:
        return {
            "error_type": "PYTHON_LOGIC_ERROR",
            "error_title": "Логическая ошибка Python-решения",
            "error_details": "Код запускается, но результат функции не совпадает с ожидаемым.",
            "recommendation": "Сравните ожидаемый результат теста с тем, что возвращает ваша функция.",
            "error_confidence": 85
        }

# Якщо вивід містить помилки імені, коли код намагається використовувати змінну або функцію, яка не була визначена, повертаємо відповідний статус та рекомендації для студента щодо перевірки назв змінних та функцій.
    if "nameerror" in output_lower:
        return {
            "error_type": "PYTHON_NAME_ERROR",
            "error_title": "Ошибка имени переменной или функции",
            "error_details": "В коде используется имя, которое не было определено.",
            "recommendation": "Проверьте названия переменных и функций.",
            "error_confidence": 90
        }

    return {
        "error_type": "PYTHON_RUNTIME_ERROR",
        "error_title": "Ошибка выполнения Python-кода",
        "error_details": "Код не прошел проверку unit-тестами.",
        "recommendation": "Изучите вывод тестов и проверьте логику решения.",
        "error_confidence": 70
    }


# Основна функція для класифікації помилок у рішеннях студентів на основі статусу перевірки, виводу та теми лабораторної роботи.
def classify_solution_error(status, output, lab, code):

    checker_type = lab["checker_type"] or "hdl_testbench"

    if checker_type == "hdl_testbench":
        return classify_hdl_error(
            status=status,
            output=output,
            lab=lab,
            code=code
        )

    if checker_type == "python_unit_tests":
        return classify_python_error(
            status=status,
            output=output,
            lab=lab,
            code=code
        )

    return {
        "error_type": "FUNCTIONAL_ERROR",
        "error_title": "Ошибка выполнения задания",
        "error_details": "Решение не прошло автоматическую проверку.",
        "recommendation": "Проанализируйте отчет проверки и исправьте решение.",
        "error_confidence": 60
    }

    
# =========================
# 9. Адаптивний ІІ-модуль та підказки
# =========================

# Функція для визначення номера наступної спроби виконання додаткового завдання (extra task) по конкретній спробі.
def extract_failed_tests(output):

# Витягує блоки з виводу, які містять інформацію про помилкові тести, 
# щоб потім використовувати їх для формування детальних рекомендацій для студента.
    lines = output.splitlines()
    failed = []

    for index, line in enumerate(lines):
        if "— ошибка" in line or "- ошибка" in line:
            block = [line]

            if index + 1 < len(lines):
                block.append(lines[index + 1])

            if index + 2 < len(lines):
                block.append(lines[index + 2])

            failed.append("\n".join(block))

    return failed


# Функція для витягу помилкових тестів з виводу перевірки, яка використовується адаптивним модулем 
# для розуміння конкретної помилки та формування більш точних підказок для студента.
def extract_failed_tests_for_adaptive_module(output):

# Витягує інформацію про помилкові тести з виводу перевірки, щоб адаптивний модуль міг аналізувати 
# конкретні помилки студента та формувати більш точні підказки.
    lines = output.splitlines()
    failed_tests = []

    for index, line in enumerate(lines):
        line_lower = line.lower()

# Шукаємо рядки, які починаються з "тест" і містять слово "ошибка". 
# Це вказує на початок блоку з інформацією про помилковий тест.
        if line_lower.strip().startswith("тест") and "ошибка" in line_lower:
            test_block = {
                "test_line": line,
                "expected": "",
                "actual": ""
            }

            if index + 1 < len(lines) and "ожидалось" in lines[index + 1].lower():
                test_block["expected"] = lines[index + 1]

            if index + 2 < len(lines) and "получено" in lines[index + 2].lower():
                test_block["actual"] = lines[index + 2]

            failed_tests.append(test_block)

    return failed_tests


# Функція для визначення теми лабораторної роботи на основі її назви, опису, тестбенча та коду студента. 
# Використовується адаптивним модулем для розуміння конкретної теми лабораторної роботи 
# та формування більш точних підказок для студента.
def detect_lab_topic_adaptive(submission, code):

    text = (
        str(submission["lab_title"]) + " " +
        str(submission["lab_description"]) + " " +
        str(submission["lab_testbench"]) + " " +
        str(code)
    ).lower()

    if "mux" in text or "мультиплексор" in text or "sel" in text:
        return "mux"

    if "adder" in text or "сумматор" in text or "sum" in text or "carry" in text:
        return "adder"

    if "counter" in text or "счетчик" in text or "счётчик" in text or "count" in text:
        return "counter"

    if "register" in text or "регистр" in text:
        return "register"

    if "fsm" in text or "автомат" in text or "state" in text:
        return "fsm"

    return "general"


# Функція для визначення рівня підказки на основі кількості спроб та повторів помилки. 
# Чим більше спроб і повторів помилки, тим конкретніше підказка, щоб допомогти студенту зрозуміти і виправити помилку.
def define_hint_level(submission, error_history):

    attempt_number = int(submission["attempt_number"] or 1)
    repeated_error_count = 0

    for row in error_history:
        if row["error_type"] == submission["error_type"]:
            repeated_error_count = row["count"]
            break

    if attempt_number <= 1 and repeated_error_count <= 1:
        return 1

    if attempt_number == 2 or repeated_error_count == 2:
        return 2

    return 3


# Функція для формування списку тем, які студенту рекомендується повторити, на основі теми лабораторної роботи та типу помилки.
def build_recommendations_to_repeat(topic, error_type):

    recommendations = []

    if error_type == "MODULE_NAME_MISMATCH":
        recommendations.append("структура Verilog-модуля и имя module")
        recommendations.append("соответствие имени модуля testbench-сценарию")

    elif error_type == "PORT_MISMATCH":
        recommendations.append("объявление входов и выходов input/output")
        recommendations.append("соответствие портов модуля проверочному testbench")

    elif error_type == "COMPILE_ERROR":
        recommendations.append("синтаксис Verilog")
        recommendations.append("точки с запятой, assign, module и endmodule")

    elif error_type == "CONTROL_SIGNAL_ERROR":
        recommendations.append("управляющие сигналы в комбинационной логике")
        recommendations.append("условный оператор Verilog")
        recommendations.append("таблица истинности мультиплексора")

    elif error_type == "INCOMPLETE_CONDITION":
        recommendations.append("полное описание условий if-else")
        recommendations.append("default-ветка в case-конструкциях")
        recommendations.append("избежание неопределенных значений")

    elif error_type == "RESET_CLOCK_ERROR":
        recommendations.append("последовательностная логика")
        recommendations.append("clock/reset")
        recommendations.append("always-блоки и изменение состояния")

    elif error_type == "BOUNDARY_TEST_FAILED":
        recommendations.append("граничные тесты")
        recommendations.append("проверка всех комбинаций входных сигналов")

    elif error_type == "WRONG_COMBINATIONAL_LOGIC":
        recommendations.append("комбинационная логика")
        recommendations.append("оператор assign")
        recommendations.append("таблицы истинности")

    else:
        recommendations.append("анализ testbench")
        recommendations.append("сравнение ожидаемых и полученных значений")

    if topic == "mux":
        recommendations.append("мультиплексор 2 к 1")

    if topic == "adder":
        recommendations.append("логика суммы и переноса")

    if topic == "counter":
        recommendations.append("счетчики и изменение значения по такту")

    return list(dict.fromkeys(recommendations))


# Функція для формування одного додаткового завдання з заданими параметрами, які визначають його зміст та вимоги до відповіді.
def build_task(field, title, text, required_groups, min_length=25):

    return {
        "field": field,
        "title": title,
        "text": text,
        "required_groups": required_groups,
        "min_length": min_length
    }


# Функція для формування адаптивної підказки з урахуванням теми лабораторної роботи, типу помилки, помилкових тестів та рівня підказки.
def generate_adaptive_hint(submission, topic, failed_tests, hint_level):

    error_type = submission["error_type"]

    failed_text = ""

# Якщо є інформація про помилкові тести, включаємо її в підказку, щоб допомогти студенту зрозуміти конкретну помилку в його рішенні.
    if failed_tests:
        first_failed = failed_tests[0]
        failed_text = (
            f"\n\nОдин из ошибочных тестов:\n"
            f"{first_failed['test_line']}\n"
            f"{first_failed['expected']}\n"
            f"{first_failed['actual']}"
        )

# Формуємо підказки на різних рівнях конкретності в залежності від типу помилки та теми лабораторної роботи.
    if error_type == "MODULE_NAME_MISMATCH":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Проблема связана не с логикой схемы, а с подключением модуля к testbench. "
                "Проверьте, совпадает ли имя вашего module с тем, которое требуется в задании."
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо структури Verilog-коду та імені модуля.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Testbench вызывает конкретное имя модуля. Если в задании требуется mux2to1, "
                "то в коде должно быть написано именно module mux2to1(...)."
            )

# Якщо студент продовжує робити помилки з іменем модуля, даємо максимально конкретну підказку з прикладом правильного заголовка модуля.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Проверьте первую строку вашего Verilog-кода. Она должна иметь вид:\n\n"
            "module имя_из_задания(...);\n\n"
            "Не меняйте имя модуля произвольно, иначе testbench не сможет его проверить."
        )

# Якщо помилка пов'язана з портами, формуємо підказки, які допоможуть студенту зрозуміти важливість правильного оголошення входів та виходів у Verilog-модулі та їх відповідності testbench.
    if error_type == "PORT_MISMATCH":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Проблема может быть связана с тем, что имена входов и выходов в вашем модуле "
                "не совпадают с теми, которые ожидает testbench."
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо порівняння списку портів у коді та в умові лабораторної роботи.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Сравните список портов в условии лабораторной работы и в вашем module. "
                "Даже одна лишняя буква в имени порта может привести к ошибке подключения."
            )

# Якщо студент продовжує робити помилки з портами, даємо максимально конкретну підказку з прикладом правильного оголошення портів у заголовку модуля.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Проверьте заголовок модуля. Например, если testbench ожидает d0, d1, sel и y, "
            "то именно эти имена должны быть указаны в списке input/output."
        )

# Якщо помилка пов'язана з логікою вибору для мультиплексора, формуємо підказки, які допоможуть студенту зрозуміти, як правильно описати логіку вибору входів на вихід в залежності від управляючого сигналу sel.
    if error_type == "CONTROL_SIGNAL_ERROR" and topic == "mux":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Ошибка связана с выбором входа. В мультиплексоре управляющий сигнал sel определяет, "
                "какой вход должен попасть на выход y."
                f"{failed_text}"
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо того, який вход вибирається при різних значеннях sel та можливого переплутування d0 і d1.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, какой вход выбирается при sel = 0 и какой при sel = 1. "
                "Если часть тестов не проходит, возможно, d0 и d1 перепутаны местами."
                f"{failed_text}"
            )

# Якщо студент продовжує робити помилки з логікою вибору, даємо максимально конкретну підказку з рекомендацією сравнить условное выражение для y с таблицей истинности мультиплексора.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для мультиплексора 2 к 1 логика выбора должна учитывать оба случая: "
            "sel = 0 и sel = 1. Проверьте условное выражение справа от assign и сопоставьте его "
            "с таблицей истинности."
            f"{failed_text}"
        )

# Якщо помилка пов'язана з reset/clock для послідовних схем, формуємо підказки, які допоможуть студенту зрозуміти важливість правильного опису тактового сигналу та сигналу сброса, а також їх вплив на поведінку схеми.
    if error_type == "RESET_CLOCK_ERROR":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Ошибка связана с последовательностной логикой. Для таких схем важно правильно описать "
                "clock, reset и момент изменения значения."
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо того, як состояние схемы должно меняться по фронту clock и как reset задает начальное значение.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, что состояние схемы меняется по нужному фронту clock, а reset задает корректное "
                "начальное значение."
            )

# Якщо студент продовжує робити помилки з reset/clock, даємо максимально конкретну підказку з рекомендацією сосредоточиться на always-блоке и порядке условий внутри него.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Обратите внимание на always-блок. Для последовательностных схем обычно проверяют чувствительность "
            "к clock/reset и порядок условий внутри блока."
        )

# Якщо помилка пов'язана з неповним описом умов, формуємо підказки, які допоможуть студенту зрозуміти важливість опису всіх можливих варіантів входних сигналів та уникнення неопределенных значений.
    if error_type == "INCOMPLETE_CONDITION":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "В коде может быть не описан один из вариантов входных сигналов."
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо того, що может отсутствовать ветка else для if-условий или default для case-конструкций.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, есть ли ветка else для if-условий или default для case-конструкций."
            )

# Якщо студент продовжує робити помилки з неповним описом умов, даємо максимально конкретну підказку з рекомендацією сосредоточиться на тех входных комбинациях, которые не описаны в коде и могут приводить к неопределенным значениям.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для комбинационной логики важно, чтобы выход получал значение при всех возможных вариантах входов. "
            "Иначе могут появиться неопределенные значения или защелки."
        )

# Якщо помилка пов'язана з неправильною комбінаційною логікою, формуємо підказки, які допоможуть студенту зрозуміти, що код компілюється, але логіка схеми не співпадає з очікуваною, та рекомендуємо сравнить таблицу истинности задания с выражениями assign или always в коде.
    if error_type == "WRONG_COMBINATIONAL_LOGIC":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Код компилируется, но логика схемы не совпадает с ожидаемой."
                f"{failed_text}"
            )

# Якщо студент вже робив кілька спроб і помилка повторюється, даємо більш конкретну підказку щодо того, что может быть ошибка в логических выражениях, и рекомендуем сравнить таблицу истинности задания с выражениями assign или always в коде.
        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Сравните таблицу истинности задания с выражениями assign или always в вашем коде."
                f"{failed_text}"
            )

# Якщо студент продовжує робити помилки з логікою, даємо максимально конкретну підказку з рекомендацією сосредоточиться на тех входных комбинациях, где testbench показывает различия между ожидаемым и полученным значением, чтобы понять, в чем именно заключается ошибка логики.
        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Сосредоточьтесь на тех входных комбинациях, где testbench показывает различие между "
            "ожидаемым и полученным значением."
            f"{failed_text}"
        )

# Для інших типів помилок формуємо загальну підказку з рекомендацією проаналізувати строки "Ожидалось" и "Получено" в отчёте testbench, щоб найти конкретную ошибку в логике решения.
    return (
        f"ИИ-подсказка {hint_level} уровня:\n\n"
        "Система обнаружила ошибку в решении. Начните с анализа строк отчета testbench: "
        "сравните ожидаемые и полученные значения."
        f"{failed_text}"
    )


# Функція для формування індивідуальних додаткових питань на основі теми лабораторної роботи, типу помилки, помилкових тестів та рівня підказки.
def generate_adaptive_questions(submission, topic, failed_tests, hint_level):

    error_type = submission["error_type"]

# Формуємо додаткові питання на різних рівнях конкретності в залежності від типу помилки та теми лабораторної роботи, щоб допомогти студенту краще зрозуміти помилку та виправити її.
    if topic == "mux":
        if error_type == "CONTROL_SIGNAL_ERROR":
            return [
                build_task(
                    "answer_1",
                    "Вопрос 1. Роль управляющего сигнала",
                    "Объясните, какую роль выполняет сигнал sel в мультиплексоре 2 к 1.",
                    [
                        ["sel"],
                        ["выбор", "выбирает", "управляет"],
                        ["d0", "d1", "вход"]
                    ]
                ),
                build_task(
                    "answer_2",
                    "Вопрос 2. Поведение выхода",
                    "Что должно быть на выходе y при sel = 0 и при sel = 1?",
                    [
                        ["sel=0", "sel = 0"],
                        ["d0"],
                        ["sel=1", "sel = 1"],
                        ["d1"]
                    ]
                ),
                build_task(
                    "answer_3",
                    "Вопрос 3. Анализ ошибки",
                    "Какая ошибка могла возникнуть в выражении для y, если при некоторых значениях sel выбирается не тот вход?",
                    [
                        ["sel", "d0", "d1", "y"],
                        ["перепут", "наоборот", "неверно", "ошибка", "условие"]
                    ]
                )
            ]

# Якщо помилка не пов'язана з управляющим сигналом, формуємо загальні питання по темі мультиплексора, щоб допомогти студенту краще зрозуміти його призначення та логіку роботи.
        return [
            build_task(
                "answer_1",
                "Вопрос 1. Назначение мультиплексора",
                "Объясните, для чего используется мультиплексор 2 к 1.",
                [
                    ["мультиплексор", "mux"],
                    ["выбор", "выбирает", "один"],
                    ["вход", "выход"]
                ]
            ),
            build_task(
                "answer_2",
                "Вопрос 2. Таблица истинности",
                "Опишите, как изменяется выход y в зависимости от d0, d1 и sel.",
                [
                    ["y", "выход"],
                    ["sel"],
                    ["d0", "d1"]
                ]
            ),
            build_task(
                "answer_3",
                "Вопрос 3. План исправления",
                "Что вы проверите в HDL-коде перед повторной отправкой решения?",
                [
                    ["провер", "исправ", "измен"],
                    ["assign", "условие", "sel", "код"]
                ]
            )
        ]

# Якщо тема лабораторної роботи пов'язана з сумматором, формуємо питання, які допоможуть студенту краще зрозуміти різницю між sum і carry, граничні випадки та логічні операції, які використовуються для опису їх поведінки.
    if topic == "adder":
        return [
            build_task(
                "answer_1",
                "Вопрос 1. Сумма и перенос",
                "Объясните различие между выходом sum и выходом carry.",
                [
                    ["sum", "сумма"],
                    ["carry", "перенос"]
                ]
            ),
            build_task(
                "answer_2",
                "Вопрос 2. Граничный случай",
                "Что должно произойти при входах 1 и 1 в сумматоре?",
                [
                    ["1"],
                    ["carry", "перенос"],
                    ["sum", "сумма"]
                ]
            ),
            build_task(
                "answer_3",
                "Вопрос 3. Логические операции",
                "Какие логические операции Verilog можно использовать для описания sum и carry?",
                [
                    ["^", "xor", "исключающее"],
                    ["&", "and", "и"]
                ]
            )
        ]

# Якщо тема лабораторної роботи пов'язана з счетчиком, формуємо питання, які допоможуть студенту краще зрозуміти, як должен изменяться выход счетчика при поступлении тактового сигнала, зачем нужен reset и какое значение должен принимать счетчик после сброса, а также какую ошибку может возникнуть при неправильном описании clock или reset.
    if topic == "counter":
        return [
            build_task(
                "answer_1",
                "Вопрос 1. Работа счетчика",
                "Объясните, как должен изменяться выход счетчика при поступлении тактового сигнала.",
                [
                    ["clock", "clk", "такт"],
                    ["увелич", "счит", "значение"]
                ]
            ),
            build_task(
                "answer_2",
                "Вопрос 2. Reset",
                "Зачем нужен reset и какое значение должен принимать счетчик после сброса?",
                [
                    ["reset", "rst", "сброс"],
                    ["0", "ноль", "начальное"]
                ]
            ),
            build_task(
                "answer_3",
                "Вопрос 3. Ошибка последовательностной логики",
                "Какая ошибка может возникнуть, если неправильно описать clock или reset?",
                [
                    ["clock", "clk", "такт", "reset", "rst"],
                    ["ошибка", "значение", "состояние", "неверно"]
                ]
            )
        ]

# Для інших тем формуємо загальні питання, які допоможуть студенту краще зрозуміти призначення HDL-модуля, проаналізувати помилкові тести та визначити, яку частину коду потрібно перевірити перед повторною відправкою рішення.
    return [
        build_task(
            "answer_1",
            "Вопрос 1. Назначение модуля",
            "Опишите назначение HDL-модуля из данной лабораторной работы.",
            [
                ["модуль", "module"],
                ["вход", "выход", "сигнал"]
            ]
        ),
        build_task(
            "answer_2",
            "Вопрос 2. Анализ ошибки",
            "Сравните ожидаемые и полученные значения в ошибочных тестах. Что именно не совпадает?",
            [
                ["ожид", "получ"],
                ["ошибка", "не совпадает", "неверно"]
            ]
        ),
        build_task(
            "answer_3",
            "Вопрос 3. Повторная отправка",
            "Какую часть кода нужно проверить перед повторной отправкой?",
            [
                ["провер", "исправ", "измен"],
                ["код", "логика", "условие", "сигнал"]
            ]
        )
    ]


# Функція для генерації підказки на основі теми лабораторної роботи, типу помилки, помилкових тестів та рівня підказки.
def generate_ai_hint(submission, code, level):

    status = submission["status"]
    output = submission["output"]
    lab_title = submission["lab_title"].lower()
    code_lower = code.lower()
    failed_tests = extract_failed_tests(output)

# Формуємо підказки на різних рівнях конкретності в залежності від типу помилки та теми лабораторної роботи, щоб допомогти студенту краще зрозуміти помилку та виправити її.
    if status == "COMPILE_ERROR":
        if level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "В коде обнаружена ошибка компиляции. Это означает, что симулятор не смог собрать HDL-модуль "
                "вместе с testbench. Чаще всего причина связана с синтаксисом Verilog, неправильным именем модуля "
                "или несовпадением портов.\n\n"
                "Рекомендация: сначала проверьте имя модуля, список входов и выходов, точки с запятой и наличие endmodule."
            )

        if level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Сравните имя модуля и имена портов в задании с тем, что написано в вашем файле. "
                "Если testbench ожидает модуль mux2to1, то в решении должен быть именно module mux2to1. "
                "Если ожидаются порты d0, d1, sel, y, они должны присутствовать в заголовке модуля.\n\n"
                "Также проверьте, что каждая строка assign завершается точкой с запятой."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Похожая структура Verilog-модуля обычно выглядит так:\n\n"
            "module имя_модуля(\n"
            "    input вход1,\n"
            "    input вход2,\n"
            "    output выход\n"
            ");\n\n"
            "assign выход = выражение;\n\n"
            "endmodule\n\n"
            "Используйте эту форму как ориентир, но подставьте имена сигналов из задания."
        )

    if "mux" in lab_title or "мультиплексор" in lab_title:
        if level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Система обнаружила, что решение работает неверно для части входных комбинаций. "
                "Для мультиплексора 2 к 1 ключевым является сигнал выбора sel. "
                "Он определяет, какой из входов должен попасть на выход y.\n\n"
                "Рекомендация: проверьте, что при разных значениях sel выход y получает значение от разных входов."
            )

        if level == 2:
            details = "\n\n".join(failed_tests[:3]) if failed_tests else "Посмотрите строки тестов, где указано «ошибка»."

            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Обратите внимание на тесты, которые не прошли:\n\n"
                f"{details}\n\n"
                "Если ошибка возникает при sel = 0 или sel = 1, вероятно, в коде перепутаны входы d0 и d1 "
                "или условие выбора описано наоборот."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для комбинаторного выбора в Verilog часто используют условный оператор:\n\n"
            "assign выход = условие ? значение_если_истина : значение_если_ложь;\n\n"
            "Это не готовое решение, а пример похожей конструкции. "
            "Проверьте, какое значение должен принимать выход при sel = 0 и при sel = 1 согласно условию задания."
        )

    if "adder" in lab_title or "сумматор" in lab_title:
        if level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Ошибка связана с логикой работы сумматора. Для таких схем важно отдельно проверить сумму "
                "и перенос. Даже если один выход работает правильно, второй может быть рассчитан неверно.\n\n"
                "Рекомендация: составьте таблицу истинности и сравните ее с результатами тестов."
            )

        if level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте случаи, где оба входа равны 1. Для сумматоров именно эта комбинация часто показывает, "
                "правильно ли реализован перенос. Если тест падает на такой комбинации, ошибка может быть в выражении "
                "для carry или sum."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для описания простой комбинаторной логики можно использовать assign и логические операторы Verilog: "
            "^, &, |. Не копируйте готовое решение, а сопоставьте каждый оператор с таблицей истинности вашей схемы."
        )

    if level == 1:
        return (
            "ИИ-подсказка 1 уровня:\n\n"
            "Решение не прошло часть тестов. Это означает, что код компилируется, но поведение HDL-модуля "
            "не совпадает с ожидаемым результатом testbench.\n\n"
            "Рекомендация: начните с анализа тех тестов, где указано «ошибка»."
        )

    if level == 2:
        details = "\n\n".join(failed_tests[:3]) if failed_tests else "Не удалось выделить конкретные ошибочные тесты."

        return (
            "ИИ-подсказка 2 уровня:\n\n"
            f"{details}\n\n"
            "Сравните ожидаемые и полученные значения. Это поможет понять, какая часть логики описана неверно."
        )

    return (
        "ИИ-подсказка 3 уровня:\n\n"
        "Для комбинаторных схем убедитесь, что выход получает значение для всех возможных комбинаций входов. "
        "Для последовательностных схем проверьте clock, reset и изменение состояния по фронту сигнала."
    )


# Функція для визначення теми лабораторної роботи на основі назви, опису та коду студента. 
# Це допомагає адаптивно формувати підказки та питання, які більш точно відповідають конкретній темі лабораторної роботи.
def detect_lab_topic(submission, code):

    text = (
        str(submission["lab_title"]) + " " +
        str(submission["lab_description"]) + " " +
        code
    ).lower()

    if "mux" in text or "мультиплексор" in text or "селектор" in text:
        return "mux"

    if "adder" in text or "сумматор" in text or "sum" in text or "carry" in text:
        return "adder"

    if "counter" in text or "счетчик" in text or "лічильник" in text:
        return "counter"

    if "register" in text or "регистр" in text or "регістр" in text:
        return "register"

    if "fsm" in text or "автомат" in text or "state" in text:
        return "fsm"

    return "general"


# Функція для визначення, на чому краще сфокусувати додаткові питання, 
# на основі результату перевірки, теми лабораторної роботи та коду студента.
def detect_error_focus(submission, code, topic):

    output = str(submission["output"]).lower()
    code_lower = code.lower()

# Якщо помилка пов'язана з компіляцією, намагаємося визначити, чи вона пов'язана з іменем модуля, портами чи синтаксисом, щоб сфокусувати питання на відповідній темі.
    if submission["status"] == "COMPILE_ERROR":
        if "unknown module" in output or "unable to bind" in output:
            return "module_or_ports"

        if "syntax" in output or "malformed" in output:
            return "syntax"

        return "compile"

# Якщо помилка пов'язана з логікою, намагаємося визначити, чи вона пов'язана з конкретними аспектами теми лабораторної роботи, щоб сфокусувати питання на цих аспектах.
    if topic == "mux":
        if "sel=0" in output and "ошибка" in output:
            return "mux_sel_0"

        if "sel=1" in output and "ошибка" in output:
            return "mux_sel_1"

        if "d0" in output and "d1" in output:
            return "mux_logic"

        return "mux_general"

# Якщо тема лабораторної роботи пов'язана з сумматором, намагаємося визначити, чи помилка пов'язана з логікою суми, переноса чи загальною логікою, щоб сфокусувати питання на цих аспектах.
    if topic == "adder":
        if "carry" in output:
            return "adder_carry"

        if "sum" in output:
            return "adder_sum"

        return "adder_general"

# Якщо тема лабораторної роботи пов'язана з счетчиком, намагаємося визначити, чи помилка пов'язана з логікою сброса, тактового сигнала чи загальною логікою, щоб сфокусувати питання на цих аспектах.
    if topic == "counter":
        if "reset" in output or "rst" in output:
            return "counter_reset"

        if "clk" in code_lower or "clock" in code_lower:
            return "counter_clock"

        return "counter_general"

# Якщо тема лабораторної роботи пов'язана з регістром, намагаємося визначити, чи помилка пов'язана з логікою сброса чи загальною логікою, щоб сфокусувати питання на цих аспектах.
    if topic == "register":
        if "reset" in output or "rst" in output:
            return "register_reset"

        return "register_general"

# Якщо тема лабораторної роботи пов'язана з автоматом, намагаємося визначити, чи помилка пов'язана з логікою состояний чи загальною логікою, щоб сфокусувати питання на цих аспектах.
    if topic == "fsm":
        if "state" in output or "состоя" in output:
            return "fsm_state"

        return "fsm_general"

    return "general_logic"


# Функція для генерації набору додаткових завдань на основі теми лабораторної роботи, типу помилки, помилкових тестів та кількості спроб студента, щоб допомогти йому краще зрозуміти помилку та виправити її.
def generate_extra_tasks(submission, code):

    topic = detect_lab_topic(submission, code)
    error_focus = detect_error_focus(submission, code, topic)
    attempts_count = get_student_attempts_count(
        submission["username"],
        submission["lab_id"]
    )

    tasks = []

    if topic == "mux":
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Назначение управляющего сигнала",
                "Объясните, какую роль выполняет сигнал sel в мультиплексоре 2 к 1 и почему без него нельзя выбрать нужный вход.",
                [
                    ["sel"],
                    ["выбор", "выбирает", "управляет", "управляющий"],
                    ["d0", "d1", "вход"]
                ]
            )
        )

        if error_focus == "mux_sel_0":
            tasks.append(
                build_task(
                    "answer_2",
                    "Вопрос 2. Анализ случая sel = 0",
                    "Система обнаружила ошибку в одном из тестов с sel = 0. Объясните, какой вход должен передаваться на выход y при sel = 0.",
                    [
                        ["sel=0", "sel = 0"],
                        ["d0"],
                        ["y", "выход"]
                    ]
                )
            )
        elif error_focus == "mux_sel_1":
            tasks.append(
                build_task(
                    "answer_2",
                    "Вопрос 2. Анализ случая sel = 1",
                    "Система обнаружила ошибку в одном из тестов с sel = 1. Объясните, какой вход должен передаваться на выход y при sel = 1.",
                    [
                        ["sel=1", "sel = 1"],
                        ["d1"],
                        ["y", "выход"]
                    ]
                )
            )
        else:
            tasks.append(
                build_task(
                    "answer_2",
                    "Вопрос 2. Поведение выхода y",
                    "Опишите полную логику работы выхода y: что должно быть на выходе при sel = 0 и что должно быть при sel = 1.",
                    [
                        ["sel=0", "sel = 0"],
                        ["d0"],
                        ["sel=1", "sel = 1"],
                        ["d1"]
                    ]
                )
            )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. Причина ошибки в HDL-коде",
                "Сравните ожидаемые и полученные значения в ошибочных тестах. Какая логическая ошибка могла быть допущена в выражении для y?",
                [
                    ["ошибка", "неверно", "перепутаны", "наоборот", "условие"],
                    ["sel", "d0", "d1", "y"]
                ]
            )
        )

    elif topic == "adder":
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Назначение выходов сумматора",
                "Объясните различие между выходом суммы и выходом переноса в сумматоре.",
                [
                    ["sum", "сумма"],
                    ["carry", "перенос"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_2",
                "Вопрос 2. Проверка граничного случая",
                "Что должно происходить в сумматоре, если оба входных сигнала равны 1? Почему этот случай важен для проверки?",
                [
                    ["1"],
                    ["carry", "перенос"],
                    ["sum", "сумма"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. Логические операции",
                "Какие логические операции Verilog можно использовать для описания суммы и переноса?",
                [
                    ["^", "xor", "исключающее"],
                    ["&", "and", "и"]
                ]
            )
        )

    elif topic == "counter":
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Принцип работы счётчика",
                "Объясните, как должен изменяться выход счётчика при поступлении тактового сигнала.",
                [
                    ["clock", "clk", "такт", "тактовый"],
                    ["увелич", "счит", "значение"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_2",
                "Вопрос 2. Роль reset",
                "Объясните, зачем в счётчике используется сигнал reset и какое значение должен принимать выход после сброса.",
                [
                    ["reset", "rst", "сброс"],
                    ["0", "ноль", "начальное"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. Ошибка последовательностной логики",
                "Какая ошибка может возникнуть, если неправильно описать изменение значения по clock или не учесть reset?",
                [
                    ["clock", "clk", "такт"],
                    ["reset", "rst", "сброс", "состояние", "значение"]
                ]
            )
        )

    elif topic == "register":
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Назначение регистра",
                "Объясните, для чего используется регистр в цифровой схеме и чем он отличается от простой комбинационной логики.",
                [
                    ["регистр", "register"],
                    ["хран", "запомина", "значение"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_2",
                "Вопрос 2. Clock и запись данных",
                "Объясните, при каком условии регистр должен записывать новое значение входного сигнала.",
                [
                    ["clock", "clk", "такт"],
                    ["запис", "сохраня", "значение"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. Анализ ошибки",
                "Какие ошибки могут возникнуть, если в регистре неправильно описать reset или условие записи?",
                [
                    ["reset", "rst", "сброс", "clock", "clk"],
                    ["ошибка", "неверно", "значение", "состояние"]
                ]
            )
        )

    elif topic == "fsm":
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Состояния автомата",
                "Объясните, что такое состояние конечного автомата и зачем оно нужно при описании цифровой логики.",
                [
                    ["состояние", "state"],
                    ["автомат", "fsm", "переход"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_2",
                "Вопрос 2. Условия переходов",
                "Опишите, почему для конечного автомата важно корректно задать условия переходов между состояниями.",
                [
                    ["переход"],
                    ["состояние", "state"],
                    ["условие", "вход"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. Ошибка в логике автомата",
                "Какая ошибка может возникнуть, если не обработать одно из состояний или один из входных вариантов?",
                [
                    ["состояние", "state"],
                    ["ошибка", "не обработ", "не учтен", "вариант"]
                ]
            )
        )

    else:
        tasks.append(
            build_task(
                "answer_1",
                "Вопрос 1. Назначение модуля",
                "Опишите назначение HDL-модуля, который требуется разработать в этой лабораторной работе.",
                [
                    ["модуль", "module"],
                    ["вход", "выход", "сигнал"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_2",
                "Вопрос 2. Анализ ошибочных тестов",
                "Сравните ожидаемые и полученные значения в ошибочных тестах. Что именно не совпадает?",
                [
                    ["ожид", "получ"],
                    ["ошибка", "не совпадает", "неверно"]
                ]
            )
        )

        tasks.append(
            build_task(
                "answer_3",
                "Вопрос 3. План исправления",
                "Опишите, какую часть HDL-кода нужно проверить в первую очередь перед повторной отправкой решения.",
                [
                    ["провер", "исправ", "измен"],
                    ["код", "логика", "условие", "сигнал"]
                ]
            )
        )

    if attempts_count >= 3:
        tasks[2]["text"] += (
            " У вас уже несколько попыток по этой лабораторной работе, поэтому ответ должен содержать не только общее объяснение, "
            "но и конкретное указание, что именно вы планируете изменить в коде."
        )

        tasks[2]["required_groups"].append(
            ["исправ", "измен", "провер", "планирую"]
        )

    return tasks


# Функція для нормалізації тексту відповіді студента, щоб система однаково розуміла відповіді, незалежно від регістру, наявності зайвих пробілів та інших незначних відмінностей у форматуванні.
def normalize_text(text):
    if text is None:
        return ""

    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Функція для видалення пробілів з тексту, щоб система однаково розуміла відповіді, незалежно від наявності пробілів між словами чи знаками рівності.
def compact_text(text):
    text = normalize_text(text)
    return text.replace(" ", "")


# Функція для визначення, чи є відповідь студента занадто короткою або явно безглуздою, щоб відсікти такі відповіді та не враховувати їх при оцінюванні додаткових завдань.
def is_bad_answer(text):

    normalized = normalize_text(text)

    if len(normalized) < 20:
        return True

    bad_phrases = [
        "не знаю",
        "хз",
        "asdf",
        "qwerty",
        "чушь",
        "123",
        "нет ответа",
        "не понял",
        "не понимаю"
    ]

    if any(phrase in normalized for phrase in bad_phrases):
        return True

    letters_only = re.sub(r"[^a-zа-я0-9]", "", normalized)

    if len(letters_only) > 0 and len(set(letters_only)) <= 3:
        return True

    return False


# Функція для перевірки відповіді студента на відповідність вимогам конкретного завдання, включаючи мінімальну довжину та наявність ключових понять, щоб визначити, чи можна вважати відповідь прийнятною для отримання бонусу.
def answer_matches_task(answer, task):

    normalized = normalize_text(answer)
    compact = compact_text(answer)

    if is_bad_answer(answer):
        return False

    if len(normalized) < task.get("min_length", 25):
        return False

    required_groups = task.get("required_groups", [])

    for group in required_groups:
        group_matched = False

        for keyword in group:
            keyword_normalized = normalize_text(keyword)
            keyword_compact = compact_text(keyword)

            if keyword_normalized in normalized or keyword_compact in compact:
                group_matched = True
                break

        if not group_matched:
            return False

    return True


# Функція для оцінювання відповідей студента на додаткові завдання та визначення кількості правильних відповідей, розміру бонусу та формування тексту зворотного зв'язку, щоб надати студенту конкретну інформацію про те, які відповіді були прийняті, а які ні, і чому.
def evaluate_extra_task_answers(submission, answers):

    code = read_submission_code(submission["filename"])
    tasks = generate_extra_tasks(submission, code)

    correct_count = 0
    feedback_lines = []

    for task in tasks:
        field = task["field"]
        answer = answers.get(field, "")

        if answer_matches_task(answer, task):
            correct_count += 1
            feedback_lines.append(
                f"{task['title']}: ответ принят."
            )
        else:
            feedback_lines.append(
                f"{task['title']}: ответ не принят. Ответ слишком короткий, бессодержательный или не содержит ключевых понятий по теме задания."
            )

    if correct_count == 3:
        bonus = 20
    elif correct_count == 2:
        bonus = 10
    else:
        bonus = 0

    return correct_count, bonus, "\n".join(feedback_lines)


# Функція для отримання списку ключових понять з паспорта лабораторної роботи, щоб використовувати ці поняття при формуванні підказок та додаткових завдань, які більш точно відповідають темі лабораторної роботи.
def get_lab_concepts(lab_or_submission):

    concepts = ""

    if "concepts" in lab_or_submission.keys():
        concepts = lab_or_submission["concepts"] or ""

    elif "lab_concepts" in lab_or_submission.keys():
        concepts = lab_or_submission["lab_concepts"] or ""

    return [
        concept.strip()
        for concept in str(concepts).split(",")
        if concept.strip()
    ]


# Функція для визначення теми лабораторної роботи на основі інформації з паспорта лабораторної роботи та коду студента, щоб більш точно визначити тему та формувати підказки та завдання, які відповідають цій темі.
def get_lab_topic_from_passport(lab_or_submission, code=""):
    """
    Сначала берет тему из паспорта лабораторной работы.
    Если тема не заполнена, пытается определить тему по коду.
    """

    if "topic" in lab_or_submission.keys() and lab_or_submission["topic"]:
        return lab_or_submission["topic"].strip().lower()

    if "lab_topic" in lab_or_submission.keys() and lab_or_submission["lab_topic"]:
        return lab_or_submission["lab_topic"].strip().lower()

    text = str(code).lower()

    if "mux" in text or "sel" in text:
        return "mux"

    if "adder" in text or "sum" in text or "carry" in text:
        return "adder"

    if "counter" in text or "count" in text:
        return "counter"

    if "register" in text or "регистр" in text:
        return "register"

    if "fsm" in text or "state" in text:
        return "fsm"

    if "for " in text or "range" in text:
        return "python_loops"

    return "general"


# Головний алгоритм адаптивного навчального модуля, який приймає інформацію про відправлення студента та код, і на основі цього формує тип помилки, рівень підказки, текст підказки, додаткові питання, рекомендації до повторення та обмежений бонус, щоб допомогти студенту краще зрозуміти помилку та виправити її.
def build_adaptive_learning_plan(submission, code):
   
    topic = get_lab_topic_from_passport(submission, code)
    concepts = get_lab_concepts(submission)
    failed_tests = extract_failed_tests_for_adaptive_module(submission["output"])
    error_history = get_student_error_history(
        submission["username"],
        submission["lab_id"]
    )

    hint_level = define_hint_level(submission, error_history)

    hint_text = generate_adaptive_hint(
        submission=submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=hint_level
    )

    questions = generate_adaptive_questions(
        submission=submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=hint_level
    )

    repeat_topics = build_recommendations_to_repeat(
        topic=topic,
        error_type=submission["error_type"]
    )

    if submission["status"] == "PASSED":
        max_bonus = 0
        bonus_cap = int(submission["score"] or 100)
    elif hint_level == 1:
        max_bonus = 20
        bonus_cap = 80
    elif hint_level == 2:
        max_bonus = 15
        bonus_cap = 75
    else:
        max_bonus = 10
        bonus_cap = 70

    return {
        "topic": topic,
        "concepts": concepts,
        "error_type": submission["error_type"],
        "error_title": submission["error_title"],
        "hint_level": hint_level,
        "hint_text": hint_text,
        "questions": questions,
        "repeat_topics": repeat_topics,
        "max_bonus": max_bonus,
        "bonus_cap": bonus_cap,
        "failed_tests": failed_tests,
        "error_history": error_history
    }


# =========================
# 10. Auth routes - вхід, реєстрація, вихід
# =========================

# Роути для аутентифікації, відображення головної сторінки зі списком лабораторних робіт та сторінки з деталями конкретної лабораторної роботи, 
# включаючи історію відправок студента та результати інших студентів для вчителів.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            if user["status"] != "active":
                if user["status"] == "pending":
                    flash("Ваша учетная запись ожидает подтверждения администратором.")
                elif user["status"] == "blocked":
                    flash("Ваша учетная запись заблокирована.")
                else:
                    flash("Вход временно недоступен.")

                return redirect(url_for("login"))

            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_panel"))

            return redirect(url_for("index"))

        flash("Неверный логин или пароль.")

    return render_template("auth/login.html")


# Роут для реєстрації, який дозволяє новим користувачам створювати облікові записи з роллю студента або викладача, але з початковим статусом "pending", що вимагає підтвердження адміністратора перед активацією облікового запису.
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        full_name = request.form.get("full_name", "").strip()
        student_group = request.form.get("student_group", "").strip()
        email = request.form.get("email", "").strip()

        if role not in ["student", "teacher"]:
            flash("Можно зарегистрироваться только как студент или преподаватель.")
            return redirect(url_for("register"))

        if not username or not password or not full_name:
            flash("Нужно заполнить логин, пароль и ФИО.")
            return redirect(url_for("register"))

        if role == "student" and not student_group:
            flash("Для студента нужно указать группу.")
            return redirect(url_for("register"))

        if role == "teacher":
            student_group = ""

        conn = get_db()

        try:
            conn.execute(
                """
                INSERT INTO users (
                    username,
                    password,
                    role,
                    full_name,
                    student_group,
                    email,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    password,
                    role,
                    full_name,
                    student_group,
                    email,
                    "pending",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )

            conn.commit()
            flash("Заявка на регистрацию отправлена. Дождитесь подтверждения администратора.")

        except sqlite3.IntegrityError:
            flash("Пользователь с таким логином уже существует.")

        conn.close()

        return redirect(url_for("login"))

    return render_template("auth/register.html")


@app.route("/auth/google")
def google_login():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
        google_user = token.get("userinfo")

        if not google_user:
            google_user = google.parse_id_token(token)

    except Exception:
        flash("Не удалось выполнить вход через Google.")
        return redirect(url_for("login"))

    google_id = google_user.get("sub", "")
    email = google_user.get("email", "")
    full_name = google_user.get("name", "")

    if not google_id or not email:
        flash("Google не передал необходимые данные пользователя.")
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE google_id = ?
        """,
        (google_id,)
    ).fetchone()

    if not user:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if user:
            conn.execute(
                """
                UPDATE users
                SET google_id = ?,
                    auth_provider = 'google'
                WHERE id = ?
                """,
                (
                    google_id,
                    user["id"]
                )
            )

            conn.commit()

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE id = ?
                """,
                (user["id"],)
            ).fetchone()

    if user:
        if user["status"] != "active":
            conn.close()

            if user["status"] == "pending":
                flash("Ваша учетная запись ожидает подтверждения администратором.")
            elif user["status"] == "blocked":
                flash("Ваша учетная запись заблокирована.")
            else:
                flash("Вход временно недоступен.")

            return redirect(url_for("login"))

        session["username"] = user["username"]
        session["role"] = user["role"]

        conn.close()

        if user["role"] == "admin":
            return redirect(url_for("admin_panel"))

        return redirect(url_for("index"))

    session["google_registration"] = {
        "google_id": google_id,
        "email": email,
        "full_name": full_name
    }

    conn.close()

    return redirect(url_for("complete_google_registration"))


@app.route("/auth/google/complete", methods=["GET", "POST"])
def complete_google_registration():
    google_data = session.get("google_registration")

    if not google_data:
        flash("Данные Google-регистрации не найдены.")
        return redirect(url_for("login"))

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        student_group = request.form.get("student_group", "").strip()
        full_name = request.form.get("full_name", "").strip()

        if role not in ["student", "teacher"]:
            flash("Можно выбрать только роль студента или преподавателя.")
            return redirect(url_for("complete_google_registration"))

        if not full_name:
            flash("Укажите ФИО.")
            return redirect(url_for("complete_google_registration"))

        if role == "student" and not student_group:
            flash("Для студента нужно указать группу.")
            return redirect(url_for("complete_google_registration"))

        if role == "teacher":
            student_group = ""

        conn = get_db()

        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
               OR google_id = ?
            """,
            (
                google_data["email"],
                google_data["google_id"]
            )
        ).fetchone()

        if existing:
            conn.close()
            session.pop("google_registration", None)
            flash("Пользователь с таким Google-аккаунтом уже существует.")
            return redirect(url_for("login"))

        email_prefix = google_data["email"].split("@")[0]
        username = build_unique_username(conn, email_prefix)

        conn.execute(
            """
            INSERT INTO users (
                username,
                password,
                role,
                full_name,
                student_group,
                email,
                status,
                created_at,
                google_id,
                auth_provider
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                "",
                role,
                full_name,
                student_group,
                google_data["email"],
                "pending",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                google_data["google_id"],
                "google"
            )
        )

        conn.commit()
        conn.close()

        session.pop("google_registration", None)

        flash("Заявка создана через Google. Дождитесь подтверждения администратора.")
        return redirect(url_for("login"))

    return render_template(
        "auth/google_complete.html",
        google_data=google_data
    )


# Роут для виходу із системи, який очищає сесію та перенаправляє користувача на сторінку входу.
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# 11. Common routes - спільні сторінки
# =========================

# Роут для головної сторінки, який відображає список лабораторних робіт та останні відправки студента. 
# Доступ до цієї сторінки мають лише аутентифіковані користувачі.
@app.route("/")
def index():
    if "username" not in session:
        return render_template(
            "common/index.html",
            is_landing=True,
            labs=[],
            my_submissions=[]
        )

    conn = get_db()

    labs = conn.execute(
        """
        SELECT *
        FROM labs
        ORDER BY id DESC
        """
    ).fetchall()

    my_submissions = conn.execute(
        """
        SELECT
            submissions.*,
            labs.title AS lab_title
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        WHERE submissions.username = ?
        ORDER BY submissions.created_at DESC
        LIMIT 5
        """,
        (session["username"],)
    ).fetchall()

    conn.close()

    return render_template(
        "common/index.html",
        is_landing=False,
        labs=labs,
        my_submissions=my_submissions
    )

# Роут для сторінки з деталями лабораторної роботи, який відображає інформацію про лабораторну роботу, 
# історію відправок студента та результати інших студентів для вчителів. 
# Доступ до цієї сторінки мають лише аутентифіковані користувачі.
@app.route("/lab/<int:lab_id>")
@login_required
def lab_detail(lab_id):
    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

# Якщо лабораторна робота не знайдена, закриваємо з'єднання та повертаємо помилку 404.
    if not lab:
        conn.close()
        return "Лабораторная работа не найдена", 404

    if session.get("role") == "teacher":
        access = conn.execute(
            """
            SELECT 1
            FROM labs
            WHERE id = ?
            AND (
                created_by = ?
                OR discipline IN (
                    SELECT discipline
                    FROM teacher_subject_groups
                    WHERE teacher_username = ?
                )
            )
            """,
            (
                lab_id,
                session["username"],
                session["username"]
            )
        ).fetchone()

        if not access:
            conn.close()
            flash("У вас нет доступа к этой лабораторной работе.")
            return redirect(url_for("teacher_panel"))

# Для вчителів відображаємо всі відправки студентів та їх результати, а для студентів - лише їх останню відправку та кількість спроб.
    if session.get("role") == "teacher":
        attempts_count = None

        submissions = conn.execute(
            """
            SELECT 
                submissions.*,
                users.full_name,
                users.student_group,
                (
                    SELECT MAX(s2.score)
                    FROM submissions s2
                    WHERE s2.username = submissions.username
                    AND s2.lab_id = submissions.lab_id
                ) AS best_score
            FROM submissions
            LEFT JOIN users ON submissions.username = users.username
            WHERE submissions.lab_id = ?
            ORDER BY submissions.id DESC
            """,
            (lab_id,)
        ).fetchall()

        student_results = conn.execute(
            """
            SELECT
                submissions.username,
                COALESCE(users.full_name, submissions.username) AS full_name,
                COALESCE(users.student_group, '') AS student_group,
                COUNT(submissions.id) AS attempts_count,
                MAX(submissions.score) AS best_score,
                (
                    SELECT s2.status
                    FROM submissions s2
                    WHERE s2.lab_id = submissions.lab_id
                      AND s2.username = submissions.username
                    ORDER BY s2.id DESC
                    LIMIT 1
                ) AS last_status,
                (
                    SELECT s2.filename
                    FROM submissions s2
                    WHERE s2.lab_id = submissions.lab_id
                      AND s2.username = submissions.username
                    ORDER BY s2.id DESC
                    LIMIT 1
                ) AS last_filename,
                (
                    SELECT s2.id
                    FROM submissions s2
                    WHERE s2.lab_id = submissions.lab_id
                      AND s2.username = submissions.username
                    ORDER BY s2.id DESC
                    LIMIT 1
                ) AS last_submission_id,
                (
                    SELECT s2.created_at
                    FROM submissions s2
                    WHERE s2.lab_id = submissions.lab_id
                      AND s2.username = submissions.username
                    ORDER BY s2.id DESC
                    LIMIT 1
                ) AS last_created_at
            FROM submissions
            LEFT JOIN users ON submissions.username = users.username
            WHERE submissions.lab_id = ?
            GROUP BY submissions.username
            ORDER BY best_score DESC, attempts_count DESC
            """,
            (lab_id,)
        ).fetchall()

# Для студентів отримуємо лише їх останню відправку та кількість спроб по цій лабораторній роботі.
    else:
        submissions = conn.execute(
            """
            SELECT
                submissions.*,
                (
                    SELECT COUNT(*)
                    FROM extra_task_attempts
                    WHERE extra_task_attempts.submission_id = submissions.id
                ) AS extra_attempts_count
            FROM submissions
            WHERE lab_id = ? AND username = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (lab_id, session["username"])
        ).fetchall()

        student_results = []

        attempts_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM submissions
            WHERE lab_id = ? AND username = ?
            """,
            (lab_id, session["username"])
        ).fetchone()["count"]

    conn.close()

    return render_template(
        "student/lab_detail.html",
        lab=lab,
        submissions=submissions,
        student_results=student_results,
        attempts_count=attempts_count
    )


# Роут для завантаження файлу рішення студента, який дозволяє студенту 
# або вчителю завантажити файл з рішенням для конкретної відправки, перевіряє права доступу та наявність файлу, 
# а також враховує, чи прихований файл для студента після повторної відправки, щоб забезпечити безпечний доступ до файлів рішень 
# та уникнути проблем з відображенням історії відправок студентів.
@app.route("/download/<int:submission_id>")
@login_required
def download_submission(submission_id):
    conn = get_db()

    submission = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    ).fetchone()

    conn.close()

    if not submission:
        abort(404)

    if submission["file_deleted"]:
        flash("Файл этой попытки недоступен.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    file_path = os.path.join(UPLOAD_DIR, submission["filename"])

    if not os.path.exists(file_path):
        flash("Файл отсутствует в папке загрузок.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if session.get("role") == "teacher":
        return send_from_directory(
            UPLOAD_DIR,
            submission["filename"],
            as_attachment=True
        )

    if submission["username"] != session["username"]:
        abort(403)

    if submission["file_hidden_for_student"]:
        flash("Файл этой попытки скрыт после повторной отправки.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    return send_from_directory(
        UPLOAD_DIR,
        submission["filename"],
        as_attachment=True
    )

@app.route("/waveform/<int:submission_id>")
@login_required
def download_waveform(submission_id):
    conn = get_db()

    submission = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    ).fetchone()

    conn.close()

    if not submission:
        abort(404)

    if not submission["waveform_filename"]:
        flash("Для этой попытки временная диаграмма недоступна.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    waveform_path = os.path.join(WAVEFORM_DIR, submission["waveform_filename"])

    if not os.path.exists(waveform_path):
        flash("Файл временной диаграммы отсутствует на сервере.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if session.get("role") == "teacher":
        return send_from_directory(
            WAVEFORM_DIR,
            submission["waveform_filename"],
            as_attachment=True
        )

    if submission["username"] != session["username"]:
        abort(403)

    return send_from_directory(
        WAVEFORM_DIR,
        submission["waveform_filename"],
        as_attachment=True
    )

# =========================
# 12. Student routes - студент
# =========================

@app.route("/student/gradebook")
@login_required
def student_gradebook():
    if session.get("role") != "student":
        flash("Зачётка доступна только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    disciplines = conn.execute(
        """
        SELECT DISTINCT labs.discipline
        FROM labs
        JOIN submissions ON submissions.lab_id = labs.id
        WHERE submissions.username = ?

        UNION

        SELECT DISTINCT labs.discipline
        FROM labs
        JOIN grade_overrides ON grade_overrides.lab_id = labs.id
        WHERE grade_overrides.username = ?

        ORDER BY discipline ASC
        """,
        (
            username,
            username
        )
    ).fetchall()

    gradebook_rows = []

    for item in disciplines:
        discipline = item["discipline"]

        teachers = conn.execute(
            """
            SELECT DISTINCT users.full_name
            FROM teacher_subject_groups tsg
            JOIN users ON users.username = tsg.teacher_username
            WHERE tsg.discipline = ?
              AND tsg.student_group = ?
            ORDER BY users.full_name ASC
            """,
            (
                discipline,
                student["student_group"]
            )
        ).fetchall()

        labs = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE discipline = ?
            ORDER BY created_at ASC, id ASC
            """,
            (discipline,)
        ).fetchall()

        lab_results = []
        total_score = 0
        completed_count = 0

        for lab in labs:
            auto_result = conn.execute(
                """
                SELECT
                    MAX(score) AS best_score,
                    COUNT(id) AS attempts_count
                FROM submissions
                WHERE username = ?
                  AND lab_id = ?
                """,
                (
                    username,
                    lab["id"]
                )
            ).fetchone()

            override = conn.execute(
                """
                SELECT *
                FROM grade_overrides
                WHERE username = ?
                  AND lab_id = ?
                """,
                (
                    username,
                    lab["id"]
                )
            ).fetchone()

            auto_score = auto_result["best_score"] if auto_result and auto_result["best_score"] is not None else None
            attempts_count = auto_result["attempts_count"] if auto_result else 0

            if override:
                display_score = override["score"]
                source = "manual"
            else:
                display_score = auto_score
                source = "auto"

            if display_score is not None:
                total_score += int(display_score)
                completed_count += 1

            lab_results.append({
                "lab": lab,
                "display_score": display_score,
                "auto_score": auto_score,
                "source": source,
                "attempts_count": attempts_count
            })

        average_score = round(total_score / completed_count, 1) if completed_count > 0 else None

        final_grade = conn.execute(
            """
            SELECT *
            FROM subject_final_grades
            WHERE username = ?
              AND discipline = ?
            """,
            (
                username,
                discipline
            )
        ).fetchone()

        gradebook_rows.append({
            "discipline": discipline,
            "teachers": teachers,
            "labs": lab_results,
            "average_score": average_score,
            "completed_count": completed_count,
            "total_labs": len(labs),
            "final_grade": final_grade
        })

    conn.close()

    return render_template(
        "student/gradebook.html",
        student=student,
        gradebook_rows=gradebook_rows
    )


# Роут для сторінки з історією відправок студента по конкретній лабораторній роботі, який відображає всі відправки студента та їх результати.
@app.route("/lab/<int:lab_id>/history")
@login_required
def student_lab_history(lab_id):
    if session.get("role") != "student":
        flash("История попыток доступна только студенту.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if not lab:
        conn.close()
        return "Лабораторная работа не найдена", 404

    submissions = conn.execute(
        """
        SELECT *
        FROM submissions
        WHERE lab_id = ? AND username = ?
        ORDER BY id DESC
        """,
        (lab_id, session["username"])
    ).fetchall()

    conn.close()

    return render_template(
        "student/history.html",
        lab=lab,
        submissions=submissions
    )


# Роут для відправки рішення студентом по конкретній лабораторній роботі, який приймає файл з рішенням, перевіряє його, зберігає результат та формує адаптивний навчальний план на основі результату перевірки. Доступ до цього роуту мають лише студенти.
@app.route("/submit/<int:lab_id>", methods=["POST"])
@login_required
def submit_solution(lab_id):
    if session.get("role") != "student":
        flash("Отправлять решения может только студент.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

# Якщо лабораторна робота не знайдена, закриваємо з'єднання та повертаємо помилку.
    if lab is None:
        conn.close()
        flash("Лабораторная работа не найдена.")
        return redirect(url_for("index"))

    file = request.files.get("solution")

# Якщо файл не вибрано або його ім'я порожнє, закриваємо з'єднання та показуємо повідомлення про помилку.
    if not file or file.filename.strip() == "":
        conn.close()
        flash("Файл не выбран.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

# Якщо розширення файлу не дозволене для цієї лабораторної роботи, закриваємо з'єднання та показуємо повідомлення про помилку з переліком дозволених розширень.
    if not is_allowed_solution_file(file.filename, lab):
        allowed_extensions = ", ".join(get_allowed_extensions_for_lab(lab))
        conn.close()
        flash(f"Для этой лабораторной можно загружать только файлы: {allowed_extensions}")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    filename = secure_filename(file.filename)

# Перевіряємо кількість спроб студента по цій лабораторній роботі. Якщо кількість спроб досягла максимуму, закриваємо з'єднання та показуємо повідомлення про те, що ліміт спроб вичерпано.
    attempts_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM submissions
        WHERE lab_id = ? AND username = ?
        """,
        (lab_id, session["username"])
    ).fetchone()["count"]

    max_attempts = lab["max_attempts"] or 3

# Якщо кількість спроб студента по цій лабораторній роботі досягла максимуму, закриваємо з'єднання та показуємо повідомлення про те, що ліміт спроб вичерпано.
    if attempts_count >= max_attempts:
        conn.close()
        flash("Лимит попыток по этой лабораторной работе исчерпан.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

# Якщо студент вже має попередні відправки по цій лабораторній роботі, позначаємо їх як приховані для студента, щоб він бачив лише свою останню відправку та не міг плутатися в історії відправок.
    previous_submission = conn.execute(
        """
        SELECT *
        FROM submissions
        WHERE lab_id = ? AND username = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (lab_id, session["username"])
    ).fetchone()

# Якщо знайдена попередня відправка, оновлюємо її, встановивши поле file_hidden_for_student в 1, щоб приховати її від студента.
    if previous_submission:
        conn.execute(
            """
            UPDATE submissions
            SET file_hidden_for_student = 1
            WHERE id = ?
            """,
            (previous_submission["id"],)
        )

    attempt_number = attempts_count + 1

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (session["username"],)
    ).fetchone()

    saved_filename = build_submission_filename(
        lab=lab,
        student=student,
        attempt_number=attempt_number,
        original_filename=file.filename
    )

    saved_path = os.path.join(UPLOAD_DIR, saved_filename)
    file.save(saved_path)

    waveform_filename = build_waveform_filename(saved_filename)
    waveform_save_path = os.path.join(WAVEFORM_DIR, waveform_filename)

    check_result = run_solution_check(
        saved_path,
        lab,
        waveform_save_path=waveform_save_path
    )

    if not check_result.get("waveform_created"):
        waveform_filename = ""
        if os.path.exists(waveform_save_path):
            os.remove(waveform_save_path)

    status = check_result["status"]
    output = check_result["output"]
    score = check_result["score"]
    passed_tests = check_result["passed_tests"]
    total_tests = check_result["total_tests"]

# Читаємо код студента з збереженого файлу, щоб передати його в функцію класифікації помилки та формування діагностики.
    with open(saved_path, "r", encoding="utf-8", errors="replace") as code_file:
        student_code = code_file.read()

    diagnostics = classify_solution_error(
        status=status,
        output=output,
        lab=lab,
        code=student_code
    )

# Зберігаємо результат відправки в базі даних, включаючи діагностику помилки, щоб потім використовувати цю інформацію для формування адаптивного навчального плану та надання студенту конкретних рекомендацій щодо виправлення помилки.
    conn.execute(
        """
        INSERT INTO submissions
        (lab_id, username, filename, waveform_filename, status, score, passed_tests, total_tests,
        error_type, error_title, error_details, recommendation, error_confidence,
        output, created_at, attempt_number, file_deleted, file_hidden_for_student)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lab_id,
            session["username"],
            saved_filename,
            waveform_filename,
            status,
            score,
            passed_tests,
            total_tests,
            diagnostics["error_type"],
            diagnostics["error_title"],
            diagnostics["error_details"],
            diagnostics["recommendation"],
            diagnostics["error_confidence"],
            output,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            attempt_number,
            0,
            0
        )
    )

    conn.commit()
    conn.close()

    flash("Решение отправлено и проверено.")
    return redirect(url_for("lab_detail", lab_id=lab_id))


@app.route("/submit-code/<int:lab_id>", methods=["POST"])
@login_required
def submit_code_from_editor(lab_id):
    if session.get("role") != "student":
        flash("Отправлять решения может только студент.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if lab is None:
        conn.close()
        flash("Лабораторная работа не найдена.")
        return redirect(url_for("index"))

    checker_type = lab["checker_type"] or "hdl_testbench"

    if checker_type != "hdl_testbench":
        conn.close()
        flash("HDL-редактор доступен только для Verilog-заданий.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    code_text = request.form.get("code_text", "").strip()

    if not code_text:
        conn.close()
        flash("Код решения не может быть пустым.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    attempts_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM submissions
        WHERE lab_id = ? AND username = ?
        """,
        (lab_id, session["username"])
    ).fetchone()["count"]

    max_attempts = lab["max_attempts"] or 3

    if attempts_count >= max_attempts:
        conn.close()
        flash("Лимит попыток по этой лабораторной работе исчерпан.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    previous_submission = conn.execute(
        """
        SELECT *
        FROM submissions
        WHERE lab_id = ? AND username = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (lab_id, session["username"])
    ).fetchone()

    if previous_submission:
        conn.execute(
            """
            UPDATE submissions
            SET file_hidden_for_student = 1
            WHERE id = ?
            """,
            (previous_submission["id"],)
        )

    attempt_number = attempts_count + 1

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (session["username"],)
    ).fetchone()

    saved_filename = build_submission_filename(
        lab=lab,
        student=student,
        attempt_number=attempt_number,
        original_filename="editor_solution.v"
    )

    saved_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(saved_path, "w", encoding="utf-8") as file:
        file.write(code_text)

    waveform_filename = build_waveform_filename(saved_filename)
    waveform_save_path = os.path.join(WAVEFORM_DIR, waveform_filename)

    check_result = run_solution_check(
        saved_path,
        lab,
        waveform_save_path=waveform_save_path
    )

    if not check_result.get("waveform_created"):
        waveform_filename = ""

        if os.path.exists(waveform_save_path):
            os.remove(waveform_save_path)

    status = check_result["status"]
    output = check_result["output"]
    score = check_result["score"]
    passed_tests = check_result["passed_tests"]
    total_tests = check_result["total_tests"]

    diagnostics = classify_solution_error(
        status=status,
        output=output,
        lab=lab,
        code=code_text
    )

    conn.execute(
        """
        INSERT INTO submissions
        (lab_id, username, filename, waveform_filename, status, score, passed_tests, total_tests,
        error_type, error_title, error_details, recommendation, error_confidence,
        output, created_at, attempt_number, file_deleted, file_hidden_for_student)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lab_id,
            session["username"],
            saved_filename,
            waveform_filename,
            status,
            score,
            passed_tests,
            total_tests,
            diagnostics["error_type"],
            diagnostics["error_title"],
            diagnostics["error_details"],
            diagnostics["recommendation"],
            diagnostics["error_confidence"],
            output,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            attempt_number,
            0,
            0
        )
    )

    conn.commit()
    conn.close()

    flash("Код из HDL-редактора отправлен и проверен.")
    return redirect(url_for("lab_detail", lab_id=lab_id))


# Роут для повторної відправки рішення студентом по конкретній лабораторній роботі, 
# який дозволяє студенту завантажити новий файл з рішенням після того, 
# як його попередня відправка не пройшла перевірку, та формує адаптивний навчальний план на основі результату перевірки. 
# Доступ до цього роуту мають лише студенти, і він також перевіряє ліміт спроб по цій лабораторній роботі, 
# щоб не дозволяти студенту перевищувати кількість спроб.
@app.route("/retry/<int:submission_id>", methods=["POST"])
@login_required
def retry_submission(submission_id):
    submission = get_submission_for_current_user(submission_id)

    if session.get("role") != "student":
        flash("Повторная отправка доступна только студенту.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (submission["lab_id"],)
    ).fetchone()

    attempts_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM submissions
        WHERE lab_id = ? AND username = ?
        """,
        (submission["lab_id"], session["username"])
    ).fetchone()["count"]

    conn.close()

    if attempts_count >= (lab["max_attempts"] or 3):
        flash("Лимит попыток по этой лабораторной работе исчерпан.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    flash("Загрузите новый файл решения в форме отправки выше.")
    return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))


# Роут для отримання підказки від ІІ-помічника на основі результату перевірки рішення студента, 
# який формує адаптивний навчальний план та надає студенту конкретні рекомендації щодо виправлення помилки.
@app.route("/ai-help/<int:submission_id>")
@login_required
def ai_help(submission_id):
    submission = get_submission_for_current_user(submission_id)

    if submission["status"] == "PASSED":
        flash("Решение уже прошло все тесты. Подсказка ИИ не требуется.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    code = read_submission_code(submission["filename"])
    adaptive_plan = build_adaptive_learning_plan(submission, code)

    return render_template(
        "student/ai_help.html",
        submission=submission,
        hint=adaptive_plan["hint_text"],
        level=adaptive_plan["hint_level"],
        code=code,
        adaptive_plan=adaptive_plan
    )


# Роут для покращення оцінки рішення студента через додаткові завдання від ІІ-помічника, 
# який формує адаптивний навчальний план з додатковими питаннями.
@app.route("/improve-score/<int:submission_id>", methods=["GET", "POST"])
@login_required
def improve_score(submission_id):
    submission = get_submission_for_current_user(submission_id)

    if submission["status"] == "PASSED":
        flash("Решение уже имеет максимальный результат.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (submission["lab_id"],)
    ).fetchone()

    used_extra_attempts = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM extra_task_attempts
        WHERE submission_id = ?
        """,
        (submission_id,)
    ).fetchone()["count"]

    conn.close()

    if not lab:
        flash("Лабораторная работа не найдена.")
        return redirect(url_for("index"))

    if not lab["allow_extra_questions"]:
        flash("Для этой лабораторной работы улучшение оценки через дополнительные вопросы отключено.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if used_extra_attempts > 0:
        flash("Вы уже использовали возможность улучшить оценку для этой попытки.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    code = read_submission_code(submission["filename"])
    adaptive_plan = build_adaptive_learning_plan(submission, code)
    tasks = adaptive_plan["questions"]

    check_result = None

    student_answers = {
        "answer_1": "",
        "answer_2": "",
        "answer_3": ""
    }

    if request.method == "POST":
        student_answers = {
            "answer_1": request.form.get("answer_1", ""),
            "answer_2": request.form.get("answer_2", ""),
            "answer_3": request.form.get("answer_3", "")
        }

        correct_count, bonus, feedback = evaluate_extra_task_answers(
            submission,
            student_answers
        )

        score_before = int(submission["score"] or 0)

        if correct_count >= 2:
            score_after = min(adaptive_plan["bonus_cap"], score_before + bonus)
        else:
            score_after = score_before

        conn = get_db()

        conn.execute(
            """
            INSERT INTO extra_task_attempts
            (submission_id, username, answer_1, answer_2, answer_3,
             correct_count, total_count, bonus, score_before, score_after,
             feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                session["username"],
                student_answers["answer_1"],
                student_answers["answer_2"],
                student_answers["answer_3"],
                correct_count,
                3,
                bonus,
                score_before,
                score_after,
                feedback,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        if score_after > score_before:
            updated_output = (
                submission["output"]
                + "\n\n---\n"
                + "Дополнительные задания ИИ-помощника выполнены.\n"
                + f"Правильных ответов: {correct_count} из 3.\n"
                + f"Бонус: +{score_after - score_before} баллов.\n"
                + f"Итоговый учебный балл: {score_after} / 100.\n"
            )

            conn.execute(
                """
                UPDATE submissions
                SET score = ?, output = ?
                WHERE id = ?
                """,
                (score_after, updated_output, submission_id)
            )

            flash("Ответы приняты. Учебный балл был повышен.")
        else:
            flash("Ответы не прошли проверку. Оценка не изменена.")

        conn.commit()
        conn.close()

        check_result = {
            "correct_count": correct_count,
            "bonus": bonus,
            "score_before": score_before,
            "score_after": score_after,
            "feedback": feedback
        }

    return render_template(
        "student/improve_score.html",
        submission=submission,
        tasks=tasks,
        check_result=check_result,
        student_answers=student_answers,
        adaptive_plan=adaptive_plan
    )


# =========================
# 13. Grade routes - оцінки
# =========================

@app.route("/grades/lab/<int:lab_id>/<username>/update", methods=["POST"])
@login_required
def update_lab_grade(lab_id, username):
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in ["admin", "teacher"]:
        flash("Редактировать оценки может только преподаватель или администратор.")
        return redirect(url_for("index"))

    score_raw = request.form.get("score", "").strip()
    comment = request.form.get("comment", "").strip()

    conn = get_db()

    if not can_edit_lab_grade(conn, current_username, current_role, username, lab_id):
        conn.close()
        flash("У вас нет прав на редактирование этой оценки.")
        return redirect(request.referrer or url_for("index"))

    if score_raw == "":
        conn.execute(
            """
            DELETE FROM grade_overrides
            WHERE username = ?
              AND lab_id = ?
            """,
            (username, lab_id)
        )

        conn.commit()
        conn.close()

        flash("Ручная оценка удалена. В журнале снова будет отображаться автоматический результат.")
        return redirect(request.referrer or url_for("teacher_journal"))

    try:
        score = int(score_raw)
    except ValueError:
        conn.close()
        flash("Оценка должна быть числом от 0 до 100.")
        return redirect(request.referrer or url_for("teacher_journal"))

    if score < 0 or score > 100:
        conn.close()
        flash("Оценка должна быть в диапазоне от 0 до 100.")
        return redirect(request.referrer or url_for("teacher_journal"))

    existing = conn.execute(
        """
        SELECT id
        FROM grade_overrides
        WHERE username = ?
          AND lab_id = ?
        """,
        (username, lab_id)
    ).fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing:
        conn.execute(
            """
            UPDATE grade_overrides
            SET score = ?,
                comment = ?,
                edited_by = ?,
                edited_at = ?
            WHERE username = ?
              AND lab_id = ?
            """,
            (
                score,
                comment,
                current_username,
                now,
                username,
                lab_id
            )
        )
    else:
        conn.execute(
            """
            INSERT INTO grade_overrides (
                username,
                lab_id,
                score,
                comment,
                edited_by,
                edited_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                lab_id,
                score,
                comment,
                current_username,
                now
            )
        )

    conn.commit()
    conn.close()

    flash("Оценка обновлена.")
    return redirect(request.referrer or url_for("teacher_journal"))


@app.route("/teacher/journal/update-group", methods=["POST"])
@login_required
def update_group_journal():
    if session.get("role") not in ["teacher", "admin"]:
        flash("Недостаточно прав для редактирования журнала.")
        return redirect(url_for("index"))

    conn = get_db()

    for key, value in request.form.items():
        if not key.startswith("score__"):
            continue

        try:
            _, username, lab_id = key.split("__", 2)
        except ValueError:
            continue

        score_text = value.strip()
        comment_key = f"comment__{username}__{lab_id}"
        comment = request.form.get(comment_key, "").strip()

        existing = conn.execute(
            """
            SELECT *
            FROM grade_overrides
            WHERE username = ?
              AND lab_id = ?
            """,
            (username, lab_id)
        ).fetchone()

        if score_text == "" and comment == "":
            if existing:
                conn.execute(
                    """
                    DELETE FROM grade_overrides
                    WHERE username = ?
                      AND lab_id = ?
                    """,
                    (username, lab_id)
                )

            continue

        try:
            score = int(score_text)
        except ValueError:
            continue

        if score < 0 or score > 100:
            continue

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if existing:
            conn.execute(
                """
                UPDATE grade_overrides
                SET score = ?,
                    comment = ?,
                    edited_by = ?,
                    edited_at = ?
                WHERE username = ?
                  AND lab_id = ?
                """,
                (
                    score,
                    comment,
                    session["username"],
                    now,
                    username,
                    lab_id
                )
            )
        else:
            conn.execute(
                """
                INSERT INTO grade_overrides (
                    username,
                    lab_id,
                    score,
                    comment,
                    edited_by,
                    edited_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    lab_id,
                    score,
                    comment,
                    session["username"],
                    now
                )
            )

    conn.commit()
    conn.close()

    flash("Изменения в журнале сохранены.")
    return redirect(request.referrer or url_for("teacher_journal"))


# =========================
# 14. Admin routes - адміністратор
# =========================

# Роут для адміністративної панелі, який відображає статистику по користувачах та список користувачів зі статусом "pending" для підтвердження або блокування. Доступ до цієї сторінки мають лише адміністратори.
@app.route("/admin")
@admin_required
def admin_panel():
    conn = get_db()

    stats = conn.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_users,
            SUM(CASE WHEN role = 'student' THEN 1 ELSE 0 END) AS students,
            SUM(CASE WHEN role = 'teacher' THEN 1 ELSE 0 END) AS teachers,
            SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admins
        FROM users
        """
    ).fetchone()

    pending_users = conn.execute(
        """
        SELECT *
        FROM users
        WHERE status = 'pending'
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        pending_users=pending_users
    )


# Роут для сторінки зі списком користувачів, який відображає всіх користувачів з їх ролями та статусами, а також дозволяє адміністраторам швидко знаходити користувачів за роллю або статусом. Доступ до цієї сторінки мають лише адміністратори.
@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db()

    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY
            CASE status
                WHEN 'pending' THEN 1
                WHEN 'active' THEN 2
                WHEN 'blocked' THEN 3
                ELSE 4
            END,
            role ASC,
            full_name ASC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/users.html",
        users=users
    )


@app.route("/admin/groups", methods=["GET", "POST"])
@admin_required
def admin_groups():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            conn.close()
            flash("Название группы не может быть пустым.")
            return redirect(url_for("admin_groups"))

        try:
            conn.execute(
                """
                INSERT INTO study_groups (name, description, created_at, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    session["username"]
                )
            )
            conn.commit()
            flash("Группа добавлена.")
        except sqlite3.IntegrityError:
            flash("Такая группа уже существует.")

        conn.close()
        return redirect(url_for("admin_groups"))

    groups = conn.execute(
        """
        SELECT *
        FROM study_groups
        ORDER BY name ASC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/groups.html",
        groups=groups
    )


@app.route("/admin/disciplines", methods=["GET", "POST"])
@admin_required
def admin_disciplines():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            conn.close()
            flash("Название предмета не может быть пустым.")
            return redirect(url_for("admin_disciplines"))

        try:
            conn.execute(
                """
                INSERT INTO disciplines (name, description, created_at, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    session["username"]
                )
            )
            conn.commit()
            flash("Предмет добавлен.")
        except sqlite3.IntegrityError:
            flash("Такой предмет уже существует.")

        conn.close()
        return redirect(url_for("admin_disciplines"))

    disciplines = conn.execute(
        """
        SELECT *
        FROM disciplines
        ORDER BY name ASC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/disciplines.html",
        disciplines=disciplines
    )


@app.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def admin_approve_user(user_id):
    conn = get_db()

    conn.execute(
        """
        UPDATE users
        SET status = 'active',
            approved_by = ?
        WHERE id = ?
        """,
        (session["username"], user_id)
    )

    conn.commit()
    conn.close()

    flash("Пользователь активирован.")
    return redirect(request.referrer or url_for("admin_users"))


# Роут для блокування користувача, який дозволяє адміністраторам швидко блокувати користувачів, які порушують правила або мають підозрілу активність. Заблоковані користувачі не зможуть входити в систему та отримуватимуть повідомлення про блокування при спробі входу.
@app.route("/admin/users/<int:user_id>/block", methods=["POST"])
@admin_required
def admin_block_user(user_id):
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        flash("Пользователь не найден.")
        return redirect(url_for("admin_users"))

    if user["role"] == "admin":
        conn.close()
        flash("Нельзя заблокировать администратора.")
        return redirect(url_for("admin_users"))

    conn.execute(
        """
        UPDATE users
        SET status = 'blocked'
        WHERE id = ?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()

    flash("Пользователь заблокирован.")
    return redirect(request.referrer or url_for("admin_users"))


# Роут для управління доступом викладачів до груп студентів та предметів, який дозволяє адміністраторам швидко надавати або видаляти доступ викладачам до певних груп студентів та предметів, щоб вони могли переглядати відправки та результати лише тих студентів, які їм підпорядковані.
@app.route("/admin/teacher-access", methods=["GET", "POST"])
@admin_required
def admin_teacher_access():
    conn = get_db()

    if request.method == "POST":
        teacher_username = request.form.get("teacher_username", "").strip()
        discipline = request.form.get("discipline", "").strip()
        student_group = request.form.get("student_group", "").strip()

        if not teacher_username or not discipline or not student_group:
            conn.close()
            flash("Нужно выбрать преподавателя, предмет и группу.")
            return redirect(url_for("admin_teacher_access"))

        try:
            conn.execute(
                """
                INSERT INTO teacher_subject_groups (
                    teacher_username,
                    discipline,
                    student_group,
                    created_at,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    teacher_username,
                    discipline,
                    student_group,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    session["username"]
                )
            )

            conn.commit()
            flash("Доступ преподавателю добавлен.")

        except sqlite3.IntegrityError:
            flash("Такой доступ уже существует.")

        conn.close()
        return redirect(url_for("admin_teacher_access"))

    teachers = conn.execute(
        """
        SELECT *
        FROM users
        WHERE role = 'teacher'
          AND status = 'active'
        ORDER BY full_name ASC
        """
    ).fetchall()

    disciplines = conn.execute(
        """
        SELECT name AS discipline
        FROM disciplines
        ORDER BY name ASC
        """
    ).fetchall()

    groups = conn.execute(
        """
        SELECT name AS student_group
        FROM study_groups
        ORDER BY name ASC
        """
    ).fetchall()

    access_rows = conn.execute(
        """
        SELECT
            teacher_subject_groups.*,
            users.full_name AS teacher_full_name
        FROM teacher_subject_groups
        LEFT JOIN users ON users.username = teacher_subject_groups.teacher_username
        ORDER BY
            teacher_subject_groups.discipline ASC,
            teacher_subject_groups.student_group ASC,
            users.full_name ASC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/teacher_access.html",
        teachers=teachers,
        disciplines=disciplines,
        groups=groups,
        access_rows=access_rows
    )


# =========================
# 15. Teacher routes - викладач
# =========================

# Роут для вчителя, який відображає загальну статистику по всім лабораторним роботам та відправкам студентів,
# а також зведення по типах помилок, щоб вчитель міг швидко оцінити загальний рівень успішності студентів, виявити найпоширеніші проблеми та помилки,
# а також приймати обґрунтовані рішення щодо коригування навчального плану, надання додаткових пояснень або матеріалів для покращення розуміння студентами складних тем.    
@app.route("/teacher")
@teacher_required
def teacher_panel():
    conn = get_db()

    stats = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE role = 'student') AS total_students,
            (SELECT COUNT(*) FROM labs) AS total_labs,
            COUNT(submissions.id) AS total_submissions,
            SUM(CASE WHEN status = 'PASSED' THEN 1 ELSE 0 END) AS passed,
            SUM(CASE WHEN status = 'PARTIAL' THEN 1 ELSE 0 END) AS partial,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN status = 'COMPILE_ERROR' THEN 1 ELSE 0 END) AS compile_errors,
            ROUND(AVG(score), 1) AS average_score,
            ROUND(
                100.0 * SUM(CASE WHEN status = 'PASSED' THEN 1 ELSE 0 END) / NULLIF(COUNT(submissions.id), 0),
                1
            ) AS success_percent
        FROM submissions
    """).fetchone()

    error_summary = conn.execute("""
        SELECT
            error_type,
            error_title,
            COUNT(*) AS count
        FROM submissions
        WHERE error_type IS NOT NULL
          AND error_type != ''
          AND error_type != 'NO_ERROR'
        GROUP BY error_type, error_title
        ORDER BY count DESC
    """).fetchall()

    conn.close()

    return render_template(
        "teacher/dashboard.html",
        stats=stats,
        error_summary=error_summary
    )


# Роут для преподавателя и администратора.
# Отображает журнал успеваемости студентов по лабораторным работам.
# Администратор видит весь журнал.
# Преподаватель видит только свои лабораторные и назначенные ему группы/предметы.
@app.route("/teacher/journal")
@login_required
def teacher_journal():
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in ["teacher", "admin"]:
        flash("Журнал оценок доступен только преподавателю или администратору.")
        return redirect(url_for("index"))

    is_admin = current_role == "admin"

    conn = get_db()

    selected_discipline = request.args.get("discipline", "").strip()
    selected_lab_id = request.args.get("lab_id", "").strip()
    selected_group = request.args.get("group", "").strip()

    # -----------------------------
    # 1. Список предметов для фильтра
    # -----------------------------

    if is_admin:
        disciplines = conn.execute(
            """
            SELECT DISTINCT name AS discipline
            FROM disciplines
            WHERE name IS NOT NULL
              AND name != ''
            ORDER BY name ASC
            """
        ).fetchall()

        # Если справочник предметов пока пустой,
        # берем предметы напрямую из лабораторных работ.
        if not disciplines:
            disciplines = conn.execute(
                """
                SELECT DISTINCT discipline
                FROM labs
                WHERE discipline IS NOT NULL
                  AND discipline != ''
                ORDER BY discipline ASC
                """
            ).fetchall()

    else:
        disciplines = conn.execute(
            """
            SELECT DISTINCT labs.discipline
            FROM labs
            LEFT JOIN teacher_subject_groups tsg
                ON tsg.discipline = labs.discipline
               AND tsg.teacher_username = ?
            WHERE labs.created_by = ?
               OR tsg.teacher_username = ?
            ORDER BY labs.discipline ASC
            """,
            (
                current_username,
                current_username,
                current_username
            )
        ).fetchall()

    # -----------------------------
    # 2. Лабораторные для построения журнала
    # -----------------------------

    if is_admin:
        labs_sql = """
            SELECT DISTINCT labs.*
            FROM labs
            WHERE 1 = 1
        """

        labs_params = []

    else:
        labs_sql = """
            SELECT DISTINCT labs.*
            FROM labs
            LEFT JOIN teacher_subject_groups tsg
                ON tsg.discipline = labs.discipline
               AND tsg.teacher_username = ?
            WHERE labs.created_by = ?
               OR tsg.teacher_username = ?
        """

        labs_params = [
            current_username,
            current_username,
            current_username
        ]

    if selected_discipline:
        labs_sql += " AND labs.discipline = ?"
        labs_params.append(selected_discipline)

    if selected_lab_id:
        labs_sql += " AND labs.id = ?"
        labs_params.append(selected_lab_id)

    labs_sql += """
        ORDER BY labs.created_at ASC, labs.id ASC
    """

    labs = conn.execute(labs_sql, labs_params).fetchall()

    # -----------------------------
    # 3. Лабораторные для выпадающего фильтра
    # -----------------------------

    if is_admin:
        labs_for_filter = conn.execute(
            """
            SELECT DISTINCT labs.id, labs.title, labs.discipline
            FROM labs
            ORDER BY labs.discipline ASC, labs.title ASC
            """
        ).fetchall()

    else:
        labs_for_filter = conn.execute(
            """
            SELECT DISTINCT labs.id, labs.title, labs.discipline
            FROM labs
            LEFT JOIN teacher_subject_groups tsg
                ON tsg.discipline = labs.discipline
               AND tsg.teacher_username = ?
            WHERE labs.created_by = ?
               OR tsg.teacher_username = ?
            ORDER BY labs.discipline ASC, labs.title ASC
            """,
            (
                current_username,
                current_username,
                current_username
            )
        ).fetchall()

    # -----------------------------
    # 4. Список групп для фильтра
    # -----------------------------

    if is_admin:
        groups = conn.execute(
            """
            SELECT DISTINCT name AS student_group
            FROM study_groups
            WHERE name IS NOT NULL
              AND name != ''
            ORDER BY name ASC
            """
        ).fetchall()

        # Если справочник групп пока пустой,
        # берем группы напрямую из пользователей.
        if not groups:
            groups = conn.execute(
                """
                SELECT DISTINCT student_group
                FROM users
                WHERE role = 'student'
                  AND student_group != ''
                ORDER BY student_group ASC
                """
            ).fetchall()

    else:
        groups = conn.execute(
            """
            SELECT DISTINCT users.student_group
            FROM users
            WHERE users.role = 'student'
              AND users.student_group != ''
              AND (
                  users.student_group IN (
                      SELECT student_group
                      FROM teacher_subject_groups
                      WHERE teacher_username = ?
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM submissions
                      JOIN labs ON submissions.lab_id = labs.id
                      WHERE submissions.username = users.username
                        AND labs.created_by = ?
                  )
              )
            ORDER BY users.student_group ASC
            """,
            (
                current_username,
                current_username
            )
        ).fetchall()

    # -----------------------------
    # 5. Список студентов
    # -----------------------------

    if is_admin:
        students_sql = """
            SELECT *
            FROM users
            WHERE role = 'student'
        """

        students_params = []

    else:
        students_sql = """
            SELECT *
            FROM users
            WHERE role = 'student'
              AND (
                  student_group IN (
                      SELECT student_group
                      FROM teacher_subject_groups
                      WHERE teacher_username = ?
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM submissions
                      JOIN labs ON submissions.lab_id = labs.id
                      WHERE submissions.username = users.username
                        AND labs.created_by = ?
                  )
              )
        """

        students_params = [
            current_username,
            current_username
        ]

    if selected_group:
        students_sql += " AND student_group = ?"
        students_params.append(selected_group)

    students_sql += """
        ORDER BY student_group ASC, full_name ASC
    """

    students = conn.execute(students_sql, students_params).fetchall()

    # -----------------------------
    # 6. Формирование журнала по группам
    # -----------------------------

    journal_by_groups = {}

    for student in students:
        group_name = student["student_group"] or "Без группы"

        if group_name not in journal_by_groups:
            journal_by_groups[group_name] = []

        cells = []
        total_score = 0
        completed_count = 0

        for lab in labs:
            result = conn.execute(
                """
                SELECT
                    COUNT(submissions.id) AS attempts_count,
                    MAX(submissions.score) AS best_score,
                    (
                        SELECT status
                        FROM submissions s2
                        WHERE s2.username = ?
                          AND s2.lab_id = ?
                        ORDER BY s2.id DESC
                        LIMIT 1
                    ) AS last_status,
                    (
                        SELECT created_at
                        FROM submissions s2
                        WHERE s2.username = ?
                          AND s2.lab_id = ?
                        ORDER BY s2.id DESC
                        LIMIT 1
                    ) AS last_created_at
                FROM submissions
                WHERE submissions.username = ?
                  AND submissions.lab_id = ?
                """,
                (
                    student["username"],
                    lab["id"],
                    student["username"],
                    lab["id"],
                    student["username"],
                    lab["id"]
                )
            ).fetchone()

            override = conn.execute(
                """
                SELECT *
                FROM grade_overrides
                WHERE username = ?
                  AND lab_id = ?
                """,
                (
                    student["username"],
                    lab["id"]
                )
            ).fetchone()

            attempts_count = result["attempts_count"] if result else 0
            auto_score = result["best_score"] if result and result["best_score"] is not None else None
            last_status = result["last_status"] if result else ""
            last_created_at = result["last_created_at"] if result else ""

            manual_score = override["score"] if override else None
            manual_comment = override["comment"] if override else ""
            edited_by = override["edited_by"] if override else ""
            edited_at = override["edited_at"] if override else ""

            if manual_score is not None:
                display_score = manual_score
                grade_source = "manual"
            else:
                display_score = auto_score
                grade_source = "auto"

            if display_score is not None:
                total_score += int(display_score)
                completed_count += 1

            cells.append({
                "lab_id": lab["id"],
                "display_score": display_score,
                "auto_score": auto_score,
                "manual_score": manual_score,
                "grade_source": grade_source,
                "manual_comment": manual_comment,
                "edited_by": edited_by,
                "edited_at": edited_at,
                "attempts_count": attempts_count,
                "last_status": last_status,
                "last_created_at": last_created_at
            })

        average_score = round(total_score / completed_count, 1) if completed_count > 0 else None

        journal_by_groups[group_name].append({
            "student": student,
            "cells": cells,
            "average_score": average_score,
            "completed_count": completed_count
        })

    conn.close()

    return render_template(
        "teacher/journal.html",
        groups=groups,
        disciplines=disciplines,
        labs=labs,
        labs_for_filter=labs_for_filter,
        journal_by_groups=journal_by_groups,
        selected_discipline=selected_discipline,
        selected_lab_id=selected_lab_id,
        selected_group=selected_group
    )


# Роут для вчителя, який відображає список лабораторних робіт з інформацією про кількість відправок, середній бал та кількість успішних рішень,
@app.route("/teacher/labs")
@teacher_required
def teacher_labs():
    conn = get_db()

    labs = conn.execute(
        """
        SELECT
            labs.*,
            COUNT(submissions.id) AS submissions_count,
            ROUND(AVG(submissions.score), 1) AS average_score,
            SUM(CASE WHEN submissions.status = 'PASSED' THEN 1 ELSE 0 END) AS passed_count
        FROM labs
        LEFT JOIN submissions ON submissions.lab_id = labs.id
        WHERE labs.created_by = ?
           OR labs.discipline IN (
                SELECT discipline
                FROM teacher_subject_groups
                WHERE teacher_username = ?
           )
        GROUP BY labs.id
        ORDER BY labs.discipline ASC, labs.id DESC
        """,
        (
            session["username"],
            session["username"]
        )
    ).fetchall()

    conn.close()

    return render_template(
        "teacher/labs.html",
        labs=labs
    )


# Роут для вчителя, який відображає історію відправок студентів по лабораторним роботам з можливістю фільтрації за різними параметрами та пошуку,
@app.route("/teacher/submissions-history")
@teacher_required
def teacher_submissions_history():
    conn = get_db()

    search_query = request.args.get("q", "").strip()
    selected_discipline = request.args.get("discipline", "").strip()
    selected_lab_id = request.args.get("lab_id", "").strip()
    selected_group = request.args.get("group", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_error_type = request.args.get("error_type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    sort = request.args.get("sort", "submitted_at")
    direction = request.args.get("direction", "desc")

    if direction not in ["asc", "desc"]:
        direction = "desc"

    if sort not in [
        "submitted_at",
        "student",
        "group",
        "lab",
        "best_score",
        "status",
        "attempt"
    ]:
        sort = "submitted_at"

    sql = f"""
        SELECT
            submissions.*,
            labs.title AS lab_title,
            labs.created_at AS lab_created_at,
            labs.discipline AS discipline,
            labs.programming_language AS programming_language,
            labs.checker_type AS checker_type,
            users.full_name,
            users.student_group
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        LEFT JOIN users ON submissions.username = users.username
        WHERE {get_teacher_access_condition()}
    """

    params = [
        session["username"],
        session["username"]
    ]

    if search_query:
        sql += """
            AND (
                users.full_name LIKE ?
                OR users.username LIKE ?
                OR labs.title LIKE ?
                OR submissions.filename LIKE ?
            )
        """
        search_value = f"%{search_query}%"
        params.extend([search_value, search_value, search_value, search_value])

    if selected_discipline:
        sql += " AND labs.discipline = ?"
        params.append(selected_discipline)

    if selected_lab_id:
        sql += " AND labs.id = ?"
        params.append(selected_lab_id)

    if selected_group:
        sql += " AND users.student_group = ?"
        params.append(selected_group)

    if selected_status:
        sql += " AND submissions.status = ?"
        params.append(selected_status)

    if selected_error_type:
        sql += " AND submissions.error_type = ?"
        params.append(selected_error_type)

    if date_from:
        sql += " AND submissions.created_at >= ?"
        params.append(date_from + " 00:00:00")

    if date_to:
        sql += " AND submissions.created_at <= ?"
        params.append(date_to + " 23:59:59")

    sql += """
        ORDER BY
            submissions.username ASC,
            submissions.lab_id ASC,
            submissions.attempt_number DESC,
            submissions.id DESC
    """

    attempt_rows = conn.execute(sql, params).fetchall()

    disciplines = conn.execute(
        """
        SELECT DISTINCT labs.discipline
        FROM labs
        LEFT JOIN teacher_subject_groups tsg
            ON tsg.discipline = labs.discipline
           AND tsg.teacher_username = ?
        WHERE labs.created_by = ?
           OR tsg.teacher_username = ?
        ORDER BY labs.discipline ASC
        """,
        (
            session["username"],
            session["username"],
            session["username"]
        )
    ).fetchall()

    labs_query = """
        SELECT DISTINCT labs.id, labs.title, labs.discipline
        FROM labs
        LEFT JOIN teacher_subject_groups tsg
            ON tsg.discipline = labs.discipline
           AND tsg.teacher_username = ?
        WHERE labs.created_by = ?
           OR tsg.teacher_username = ?
    """

    labs_params = [
        session["username"],
        session["username"],
        session["username"]
    ]

    if selected_discipline:
        labs_query += " AND labs.discipline = ?"
        labs_params.append(selected_discipline)

    labs_query += """
        ORDER BY labs.discipline ASC, labs.title ASC
    """

    labs = conn.execute(labs_query, labs_params).fetchall()

    groups = conn.execute(
        """
        SELECT DISTINCT users.student_group
        FROM users
        WHERE users.role = 'student'
          AND users.student_group != ''
          AND (
              users.student_group IN (
                  SELECT student_group
                  FROM teacher_subject_groups
                  WHERE teacher_username = ?
              )
              OR EXISTS (
                  SELECT 1
                  FROM submissions
                  JOIN labs ON submissions.lab_id = labs.id
                  WHERE submissions.username = users.username
                    AND labs.created_by = ?
              )
          )
        ORDER BY users.student_group ASC
        """,
        (
            session["username"],
            session["username"]
        )
    ).fetchall()

    conn.close()

    grouped = {}

    for row in attempt_rows:
        attempt = dict(row)
        key = (attempt["username"], attempt["lab_id"])

        if key not in grouped:
            grouped[key] = {
                "username": attempt["username"],
                "full_name": attempt["full_name"] or attempt["username"],
                "student_group": attempt["student_group"] or "—",
                "lab_id": attempt["lab_id"],
                "lab_title": attempt["lab_title"],
                "lab_created_at": attempt["lab_created_at"],
                "discipline": attempt["discipline"] or "—",
                "programming_language": attempt["programming_language"] or "—",
                "checker_type": attempt["checker_type"] or "—",
                "attempts": []
            }

        grouped[key]["attempts"].append(attempt)

    submission_groups = []

    for group in grouped.values():
        attempts = group["attempts"]

        attempts.sort(
            key=lambda item: int(item["attempt_number"] or 1),
            reverse=True
        )

        best_score = max(int(item["score"] or 0) for item in attempts)

        successful_attempts = [
            item for item in attempts
            if item["status"] == "PASSED"
        ]

        if successful_attempts:
            display_attempt = sorted(
                successful_attempts,
                key=lambda item: (
                    int(item["score"] or 0),
                    int(item["attempt_number"] or 1),
                    int(item["id"])
                ),
                reverse=True
            )[0]

            display_label = "Успешная попытка"
        else:
            display_attempt = sorted(
                attempts,
                key=lambda item: (
                    int(item["score"] or 0),
                    int(item["attempt_number"] or 1),
                    int(item["id"])
                ),
                reverse=True
            )[0]

            display_label = "Лучшая попытка"

        group["attempts_count"] = len(attempts)
        group["best_score"] = best_score
        group["display_attempt"] = display_attempt
        group["display_label"] = display_label

        submission_groups.append(group)

    def sort_value(group):
        display_attempt = group["display_attempt"]

        if sort == "student":
            return group["full_name"].lower()

        if sort == "group":
            return group["student_group"].lower()

        if sort == "lab":
            return group["lab_title"].lower()

        if sort == "best_score":
            return int(group["best_score"] or 0)

        if sort == "status":
            return display_attempt["status"] or ""

        if sort == "attempt":
            return int(display_attempt["attempt_number"] or 1)

        return display_attempt["created_at"] or ""

    submission_groups.sort(
        key=sort_value,
        reverse=(direction == "desc")
    )

    return render_template(
        "teacher/submissions_history.html",
        submission_groups=submission_groups,
        labs=labs,
        groups=groups,
        disciplines=disciplines,
        search_query=search_query,
        selected_discipline=selected_discipline,
        selected_lab_id=selected_lab_id,
        selected_group=selected_group,
        selected_status=selected_status,
        selected_error_type=selected_error_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        direction=direction
    )


# Роут для вчителя, який дозволяє керувати студентами: додавати нових студентів, редагувати дані існуючих студентів та видаляти студентів з системи,
@app.route("/teacher/students", methods=["GET", "POST"])
@teacher_required
def manage_students():
    conn = get_db()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        student_group = request.form.get("student_group")

        if not username or not password or not full_name or not student_group:
            conn.close()
            flash("Нужно заполнить все поля.")
            return redirect(url_for("manage_students"))

        try:
            conn.execute(
                """
                INSERT INTO users (username, password, role, full_name, student_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password, "student", full_name, student_group)
            )
            conn.commit()
            flash("Студент успешно добавлен.")

        except sqlite3.IntegrityError:
            flash("Пользователь с таким логином уже существует.")

        conn.close()
        return redirect(url_for("manage_students"))

    search_query = request.args.get("q", "").strip()
    selected_group = request.args.get("group", "").strip()

    groups = conn.execute(
        """
        SELECT DISTINCT student_group
        FROM users
        WHERE role = 'student'
          AND student_group != ''
        ORDER BY student_group
        """
    ).fetchall()

    sql = """
        SELECT
            users.id,
            users.username,
            users.password,
            users.role,
            users.full_name,
            users.student_group,
            COUNT(submissions.id) AS attempts_count,
            ROUND(AVG(submissions.score), 1) AS average_score,
            MAX(submissions.score) AS best_score
        FROM users
        LEFT JOIN submissions
            ON submissions.username = users.username
        WHERE users.role = 'student'
    """

    params = []

    if search_query:
        sql += """
            AND (
                users.full_name LIKE ?
                OR users.username LIKE ?
            )
        """
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    if selected_group:
        sql += """
            AND users.student_group = ?
        """
        params.append(selected_group)

    sql += """
        GROUP BY
            users.id,
            users.username,
            users.password,
            users.role,
            users.full_name,
            users.student_group
        ORDER BY
            users.student_group ASC,
            users.full_name ASC
    """

    students = conn.execute(sql, params).fetchall()

    conn.close()

    return render_template(
        "teacher/students.html",
        students=students,
        groups=groups,
        search_query=search_query,
        selected_group=selected_group
    )


# Роут для вчителя, який дозволяє редагувати дані існуючого студента, включаючи логін, пароль, повне ім'я та групу студента
@app.route("/teacher/edit-student/<int:user_id>", methods=["GET", "POST"])
@teacher_required
def edit_student(user_id):
    conn = get_db()

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ? AND role = 'student'
        """,
        (user_id,)
    ).fetchone()

    if not student:
        conn.close()
        flash("Студент не найден.")
        return redirect(url_for("manage_students"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        student_group = request.form.get("student_group")

        if not username or not password or not full_name or not student_group:
            conn.close()
            flash("Нужно заполнить все поля.")
            return redirect(url_for("edit_student", user_id=user_id))

        old_username = student["username"]

        existing_user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE username = ? AND id != ?
            """,
            (username, user_id)
        ).fetchone()

        if existing_user:
            conn.close()
            flash("Пользователь с таким логином уже существует.")
            return redirect(url_for("edit_student", user_id=user_id))

        conn.execute(
            """
            UPDATE users
            SET username = ?, password = ?, full_name = ?, student_group = ?
            WHERE id = ? AND role = 'student'
            """,
            (username, password, full_name, student_group, user_id)
        )

        if old_username != username:
            conn.execute(
                """
                UPDATE submissions
                SET username = ?
                WHERE username = ?
                """,
                (username, old_username)
            )

        conn.commit()
        conn.close()

        flash("Данные студента обновлены.")
        return redirect(url_for("manage_students"))

    conn.close()

    return render_template("admin/edit_student.html", student=student)


# Роут для вчителя, який дозволяє видалити студента з системи разом з усіма його відправками та файлами рішень
@app.route("/teacher/delete-student/<int:user_id>", methods=["POST"])
@teacher_required
def delete_student(user_id):
    conn = get_db()

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ? AND role = 'student'
        """,
        (user_id,)
    ).fetchone()

    if not student:
        conn.close()
        flash("Студент не найден.")
        return redirect(url_for("manage_students"))

    username = student["username"]

    submission_files = conn.execute(
        """
        SELECT filename
        FROM submissions
        WHERE username = ?
        """,
        (username,)
    ).fetchall()

    conn.execute(
        "DELETE FROM submissions WHERE username = ?",
        (username,)
    )

    conn.execute(
        "DELETE FROM users WHERE id = ? AND role = 'student'",
        (user_id,)
    )

    conn.commit()
    conn.close()

    for item in submission_files:
        file_path = os.path.join(UPLOAD_DIR, item["filename"])

        if os.path.exists(file_path):
            os.remove(file_path)

    flash("Студент и его попытки удалены.")
    return redirect(url_for("manage_students"))


# Роут для вчителя, який дозволяє видалити всю групу студентів разом з усіма їх відправками та файлами рішень
@app.route("/teacher/delete-group", methods=["POST"])
@teacher_required
def delete_group_students():
    student_group = request.form.get("student_group")

    if not student_group:
        flash("Нужно выбрать группу для удаления.")
        return redirect(url_for("manage_students"))

    conn = get_db()

    students = conn.execute(
        """
        SELECT username
        FROM users
        WHERE role = 'student' AND student_group = ?
        """,
        (student_group,)
    ).fetchall()

    if not students:
        conn.close()
        flash("В выбранной группе нет студентов.")
        return redirect(url_for("manage_students"))

    usernames = [student["username"] for student in students]

    submission_files = []

    for username in usernames:
        files = conn.execute(
            """
            SELECT filename
            FROM submissions
            WHERE username = ?
            """,
            (username,)
        ).fetchall()

        for item in files:
            submission_files.append(item["filename"])

        conn.execute(
            "DELETE FROM submissions WHERE username = ?",
            (username,)
        )

    conn.execute(
        """
        DELETE FROM users
        WHERE role = 'student' AND student_group = ?
        """,
        (student_group,)
    )

    conn.commit()
    conn.close()

    for filename in submission_files:
        file_path = os.path.join(UPLOAD_DIR, filename)

        if os.path.exists(file_path):
            os.remove(file_path)

    flash(f"Группа {student_group} удалена вместе со студентами, попытками и файлами.")
    return redirect(url_for("manage_students"))


# Роут для вчителя, який дозволяє додати нову лабораторну роботу з усіма необхідними параметрами та налаштуваннями
@app.route("/teacher/labs/new", methods=["GET", "POST"])
@teacher_required
def add_lab():

    if request.method == "GET":
        return render_template("teacher/add_lab.html")

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    testbench = request.form.get("testbench", "").strip()

    discipline = request.form.get("discipline", "FPGA-проектирование").strip()
    programming_language = request.form.get("programming_language", "Verilog").strip()
    checker_type = request.form.get("checker_type", "hdl_testbench").strip()
    topic = request.form.get("topic", "").strip()
    difficulty = request.form.get("difficulty", "basic").strip()
    concepts = request.form.get("concepts", "").strip()
    grading_policy = request.form.get("grading_policy", "").strip()
    starter_code = request.form.get("starter_code", "").strip()

    max_attempts = request.form.get("max_attempts", "3")
    allow_extra_questions = 1 if request.form.get("allow_extra_questions") == "on" else 0

    if not title or not description or not testbench:
        flash("Нужно заполнить название, описание и проверочный сценарий.")
        return redirect(url_for("teacher_panel"))

    try:
        max_attempts = int(max_attempts)
    except ValueError:
        max_attempts = 3

    if max_attempts < 1:
        max_attempts = 1

    conn = get_db()

    conn.execute(
        """
        INSERT INTO labs (
            title,
            description,
            testbench,
            discipline,
            programming_language,
            checker_type,
            topic,
            difficulty,
            concepts,
            grading_policy,
            starter_code,
            max_attempts,
            allow_extra_questions,
            created_by,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            testbench,
            discipline,
            programming_language,
            checker_type,
            topic,
            difficulty,
            concepts,
            grading_policy,
            starter_code,
            max_attempts,
            allow_extra_questions,
            session["username"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

    flash("Лабораторная работа успешно добавлена.")

    return redirect(url_for("teacher_panel"))


# Роут для вчителя, який дозволяє редагувати існуючу лабораторну роботу, включаючи всі параметри та налаштування лабораторної роботи
@app.route("/teacher/edit-lab/<int:lab_id>", methods=["GET", "POST"])
@teacher_required
def edit_lab(lab_id):
    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if lab is None:
        conn.close()
        flash("Лабораторная работа не найдена.")
        return redirect(url_for("teacher_panel"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        testbench = request.form.get("testbench", "").strip()

        discipline = request.form.get("discipline", "FPGA-проектирование").strip()
        programming_language = request.form.get("programming_language", "Verilog").strip()
        checker_type = request.form.get("checker_type", "hdl_testbench").strip()
        topic = request.form.get("topic", "").strip()
        difficulty = request.form.get("difficulty", "basic").strip()
        concepts = request.form.get("concepts", "").strip()
        grading_policy = request.form.get("grading_policy", "").strip()
        starter_code = request.form.get("starter_code", "").strip()

        try:
            max_attempts = int(request.form.get("max_attempts", 3))
        except ValueError:
            max_attempts = 3

        if max_attempts < 1:
            max_attempts = 1

        allow_extra_questions = 1 if request.form.get("allow_extra_questions") == "on" else 0

        if not title or not description or not testbench:
            conn.close()
            flash("Название, описание и проверочный сценарий обязательны для заполнения.")
            return redirect(url_for("edit_lab", lab_id=lab_id))

        conn.execute(
            """
            UPDATE labs
            SET title = ?,
                description = ?,
                testbench = ?,
                discipline = ?,
                programming_language = ?,
                checker_type = ?,
                topic = ?,
                difficulty = ?,
                concepts = ?,
                grading_policy = ?,
                starter_code = ?,
                max_attempts = ?,
                allow_extra_questions = ?
            WHERE id = ?
            """,
            (
                title,
                description,
                testbench,
                discipline,
                programming_language,
                checker_type,
                topic,
                difficulty,
                concepts,
                grading_policy,
                starter_code,
                max_attempts,
                allow_extra_questions,
                lab_id
            )
        )

        conn.commit()
        conn.close()

        flash("Лабораторная работа обновлена.")
        return redirect(url_for("teacher_panel"))

    conn.close()

    return render_template(
        "teacher/edit_lab.html",
        lab=lab
    )


# Роут для вчителя, який дозволяє видалити лабораторну роботу з системи разом з усіма відправками студентів та файлами рішень, пов'язаними з цією лабораторною роботою
@app.route("/teacher/delete-lab/<int:lab_id>", methods=["POST"])
@teacher_required
def delete_lab(lab_id):
    conn = get_db()

    conn.execute(
        "DELETE FROM submissions WHERE lab_id = ?",
        (lab_id,)
    )

    conn.execute(
        "DELETE FROM labs WHERE id = ?",
        (lab_id,)
    )

    conn.commit()
    conn.close()

    flash("Лабораторная работа удалена.")
    return redirect(url_for("teacher_panel"))


# =========================
# 16. App start
# =========================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
