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

import json
import random
import hashlib
import requests
import secrets
import hmac

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# sys дозволяє працювати з параметрами та налаштуваннями Python-інтерпретатора
# Наприклад, можна отримувати аргументи запуску програми або завершувати програму
import sys

# ast використовується для аналізу Python-коду як структури
# Може застосовуватись для безпечної перевірки коду без його прямого виконання
import ast

from urllib.parse import quote_plus
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

from bs4 import BeautifulSoup


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
from flask import Flask, request, redirect, url_for, session, render_template, flash, send_from_directory, abort, jsonify


# secure_filename безпечно обробляє ім'я файлу, що завантажується
# Це захищає від небезпечних імен файлів та шляхів
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


# Абсолютный путь до папки, где лежит app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Загружаем переменные окружения из файла .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Створюємо екземпляр Flask-додатки
app = Flask(__name__)

# Ограничение размера входящих запросов.
# 256 КБ достаточно для учебных HDL/Python-файлов.
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

# Дополнительный лимит для кода, отправленного через встроенный редактор.
MAX_EDITOR_CODE_LENGTH = 100_000

# Секретный ключ Flask берётся только из .env
app.secret_key = os.getenv("SECRET_KEY", "").strip()

if not app.secret_key:
    raise RuntimeError("SECRET_KEY не задан в .env")

# Реєструємо Google як зовнішній сервіс для авторизації
oauth = OAuth(app)

# ID і секрет клієнта беруться з файлу .env
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
WAVEFORM_DIR = os.path.join(BASE_DIR, "waveforms")


# =========================
# API-настройки
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

LEARNING_PATH_MODE = os.getenv("LEARNING_PATH_MODE", "free").strip().lower()

TRAINER_AI_MODE = os.getenv("TRAINER_AI_MODE", "template").strip().lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate").strip()

VERILATOR_PERL_PATH = os.getenv(
    "VERILATOR_PERL_PATH",
    r"Y:\MSYS2\usr\bin\perl.exe"
)

VERILATOR_SCRIPT_PATH = os.getenv(
    "VERILATOR_SCRIPT_PATH",
    r"Y:\MSYS2\ucrt64\bin\verilator"
)

VERILATOR_UCRT_BIN = os.getenv(
    "VERILATOR_UCRT_BIN",
    r"Y:\MSYS2\ucrt64\bin"
)

VERILATOR_USR_BIN = os.getenv(
    "VERILATOR_USR_BIN",
    r"Y:\MSYS2\usr\bin"
)

YOSYS_EXE_PATH = os.getenv(
    "YOSYS_EXE_PATH",
    r"Y:\MSYS2\ucrt64\bin\yosys.exe"
)

YOSYS_UCRT_BIN = os.getenv(
    "YOSYS_UCRT_BIN",
    r"Y:\MSYS2\ucrt64\bin"
)

YOSYS_USR_BIN = os.getenv(
    "YOSYS_USR_BIN",
    r"Y:\MSYS2\usr\bin"
)

# Назва Docker-образу, в якому запускатиметься перевірка Python-коду
PYTHON_DOCKER_IMAGE = "fpga-python-checker:latest"
# Максимальний час перевірки Python-коду 
PYTHON_CHECK_TIMEOUT_SECONDS = 15

HDL_CHECK_MODE = os.getenv("HDL_CHECK_MODE", "docker").strip().lower()
HDL_LINT_MODE = os.getenv("HDL_LINT_MODE", "docker").strip().lower()
HDL_DOCKER_IMAGE = os.getenv("HDL_DOCKER_IMAGE", "fpga-hdl-checker:latest").strip()

def get_int_env(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


HDL_COMPILE_TIMEOUT_SECONDS = get_int_env("HDL_COMPILE_TIMEOUT_SECONDS", 10)
HDL_SIM_TIMEOUT_SECONDS = get_int_env("HDL_SIM_TIMEOUT_SECONDS", 10)

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


# ============================================================
# CSRF-защита POST-форм
# ============================================================

def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


@app.context_processor
def inject_csrf_token():
    return {
        "csrf_token": generate_csrf_token
    }


@app.before_request
def csrf_protect():
    if request.method != "POST":
        return None

    session_token = session.get("csrf_token", "")
    form_token = request.form.get("csrf_token", "")
    header_token = request.headers.get("X-CSRFToken", "")

    submitted_token = form_token or header_token

    if not session_token or not submitted_token:
        abort(400, description="CSRF token is missing.")

    if not hmac.compare_digest(session_token, submitted_token):
        abort(400, description="Invalid CSRF token.")

    return None


# ============================================================
# Попытки выполнения лабораторных работ
# ============================================================

def get_extra_attempts_count(conn, lab_id, username):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(extra_attempts), 0) AS extra_attempts
        FROM attempt_overrides
        WHERE lab_id = ?
          AND username = ?
        """,
        (
            lab_id,
            username
        )
    ).fetchone()

    if not row:
        return 0

    return int(row["extra_attempts"] or 0)


def get_used_attempts_count(conn, lab_id, username):
    row = conn.execute(
        """
        SELECT COUNT(*) AS attempts_count
        FROM submissions
        WHERE lab_id = ?
          AND username = ?
        """,
        (
            lab_id,
            username
        )
    ).fetchone()

    if not row:
        return 0

    return int(row["attempts_count"] or 0)


def get_attempts_info(conn, lab, username):
    lab_id = lab["id"]
    base_limit = int(lab["max_attempts"] or 0)

    used_attempts = get_used_attempts_count(conn, lab_id, username)
    extra_attempts = get_extra_attempts_count(conn, lab_id, username)

    total_limit = base_limit + extra_attempts

    if total_limit <= 0:
        attempts_left = 0
    else:
        attempts_left = max(total_limit - used_attempts, 0)

    return {
        "base_limit": base_limit,
        "extra_attempts": extra_attempts,
        "total_limit": total_limit,
        "used_attempts": used_attempts,
        "attempts_left": attempts_left,
        "is_limit_reached": total_limit > 0 and used_attempts >= total_limit
    }


def password_is_hashed(password_value):
    password_value = str(password_value or "")

    return (
        password_value.startswith("scrypt:")
        or password_value.startswith("pbkdf2:")
        or password_value.startswith("argon2:")
    )


def hash_password(raw_password):
    return generate_password_hash(str(raw_password))


def verify_password(stored_password, raw_password):
    stored_password = str(stored_password or "")
    raw_password = str(raw_password or "")

    if not stored_password or not raw_password:
        return False

    if password_is_hashed(stored_password):
        try:
            return check_password_hash(stored_password, raw_password)
        except Exception:
            return False

    # Временная поддержка старых паролей, которые уже лежали в базе открытым текстом.
    # После успешного входа они будут автоматически заменены на хеш.
    return stored_password == raw_password


def validate_password_strength(password, username=""):
    password = str(password or "")
    username = str(username or "").lower()

    errors = []

    if not password:
        errors.append("Пароль не может быть пустым.")

    if password.strip() != password:
        errors.append("Пароль не должен начинаться или заканчиваться пробелом.")

    if len(password) < 8:
        errors.append("Пароль должен содержать минимум 8 символов.")

    if not re.search(r"[A-Za-zА-Яа-я]", password):
        errors.append("Пароль должен содержать хотя бы одну букву.")

    if not re.search(r"\d", password):
        errors.append("Пароль должен содержать хотя бы одну цифру.")

    if username and username in password.lower():
        errors.append("Пароль не должен содержать логин пользователя.")

    if errors:
        return False, " ".join(errors)

    return True, ""


# ============================================================
# Расчёт итоговой оценки по лабораторной работе
# ============================================================

def clamp_score(value):
    try:
        value = int(round(float(value or 0)))
    except (TypeError, ValueError):
        value = 0

    return max(0, min(100, value))


def map_score_to_ukrainian_ects(score):
    score = clamp_score(score)

    if score >= 90:
        return {
            "ects_grade": "A",
            "national_grade": "отлично",
            "final_status": "Зачтено"
        }

    if score >= 82:
        return {
            "ects_grade": "B",
            "national_grade": "хорошо",
            "final_status": "Зачтено"
        }

    if score >= 74:
        return {
            "ects_grade": "C",
            "national_grade": "хорошо",
            "final_status": "Зачтено"
        }

    if score >= 64:
        return {
            "ects_grade": "D",
            "national_grade": "удовлетворительно",
            "final_status": "Зачтено"
        }

    if score >= 60:
        return {
            "ects_grade": "E",
            "national_grade": "удовлетворительно",
            "final_status": "Зачтено"
        }

    if score >= 35:
        return {
            "ects_grade": "FX",
            "national_grade": "неудовлетворительно, требуется доработка",
            "final_status": "Требуется доработка"
        }

    return {
        "ects_grade": "F",
        "national_grade": "неудовлетворительно, требуется повторное выполнение",
        "final_status": "Не зачтено"
    }


def get_component_score(score, status=None):
    score = clamp_score(score)

    if status in ["UNAVAILABLE", "SYSTEM_ERROR", "TIMEOUT"]:
        return None

    return score


def build_lab_final_grade(
    testbench_score,
    lint_score,
    synth_score,
    questions_score=0,
    has_questions=False,
    lint_status="OK",
    synth_status="OK"
):
    testbench_score = clamp_score(testbench_score)
    questions_score = clamp_score(questions_score)

    lint_component = get_component_score(lint_score, lint_status)
    synth_component = get_component_score(synth_score, synth_status)

    if has_questions:
        weights = {
            "testbench": 70,
            "lint": 10,
            "synthesis": 10,
            "questions": 10
        }
    else:
        weights = {
            "testbench": 70,
            "lint": 15,
            "synthesis": 15,
            "questions": 0
        }

    # Если lint или synthesis недоступны по системной причине,
    # их вес переносится в функциональную проверку, чтобы не штрафовать студента.
    if lint_component is None:
        weights["testbench"] += weights["lint"]
        weights["lint"] = 0
        lint_component = 0

    if synth_component is None:
        weights["testbench"] += weights["synthesis"]
        weights["synthesis"] = 0
        synth_component = 0

    final_score = round(
        testbench_score * weights["testbench"] / 100
        + lint_component * weights["lint"] / 100
        + synth_component * weights["synthesis"] / 100
        + questions_score * weights["questions"] / 100
    )

    final_score = clamp_score(final_score)
    mapped_grade = map_score_to_ukrainian_ects(final_score)

    # Строгое инженерное правило:
    # если функциональная проверка testbench ниже 60,
    # лабораторная требует доработки независимо от итогового балла.
    if testbench_score < 60:
        mapped_grade["final_status"] = "Требуется доработка"

    grading_breakdown = {
        "testbench_score": testbench_score,
        "lint_score": lint_component,
        "synthesis_score": synth_component,
        "questions_score": questions_score,
        "weights": weights,
        "final_score": final_score,
        "ects_grade": mapped_grade["ects_grade"],
        "national_grade": mapped_grade["national_grade"],
        "final_status": mapped_grade["final_status"],
        "testbench_rule_applied": testbench_score < 60
    }

    return {
        "final_score": final_score,
        "ects_grade": mapped_grade["ects_grade"],
        "national_grade": mapped_grade["national_grade"],
        "final_status": mapped_grade["final_status"],
        "grading_breakdown": grading_breakdown
    }



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

    # Персональные настройки внешнего вида пользователя.
    # Добавляются безопасно через PRAGMA table_info(users),
    # чтобы не ломать уже существующую базу данных.
    if "theme" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'light'")

    if "palette" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN palette TEXT DEFAULT 'pastel'")

    if "font_size" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN font_size TEXT DEFAULT 'normal'")

    if "ui_density" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN ui_density TEXT DEFAULT 'comfortable'")

    if "first_login_completed" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN first_login_completed INTEGER DEFAULT 0")

    if "show_beginner_tips" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN show_beginner_tips INTEGER DEFAULT 1")

    if "avatar_filename" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN avatar_filename TEXT DEFAULT ''")

    # Нормализация значений для старых пользователей.
    # Если в старой базе поле пустое или NULL, подставляем безопасное значение по умолчанию.

    cur.execute("""
        UPDATE users
        SET show_beginner_tips = 1
        WHERE show_beginner_tips IS NULL
    """)

    cur.execute("""
        UPDATE users
        SET theme = 'light'
        WHERE theme IS NULL OR theme = ''
    """)

    cur.execute("""
        UPDATE users
        SET palette = 'pastel'
        WHERE palette IS NULL OR palette = ''
    """)

    cur.execute("""
        UPDATE users
        SET font_size = 'normal'
        WHERE font_size IS NULL OR font_size = ''
    """)

    cur.execute("""
        UPDATE users
        SET ui_density = 'comfortable'
        WHERE ui_density IS NULL OR ui_density = ''
    """)

    cur.execute("""
        UPDATE users
        SET first_login_completed = 0
        WHERE first_login_completed IS NULL
    """)

    cur.execute("""
        UPDATE users
        SET avatar_filename = ''
        WHERE avatar_filename IS NULL
    """)


# Таблиця лабораторних робіт:
# зберігає опис завдання, тестбенч, параметри перевірки та налаштування оцінювання
    cur.execute("""
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            testbench TEXT NOT NULL,
                
            public_testbench TEXT DEFAULT '',
            hidden_testbench TEXT DEFAULT '',
            show_hidden_details INTEGER DEFAULT 0,

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
    if "public_testbench" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN public_testbench TEXT DEFAULT ''")

    if "hidden_testbench" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN hidden_testbench TEXT DEFAULT ''")

    if "show_hidden_details" not in column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN show_hidden_details INTEGER DEFAULT 0")
    
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


    cur.execute("""
        UPDATE labs
        SET public_testbench = testbench
        WHERE (public_testbench IS NULL OR public_testbench = '')
        AND testbench IS NOT NULL
        AND testbench != ''
    """)


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
            
            synth_status TEXT DEFAULT '',
            synth_score INTEGER DEFAULT 0,
            synth_cells_count INTEGER DEFAULT 0,
            synth_wires_count INTEGER DEFAULT 0,
            synth_wire_bits_count INTEGER DEFAULT 0,
            synth_warnings_count INTEGER DEFAULT 0,
            synth_output TEXT DEFAULT '',
            synth_recommendation TEXT DEFAULT '',
            synth_stats_json TEXT DEFAULT '',
                
            public_status TEXT DEFAULT '',
            public_score INTEGER DEFAULT 0,
            public_passed_tests INTEGER DEFAULT 0,
            public_total_tests INTEGER DEFAULT 0,
            public_output TEXT DEFAULT '',

            hidden_status TEXT DEFAULT '',
            hidden_score INTEGER DEFAULT 0,
            hidden_passed_tests INTEGER DEFAULT 0,
            hidden_total_tests INTEGER DEFAULT 0,
            hidden_output TEXT DEFAULT '',
                
            lint_status TEXT DEFAULT '',
            lint_score INTEGER DEFAULT 0,
            lint_issues_count INTEGER DEFAULT 0,
            lint_output TEXT DEFAULT '',
            lint_recommendation TEXT DEFAULT '',
            lint_issues_json TEXT DEFAULT '',

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

    # Поля для комплексной итоговой оценки лабораторной работы.
    if "testbench_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN testbench_score INTEGER DEFAULT 0")

    if "questions_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN questions_score INTEGER DEFAULT 0")

    if "final_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN final_score INTEGER DEFAULT 0")

    if "final_status" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN final_status TEXT DEFAULT ''")

    if "ects_grade" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN ects_grade TEXT DEFAULT ''")

    if "national_grade" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN national_grade TEXT DEFAULT ''")

    if "grading_breakdown" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN grading_breakdown TEXT DEFAULT ''")


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

# Таблица кэша для интернет-рекомендаций индивидуальной траектории обучения.
# Нужна, чтобы не выполнять внешний поиск при каждом открытии страницы.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_path_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            lab_id INTEGER DEFAULT 0,
            cache_key TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

# Таблица заданий тренажёра
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainer_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT DEFAULT '',
            source_mode TEXT DEFAULT 'template',

            topic_slug TEXT NOT NULL,
            competency TEXT DEFAULT '',
            error_type TEXT DEFAULT '',

            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            difficulty TEXT DEFAULT 'basic',

            prompt TEXT NOT NULL,
            code_snippet TEXT DEFAULT '',
            options_json TEXT DEFAULT '[]',
            correct_answer_json TEXT DEFAULT '{}',
            explanation TEXT DEFAULT '',

            source_title TEXT DEFAULT '',
            source_url TEXT DEFAULT '',

            ai_prompt TEXT DEFAULT '',
            ai_raw_output TEXT DEFAULT '',

            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)

# Таблица попыток по заданиям тренажёра
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainer_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            task_id INTEGER NOT NULL,

            answer_text TEXT DEFAULT '',
            selected_option TEXT DEFAULT '',

            is_correct INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            feedback TEXT DEFAULT '',

            created_at TEXT NOT NULL
        )
    """)

    # Таблица тренировочных тестов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainer_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,

            topic_slug TEXT DEFAULT '',
            competency TEXT DEFAULT '',
            error_type TEXT DEFAULT '',
            error_title TEXT DEFAULT '',

            title TEXT NOT NULL,
            source_mode TEXT DEFAULT 'template',

            status TEXT DEFAULT 'active',
            total_questions INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,

            created_at TEXT NOT NULL,
            submitted_at TEXT DEFAULT ''
        )
    """)

    # Связь теста с вопросами
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainer_session_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            order_number INTEGER DEFAULT 1,

            FOREIGN KEY (session_id) REFERENCES trainer_sessions(id),
            FOREIGN KEY (task_id) REFERENCES trainer_tasks(id)
        )
    """)

    # Ответы студента внутри тренировочного теста
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainer_session_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            username TEXT NOT NULL,

            selected_option TEXT DEFAULT '',
            is_correct INTEGER DEFAULT 0,
            correct_answer TEXT DEFAULT '',
            feedback TEXT DEFAULT '',

            created_at TEXT NOT NULL,

            UNIQUE(session_id, task_id),
            FOREIGN KEY (session_id) REFERENCES trainer_sessions(id),
            FOREIGN KEY (task_id) REFERENCES trainer_tasks(id)
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

    if "public_status" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN public_status TEXT DEFAULT ''")

    if "public_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN public_score INTEGER DEFAULT 0")

    if "public_passed_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN public_passed_tests INTEGER DEFAULT 0")

    if "public_total_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN public_total_tests INTEGER DEFAULT 0")

    if "public_output" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN public_output TEXT DEFAULT ''")

    if "hidden_status" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN hidden_status TEXT DEFAULT ''")

    if "hidden_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN hidden_score INTEGER DEFAULT 0")

    if "hidden_passed_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN hidden_passed_tests INTEGER DEFAULT 0")

    if "hidden_total_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN hidden_total_tests INTEGER DEFAULT 0")

    if "hidden_output" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN hidden_output TEXT DEFAULT ''")

    if "lint_status" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_status TEXT DEFAULT ''")

    if "lint_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_score INTEGER DEFAULT 0")

    if "lint_issues_count" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_issues_count INTEGER DEFAULT 0")

    if "lint_output" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_output TEXT DEFAULT ''")

    if "lint_recommendation" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_recommendation TEXT DEFAULT ''")

    if "lint_issues_json" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN lint_issues_json TEXT DEFAULT ''")

    if "synth_status" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_status TEXT DEFAULT ''")

    if "synth_score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_score INTEGER DEFAULT 0")

    if "synth_cells_count" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_cells_count INTEGER DEFAULT 0")

    if "synth_wires_count" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_wires_count INTEGER DEFAULT 0")

    if "synth_wire_bits_count" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_wire_bits_count INTEGER DEFAULT 0")

    if "synth_warnings_count" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_warnings_count INTEGER DEFAULT 0")

    if "synth_output" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_output TEXT DEFAULT ''")

    if "synth_recommendation" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_recommendation TEXT DEFAULT ''")

    if "synth_stats_json" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN synth_stats_json TEXT DEFAULT ''")


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

    # Индивидуальные дополнительные попытки по лабораторным работам
    # Таблица хранит не саму попытку, а разрешение преподавателя
    # на дополнительные отправки по конкретной лабораторной работе.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attempt_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id INTEGER NOT NULL,
            username TEXT NOT NULL,

            extra_attempts INTEGER DEFAULT 1,
            reason TEXT DEFAULT '',

            granted_by TEXT DEFAULT '',
            created_at TEXT NOT NULL,

            FOREIGN KEY (lab_id) REFERENCES labs(id)
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
                hash_password("student123"),
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
                hash_password("teacher123"),
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
                hash_password("admin123"),
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

    # Миграция старых паролей:
    # если в базе пароль хранится открытым текстом, заменяем его на хеш.
    legacy_users = cur.execute(
        """
        SELECT id, password
        FROM users
        """
    ).fetchall()

    for legacy_user in legacy_users:
        current_password = legacy_user["password"] or ""

        if current_password and not password_is_hashed(current_password):
            cur.execute(
                """
                UPDATE users
                SET password = ?
                WHERE id = ?
                """,
                (
                    hash_password(current_password),
                    legacy_user["id"]
                )
            )


    # ============================================================
    # Индексы для ускорения журнала, аналитики и истории попыток
    # ============================================================

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_submissions_lab_username
        ON submissions(lab_id, username)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_submissions_username_created
        ON submissions(username, created_at)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_role_group
        ON users(role, student_group)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_labs_discipline
        ON labs(discipline)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_attempt_overrides_lab_username
        ON attempt_overrides(lab_id, username)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_extra_task_attempts_submission
        ON extra_task_attempts(submission_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_teacher_subject_groups_access
        ON teacher_subject_groups(teacher_username, discipline, student_group)
    """)

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


@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Файл или отправленные данные слишком большие. Максимальный размер — 256 КБ.")
    return redirect(request.referrer or url_for("index"))


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

def get_row_value(row, key, default=""):
    if not row:
        return default

    if key in row.keys():
        value = row[key]

        if value is not None:
            return value

    return default


def normalize_user_ui_value(value, default_value, allowed_values):
    value = str(value or "").strip()

    if not value:
        return default_value

    if value not in allowed_values:
        return default_value

    return value


def load_user_ui_settings_to_session(user):
    theme = normalize_user_ui_value(
        get_row_value(user, "theme", "light"),
        "light",
        ["light", "dark", "system"]
    )

    palette = normalize_user_ui_value(
        get_row_value(user, "palette", "pastel"),
        "pastel",
        ["pastel", "indigo", "burgundy", "green"]
    )

    font_size = normalize_user_ui_value(
        get_row_value(user, "font_size", "normal"),
        "normal",
        ["small", "normal", "large"]
    )

    ui_density = normalize_user_ui_value(
        get_row_value(user, "ui_density", "comfortable"),
        "comfortable",
        ["comfortable", "compact"]
    )

    avatar_filename = str(
        get_row_value(user, "avatar_filename", "") or ""
    ).strip()

    first_login_completed = int(
        get_row_value(user, "first_login_completed", 0) or 0
    )

    show_beginner_tips = int(
        get_row_value(user, "show_beginner_tips", 1) or 0
    )

    session["theme"] = theme
    session["palette"] = palette
    session["font_size"] = font_size
    session["ui_density"] = ui_density
    session["avatar_filename"] = avatar_filename
    session["first_login_completed"] = first_login_completed
    session["show_beginner_tips"] = show_beginner_tips

def get_default_redirect_for_role(role):
    if role == "student":
        return url_for("index")

    if role == "teacher":
        return url_for("teacher_panel")

    if role == "admin":
        return url_for("admin_panel")

    return url_for("index")

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

def delete_waveform_file(filename):
    if not filename:
        return

    file_path = os.path.join(WAVEFORM_DIR, filename)

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

def teacher_can_access_submission(conn, teacher_username, submission_id):
    access = conn.execute(
        """
        SELECT 1
        FROM submissions
        JOIN labs ON labs.id = submissions.lab_id
        LEFT JOIN users AS student ON student.username = submissions.username
        WHERE submissions.id = ?
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
            submission_id,
            teacher_username,
            teacher_username
        )
    ).fetchone()

    return access is not None


# =========================
# 6. Перевірка HDL / Verilog-рішень
# =========================

def get_verilator_base_command():
    """
    Возвращает базовую команду для запуска Verilator.

    На Windows/MSYS2 Verilator установлен как Perl-скрипт,
    поэтому запускаем его через perl.exe.

    На Linux/macOS можно запускать просто команду verilator.
    """
    if os.name == "nt":
        if os.path.exists(VERILATOR_PERL_PATH) and os.path.exists(VERILATOR_SCRIPT_PATH):
            return [
                VERILATOR_PERL_PATH,
                VERILATOR_SCRIPT_PATH
            ]

    return ["verilator"]


def get_verilator_environment():
    """
    Формирует окружение для запуска Verilator.
    Добавляет MSYS2 ucrt64/bin и usr/bin в PATH.
    """
    env = os.environ.copy()

    if os.name == "nt":
        old_path = env.get("PATH", "")

        env["PATH"] = (
            VERILATOR_UCRT_BIN
            + os.pathsep
            + VERILATOR_USR_BIN
            + os.pathsep
            + old_path
        )

        # Лучше не задавать VERILATOR_ROOT вручную.
        # MSYS2-обёртка Verilator сама определяет корректный путь.
        env.pop("VERILATOR_ROOT", None)

    return env


def normalize_path_for_verilator(file_path):
    """
    На Windows заменяет обратные слэши на обычные.
    Это уменьшает риск ошибок при передаче пути в MSYS2/Verilator.
    """
    return os.path.abspath(file_path).replace("\\", "/")


def is_verilator_available():
    try:
        command = get_verilator_base_command() + ["--version"]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            env=get_verilator_environment()
        )

        return result.returncode == 0

    except Exception:
        return False


def strip_verilog_comments(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"//.*", "", code)
    return code


def run_hdl_lint_check_local(solution_path):
    if not is_verilator_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": "Verilator не найден. Установите Verilator и добавьте команду verilator в PATH.",
            "lint_recommendation": "Lint-проверка HDL-кода не выполнена, так как Verilator недоступен.",
            "lint_issues": []
        }

    try:
        with open(solution_path, "r", encoding="utf-8", errors="replace") as file:
            code = file.read()

        custom_issues = run_custom_hdl_style_checks(code)

        verilator_solution_path = normalize_path_for_verilator(solution_path)

        command = get_verilator_base_command() + [
            "--lint-only",
            "-Wall",
            "-Wno-fatal",
            "-Wno-DECLFILENAME",
            "-sv",
            verilator_solution_path
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            env=get_verilator_environment()
        )

        raw_output = (result.stdout or "") + "\n" + (result.stderr or "")

        if (
            "Cannot find verilated_std_waiver.vlt" in raw_output
            or "Cannot find verilated_std.sv" in raw_output
        ):
            return {
                "lint_status": "UNAVAILABLE",
                "lint_score": 0,
                "lint_issues_count": 0,
                "lint_output": (
                    "Verilator найден, но его системные файлы MSYS2 недоступны.\n\n"
                    "Это не ошибка HDL-кода студента, а ошибка настройки локального Verilator.\n\n"
                    "--- Вывод Verilator ---\n"
                    + raw_output.strip()
                ),
                "lint_recommendation": (
                    "Lint-проверка временно недоступна из-за проблемы конфигурации Verilator. "
                    "Функциональная HDL-проверка выполнена в Docker-песочнице."
                ),
                "lint_issues": []
            }

        verilator_issues = parse_verilator_lint_output(raw_output)

        all_issues = custom_issues + verilator_issues

        lint_score = calculate_hdl_lint_score(all_issues)
        lint_recommendation = build_hdl_lint_recommendation(all_issues)

        if any(issue.get("severity") == "error" for issue in all_issues):
            lint_status = "ERROR"
        elif all_issues:
            lint_status = "WARNING"
        else:
            lint_status = "OK"

        if not raw_output.strip():
            raw_output = "Verilator не выявил предупреждений."

        report_lines = []
        report_lines.append(f"Статус lint-проверки: {lint_status}")
        report_lines.append(f"Качество HDL-кода: {lint_score} / 100")
        report_lines.append(f"Количество замечаний: {len(all_issues)}")
        report_lines.append("")
        report_lines.append("Рекомендация:")
        report_lines.append(lint_recommendation)
        report_lines.append("")

        if all_issues:
            report_lines.append("Список замечаний:")

            for index, issue in enumerate(all_issues, start=1):
                source = issue.get("source", "unknown")
                code = issue.get("code", "UNKNOWN")
                message = issue.get("message", "")

                report_lines.append(
                    f"{index}. [{source}] {code}: {message}"
                )

            report_lines.append("")

        report_lines.append("--- Вывод Verilator ---")
        report_lines.append(raw_output.strip())

        return {
            "lint_status": lint_status,
            "lint_score": lint_score,
            "lint_issues_count": len(all_issues),
            "lint_output": "\n".join(report_lines),
            "lint_recommendation": lint_recommendation,
            "lint_issues": all_issues
        }

    except subprocess.TimeoutExpired:
        return {
            "lint_status": "TIMEOUT",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": "Lint-проверка выполнялась слишком долго и была остановлена.",
            "lint_recommendation": "Проверьте сложность HDL-кода или наличие конструкций, затрудняющих статический анализ.",
            "lint_issues": []
        }

    except Exception as error:
        return {
            "lint_status": "SYSTEM_ERROR",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": f"Ошибка lint-проверки HDL-кода: {str(error)}",
            "lint_recommendation": "Проверьте настройку Verilator и корректность HDL-файла.",
            "lint_issues": []
        }


def run_hdl_lint_check_docker(solution_path):
    if not is_docker_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Docker недоступен.\n\n"
                "Lint-проверка HDL-кода не выполнена, так как Docker Desktop не запущен."
            ),
            "lint_recommendation": "Запустите Docker Desktop и повторите проверку.",
            "lint_issues": []
        }

    if not is_hdl_docker_image_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                f"Docker-образ {HDL_DOCKER_IMAGE} не найден.\n\n"
                "Соберите его командой:\n"
                "docker build -t fpga-hdl-checker:latest docker/hdl-checker"
            ),
            "lint_recommendation": "Соберите Docker-образ HDL-проверки.",
            "lint_issues": []
        }

    with tempfile.TemporaryDirectory(prefix="hdl_lint_docker_") as temp_dir:
        temp_solution_path = os.path.join(temp_dir, "solution.v")

        with open(solution_path, "r", encoding="utf-8", errors="replace") as file:
            code = file.read()

        # Убираем предупреждение Verilator о том, что в конце файла нет новой строки.
        if not code.endswith("\n"):
            code += "\n"

        with open(temp_solution_path, "w", encoding="utf-8") as file:
            file.write(code)

        custom_issues = run_custom_hdl_style_checks(code)

        command = build_hdl_docker_command(
            workspace_path=temp_dir,
            container_command=[
                "verilator",
                "--lint-only",
                "-Wall",
                "-Wno-fatal",
                "-Wno-DECLFILENAME",
                "-sv",
                "solution.v"
            ]
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )

        except subprocess.TimeoutExpired:
            return {
                "lint_status": "TIMEOUT",
                "lint_score": 0,
                "lint_issues_count": 0,
                "lint_output": "Lint-проверка HDL-кода в Docker выполнялась слишком долго и была остановлена.",
                "lint_recommendation": "Проверьте сложность HDL-кода.",
                "lint_issues": []
            }

        except Exception as error:
            return {
                "lint_status": "SYSTEM_ERROR",
                "lint_score": 0,
                "lint_issues_count": 0,
                "lint_output": f"Ошибка Docker lint-проверки HDL-кода: {str(error)}",
                "lint_recommendation": "Проверьте Docker-образ HDL-проверки.",
                "lint_issues": []
            }

        raw_output = get_process_output(result)

        verilator_issues = parse_verilator_lint_output(raw_output)

        if result.returncode != 0 and not verilator_issues:
            verilator_issues.append({
                "severity": "error",
                "code": "VERILATOR_ERROR",
                "message": raw_output or "Verilator завершился с ошибкой.",
                "source": "verilator"
            })

        all_issues = custom_issues + verilator_issues

        lint_score = calculate_hdl_lint_score(all_issues)
        lint_recommendation = build_hdl_lint_recommendation(all_issues)

        if any(issue.get("severity") == "error" for issue in all_issues):
            lint_status = "ERROR"
        elif all_issues:
            lint_status = "WARNING"
        else:
            lint_status = "OK"

        if not raw_output.strip():
            raw_output = "Verilator не выявил предупреждений."

        report_lines = []
        report_lines.append("Среда lint-проверки: Docker-песочница HDL.")
        report_lines.append("")
        report_lines.append(f"Статус lint-проверки: {lint_status}")
        report_lines.append(f"Качество HDL-кода: {lint_score} / 100")
        report_lines.append(f"Количество замечаний: {len(all_issues)}")
        report_lines.append("")
        report_lines.append("Рекомендация:")
        report_lines.append(lint_recommendation)
        report_lines.append("")

        if all_issues:
            report_lines.append("Список замечаний:")

            for index, issue in enumerate(all_issues, start=1):
                source = issue.get("source", "unknown")
                code_value = issue.get("code", "UNKNOWN")
                message = issue.get("message", "")

                report_lines.append(
                    f"{index}. [{source}] {code_value}: {message}"
                )

            report_lines.append("")

        report_lines.append("--- Вывод Verilator ---")
        report_lines.append(raw_output.strip())

        return {
            "lint_status": lint_status,
            "lint_score": lint_score,
            "lint_issues_count": len(all_issues),
            "lint_output": "\n".join(report_lines),
            "lint_recommendation": lint_recommendation,
            "lint_issues": all_issues
        }


def run_hdl_lint_check(solution_path):
    if HDL_LINT_MODE == "local":
        return run_hdl_lint_check_local(solution_path)

    return run_hdl_lint_check_docker(solution_path)


def get_yosys_base_command():
    if os.name == "nt":
        if os.path.exists(YOSYS_EXE_PATH):
            return [YOSYS_EXE_PATH]

    return ["yosys"]


def get_yosys_environment():
    env = os.environ.copy()

    if os.name == "nt":
        old_path = env.get("PATH", "")

        env["PATH"] = (
            YOSYS_UCRT_BIN
            + os.pathsep
            + YOSYS_USR_BIN
            + os.pathsep
            + old_path
        )

    return env


def is_yosys_available():
    try:
        result = subprocess.run(
            get_yosys_base_command() + ["-V"],
            capture_output=True,
            text=True,
            timeout=10,
            env=get_yosys_environment()
        )

        return result.returncode == 0

    except Exception:
        return False


def extract_yosys_number(output, label):
    output = str(output or "")

    old_pattern = rf"{re.escape(label)}:\s+(\d+)"
    old_match = re.search(old_pattern, output)

    if old_match:
        return int(old_match.group(1))

    new_patterns = {
        "Number of wires": r"^\s*(\d+)\s+wires\s*$",
        "Number of wire bits": r"^\s*(\d+)\s+wire bits\s*$",
        "Number of cells": r"^\s*(\d+)\s+cells\s*$"
    }

    pattern = new_patterns.get(label)

    if pattern:
        match = re.search(pattern, output, flags=re.MULTILINE)

        if match:
            return int(match.group(1))

    return 0


def parse_yosys_warnings(output):
    warnings = []

    for line in str(output).splitlines():
        stripped = line.strip()

        if "Warning:" in stripped or stripped.startswith("Warning:"):
            warnings.append(stripped)

    return warnings


def parse_yosys_cells(output):
    cells = {}
    lines = str(output or "").splitlines()
    after_cells_header = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Number of cells:"):
            after_cells_header = True
            continue

        if re.match(r"^\d+\s+cells\s*$", stripped):
            after_cells_header = True
            continue

        if after_cells_header:
            if not stripped:
                continue

            old_match = re.match(r"^([A-Za-z0-9_$.\-]+)\s+(\d+)$", stripped)

            if old_match:
                cell_name = old_match.group(1)
                cell_count = int(old_match.group(2))
                cells[cell_name] = cell_count
                continue

            new_match = re.match(r"^(\d+)\s+([A-Za-z0-9_$.\-]+)$", stripped)

            if new_match:
                cell_count = int(new_match.group(1))
                cell_name = new_match.group(2)
                cells[cell_name] = cell_count
                continue

            if (
                stripped.startswith("End of script")
                or stripped.startswith("Warnings:")
                or stripped.startswith("===")
                or stripped.startswith("Time spent")
            ):
                break

    return cells


def define_synthesis_complexity(cells_count, wire_bits_count):
    if cells_count == 0 and wire_bits_count <= 8:
        return "очень простая схема"

    if cells_count <= 5:
        return "простая схема"

    if cells_count <= 25:
        return "схема средней сложности"

    if cells_count <= 100:
        return "достаточно сложная схема"

    return "сложная схема"


def build_yosys_recommendation(synth_status, warnings_count, cells_count):
    if synth_status == "UNAVAILABLE":
        return "Проверка синтезируемости не выполнена, так как Yosys недоступен."

    if synth_status == "ERROR":
        return (
            "Код не прошёл этап синтеза. Проверьте, что в решении используется синтезируемый Verilog "
            "без testbench-конструкций, задержек #, неопределённых модулей и неподдерживаемых операторов."
        )

    if warnings_count > 0:
        return (
            "Код синтезируется, но Yosys выдал предупреждения. Проверьте возможные неиспользуемые сигналы, "
            "неполные присваивания и корректность описания аппаратной логики."
        )

    if cells_count == 0:
        return (
            "Код синтезируется. Логических ячеек почти нет: схема может быть очень простой "
            "или описывать прямое соединение сигналов."
        )

    return "Код успешно синтезируется. Критических проблем на этапе синтеза не обнаружено."


def run_hdl_synthesis_check(solution_path, lab=None):
    if not is_yosys_available():
        return {
            "synth_status": "UNAVAILABLE",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": "Yosys не найден или не запускается из Flask.",
            "synth_recommendation": "Проверьте путь YOSYS_EXE_PATH и наличие Yosys в MSYS2.",
            "synth_stats": {}
        }

    temp_dir = tempfile.mkdtemp(prefix="yosys_synth_")

    try:
        temp_solution_path = os.path.join(temp_dir, "solution.v")
        shutil.copy(solution_path, temp_solution_path)

        yosys_script = (
            "read_verilog -sv solution.v; "
            "hierarchy -check -auto-top; "
            "proc; "
            "opt; "
            "check; "
            "stat"
        )

        command = get_yosys_base_command() + [
            "-p",
            yosys_script
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=temp_dir,
            env=get_yosys_environment()
        )

        raw_output = (result.stdout or "") + "\n" + (result.stderr or "")

        warnings = parse_yosys_warnings(raw_output)

        wires_count = extract_yosys_number(raw_output, "Number of wires")
        wire_bits_count = extract_yosys_number(raw_output, "Number of wire bits")
        cells_count = extract_yosys_number(raw_output, "Number of cells")

        cells_by_type = parse_yosys_cells(raw_output)

        has_error = result.returncode != 0 or "ERROR:" in raw_output

        if has_error:
            synth_status = "ERROR"
            synth_score = 0
        elif warnings:
            synth_status = "WARNING"
            synth_score = max(60, 100 - len(warnings) * 10)
        else:
            synth_status = "OK"
            synth_score = 100

        complexity = define_synthesis_complexity(cells_count, wire_bits_count)

        synth_recommendation = build_yosys_recommendation(
            synth_status=synth_status,
            warnings_count=len(warnings),
            cells_count=cells_count
        )

        synth_stats = {
            "wires_count": wires_count,
            "wire_bits_count": wire_bits_count,
            "cells_count": cells_count,
            "warnings_count": len(warnings),
            "cells_by_type": cells_by_type,
            "complexity": complexity
        }

        report_lines = []
        report_lines.append(f"Статус синтеза: {synth_status}")
        report_lines.append(f"Оценка синтезируемости: {synth_score} / 100")
        report_lines.append(f"Примерная сложность: {complexity}")
        report_lines.append("")
        report_lines.append("Статистика схемы:")
        report_lines.append(f"- Количество проводов: {wires_count}")
        report_lines.append(f"- Количество битов проводов: {wire_bits_count}")
        report_lines.append(f"- Количество логических ячеек: {cells_count}")

        if cells_by_type:
            report_lines.append("")
            report_lines.append("Типы ячеек:")

            for cell_name, cell_count in cells_by_type.items():
                report_lines.append(f"- {cell_name}: {cell_count}")

        report_lines.append("")
        report_lines.append("Предупреждения синтеза:")

        if warnings:
            for warning in warnings:
                report_lines.append(f"- {warning}")
        else:
            report_lines.append("- Предупреждений нет.")

        report_lines.append("")
        report_lines.append("Рекомендация:")
        report_lines.append(synth_recommendation)
        report_lines.append("")
        report_lines.append("--- Полный вывод Yosys ---")
        report_lines.append(raw_output.strip())

        return {
            "synth_status": synth_status,
            "synth_score": synth_score,
            "synth_cells_count": cells_count,
            "synth_wires_count": wires_count,
            "synth_wire_bits_count": wire_bits_count,
            "synth_warnings_count": len(warnings),
            "synth_output": "\n".join(report_lines),
            "synth_recommendation": synth_recommendation,
            "synth_stats": synth_stats
        }

    except subprocess.TimeoutExpired:
        return {
            "synth_status": "TIMEOUT",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": "Проверка синтезируемости выполнялась слишком долго и была остановлена.",
            "synth_recommendation": "Проверьте сложность HDL-кода или наличие конструкций, затрудняющих синтез.",
            "synth_stats": {}
        }

    except Exception as error:
        return {
            "synth_status": "SYSTEM_ERROR",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_warnings_count": 0,
            "synth_wire_bits_count": 0,
            "synth_output": f"Ошибка проверки синтезируемости HDL-кода: {str(error)}",
            "synth_recommendation": "Проверьте настройку Yosys и корректность HDL-файла.",
            "synth_stats": {}
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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
def run_hdl_check_local(user_code_path, testbench_text, waveform_save_path=None):
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
                0,
                False
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


def is_hdl_docker_image_available():
    try:
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                HDL_DOCKER_IMAGE
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except Exception:
        return False


def build_hdl_docker_command(workspace_path, container_command):
    host_workspace = os.path.abspath(workspace_path)

    return [
        "docker",
        "run",
        "--rm",

        # Полностью отключаем сеть внутри контейнера.
        "--network",
        "none",

        # Ограничиваем CPU и память.
        "--cpus",
        "0.5",

        "--memory",
        "128m",

        # Ограничиваем количество процессов.
        "--pids-limit",
        "64",

        # Корневая файловая система контейнера только для чтения.
        "--read-only",

        # Даём временную папку только внутри контейнера.
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",

        # Запрещаем получение дополнительных привилегий.
        "--security-opt",
        "no-new-privileges",

        # Убираем Linux capabilities.
        "--cap-drop",
        "ALL",

        # Монтируем только временную рабочую папку.
        "-v",
        f"{host_workspace}:/workspace:rw",

        "-w",
        "/workspace",

        HDL_DOCKER_IMAGE
    ] + container_command


def get_process_output(result):
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def run_hdl_check_docker(user_code_path, testbench_text, waveform_save_path=None):
    if not is_docker_available():
        return (
            "SYSTEM_ERROR",
            (
                "Docker недоступен.\n\n"
                "Проверьте, что Docker Desktop установлен и запущен."
            ),
            0,
            0,
            0,
            False
        )

    if not is_hdl_docker_image_available():
        return (
            "SYSTEM_ERROR",
            (
                f"Docker-образ {HDL_DOCKER_IMAGE} не найден.\n\n"
                "Соберите его командой:\n"
                "docker build -t fpga-hdl-checker:latest checks/docker/hdl-checker"
            ),
            0,
            0,
            0,
            False
        )

    with tempfile.TemporaryDirectory(prefix="hdl_docker_check_") as temp_dir:
        solution_path = os.path.join(temp_dir, "solution.v")
        testbench_path = os.path.join(temp_dir, "testbench.v")

        shutil.copy(user_code_path, solution_path)

        with open(testbench_path, "w", encoding="utf-8") as file:
            file.write(testbench_text)

        compile_command = build_hdl_docker_command(
            workspace_path=temp_dir,
            container_command=[
                "iverilog",
                "-o",
                "simulation.out",
                "solution.v",
                "testbench.v"
            ]
        )

        try:
            compile_result = subprocess.run(
                compile_command,
                capture_output=True,
                text=True,
                timeout=HDL_COMPILE_TIMEOUT_SECONDS
            )

        except FileNotFoundError:
            return (
                "SYSTEM_ERROR",
                "Ошибка: Docker не установлен или команда docker не добавлена в PATH.",
                0,
                0,
                0,
                False
            )

        except subprocess.TimeoutExpired:
            return (
                "TIMEOUT",
                "Ошибка: компиляция HDL-кода в Docker выполнялась слишком долго.",
                0,
                0,
                0,
                False
            )

        if compile_result.returncode != 0:
            return (
                "COMPILE_ERROR",
                get_process_output(compile_result),
                0,
                0,
                0,
                False
            )

        run_command = build_hdl_docker_command(
            workspace_path=temp_dir,
            container_command=[
                "vvp",
                "simulation.out"
            ]
        )

        try:
            run_result = subprocess.run(
                run_command,
                capture_output=True,
                text=True,
                timeout=HDL_SIM_TIMEOUT_SECONDS
            )

        except subprocess.TimeoutExpired:
            return (
                "TIMEOUT",
                "Ошибка: HDL-симуляция в Docker выполнялась слишком долго.",
                0,
                0,
                0,
                False
            )

        full_output = get_process_output(run_result)

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
                waveform_created
            )

        if "CASE|" in full_output:
            formatted_report, score, passed_tests, total_tests = format_hdl_report(full_output)

            formatted_report = (
                "Среда проверки: Docker-песочница HDL.\n\n"
                + formatted_report
            )

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
                "Среда проверки: Docker-песочница HDL.\n\n" + full_output,
                100,
                1,
                1,
                waveform_created
            )

        return (
            "FAILED",
            (
                "Среда проверки: Docker-песочница HDL.\n\n"
                + (full_output or "Тесты не пройдены или testbench не вывел результат проверки.")
            ),
            0,
            0,
            0,
            waveform_created
        )


def run_hdl_check(user_code_path, testbench_text, waveform_save_path=None):
    if HDL_CHECK_MODE == "local":
        return run_hdl_check_local(
            user_code_path=user_code_path,
            testbench_text=testbench_text,
            waveform_save_path=waveform_save_path
        )

    return run_hdl_check_docker(
        user_code_path=user_code_path,
        testbench_text=testbench_text,
        waveform_save_path=waveform_save_path
    )


def normalize_vcd_value(value):
    value = str(value or "").strip()

    if not value:
        return "x"

    return value.lower()


def parse_vcd_file(vcd_path, max_changes_per_signal=5000):
    """
    Простой VCD-парсер для отображения временных диаграмм на сайте.

    Поддерживает:
    - scalar-сигналы: 0, 1, x, z
    - vector-сигналы: b1010, bxxxx
    - иерархические имена через $scope
    - timescale
    """

    if not os.path.exists(vcd_path):
        return {
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": "VCD-файл не найден."
        }

    timescale = ""
    scope_stack = []

    signal_defs = []
    code_to_signal_indexes = {}

    current_time = 0
    max_time = 0
    definitions_finished = False

    try:
        with open(vcd_path, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()
    except Exception as error:
        return {
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": f"Не удалось прочитать VCD-файл: {str(error)}"
        }

    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            index += 1
            continue

        # -----------------------------
        # 1. Парсинг timescale
        # -----------------------------
        if line.startswith("$timescale"):
            # Вариант: $timescale 1ns $end
            if "$end" in line:
                timescale = (
                    line
                    .replace("$timescale", "")
                    .replace("$end", "")
                    .strip()
                )
            else:
                # Вариант:
                # $timescale
                #   1ns
                # $end
                collected = []

                index += 1

                while index < len(lines):
                    inner_line = lines[index].strip()

                    if inner_line.startswith("$end"):
                        break

                    collected.append(inner_line)
                    index += 1

                timescale = " ".join(collected).strip()

        # -----------------------------
        # 2. Парсинг scope
        # -----------------------------
        elif line.startswith("$scope"):
            parts = line.split()

            # Формат: $scope module tb_mux2to1 $end
            if len(parts) >= 3:
                scope_name = parts[2]
                scope_stack.append(scope_name)

        elif line.startswith("$upscope"):
            if scope_stack:
                scope_stack.pop()

        # -----------------------------
        # 3. Парсинг переменных
        # -----------------------------
        elif line.startswith("$var"):
            parts = line.split()

            # Формат:
            # $var wire 1 ! clk $end
            # parts[0] = $var
            # parts[1] = type
            # parts[2] = size
            # parts[3] = id_code
            # parts[4:-1] = reference
            if len(parts) >= 6:
                var_type = parts[1]

                try:
                    size = int(parts[2])
                except ValueError:
                    size = 1

                code = parts[3]
                reference = " ".join(parts[4:-1])

                full_name_parts = scope_stack + [reference]
                full_name = ".".join(full_name_parts)

                signal = {
                    "index": len(signal_defs),
                    "code": code,
                    "name": full_name,
                    "short_name": reference,
                    "type": var_type,
                    "size": size,
                    "changes": []
                }

                signal_defs.append(signal)

                if code not in code_to_signal_indexes:
                    code_to_signal_indexes[code] = []

                code_to_signal_indexes[code].append(signal["index"])

        elif line.startswith("$enddefinitions"):
            definitions_finished = True

        # -----------------------------
        # 4. Парсинг временных меток
        # -----------------------------
        elif line.startswith("#"):
            try:
                current_time = int(line[1:])
                max_time = max(max_time, current_time)
            except ValueError:
                pass

        # -----------------------------
        # 5. Парсинг изменений сигналов
        # -----------------------------
        else:
            # Значения могут появиться сразу после $dumpvars,
            # поэтому не будем жестко требовать definitions_finished.
            if line.startswith("$"):
                index += 1
                continue

            # Scalar:
            # 0!
            # 1!
            # x!
            # z!
            first_char = line[0]

            if first_char in ["0", "1", "x", "X", "z", "Z"]:
                value = normalize_vcd_value(first_char)
                code = line[1:].strip()

                if code in code_to_signal_indexes:
                    for signal_index in code_to_signal_indexes[code]:
                        changes = signal_defs[signal_index]["changes"]

                        if len(changes) < max_changes_per_signal:
                            changes.append({
                                "time": current_time,
                                "value": value
                            })

            # Vector:
            # b1010 "
            # bxxxx #
            elif first_char in ["b", "B"]:
                parts = line.split(maxsplit=1)

                if len(parts) == 2:
                    value = normalize_vcd_value(parts[0][1:])
                    code = parts[1].strip()

                    if code in code_to_signal_indexes:
                        for signal_index in code_to_signal_indexes[code]:
                            changes = signal_defs[signal_index]["changes"]

                            if len(changes) < max_changes_per_signal:
                                changes.append({
                                    "time": current_time,
                                    "value": value
                                })

            # Real:
            # r3.14 !
            # Пока можно игнорировать, для FPGA-лабораторных обычно не нужно.

        index += 1

    # Если у сигнала нет изменений, добавляем x в момент 0
    for signal in signal_defs:
        if not signal["changes"]:
            signal["changes"].append({
                "time": 0,
                "value": "x"
            })

        # Убираем подряд идущие одинаковые значения
        compact_changes = []

        previous_value = None

        for change in signal["changes"]:
            if change["value"] != previous_value:
                compact_changes.append(change)
                previous_value = change["value"]

        signal["changes"] = compact_changes

    return {
        "timescale": timescale or "1ns",
        "max_time": max_time,
        "signals": signal_defs,
        "error": ""
    }


def get_waveform_submission_for_current_user(submission_id):
    conn = get_db()

    submission = conn.execute(
        """
        SELECT
            submissions.*,
            labs.title AS lab_title,
            labs.discipline AS lab_discipline,
            users.full_name AS student_full_name,
            users.student_group AS student_group
        FROM submissions
        JOIN labs ON labs.id = submissions.lab_id
        LEFT JOIN users ON users.username = submissions.username
        WHERE submissions.id = ?
        """,
        (submission_id,)
    ).fetchone()

    conn.close()

    if not submission:
        abort(404)

    current_role = session.get("role")
    current_username = session.get("username")

    if current_role == "admin":
        return submission

    if current_role == "teacher":
        return submission

    if submission["username"] != current_username:
        abort(403)

    return submission


# =========================
# 6.1. HDL lint / статический анализ Verilog-кода
# =========================

def parse_verilator_lint_output(output):
    issues = []

    for line in str(output).splitlines():
        line = line.strip()

        warning_match = re.match(r"%Warning-([A-Z0-9_]+):\s*(.*)", line)
        error_match = re.match(r"%Error-([A-Z0-9_]+):\s*(.*)", line)

        if warning_match:
            issues.append({
                "severity": "warning",
                "code": warning_match.group(1),
                "message": warning_match.group(2),
                "source": "verilator"
            })

        elif error_match:
            issues.append({
                "severity": "error",
                "code": error_match.group(1),
                "message": error_match.group(2),
                "source": "verilator"
            })

        elif line.startswith("%Error:"):
            issues.append({
                "severity": "error",
                "code": "ERROR",
                "message": line,
                "source": "verilator"
            })

    return issues


def run_custom_hdl_style_checks(code):
    clean_code = strip_verilog_comments(code)
    code_lower = clean_code.lower()

    issues = []

    # 1. case без default
    if "case" in code_lower and "default" not in code_lower:
        issues.append({
            "severity": "warning",
            "code": "CASE_WITHOUT_DEFAULT",
            "message": "В коде используется case без ветки default. Это может привести к неполному описанию логики.",
            "source": "custom"
        })

    # 2. if без else в комбинационной логике
    always_comb_blocks = re.findall(
        r"always\s*@\s*\(\s*(?:\*|.*?)\s*\)\s*begin(.*?)end",
        clean_code,
        flags=re.IGNORECASE | re.DOTALL
    )

    for block in always_comb_blocks:
        block_lower = block.lower()

        if "posedge" in block_lower or "negedge" in block_lower:
            continue

        if "if" in block_lower and "else" not in block_lower:
            issues.append({
                "severity": "warning",
                "code": "IF_WITHOUT_ELSE_COMB",
                "message": "В комбинационном always-блоке найден if без else. Возможен вывод latch.",
                "source": "custom"
            })

        if "<=" in block_lower:
            issues.append({
                "severity": "warning",
                "code": "NONBLOCKING_IN_COMB",
                "message": "В комбинационной логике найдено неблокирующее присваивание <=. Обычно в always @(*) используют blocking-присваивание =.",
                "source": "custom"
            })

    # 3. blocking assignment в последовательностной логике
    seq_blocks = re.findall(
        r"always\s*@\s*\(([^)]*(?:posedge|negedge)[^)]*)\)\s*begin(.*?)end",
        clean_code,
        flags=re.IGNORECASE | re.DOTALL
    )

    for sensitivity, block in seq_blocks:
        block_without_comparisons = re.sub(r"==|!=|<=|>=", "", block)

        if re.search(r"(?<![<>=!])=(?!=)", block_without_comparisons):
            issues.append({
                "severity": "warning",
                "code": "BLOCKING_IN_SEQ",
                "message": "В последовательностной логике найдено blocking-присваивание =. Для триггеров обычно используют <=.",
                "source": "custom"
            })

    # 4. reset есть в списке портов/сигналов, но не используется в always-блоке
    has_reset_signal = re.search(r"\b(reset|rst)\b", code_lower) is not None

    if has_reset_signal and "posedge" in code_lower:
        reset_used_in_condition = re.search(
            r"if\s*\(\s*(reset|rst|!\s*reset|!\s*rst)\s*\)",
            code_lower
        ) is not None

        if not reset_used_in_condition:
            issues.append({
                "severity": "warning",
                "code": "RESET_NOT_HANDLED",
                "message": "В коде есть сигнал reset/rst, но не найдено явной обработки reset в условии if.",
                "source": "custom"
            })

    # 5. подозрение на несинтезируемые задержки в решении студента
    if re.search(r"#\s*\d+", clean_code):
        issues.append({
            "severity": "warning",
            "code": "DELAY_IN_DESIGN",
            "message": "В HDL-решении найдено временное задерживание через #. Для синтезируемого FPGA-кода такие задержки обычно не используются.",
            "source": "custom"
        })

    # 6. initial в решении студента
    if re.search(r"\binitial\b", code_lower):
        issues.append({
            "severity": "warning",
            "code": "INITIAL_IN_DESIGN",
            "message": "В решении найден блок initial. В учебных testbench он допустим, но в синтезируемом FPGA-модуле обычно нежелателен.",
            "source": "custom"
        })

    return issues


def calculate_hdl_lint_score(issues):
    score = 100

    penalties = {
        "error": 40,
        "warning": 10
    }

    code_specific_penalties = {
        "LATCH": 25,
        "CASE_WITHOUT_DEFAULT": 15,
        "IF_WITHOUT_ELSE_COMB": 20,
        "BLOCKING_IN_SEQ": 15,
        "NONBLOCKING_IN_COMB": 10,
        "UNUSEDSIGNAL": 5,
        "UNDRIVEN": 20,
        "RESET_NOT_HANDLED": 15,
        "DELAY_IN_DESIGN": 20,
        "INITIAL_IN_DESIGN": 10,
        "BLKSEQ": 15
    }

    for issue in issues:
        issue_code = issue.get("code", "")
        severity = issue.get("severity", "warning")

        penalty = code_specific_penalties.get(
            issue_code,
            penalties.get(severity, 10)
        )

        score -= penalty

    if score < 0:
        score = 0

    return score


def build_hdl_lint_recommendation(issues):
    if not issues:
        return "HDL-код не содержит заметных стилевых предупреждений. Код выглядит аккуратно."

    recommendations = []

    codes = {issue.get("code", "") for issue in issues}

    if "CASE_WITHOUT_DEFAULT" in codes:
        recommendations.append("Добавьте ветку default в case-конструкцию.")

    if "IF_WITHOUT_ELSE_COMB" in codes or "LATCH" in codes:
        recommendations.append("Проверьте полноту условий в комбинационной логике, чтобы избежать latch.")

    if "BLOCKING_IN_SEQ" in codes or "BLKSEQ" in codes:
        recommendations.append("В последовательностной логике используйте неблокирующие присваивания <=.")

    if "NONBLOCKING_IN_COMB" in codes:
        recommendations.append("В комбинационной логике обычно используют blocking-присваивание =.")

    if "UNUSEDSIGNAL" in codes:
        recommendations.append("Удалите или используйте объявленные, но неиспользуемые сигналы.")

    if "UNDRIVEN" in codes:
        recommendations.append("Проверьте сигналы, которым не присваивается значение.")

    if "RESET_NOT_HANDLED" in codes:
        recommendations.append("Добавьте явную обработку reset/rst в последовательностной логике.")

    if "DELAY_IN_DESIGN" in codes:
        recommendations.append("Уберите задержки # из синтезируемого HDL-модуля.")

    if "INITIAL_IN_DESIGN" in codes:
        recommendations.append("Проверьте необходимость initial-блока: для FPGA-дизайна он часто нежелателен.")

    if not recommendations:
        recommendations.append("Изучите предупреждения Verilator и скорректируйте стиль HDL-описания.")

    return " ".join(recommendations)


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


def build_student_visible_hdl_output(
    public_result,
    hidden_result,
    final_score,
    show_hidden_details=False
):
    public_passed = public_result["passed_tests"]
    public_total = public_result["total_tests"]

    hidden_passed = hidden_result["passed_tests"]
    hidden_total = hidden_result["total_tests"]

    output_lines = []

    output_lines.append(f"Открытые тесты: {public_passed} из {public_total}")

    if hidden_total > 0:
        output_lines.append(f"Скрытые тесты: {hidden_passed} из {hidden_total}")
    else:
        output_lines.append("Скрытые тесты: не заданы")

    output_lines.append(f"Итоговый балл: {final_score} / 100")
    output_lines.append("")
    output_lines.append("--- Открытый отчёт проверки ---")
    output_lines.append(public_result["output"])

    if hidden_total > 0:
        output_lines.append("")
        output_lines.append("--- Скрытые тесты ---")

        if show_hidden_details:
            output_lines.append(hidden_result["output"])
        else:
            output_lines.append(
                "Детали скрытых тестов не показываются студенту. "
                "Они используются только для итоговой оценки."
            )

    return "\n".join(output_lines)


def run_hdl_public_hidden_check(solution_path, lab, waveform_save_path=None):
    public_testbench = ""

    if "public_testbench" in lab.keys():
        public_testbench = lab["public_testbench"] or ""

    if not public_testbench:
        public_testbench = lab["testbench"] or ""

    hidden_testbench = ""

    if "hidden_testbench" in lab.keys():
        hidden_testbench = lab["hidden_testbench"] or ""

    show_hidden_details = 0

    if "show_hidden_details" in lab.keys():
        show_hidden_details = int(lab["show_hidden_details"] or 0)

    # 1. Запускаем открытые тесты.
    public_status, public_output, public_score, public_passed, public_total, waveform_created = run_hdl_check(
        solution_path,
        public_testbench,
        waveform_save_path
    )

    public_result = {
        "status": public_status,
        "output": public_output,
        "score": public_score,
        "passed_tests": public_passed,
        "total_tests": public_total
    }

    # Если открытые тесты не скомпилировались, скрытые запускать нет смысла.
    critical_statuses = [
        "COMPILE_ERROR",
        "SYSTEM_ERROR",
        "TIMEOUT",
        "SIMULATION_ERROR"
    ]

    if public_status in critical_statuses:
        hidden_result = {
            "status": "NOT_RUN",
            "output": "Скрытые тесты не запускались, так как открытая проверка завершилась критической ошибкой.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

        final_score = 0

        student_output = build_student_visible_hdl_output(
            public_result=public_result,
            hidden_result=hidden_result,
            final_score=final_score,
            show_hidden_details=False
        )

        return {
            "status": public_status,
            "output": student_output,
            "score": final_score,
            "passed_tests": public_passed,
            "total_tests": public_total,
            "public_status": public_status,
            "public_score": public_score,
            "public_passed_tests": public_passed,
            "public_total_tests": public_total,
            "public_output": public_output,
            "hidden_status": "NOT_RUN",
            "hidden_score": 0,
            "hidden_passed_tests": 0,
            "hidden_total_tests": 0,
            "hidden_output": hidden_result["output"],
            "waveform_created": waveform_created
        }

    # 2. Если скрытый testbench не задан, работаем как раньше.
    if not hidden_testbench:
        hidden_result = {
            "status": "NOT_CONFIGURED",
            "output": "Скрытые тесты для этой лабораторной работы не заданы.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        }

        final_passed = public_passed
        final_total = public_total

        if final_total > 0:
            final_score = round((final_passed / final_total) * 100)
        else:
            final_score = public_score

        if public_status == "PASSED":
            final_status = "PASSED"
        elif public_passed > 0:
            final_status = "PARTIAL"
        else:
            final_status = "FAILED"

        student_output = build_student_visible_hdl_output(
            public_result=public_result,
            hidden_result=hidden_result,
            final_score=final_score,
            show_hidden_details=False
        )

        return {
            "status": final_status,
            "output": student_output,
            "score": final_score,
            "passed_tests": final_passed,
            "total_tests": final_total,
            "public_status": public_status,
            "public_score": public_score,
            "public_passed_tests": public_passed,
            "public_total_tests": public_total,
            "public_output": public_output,
            "hidden_status": "NOT_CONFIGURED",
            "hidden_score": 0,
            "hidden_passed_tests": 0,
            "hidden_total_tests": 0,
            "hidden_output": hidden_result["output"],
            "waveform_created": waveform_created
        }

    # 3. Запускаем скрытые тесты.
    hidden_status, hidden_output, hidden_score, hidden_passed, hidden_total, hidden_waveform_created = run_hdl_check(
        solution_path,
        hidden_testbench,
        None
    )

    hidden_result = {
        "status": hidden_status,
        "output": hidden_output,
        "score": hidden_score,
        "passed_tests": hidden_passed,
        "total_tests": hidden_total
    }

    # 4. Считаем итоговый результат по всем тестам.
    final_passed = public_passed + hidden_passed
    final_total = public_total + hidden_total

    if final_total > 0:
        final_score = round((final_passed / final_total) * 100)
    else:
        final_score = 0

    if hidden_status in critical_statuses:
        final_status = hidden_status
    elif final_total > 0 and final_passed == final_total:
        final_status = "PASSED"
    elif final_passed > 0:
        final_status = "PARTIAL"
    else:
        final_status = "FAILED"

    student_output = build_student_visible_hdl_output(
        public_result=public_result,
        hidden_result=hidden_result,
        final_score=final_score,
        show_hidden_details=show_hidden_details
    )

    return {
        "status": final_status,
        "output": student_output,
        "score": final_score,
        "passed_tests": final_passed,
        "total_tests": final_total,
        "public_status": public_status,
        "public_score": public_score,
        "public_passed_tests": public_passed,
        "public_total_tests": public_total,
        "public_output": public_output,
        "hidden_status": hidden_status,
        "hidden_score": hidden_score,
        "hidden_passed_tests": hidden_passed,
        "hidden_total_tests": hidden_total,
        "hidden_output": hidden_output,
        "waveform_created": waveform_created
    }


def add_default_check_fields(result):
    result.setdefault("public_status", "")
    result.setdefault("public_score", 0)
    result.setdefault("public_passed_tests", 0)
    result.setdefault("public_total_tests", 0)
    result.setdefault("public_output", "")

    result.setdefault("hidden_status", "")
    result.setdefault("hidden_score", 0)
    result.setdefault("hidden_passed_tests", 0)
    result.setdefault("hidden_total_tests", 0)
    result.setdefault("hidden_output", "")

    result.setdefault("waveform_created", False)

    return result

# Функція для запуску перевірки рішення студента на основі типу перевірки, визначеного в лабораторній роботі, 
# та повернення результату перевірки у стандартному форматі, щоб забезпечити єдиний формат результатів перевірки 
# для всіх типів лабораторних робіт та полегшити формування адаптивного навчального плану на основі результатів перевірки.
def run_solution_check(solution_path, lab, waveform_save_path=None):

    checker_type = lab["checker_type"] or "hdl_testbench"

    if checker_type == "hdl_testbench":
        return add_default_check_fields(
            run_hdl_public_hidden_check(
                solution_path=solution_path,
                lab=lab,
                waveform_save_path=waveform_save_path
            )
        )

    if checker_type == "python_unit_tests":
        return add_default_check_fields(
            run_python_unit_tests_check(solution_path, lab)
        )

    if checker_type == "sql_query":
        return add_default_check_fields({
            "status": "SYSTEM_ERROR",
            "output": "Проверка SQL-заданий пока не реализована.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        })

    if checker_type == "cpp_tests":
        return add_default_check_fields({
            "status": "SYSTEM_ERROR",
            "output": "Проверка C++-заданий пока не реализована.",
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0
        })

    return add_default_check_fields({
        "status": "SYSTEM_ERROR",
        "output": f"Неизвестный тип проверки: {checker_type}",
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0
    })


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

def normalize_lab_topic_for_analytics(topic, title=""):
    topic = str(topic or "").strip().lower()
    title = str(title or "").strip().lower()

    text = topic + " " + title

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


def get_topic_display_name(topic):
    names = {
        "mux": "Мультиплексор",
        "adder": "Сумматор",
        "counter": "Счётчик",
        "register": "Регистр",
        "fsm": "FSM",
        "general": "Общая тема"
    }

    return names.get(topic, topic)


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


    return {
        "topic": topic,
        "concepts": concepts,
        "error_type": submission["error_type"],
        "error_title": submission["error_title"],
        "hint_level": hint_level,
        "hint_text": hint_text,
        "questions": questions,
        "repeat_topics": repeat_topics,
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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Введите логин и пароль.")
            return redirect(url_for("login"))

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if user and verify_password(user["password"], password):
            if user["status"] != "active":
                conn.close()

                if user["status"] == "pending":
                    flash("Ваша учетная запись ожидает подтверждения администратором.")
                elif user["status"] == "blocked":
                    flash("Ваша учетная запись заблокирована.")
                else:
                    flash("Вход временно недоступен.")

                return redirect(url_for("login"))

            # Если пользователь вошёл со старым открытым паролем,
            # сразу заменяем его на безопасный хеш.
            if not password_is_hashed(user["password"]):
                conn.execute(
                    """
                    UPDATE users
                    SET password = ?
                    WHERE id = ?
                    """,
                    (
                        hash_password(password),
                        user["id"]
                    )
                )

                conn.commit()

            session["username"] = user["username"]
            session["role"] = user["role"]

            load_user_ui_settings_to_session(user)

            needs_setup = int(session.get("first_login_completed", 0) or 0) == 0

            if needs_setup:
                redirect_url = url_for("setup_appearance")
            else:
                redirect_url = get_default_redirect_for_role(user["role"])

            conn.close()

            return redirect(redirect_url)

        conn.close()
        flash("Неверный логин или пароль.")

    return render_template("auth/login.html")


# Роут для реєстрації, який дозволяє новим користувачам створювати облікові записи з роллю студента або викладача, але з початковим статусом "pending", що вимагає підтвердження адміністратора перед активацією облікового запису.
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
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
        
        password_ok, password_error = validate_password_strength(password, username)

        if not password_ok:
            flash(password_error)
            return redirect(url_for("register"))

        if role == "student" and not student_group:
            flash("Для студента нужно указать группу.")
            return redirect(url_for("register"))

        if role == "teacher":
            student_group = ""

        password_hash = hash_password(password)
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
                    password_hash,
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

        load_user_ui_settings_to_session(user)

        needs_setup = int(session.get("first_login_completed", 0) or 0) == 0

        if needs_setup:
            redirect_url = url_for("setup_appearance")
        else:
            redirect_url = get_default_redirect_for_role(user["role"])

        conn.close()

        return redirect(redirect_url)

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


# ============================================================
# Настройки внешнего вида пользователя
# ============================================================

APPEARANCE_THEMES = ["light", "dark", "system"]
APPEARANCE_PALETTES = ["pastel", "indigo", "burgundy", "green"]
APPEARANCE_FONT_SIZES = ["small", "normal", "large"]
APPEARANCE_DENSITIES = ["comfortable", "compact"]


@app.route("/setup/appearance", methods=["GET", "POST"])
@login_required
def setup_appearance():
    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (session["username"],)
    ).fetchone()

    if not user:
        conn.close()
        session.clear()
        flash("Пользователь не найден. Выполните вход заново.")
        return redirect(url_for("login"))

    first_login_completed = int(
        get_row_value(user, "first_login_completed", 0) or 0
    )

    if request.method == "GET" and first_login_completed == 1:
        conn.close()
        return redirect(get_default_redirect_for_role(session.get("role")))

    if request.method == "POST":
        theme = normalize_user_ui_value(
            request.form.get("theme"),
            "light",
            APPEARANCE_THEMES
        )

        palette = normalize_user_ui_value(
            request.form.get("palette"),
            "pastel",
            APPEARANCE_PALETTES
        )

        font_size = normalize_user_ui_value(
            request.form.get("font_size"),
            "normal",
            ["normal", "large"]
        )

        ui_density = normalize_user_ui_value(
            request.form.get("ui_density"),
            "comfortable",
            APPEARANCE_DENSITIES
        )

        show_beginner_tips = 1 if request.form.get("show_beginner_tips") == "1" else 0

        conn.execute(
            """
            UPDATE users
            SET theme = ?,
                palette = ?,
                font_size = ?,
                ui_density = ?,
                show_beginner_tips = ?,
                first_login_completed = 1
            WHERE username = ?
            """,
            (
                theme,
                palette,
                font_size,
                ui_density,
                show_beginner_tips,
                session["username"]
            )
        )

        conn.commit()

        updated_user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (session["username"],)
        ).fetchone()

        load_user_ui_settings_to_session(updated_user)

        redirect_url = get_default_redirect_for_role(session.get("role"))

        conn.close()

        flash("Первичная настройка завершена.")
        return redirect(redirect_url)

    settings = {
        "theme": normalize_user_ui_value(
            get_row_value(user, "theme", "light"),
            "light",
            APPEARANCE_THEMES
        ),
        "palette": normalize_user_ui_value(
            get_row_value(user, "palette", "pastel"),
            "pastel",
            APPEARANCE_PALETTES
        ),
        "font_size": normalize_user_ui_value(
            get_row_value(user, "font_size", "normal"),
            "normal",
            ["normal", "large"]
        ),
        "ui_density": normalize_user_ui_value(
            get_row_value(user, "ui_density", "comfortable"),
            "comfortable",
            APPEARANCE_DENSITIES
        ),
        "show_beginner_tips": int(
            get_row_value(user, "show_beginner_tips", 1) or 0
        )
    }

    conn.close()

    return render_template(
        "setup/appearance.html",
        settings=settings
    )


@app.route("/settings/appearance", methods=["GET", "POST"])
@login_required
def appearance_settings():
    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (session["username"],)
    ).fetchone()

    if not user:
        conn.close()
        session.clear()
        flash("Пользователь не найден. Выполните вход заново.")
        return redirect(url_for("login"))

    if request.method == "POST":
        theme = normalize_user_ui_value(
            request.form.get("theme"),
            "light",
            APPEARANCE_THEMES
        )

        palette = normalize_user_ui_value(
            request.form.get("palette"),
            "pastel",
            APPEARANCE_PALETTES
        )

        font_size = normalize_user_ui_value(
            request.form.get("font_size"),
            "normal",
            APPEARANCE_FONT_SIZES
        )

        ui_density = normalize_user_ui_value(
            request.form.get("ui_density"),
            "comfortable",
            APPEARANCE_DENSITIES
        )

        conn.execute(
            """
            UPDATE users
            SET theme = ?,
                palette = ?,
                font_size = ?,
                ui_density = ?,
                first_login_completed = 1
            WHERE username = ?
            """,
            (
                theme,
                palette,
                font_size,
                ui_density,
                session["username"]
            )
        )

        conn.commit()

        updated_user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (session["username"],)
        ).fetchone()

        load_user_ui_settings_to_session(updated_user)

        conn.close()

        flash("Настройки внешнего вида сохранены.")
        return redirect(url_for("appearance_settings"))

    settings = {
        "theme": normalize_user_ui_value(
            get_row_value(user, "theme", "light"),
            "light",
            APPEARANCE_THEMES
        ),
        "palette": normalize_user_ui_value(
            get_row_value(user, "palette", "pastel"),
            "pastel",
            APPEARANCE_PALETTES
        ),
        "font_size": normalize_user_ui_value(
            get_row_value(user, "font_size", "normal"),
            "normal",
            APPEARANCE_FONT_SIZES
        ),
        "ui_density": normalize_user_ui_value(
            get_row_value(user, "ui_density", "comfortable"),
            "comfortable",
            APPEARANCE_DENSITIES
        )
    }

    conn.close()

    return render_template(
        "settings/appearance.html",
        settings=settings
    )


@app.route("/settings/appearance/toggle-theme", methods=["POST"])
@login_required
def appearance_toggle_theme():
    current_theme = session.get("theme") or "light"

    if current_theme == "dark":
        next_theme = "light"
    else:
        next_theme = "dark"

    conn = get_db()

    conn.execute(
        """
        UPDATE users
        SET theme = ?
        WHERE username = ?
        """,
        (
            next_theme,
            session["username"]
        )
    )

    conn.commit()

    updated_user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (session["username"],)
    ).fetchone()

    load_user_ui_settings_to_session(updated_user)

    conn.close()

    return redirect(request.referrer or url_for("index"))


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

    labs_rows = conn.execute(
        """
        SELECT
            labs.*,

            COUNT(submissions.id) AS attempts_count,
            COALESCE(MAX(submissions.score), 0) AS best_score,
            MAX(CASE WHEN submissions.status = 'PASSED' THEN 1 ELSE 0 END) AS is_passed,
            MAX(submissions.created_at) AS last_attempt_at,

            (
                SELECT s2.status
                FROM submissions AS s2
                WHERE s2.lab_id = labs.id
                  AND s2.username = ?
                ORDER BY s2.created_at DESC
                LIMIT 1
            ) AS last_status

        FROM labs
        LEFT JOIN submissions
            ON submissions.lab_id = labs.id
           AND submissions.username = ?
        GROUP BY labs.id
        ORDER BY labs.id DESC
        """,
        (
            username,
            username
        )
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
        LIMIT 6
        """,
        (username,)
    ).fetchall()

    stats_row = conn.execute(
        """
        SELECT
            ROUND(AVG(score), 1) AS average_score,
            COUNT(DISTINCT CASE WHEN status = 'PASSED' THEN lab_id END) AS completed_labs,
            COUNT(*) AS total_attempts
        FROM submissions
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    conn.close()

    labs = []

    for lab_row in labs_rows:
        lab = dict(lab_row)

        attempts_count = int(lab.get("attempts_count") or 0)
        best_score = int(lab.get("best_score") or 0)
        is_passed = int(lab.get("is_passed") or 0) == 1

        if is_passed:
            status_code = "passed"
            status_label = "Сдано"
            progress_percent = 100
        elif attempts_count > 0:
            status_code = "in_progress"
            status_label = "В работе"
            progress_percent = max(0, min(best_score, 100))
        else:
            status_code = "not_started"
            status_label = "Не начато"
            progress_percent = 0

        lab["attempts_count"] = attempts_count
        lab["best_score"] = best_score
        lab["status_code"] = status_code
        lab["status_label"] = status_label
        lab["progress_percent"] = progress_percent

        labs.append(lab)

    active_lab = None

    in_progress_labs = [
        lab for lab in labs
        if lab["status_code"] == "in_progress"
    ]

    if in_progress_labs:
        active_lab = sorted(
            in_progress_labs,
            key=lambda item: item.get("last_attempt_at") or "",
            reverse=True
        )[0]
    else:
        not_started_labs = [
            lab for lab in labs
            if lab["status_code"] == "not_started"
        ]

        if not_started_labs:
            active_lab = not_started_labs[0]
        elif labs:
            active_lab = labs[0]

    latest_submission = my_submissions[0] if my_submissions else None

    dashboard_stats = {
        "average_score": stats_row["average_score"] if stats_row and stats_row["average_score"] is not None else 0,
        "completed_labs": stats_row["completed_labs"] if stats_row and stats_row["completed_labs"] is not None else 0,
        "total_attempts": stats_row["total_attempts"] if stats_row and stats_row["total_attempts"] is not None else 0,
        "latest_score": latest_submission["score"] if latest_submission else "—"
    }

    return render_template(
        "common/index.html",
        is_landing=False,
        labs=labs,
        my_submissions=my_submissions,
        student=student,
        dashboard_stats=dashboard_stats,
        active_lab=active_lab
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

    attempts_info = None

    if session.get("role") == "student":
        attempts_info = get_attempts_info(
            conn=conn,
            lab=lab,
            username=session["username"]
        )

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

        attempts_count = attempts_info["used_attempts"] if attempts_info else 0

    conn.close()

    return render_template(
        "student/lab_detail.html",
        lab=lab,
        submissions=submissions,
        student_results=student_results,
        attempts_count=attempts_count,
        attempts_info=attempts_info
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
        """
        SELECT *
        FROM submissions
        WHERE id = ?
        """,
        (submission_id,)
    ).fetchone()

    if not submission:
        conn.close()
        abort(404)

    current_role = session.get("role")
    current_username = session.get("username")

    if current_role == "admin":
        allow = True

    elif current_role == "teacher":
        allow = teacher_can_access_submission(
            conn=conn,
            teacher_username=current_username,
            submission_id=submission_id
        )

    elif submission["username"] == current_username:
        allow = True

    else:
        allow = False

    conn.close()

    if not allow:
        abort(403)

    if submission["file_deleted"]:
        flash("Файл этой попытки недоступен.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    file_path = os.path.join(UPLOAD_DIR, submission["filename"])

    if not os.path.exists(file_path):
        flash("Файл отсутствует в папке загрузок.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if current_role == "student" and submission["file_hidden_for_student"]:
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
        """
        SELECT *
        FROM submissions
        WHERE id = ?
        """,
        (submission_id,)
    ).fetchone()

    if not submission:
        conn.close()
        abort(404)

    current_role = session.get("role")
    current_username = session.get("username")

    if current_role == "admin":
        allow = True

    elif current_role == "teacher":
        allow = teacher_can_access_submission(
            conn=conn,
            teacher_username=current_username,
            submission_id=submission_id
        )

    elif submission["username"] == current_username:
        allow = True

    else:
        allow = False

    conn.close()

    if not allow:
        abort(403)

    if not submission["waveform_filename"]:
        flash("Для этой попытки временная диаграмма недоступна.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    waveform_path = os.path.join(WAVEFORM_DIR, submission["waveform_filename"])

    if not os.path.exists(waveform_path):
        flash("Файл временной диаграммы отсутствует на сервере.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    return send_from_directory(
        WAVEFORM_DIR,
        submission["waveform_filename"],
        as_attachment=True
    )

# ============================================================
# Карта компетенций студента
# ============================================================

def get_competency_catalog():
    return {
        "combinational_logic": {
            "title": "Комбинационная логика",
            "description": "Мультиплексоры, сумматоры, логические выражения, assign и always @(*)."
        },
        "testbench_work": {
            "title": "Работа с testbench",
            "description": "Понимание проверочного сценария, совпадение имени модуля и портов."
        },
        "sequential_logic": {
            "title": "Последовательностная логика",
            "description": "Регистры, счётчики, изменение состояния по тактовому сигналу."
        },
        "fsm": {
            "title": "FSM",
            "description": "Конечные автоматы, состояния, переходы и обработка входных условий."
        },
        "reset_clock": {
            "title": "Reset/clock",
            "description": "Корректная работа со сбросом, clock, posedge/negedge и начальными состояниями."
        },
        "hdl_syntax_structure": {
            "title": "Структура HDL-модуля",
            "description": "Синтаксис Verilog, module/endmodule, input/output, wire/reg."
        }
    }


def normalize_topic_for_competencies(topic, title=""):
    topic = str(topic or "").strip().lower()
    title = str(title or "").strip().lower()

    text = topic + " " + title

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


def get_competencies_for_topic(topic):
    topic = normalize_topic_for_competencies(topic)

    mapping = {
        "mux": [
            "combinational_logic",
            "testbench_work"
        ],
        "adder": [
            "combinational_logic",
            "testbench_work"
        ],
        "counter": [
            "sequential_logic",
            "reset_clock",
            "testbench_work"
        ],
        "register": [
            "sequential_logic",
            "reset_clock",
            "testbench_work"
        ],
        "fsm": [
            "fsm",
            "sequential_logic",
            "reset_clock",
            "testbench_work"
        ],
        "general": [
            "hdl_syntax_structure",
            "testbench_work"
        ]
    }

    return mapping.get(topic, mapping["general"])


def get_competencies_for_error(error_type):
    error_type = str(error_type or "")

    mapping = {
        "MODULE_NAME_MISMATCH": [
            "testbench_work",
            "hdl_syntax_structure"
        ],
        "PORT_MISMATCH": [
            "testbench_work",
            "hdl_syntax_structure"
        ],
        "COMPILE_ERROR": [
            "hdl_syntax_structure"
        ],
        "CONTROL_SIGNAL_ERROR": [
            "combinational_logic"
        ],
        "INCOMPLETE_CONDITION": [
            "combinational_logic",
            "fsm"
        ],
        "WRONG_COMBINATIONAL_LOGIC": [
            "combinational_logic"
        ],
        "RESET_CLOCK_ERROR": [
            "reset_clock",
            "sequential_logic"
        ],
        "BOUNDARY_TEST_FAILED": [
            "combinational_logic",
            "sequential_logic"
        ],
        "HIDDEN_TEST_FAILED": [
            "testbench_work",
            "combinational_logic"
        ],
        "FUNCTIONAL_ERROR": [
            "combinational_logic",
            "testbench_work"
        ]
    }

    return mapping.get(error_type, ["testbench_work"])


def get_competency_level_title(score):
    if score is None:
        return "Нет данных"

    if score >= 85:
        return "Высокий уровень"

    if score >= 70:
        return "Хороший уровень"

    if score >= 50:
        return "Базовый уровень"

    return "Проблемная зона"


def get_competency_badge_class(score):
    if score is None:
        return "bg-secondary"

    if score >= 85:
        return "bg-success"

    if score >= 70:
        return "bg-primary"

    if score >= 50:
        return "bg-warning text-dark"

    return "bg-danger"


def build_competency_recommendation(competency_id, score, frequent_errors):
    if score is None:
        return "Пока недостаточно данных. Выполните больше лабораторных работ по этой теме."

    if score >= 85:
        return "Тема освоена хорошо. Можно переходить к более сложным заданиям."

    if competency_id == "combinational_logic":
        return "Повторите таблицы истинности, условный оператор, assign и полное описание всех входных комбинаций."

    if competency_id == "testbench_work":
        return "Проверьте соответствие имени модуля, портов и формата вывода требованиям testbench."

    if competency_id == "sequential_logic":
        return "Повторите работу регистров, счётчиков и изменение значений по фронту тактового сигнала."

    if competency_id == "fsm":
        return "Повторите описание состояний, переходов, next_state и обработку всех возможных входных условий."

    if competency_id == "reset_clock":
        return "Повторите синтаксис always-блоков с posedge/negedge и корректную обработку reset/rst."

    if competency_id == "hdl_syntax_structure":
        return "Повторите структуру Verilog-модуля: module, input/output, wire/reg, assign, always, endmodule."

    return "Изучите ошибки в последних попытках и повторите соответствующий раздел."


def calculate_student_competency_map(username):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            submissions.id,
            submissions.lab_id,
            submissions.username,
            submissions.status,
            submissions.score,
            submissions.attempt_number,
            submissions.error_type,
            submissions.error_title,
            submissions.created_at,

            labs.title AS lab_title,
            labs.description AS lab_description,
            labs.topic AS lab_topic,
            labs.discipline AS lab_discipline
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        WHERE submissions.username = ?
        ORDER BY submissions.lab_id ASC, submissions.attempt_number ASC, submissions.id ASC
        """,
        (username,)
    ).fetchall()

    conn.close()

    catalog = get_competency_catalog()

    competency_data = {}

    for competency_id, item in catalog.items():
        competency_data[competency_id] = {
            "id": competency_id,
            "title": item["title"],
            "description": item["description"],
            "values": [],
            "penalty": 0,
            "errors": {},
            "labs": []
        }

    # Группируем попытки по лабораторной работе.
    lab_attempts = {}

    for row in rows:
        row_dict = dict(row)
        lab_id = row_dict["lab_id"]

        if lab_id not in lab_attempts:
            lab_attempts[lab_id] = []

        lab_attempts[lab_id].append(row_dict)

    for lab_id, attempts in lab_attempts.items():
        attempts.sort(
            key=lambda item: (
                int(item["attempt_number"] or 1),
                int(item["id"] or 0)
            )
        )

        first_attempt = attempts[0]
        last_attempt = attempts[-1]

        best_score = max(int(item["score"] or 0) for item in attempts)
        attempts_count = len(attempts)

        topic = normalize_topic_for_competencies(
            first_attempt["lab_topic"],
            first_attempt["lab_title"]
        )

        topic_competencies = get_competencies_for_topic(topic)

        # Чем больше попыток, тем ниже уверенность в освоении темы.
        attempt_penalty = min(15, max(0, attempts_count - 1) * 4)

        base_value = max(0, best_score - attempt_penalty)

        for competency_id in topic_competencies:
            competency_data[competency_id]["values"].append(base_value)
            competency_data[competency_id]["labs"].append({
                "lab_id": lab_id,
                "lab_title": first_attempt["lab_title"],
                "topic": topic,
                "best_score": best_score,
                "attempts_count": attempts_count,
                "last_status": last_attempt["status"]
            })

        # Ошибки дополнительно снижают связанные компетенции.
        for attempt in attempts:
            error_type = attempt["error_type"] or ""

            if not error_type or error_type == "NO_ERROR":
                continue

            error_title = attempt["error_title"] or error_type
            related_competencies = get_competencies_for_error(error_type)

            for competency_id in related_competencies:
                if competency_id not in competency_data:
                    continue

                # Если компетенция ещё не получила значение от темы,
                # добавляем слабое evidence-значение, чтобы ошибка тоже учитывалась.
                if not competency_data[competency_id]["values"]:
                    competency_data[competency_id]["values"].append(50)

                competency_data[competency_id]["penalty"] += 6

                if error_title not in competency_data[competency_id]["errors"]:
                    competency_data[competency_id]["errors"][error_title] = 0

                competency_data[competency_id]["errors"][error_title] += 1

    competency_rows = []

    for competency_id, item in competency_data.items():
        values = item["values"]

        if values:
            average_value = sum(values) / len(values)
            score = round(max(0, min(100, average_value - item["penalty"])))
        else:
            score = None

        errors_sorted = sorted(
            item["errors"].items(),
            key=lambda pair: pair[1],
            reverse=True
        )

        frequent_errors = [
            {
                "title": title,
                "count": count
            }
            for title, count in errors_sorted[:3]
        ]

        competency_rows.append({
            "id": competency_id,
            "title": item["title"],
            "description": item["description"],
            "score": score,
            "level_title": get_competency_level_title(score),
            "badge_class": get_competency_badge_class(score),
            "recommendation": build_competency_recommendation(
                competency_id,
                score,
                frequent_errors
            ),
            "frequent_errors": frequent_errors,
            "labs": item["labs"][:5]
        })

    # Сначала показываем проблемные зоны, потом сильные.
    competency_rows.sort(
        key=lambda item: 999 if item["score"] is None else item["score"]
    )

    weak_competencies = [
        item for item in competency_rows
        if item["score"] is not None and item["score"] < 70
    ]

    strong_competencies = [
        item for item in competency_rows
        if item["score"] is not None and item["score"] >= 85
    ]

    completed_labs_count = len(lab_attempts)
    total_attempts_count = len(rows)

    if competency_rows:
        scored = [
            item["score"]
            for item in competency_rows
            if item["score"] is not None
        ]

        average_competency_score = round(sum(scored) / len(scored), 1) if scored else None
    else:
        average_competency_score = None

    return {
        "competencies": competency_rows,
        "weak_competencies": weak_competencies,
        "strong_competencies": strong_competencies,
        "completed_labs_count": completed_labs_count,
        "total_attempts_count": total_attempts_count,
        "average_competency_score": average_competency_score
    }


# ============================================================
# AI-траектория обучения с открытым интернет-поиском
# ============================================================

def get_openai_client():
    if not OPENAI_API_KEY or OpenAI is None:
        return None

    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        return None


def make_learning_cache_key(username, lab_id, error_type, topic_key):
    raw = f"{username}|{lab_id}|{error_type}|{topic_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_learning_topic_from_error(error_type, lab_topic="", lab_title=""):
    error_type = str(error_type or "")
    lab_topic = str(lab_topic or "").lower()
    lab_title = str(lab_title or "").lower()

    if error_type in ["RESET_CLOCK_ERROR"]:
        return "reset clock sequential logic Verilog FPGA"

    if error_type in ["CONTROL_SIGNAL_ERROR", "WRONG_COMBINATIONAL_LOGIC", "BOUNDARY_TEST_FAILED"]:
        return "combinational logic Verilog mux adder FPGA"

    if error_type in ["MODULE_NAME_MISMATCH", "PORT_MISMATCH", "COMPILE_ERROR"]:
        return "Verilog module ports testbench beginner"

    if error_type in ["INCOMPLETE_CONDITION", "CASE_WITHOUT_DEFAULT"]:
        return "Verilog case default if else latch combinational logic"

    if error_type in ["FSM_STATE_ERROR", "FSM_TRANSITION_ERROR"]:
        return "Verilog finite state machine FSM states transitions"

    if error_type in ["DELAY_IN_DESIGN", "INITIAL_IN_DESIGN", "SYNTHESIS_ERROR"]:
        return "synthesizable Verilog FPGA Yosys synthesis"

    text = lab_topic + " " + lab_title

    if "mux" in text or "мультиплексор" in text:
        return "Verilog multiplexer combinational logic"

    if "adder" in text or "сумматор" in text:
        return "Verilog adder carry combinational logic"

    if "counter" in text or "счетчик" in text or "счётчик" in text:
        return "Verilog counter reset clock sequential logic"

    if "register" in text or "регистр" in text:
        return "Verilog register reset clock sequential logic"

    if "fsm" in text or "автомат" in text or "state" in text:
        return "Verilog FSM finite state machine"

    return "Verilog FPGA beginner HDL testbench"


def get_recent_student_error_context(username, current_lab_id=None):
    conn = get_db()

    params = [username]

    sql = """
        SELECT
            submissions.id,
            submissions.lab_id,
            submissions.status,
            submissions.score,
            submissions.attempt_number,
            submissions.error_type,
            submissions.error_title,
            submissions.error_details,
            submissions.recommendation,
            submissions.created_at,

            labs.title AS lab_title,
            labs.topic AS lab_topic,
            labs.difficulty AS lab_difficulty,
            labs.discipline AS lab_discipline
        FROM submissions
        JOIN labs ON labs.id = submissions.lab_id
        WHERE submissions.username = ?
        ORDER BY submissions.created_at DESC, submissions.id DESC
        LIMIT 30
    """

    rows = conn.execute(sql, params).fetchall()

    current_lab = None

    if current_lab_id:
        current_lab = conn.execute(
            """
            SELECT id, title, topic, difficulty, discipline
            FROM labs
            WHERE id = ?
            """,
            (current_lab_id,)
        ).fetchone()

    conn.close()

    attempts = [dict(row) for row in rows]

    error_counter = {}

    for row in attempts:
        error_type = row.get("error_type") or ""

        if not error_type or error_type == "NO_ERROR":
            continue

        if error_type not in error_counter:
            error_counter[error_type] = {
                "error_type": error_type,
                "error_title": row.get("error_title") or error_type,
                "count": 0,
                "last_lab_title": row.get("lab_title") or "",
                "last_recommendation": row.get("recommendation") or "",
                "last_error_details": row.get("error_details") or ""
            }

        error_counter[error_type]["count"] += 1

    repeated_errors = sorted(
        error_counter.values(),
        key=lambda item: item["count"],
        reverse=True
    )

    main_error = repeated_errors[0] if repeated_errors else None

    if main_error:
        error_type = main_error["error_type"]
        error_title = main_error["error_title"]
    else:
        error_type = ""
        error_title = ""

    if current_lab:
        topic_key = get_learning_topic_from_error(
            error_type=error_type,
            lab_topic=current_lab["topic"],
            lab_title=current_lab["title"]
        )
    elif attempts:
        topic_key = get_learning_topic_from_error(
            error_type=error_type,
            lab_topic=attempts[0].get("lab_topic"),
            lab_title=attempts[0].get("lab_title")
        )
    else:
        topic_key = "Verilog FPGA beginner HDL"

    context = {
        "username": username,
        "current_lab_id": current_lab_id or 0,
        "current_lab": dict(current_lab) if current_lab else None,
        "main_error": main_error,
        "repeated_errors": repeated_errors[:5],
        "topic_key": topic_key,
        "recent_attempts": [
            {
                "lab_title": row.get("lab_title"),
                "status": row.get("status"),
                "score": row.get("score"),
                "attempt_number": row.get("attempt_number"),
                "error_type": row.get("error_type"),
                "error_title": row.get("error_title")
            }
            for row in attempts[:10]
        ]
    }

    return context

# ============================================================
# Интернет-рекомендации / YouTube / OpenAI
# ============================================================

def search_youtube_videos(query, max_results=3):
    if not YOUTUBE_API_KEY:
        return []

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": YOUTUBE_API_KEY,
                "relevanceLanguage": "en"
            },
            timeout=10
        )

        if response.status_code != 200:
            return []

        data = response.json()
        videos = []

        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})

            if not video_id:
                continue

            videos.append({
                "title": snippet.get("title", "Видео"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description": snippet.get("description", ""),
                "source": "YouTube"
            })

        return videos

    except Exception:
        return []
    

def extract_json_from_text(text):
    text = str(text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None


def get_direct_learning_resources(topic_slug):
    catalog = {
        "combinational_logic": {
            "lectures": [
                {
                    "title": "MIT OCW: Introduction to Verilog — Combinational Logic",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекции MIT по цифровым системам, включая комбинационную логику и Verilog.",
                    "why_useful": "Полезно для понимания mux, assign, if/else, case и таблиц истинности."
                }
            ],
            "articles": [
                {
                    "title": "Nandland: Learn Verilog",
                    "url": "https://nandland.com/learn-verilog/",
                    "description": "Подборка уроков по Verilog для начинающих.",
                    "why_useful": "Подходит для повторения assign, always-блоков и структуры Verilog-модуля."
                },
                {
                    "title": "Nandland: Verilog Tutorials",
                    "url": "https://nandland.com/category/verilog-tutorials-and-examples/verilog-tutorials/",
                    "description": "Раздел с Verilog-туториалами и примерами.",
                    "why_useful": "Можно быстро повторить базовый синтаксис и стиль описания схем."
                },
                {
                    "title": "Project F: Verilog Library",
                    "url": "https://projectf.io/verilog-lib/",
                    "description": "Практические Verilog-модули, документация и testbench-примеры.",
                    "why_useful": "Помогает увидеть, как небольшие цифровые блоки оформляются в реальном Verilog-коде."
                }
            ],
            "practice": [
                {
                    "title": "HDLBits: Problem Sets",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Практические задания по Verilog, включая комбинационную логику.",
                    "why_useful": "Можно закрепить mux, gates, adders, if/case и другие базовые схемы."
                }
            ],
            "videos": [
                {
                    "title": "Nandland YouTube: FPGA, Verilog and VHDL Tutorials",
                    "url": "https://www.youtube.com/@Nandland",
                    "description": "Канал с видеоуроками по FPGA, Verilog и VHDL.",
                    "why_useful": "Подходит для визуального объяснения базовых тем Verilog."
                },
                {
                    "title": "YouTube: Verilog Multiplexer Tutorial",
                    "url": "https://www.youtube.com/results?search_query=verilog+multiplexer+tutorial",
                    "description": "Подборка видео по мультиплексорам на Verilog.",
                    "why_useful": "Полезно при ошибках выбора управляющего сигнала sel."
                }
            ]
        },

        "sequential_logic": {
            "lectures": [
                {
                    "title": "MIT OCW: Sequential Building Blocks",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекции MIT по последовательностной логике, регистрам и простым последовательностным схемам.",
                    "why_useful": "Помогает понять, почему схема зависит от clock и предыдущего состояния."
                }
            ],
            "articles": [
                {
                    "title": "Nandland: Learn Verilog",
                    "url": "https://nandland.com/learn-verilog/",
                    "description": "Уроки по Verilog, включая always-блоки и базовую структуру кода.",
                    "why_useful": "Подходит для повторения always @(posedge clk) и различия между = и <=."
                },
                {
                    "title": "Project F: FPGA Tutorials",
                    "url": "https://projectf.io/tutorials/",
                    "description": "Практические FPGA-туториалы.",
                    "why_useful": "Помогает увидеть практическую FPGA-разработку на примерах."
                }
            ],
            "practice": [
                {
                    "title": "HDLBits: Sequential Logic Practice",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Разделы HDLBits с заданиями по последовательностной логике.",
                    "why_useful": "Можно потренировать регистры, счётчики, always-блоки и FSM."
                }
            ],
            "videos": [
                {
                    "title": "YouTube: Verilog Sequential Logic Register Counter",
                    "url": "https://www.youtube.com/results?search_query=verilog+sequential+logic+register+counter",
                    "description": "Видео по регистрам, счётчикам и последовательностной логике.",
                    "why_useful": "Полезно при ошибках в counter/register-задачах."
                },
                {
                    "title": "Nandland YouTube",
                    "url": "https://www.youtube.com/@Nandland",
                    "description": "Видео по FPGA, Verilog и VHDL.",
                    "why_useful": "Хороший источник базовых FPGA-видеоуроков."
                }
            ]
        },

        "reset_clock": {
            "lectures": [
                {
                    "title": "MIT OCW: Sequential Circuits and Verilog",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекции по последовательностным схемам, clock, состояниям и синхронизации.",
                    "why_useful": "Полезно для понимания reset/clock и обновления состояния схемы."
                }
            ],
            "articles": [
                {
                    "title": "HDLBits: Always blocks — clocked",
                    "url": "https://hdlbits.01xz.net/wiki/Alwaysff",
                    "description": "Задание и объяснение clocked always-блоков.",
                    "why_useful": "Подходит для повторения always @(posedge clk)."
                },
                {
                    "title": "HDLBits: D flip-flop",
                    "url": "https://hdlbits.01xz.net/wiki/Dff",
                    "description": "Практика по D-триггерам.",
                    "why_useful": "Помогает понять основу регистров и обновления по clock."
                },
                {
                    "title": "Nandland: Learn Verilog",
                    "url": "https://nandland.com/learn-verilog/",
                    "description": "Уроки по Verilog и always-блокам.",
                    "why_useful": "Полезно для повторения синтаксиса sequential always-блоков."
                }
            ],
            "practice": [
                {
                    "title": "HDLBits: Sequential Logic",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Практика по триггерам, регистрам, счётчикам и FSM.",
                    "why_useful": "Помогает закрепить reset/clock через короткие задания."
                }
            ],
            "videos": [
                {
                    "title": "YouTube: Verilog reset clock posedge",
                    "url": "https://www.youtube.com/results?search_query=verilog+reset+clock+posedge",
                    "description": "Видео по reset, clock и posedge в Verilog.",
                    "why_useful": "Полезно при ошибках RESET_CLOCK_ERROR."
                }
            ]
        },

        "fsm": {
            "lectures": [
                {
                    "title": "MIT OCW: Finite-State Machines and Synchronization",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекция MIT по конечным автоматам и синхронизации.",
                    "why_useful": "Помогает понять state, next_state, переходы и синхронизацию."
                }
            ],
            "articles": [
                {
                    "title": "HDLBits: Finite State Machines",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Практические задания по FSM.",
                    "why_useful": "Можно потренировать автоматы Мили/Мура и переходы между состояниями."
                },
                {
                    "title": "Nandland: Learn Verilog",
                    "url": "https://nandland.com/learn-verilog/",
                    "description": "Verilog-уроки для закрепления always/case и структуры модулей.",
                    "why_useful": "Полезно для правильного оформления FSM-кода."
                }
            ],
            "practice": [
                {
                    "title": "HDLBits: Problem Sets",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Набор практических задач по Verilog, включая FSM.",
                    "why_useful": "Позволяет отработать описание состояний и переходов."
                }
            ],
            "videos": [
                {
                    "title": "YouTube: Verilog FSM Tutorial",
                    "url": "https://www.youtube.com/results?search_query=verilog+fsm+tutorial",
                    "description": "Видео по конечным автоматам на Verilog.",
                    "why_useful": "Полезно для понимания state/next_state и case по состояниям."
                }
            ]
        },

        "testbench_work": {
            "lectures": [
                {
                    "title": "MIT OCW: Introduction to Verilog",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекции MIT по Verilog и лабораторному FPGA-проектированию.",
                    "why_useful": "Помогает понять, как Verilog используется в лабораторных работах."
                }
            ],
            "articles": [
                {
                    "title": "HDLBits: Getting Started",
                    "url": "https://hdlbits.01xz.net/wiki/Step_one",
                    "description": "Начальная страница HDLBits с первым Verilog-заданием.",
                    "why_useful": "Полезно для понимания формата проверки и структуры решения."
                },
                {
                    "title": "Nandland: Learn Verilog",
                    "url": "https://nandland.com/learn-verilog/",
                    "description": "Базовые Verilog-уроки.",
                    "why_useful": "Помогает повторить module, input/output и синтаксис."
                }
            ],
            "practice": [
                {
                    "title": "HDLBits: Verilog Practice",
                    "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
                    "description": "Практические задания с автоматической проверкой.",
                    "why_useful": "Формат похож на твою систему: студент пишет Verilog и получает результат проверки."
                }
            ],
            "videos": [
                {
                    "title": "YouTube: Verilog testbench tutorial",
                    "url": "https://www.youtube.com/results?search_query=verilog+testbench+tutorial",
                    "description": "Видео по testbench в Verilog.",
                    "why_useful": "Полезно при ошибках имени модуля, портов и проверки."
                }
            ]
        },

        "synthesis": {
            "lectures": [
                {
                    "title": "MIT OCW: Digital Systems Laboratory Lecture Notes",
                    "url": "https://ocw.mit.edu/courses/6-111-introductory-digital-systems-laboratory-spring-2006/pages/lecture-notes/",
                    "description": "Лекции по цифровым системам, Verilog и FPGA-проектированию.",
                    "why_useful": "Даёт теоретическую базу для понимания FPGA-реализации."
                }
            ],
            "articles": [
                {
                    "title": "Yosys Documentation",
                    "url": "https://yosyshq.net/yosys/documentation.html",
                    "description": "Официальная документация Yosys.",
                    "why_useful": "Полезно для понимания этапа синтеза Verilog-кода."
                },
                {
                    "title": "Yosys GitHub",
                    "url": "https://github.com/YosysHQ/yosys",
                    "description": "Репозиторий Yosys.",
                    "why_useful": "Можно изучить возможности инструмента и примеры использования."
                },
                {
                    "title": "Project F: FPGA Tutorials",
                    "url": "https://projectf.io/tutorials/",
                    "description": "Практические FPGA-туториалы.",
                    "why_useful": "Помогает понять FPGA-разработку не только на уровне симуляции, но и реализации."
                }
            ],
            "practice": [
                {
                    "title": "Project F: Verilog Library",
                    "url": "https://projectf.io/verilog-lib/",
                    "description": "Практические Verilog-модули с документацией.",
                    "why_useful": "Полезно для анализа синтезируемых Verilog-конструкций."
                }
            ],
            "videos": [
                {
                    "title": "YouTube: Yosys Verilog synthesis",
                    "url": "https://www.youtube.com/results?search_query=yosys+verilog+synthesis",
                    "description": "Видео по синтезу Verilog через Yosys.",
                    "why_useful": "Полезно для понимания проверки синтезируемости."
                }
            ]
        }
    }

    return catalog.get(topic_slug, catalog["combinational_logic"])


def detect_direct_resource_topic(context):
    topic_key = str(context.get("topic_key") or "").lower()
    main_error = context.get("main_error") or {}
    error_type = str(main_error.get("error_type") or "")

    if error_type in ["RESET_CLOCK_ERROR"]:
        return "reset_clock"

    if error_type in ["FSM_STATE_ERROR", "FSM_TRANSITION_ERROR"]:
        return "fsm"

    if error_type in ["MODULE_NAME_MISMATCH", "PORT_MISMATCH", "COMPILE_ERROR"]:
        return "testbench_work"

    if error_type in ["DELAY_IN_DESIGN", "INITIAL_IN_DESIGN", "SYNTHESIS_ERROR"]:
        return "synthesis"

    if error_type in ["CONTROL_SIGNAL_ERROR", "WRONG_COMBINATIONAL_LOGIC", "BOUNDARY_TEST_FAILED", "INCOMPLETE_CONDITION", "HIDDEN_TEST_FAILED"]:
        return "combinational_logic"

    if "reset" in topic_key or "clock" in topic_key:
        return "reset_clock"

    if "fsm" in topic_key or "state" in topic_key:
        return "fsm"

    if "counter" in topic_key or "register" in topic_key or "sequential" in topic_key:
        return "sequential_logic"

    if "yosys" in topic_key or "synthesis" in topic_key:
        return "synthesis"

    if "testbench" in topic_key or "module" in topic_key or "port" in topic_key:
        return "testbench_work"

    return "combinational_logic"


def build_open_search_fallback_learning_path(context, reason=""):
    topic_key = context.get("topic_key", "Verilog FPGA beginner HDL")
    main_error = context.get("main_error") or {}

    error_type = main_error.get("error_type", "")
    error_title = main_error.get("error_title", error_type)

    query_base = topic_key

    if error_type:
        query_base = f"{topic_key} {error_type}"

    google_query = quote_plus(query_base)
    youtube_query = quote_plus(query_base + " tutorial")
    hdlbits_query = quote_plus(query_base + " site:hdlbits.01xz.net")
    nandland_query = quote_plus(query_base + " site:nandland.com")
    projectf_query = quote_plus(query_base + " site:projectf.io")

    if "reset" in query_base.lower() or "clock" in query_base.lower():
        topic_title = "Reset/clock и последовательностная логика"
        mini_theory = (
            "Ошибка связана с обновлением состояния схемы во времени. "
            "Проверьте always-блоки, posedge clk, обработку reset и использование неблокирующих присваиваний <=."
        )
        what_to_repeat = [
            "always @(posedge clk)",
            "синхронный и асинхронный reset",
            "неблокирующее присваивание <=",
            "регистры и счётчики"
        ]
        control_question = "Чем синхронный reset отличается от асинхронного reset?"
        next_topic = "Счётчики и FSM"

    elif "fsm" in query_base.lower() or "state" in query_base.lower():
        topic_title = "Конечные автоматы FSM"
        mini_theory = (
            "Ошибка связана с описанием состояний и переходов. "
            "Проверьте state, next_state, case по состояниям и обработку всех возможных входных условий."
        )
        what_to_repeat = [
            "state и next_state",
            "case по состояниям",
            "default-переход",
            "обработка всех входных условий"
        ]
        control_question = "Зачем в FSM нужна ветка default?"
        next_topic = "Управляющие автоматы повышенной сложности"

    elif "testbench" in query_base.lower() or "module" in query_base.lower() or "port" in query_base.lower():
        topic_title = "Работа с testbench и структурой Verilog-модуля"
        mini_theory = (
            "Ошибка может быть связана с тем, что testbench ожидает конкретное имя модуля, набор портов "
            "и корректное описание input/output. Даже правильная логика не пройдёт проверку, если интерфейс модуля не совпадает."
        )
        what_to_repeat = [
            "module и endmodule",
            "input/output",
            "совпадение имён портов",
            "анализ сообщения компилятора"
        ]
        control_question = "Что произойдёт, если имя модуля не совпадает с тем, которое ожидает testbench?"
        next_topic = "Отладка HDL-кода через waveform"

    elif "synthesis" in query_base.lower() or "yosys" in query_base.lower():
        topic_title = "Синтезируемость HDL-кода"
        mini_theory = (
            "Синтезируемость означает, что Verilog-код может быть преобразован в аппаратную схему. "
            "Некоторые конструкции допустимы в симуляции, но не подходят для FPGA-синтеза."
        )
        what_to_repeat = [
            "синтезируемый Verilog",
            "разница между testbench и design-кодом",
            "задержки #",
            "Yosys synthesis"
        ]
        control_question = "Почему задержка #10 допустима в testbench, но нежелательна в синтезируемом модуле?"
        next_topic = "Оптимизация HDL-кода"

    else:
        topic_title = "Комбинационная логика Verilog"
        mini_theory = (
            "Комбинационная логика описывает схему, выход которой зависит только от текущих входных сигналов. "
            "Для таких схем важно полностью описывать все возможные комбинации входов."
        )
        what_to_repeat = [
            "таблицы истинности",
            "assign и тернарный оператор",
            "if/else",
            "case/default",
            "мультиплексоры и сумматоры"
        ]
        control_question = "Почему в комбинационной логике важно описывать все ветки условий?"
        next_topic = "Последовательностная логика"

    if error_title:
        summary = (
            f"По вашей ошибке «{error_title}» сформирована бесплатная открытая траектория: "
            f"повторите тему «{topic_title}»."
        )
    else:
        summary = (
            f"Сформирована бесплатная открытая траектория по теме «{topic_title}»."
        )

    topic_slug = detect_direct_resource_topic(context)
    direct_resources = get_direct_learning_resources(topic_slug)

    lectures = direct_resources.get("lectures", [])
    articles = direct_resources.get("articles", [])
    practice = direct_resources.get("practice", [])
    videos = direct_resources.get("videos", [])

    return {
        "status": "FREE_DIRECT_LINKS",
        "summary": summary,
        "topic_title": topic_title,
        "mini_theory": mini_theory,
        "what_to_repeat": what_to_repeat,
        "lectures": lectures,
        "articles": articles,
        "practice": practice,
        "videos": videos,
        "control_question": control_question,
        "next_topic": next_topic,
        "ai_note": reason or "Используется бесплатный режим с прямыми учебными ссылками.",
        "from_cache": False,
        "context": context
    }


def generate_live_learning_path_with_openai(context):
    client = get_openai_client()

    if client is None:
        return build_open_search_fallback_learning_path(
            context,
            reason="OpenAI API key не настроен. Используется бесплатный режим с открытым поиском."
        )

    system_prompt = """
Ты являешься AI-наставником по FPGA-проектированию и Verilog HDL.

Твоя задача:
1. Проанализировать ошибку студента.
2. Найти в интернете актуальные учебные материалы.
3. Подобрать статьи, практические задания и видео.
4. Сформировать индивидуальную траекторию обучения.

Важно:
- Не придумывай несуществующие ссылки.
- Предпочитай открытые учебные материалы: HDLBits, Nandland, Project F, официальную документацию Yosys, университетские страницы, качественные видеоуроки.
- Не отправляй студента на случайные рекламные сайты.
- Ответ верни строго в JSON.
- Язык ответа: русский.
- Ссылки могут быть на английские материалы, но пояснения должны быть на русском.

JSON-структура:
{
  "status": "OK",
  "summary": "...",
  "topic_title": "...",
  "mini_theory": "...",
  "what_to_repeat": ["...", "..."],
  "articles": [
    {
      "title": "...",
      "url": "...",
      "description": "...",
      "why_useful": "..."
    }
  ],
  "videos": [
    {
      "title": "...",
      "url": "...",
      "description": "...",
      "why_useful": "..."
    }
  ],
  "control_question": "...",
  "next_topic": "...",
  "ai_note": "..."
}
"""

    user_prompt = {
        "task": "Сформируй индивидуальную траекторию обучения по Verilog/FPGA с интернет-источниками.",
        "student_context": context
    }

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            tools=[
                {
                    "type": "web_search"
                }
            ],
            input=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": json.dumps(user_prompt, ensure_ascii=False)
                }
            ],
            temperature=0.2
        )

        output_text = getattr(response, "output_text", "")

        parsed = extract_json_from_text(output_text)

        if not parsed:
            return {
                "status": "PARSE_ERROR",
                "summary": "AI подобрал материалы, но ответ не удалось разобрать как JSON.",
                "topic_title": context.get("topic_key", "Verilog FPGA"),
                "mini_theory": output_text,
                "what_to_repeat": [],
                "articles": [],
                "videos": [],
                "control_question": "",
                "next_topic": "",
                "ai_note": "Ошибка разбора JSON."
            }

        parsed.setdefault("status", "OK")
        parsed.setdefault("summary", "")
        parsed.setdefault("topic_title", "")
        parsed.setdefault("mini_theory", "")
        parsed.setdefault("what_to_repeat", [])
        parsed.setdefault("articles", [])
        parsed.setdefault("videos", [])
        parsed.setdefault("control_question", "")
        parsed.setdefault("next_topic", "")
        parsed.setdefault("ai_note", "")

        return parsed

    except Exception as error:
        return build_open_search_fallback_learning_path(
            context,
            reason=f"OpenAI API временно недоступен: {str(error)}. Используется бесплатный режим с открытым поиском."
        )
    

def get_cached_learning_path(username, lab_id, cache_key):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM learning_path_cache
        WHERE username = ?
          AND lab_id = ?
          AND cache_key = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            username,
            lab_id or 0,
            cache_key
        )
    ).fetchone()

    conn.close()

    if not row:
        return None

    try:
        return json.loads(row["result_json"])
    except Exception:
        return None


def save_cached_learning_path(username, lab_id, cache_key, result):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO learning_path_cache
        (username, lab_id, cache_key, result_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            username,
            lab_id or 0,
            cache_key,
            json.dumps(result, ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

def build_live_learning_path(username, current_lab_id=None, refresh=False):
    context = get_recent_student_error_context(
        username=username,
        current_lab_id=current_lab_id
    )

    main_error = context.get("main_error") or {}
    error_type = main_error.get("error_type", "")
    topic_key = context.get("topic_key", "Verilog FPGA")

    cache_key = make_learning_cache_key(
        username=username,
        lab_id=current_lab_id or 0,
        error_type=error_type,
        topic_key=topic_key
    )

    if not refresh:
        cached = get_cached_learning_path(
            username=username,
            lab_id=current_lab_id or 0,
            cache_key=cache_key
        )

        if cached:
            cached["from_cache"] = True
            cached["context"] = context
            return cached

    if LEARNING_PATH_MODE == "openai":
        result = generate_live_learning_path_with_openai(context)
    else:
        result = build_open_search_fallback_learning_path(
            context=context,
            reason="Используется бесплатный режим: открытые поисковые ссылки без платного OpenAI API."
        )

    youtube_query = f"{topic_key} tutorial Verilog FPGA"

    youtube_videos = search_youtube_videos(
        query=youtube_query,
        max_results=3
    )

    if youtube_videos:
        result["videos"] = youtube_videos + result.get("videos", [])

    result["from_cache"] = False
    result["context"] = context
    result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_cached_learning_path(
        username=username,
        lab_id=current_lab_id or 0,
        cache_key=cache_key,
        result=result
    )

    return result

# ============================================================
# Тренажёр / определение темы задания
# ============================================================

def get_trainer_topic_by_error(error_type, lab_topic="", lab_title=""):
    error_type = str(error_type or "")
    lab_topic = str(lab_topic or "").lower()
    lab_title = str(lab_title or "").lower()

    text = lab_topic + " " + lab_title

    if error_type in ["CONTROL_SIGNAL_ERROR", "WRONG_COMBINATIONAL_LOGIC", "BOUNDARY_TEST_FAILED"]:
        return "mux"

    if error_type in ["MODULE_NAME_MISMATCH"]:
        return "module_name"

    if error_type in ["PORT_MISMATCH"]:
        return "ports"

    if error_type in ["INCOMPLETE_CONDITION", "CASE_WITHOUT_DEFAULT"]:
        return "case_default"

    if error_type in ["RESET_CLOCK_ERROR"]:
        return "reset_clock"

    if error_type in ["BLOCKING_IN_SEQ"]:
        return "sequential_assignment"

    if error_type in ["FSM_STATE_ERROR", "FSM_TRANSITION_ERROR"]:
        return "fsm"

    if "mux" in text or "мультиплексор" in text:
        return "mux"

    if "counter" in text or "счётчик" in text or "счетчик" in text:
        return "reset_clock"

    if "register" in text or "регистр" in text:
        return "reset_clock"

    if "fsm" in text or "state" in text or "автомат" in text:
        return "fsm"

    return "verilog_basics"


def get_trainer_source_catalog(topic_slug):
    catalog = {
        "mux": [
            {
                "title": "HDLBits: Combinational Logic",
                "url": "https://hdlbits.01xz.net/wiki/Problem_sets"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            },
            {
                "title": "Project F: Verilog Library",
                "url": "https://projectf.io/verilog-lib/"
            }
        ],

        "module_name": [
            {
                "title": "HDLBits: Getting Started",
                "url": "https://hdlbits.01xz.net/wiki/Step_one"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ],

        "ports": [
            {
                "title": "HDLBits: Getting Started",
                "url": "https://hdlbits.01xz.net/wiki/Step_one"
            },
            {
                "title": "Nandland: Verilog Tutorials",
                "url": "https://nandland.com/category/verilog-tutorials-and-examples/verilog-tutorials/"
            }
        ],

        "case_default": [
            {
                "title": "HDLBits: Always blocks",
                "url": "https://hdlbits.01xz.net/wiki/Alwaysblock1"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ],

        "reset_clock": [
            {
                "title": "HDLBits: Always blocks clocked",
                "url": "https://hdlbits.01xz.net/wiki/Alwaysff"
            },
            {
                "title": "HDLBits: D flip-flop",
                "url": "https://hdlbits.01xz.net/wiki/Dff"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ],

        "sequential_assignment": [
            {
                "title": "HDLBits: Sequential Logic",
                "url": "https://hdlbits.01xz.net/wiki/Problem_sets"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ],

        "fsm": [
            {
                "title": "HDLBits: Finite State Machines",
                "url": "https://hdlbits.01xz.net/wiki/Problem_sets"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ],

        "verilog_basics": [
            {
                "title": "HDLBits: Problem Sets",
                "url": "https://hdlbits.01xz.net/wiki/Problem_sets"
            },
            {
                "title": "Nandland: Learn Verilog",
                "url": "https://nandland.com/learn-verilog/"
            }
        ]
    }

    return catalog.get(topic_slug, catalog["verilog_basics"])


def fetch_web_source_metadata(url):
    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "Mozilla/5.0 FPGA Learning System Educational Bot"
            }
        )

        if response.status_code != 200:
            return {
                "url": url,
                "title": "",
                "description": "",
                "ok": False
            }

        soup = BeautifulSoup(response.text, "html.parser")

        title = ""

        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        description = ""

        meta_description = soup.find("meta", attrs={"name": "description"})

        if meta_description and meta_description.get("content"):
            description = meta_description.get("content").strip()

        # Ограничиваем длину, чтобы не тащить чужой материал целиком.
        title = title[:200]
        description = description[:500]

        return {
            "url": url,
            "title": title,
            "description": description,
            "ok": True
        }

    except Exception:
        return {
            "url": url,
            "title": "",
            "description": "",
            "ok": False
        }


def collect_trainer_web_context(topic_slug, limit=3):
    sources = get_trainer_source_catalog(topic_slug)
    collected = []

    for source in sources[:limit]:
        metadata = fetch_web_source_metadata(source["url"])

        collected.append({
            "source_title": source["title"],
            "source_url": source["url"],
            "page_title": metadata.get("title") or source["title"],
            "page_description": metadata.get("description") or "",
            "ok": metadata.get("ok", False)
        })

    return collected


def get_student_trainer_context(username):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            submissions.id,
            submissions.lab_id,
            submissions.status,
            submissions.score,
            submissions.attempt_number,
            submissions.error_type,
            submissions.error_title,
            submissions.error_details,
            submissions.recommendation,
            submissions.created_at,

            labs.title AS lab_title,
            labs.topic AS lab_topic,
            labs.difficulty AS lab_difficulty,
            labs.discipline AS lab_discipline
        FROM submissions
        JOIN labs ON labs.id = submissions.lab_id
        WHERE submissions.username = ?
        ORDER BY submissions.created_at DESC, submissions.id DESC
        LIMIT 30
        """,
        (username,)
    ).fetchall()

    conn.close()

    attempts = [dict(row) for row in rows]

    error_counter = {}

    for row in attempts:
        error_type = row.get("error_type") or ""

        if not error_type or error_type == "NO_ERROR":
            continue

        if error_type not in error_counter:
            error_counter[error_type] = {
                "error_type": error_type,
                "error_title": row.get("error_title") or error_type,
                "count": 0,
                "lab_title": row.get("lab_title") or "",
                "lab_topic": row.get("lab_topic") or "",
                "recommendation": row.get("recommendation") or ""
            }

        error_counter[error_type]["count"] += 1

    repeated_errors = sorted(
        error_counter.values(),
        key=lambda item: item["count"],
        reverse=True
    )

    if repeated_errors:
        main_error = repeated_errors[0]
        topic_slug = get_trainer_topic_by_error(
            error_type=main_error["error_type"],
            lab_topic=main_error["lab_topic"],
            lab_title=main_error["lab_title"]
        )
    else:
        main_error = None
        topic_slug = "verilog_basics"

    return {
        "username": username,
        "main_error": main_error,
        "repeated_errors": repeated_errors[:5],
        "topic_slug": topic_slug,
        "recent_attempts": attempts[:10]
    }


def generate_template_trainer_tasks(context, web_context, count=5):
    topic_slug = context["topic_slug"]
    main_error = context.get("main_error") or {}
    error_type = main_error.get("error_type", "")

    source = web_context[0] if web_context else {
        "source_title": "",
        "source_url": ""
    }

    tasks = []

    if topic_slug == "mux":
        tasks.extend([
            {
                "title": "Выбор выхода при sel = 0",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": "Дан мультиплексор 2 к 1: y = sel ? d1 : d0. Что будет на выходе при sel = 0?",
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": ["d0", "d1", "sel", "0"],
                "correct_answer": "d0",
                "explanation": "При sel = 0 мультиплексор выбирает первый вход d0."
            },
            {
                "title": "Выбор выхода при sel = 1",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": "Дан мультиплексор 2 к 1: y = sel ? d1 : d0. Что будет на выходе при sel = 1?",
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": ["d0", "d1", "sel", "x"],
                "correct_answer": "d1",
                "explanation": "При sel = 1 мультиплексор выбирает второй вход d1."
            },
            {
                "title": "Определить значение y",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": "Чему равен y при d0 = 1, d1 = 0, sel = 0?",
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": ["0", "1", "x", "z"],
                "correct_answer": "1",
                "explanation": "При sel = 0 выбирается d0. Так как d0 = 1, выход y = 1."
            },
            {
                "title": "Определить значение y при sel = 1",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": "Чему равен y при d0 = 1, d1 = 0, sel = 1?",
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": ["0", "1", "d0", "sel"],
                "correct_answer": "0",
                "explanation": "При sel = 1 выбирается d1. Так как d1 = 0, выход y = 0."
            },
            {
                "title": "Найти правильное описание мультиплексора",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": "Какой вариант правильно описывает мультиплексор 2 к 1, если при sel = 0 выбирается d0, а при sel = 1 выбирается d1?",
                "code_snippet": "",
                "options": [
                    "assign y = sel ? d1 : d0;",
                    "assign y = sel ? d0 : d1;",
                    "assign y = d0 & d1;",
                    "assign y = sel;"
                ],
                "correct_answer": "assign y = sel ? d1 : d0;",
                "explanation": "Тернарный оператор работает так: условие ? значение_если_истина : значение_если_ложь."
            },
            {
                "title": "Найти ошибку в коде",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": "Что не так в этом описании мультиплексора?",
                "code_snippet": "assign y = sel ? d0 : d1;",
                "options": [
                    "Перепутаны d0 и d1",
                    "Не хватает endmodule",
                    "Нельзя использовать assign",
                    "sel должен быть output"
                ],
                "correct_answer": "Перепутаны d0 и d1",
                "explanation": "Если по условию при sel = 0 должен выбираться d0, а при sel = 1 d1, то правильное выражение: assign y = sel ? d1 : d0."
            },
            {
                "title": "Роль управляющего сигнала",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": "Какой сигнал управляет выбором входа в мультиплексоре 2 к 1?",
                "code_snippet": "module mux2to1(input wire d0, input wire d1, input wire sel, output wire y);",
                "options": ["d0", "d1", "sel", "y"],
                "correct_answer": "sel",
                "explanation": "Сигнал sel определяет, какой из входов попадёт на выход y."
            }
        ])

    elif topic_slug == "module_name":
        tasks.append({
            "title": "Исправить имя модуля",
            "task_type": "single_choice",
            "difficulty": "basic",
            "prompt": "Testbench создаёт экземпляр mux2to1 uut (...). Как должно называться начало модуля?",
            "code_snippet": "module ??? (input wire d0, input wire d1, input wire sel, output wire y);",
            "options": [
                "module mux2to1",
                "module mux",
                "module testbench",
                "module uut"
            ],
            "correct_answer": "module mux2to1",
            "explanation": "Имя модуля должно совпадать с тем, что ожидает testbench."
        })

    elif topic_slug == "ports":
        tasks.append({
            "title": "Выбрать правильный порт",
            "task_type": "single_choice",
            "difficulty": "basic",
            "prompt": "Какой порт должен быть выходом в модуле мультиплексора?",
            "code_snippet": "module mux2to1(input wire d0, input wire d1, input wire sel, output wire y);",
            "options": [
                "d0",
                "d1",
                "sel",
                "y"
            ],
            "correct_answer": "y",
            "explanation": "d0, d1 и sel — входы, а y — результат работы схемы."
        })

    elif topic_slug == "case_default":
        tasks.append({
            "title": "Дописать default в case",
            "task_type": "single_choice",
            "difficulty": "medium",
            "prompt": "Что лучше добавить в case-конструкцию, чтобы избежать неполного описания логики?",
            "code_snippet": "case(sel)\n  1'b0: y = d0;\n  1'b1: y = d1;\nendcase",
            "options": [
                "default: y = 1'b0;",
                "initial y = 0;",
                "#10 y = d0;",
                "assign sel = y;"
            ],
            "correct_answer": "default: y = 1'b0;",
            "explanation": "default задаёт поведение схемы для непредусмотренных значений."
        })

    elif topic_slug == "reset_clock":
        tasks.append({
            "title": "Выбрать правильный always-блок",
            "task_type": "single_choice",
            "difficulty": "medium",
            "prompt": "Какой always-блок корректно описывает регистр с асинхронным reset?",
            "code_snippet": "",
            "options": [
                "always @(posedge clk or posedge reset)",
                "always @(*)",
                "always @(reset)",
                "always @(posedge y)"
            ],
            "correct_answer": "always @(posedge clk or posedge reset)",
            "explanation": "Асинхронный reset указывается в списке чувствительности вместе с clock."
        })

        tasks.append({
            "title": "Найти правильное присваивание в регистре",
            "task_type": "single_choice",
            "difficulty": "medium",
            "prompt": "Какое присваивание обычно используют внутри always @(posedge clk)?",
            "code_snippet": "always @(posedge clk) begin\n    q <= d;\nend",
            "options": [
                "<=",
                "=",
                "assign",
                "=="
            ],
            "correct_answer": "<=",
            "explanation": "В последовательностной логике обычно используют неблокирующее присваивание <=."
        })

    elif topic_slug == "fsm":
        tasks.append({
            "title": "Определить назначение next_state",
            "task_type": "single_choice",
            "difficulty": "medium",
            "prompt": "Для чего в FSM обычно используется сигнал next_state?",
            "code_snippet": "",
            "options": [
                "Для хранения следующего состояния автомата",
                "Для хранения входного clock",
                "Для замены reset",
                "Для вывода результата testbench"
            ],
            "correct_answer": "Для хранения следующего состояния автомата",
            "explanation": "next_state определяет, в какое состояние автомат перейдёт на следующем такте."
        })

    else:
        tasks.append({
            "title": "Определить структуру Verilog-модуля",
            "task_type": "single_choice",
            "difficulty": "basic",
            "prompt": "Какой ключевой блок обязательно завершает описание модуля Verilog?",
            "code_snippet": "module example(input wire a, output wire y);\nassign y = a;\n???",
            "options": [
                "endmodule",
                "end",
                "finish",
                "stop"
            ],
            "correct_answer": "endmodule",
            "explanation": "Описание Verilog-модуля завершается ключевым словом endmodule."
        })

    prepared = []

    random.shuffle(tasks)

    for task in tasks[:count]:
        prepared.append({
            "topic_slug": topic_slug,
            "competency": topic_slug,
            "error_type": error_type,
            "title": task["title"],
            "task_type": task["task_type"],
            "difficulty": task["difficulty"],
            "prompt": task["prompt"],
            "code_snippet": task.get("code_snippet", ""),
            "options": task.get("options", []),
            "correct_answer": task.get("correct_answer", ""),
            "explanation": task.get("explanation", ""),
            "source_title": source.get("source_title", ""),
            "source_url": source.get("source_url", ""),
            "source_mode": "template",
            "ai_prompt": "",
            "ai_raw_output": ""
        })

    return prepared


def generate_trainer_tasks_with_ollama(context, web_context, count=5):
    prompt = {
        "role": "FPGA Verilog trainer task generator",
        "language": "ru",
        "student_context": context,
        "web_sources": web_context,
        "task": (
            "Сгенерируй оригинальные мини-задания по Verilog/FPGA для тренажёра. "
            "Не копируй задания из источников дословно. Используй источники только как тему и направление. "
            "Задания должны быть короткими, проверяемыми автоматически, с одним правильным ответом."
        ),
        "allowed_task_types": [
            "single_choice"
        ],
        "json_format": {
            "tasks": [
                {
                    "title": "string",
                    "task_type": "single_choice",
                    "difficulty": "basic|medium|advanced",
                    "prompt": "string",
                    "code_snippet": "string",
                    "options": ["string", "string", "string", "string"],
                    "correct_answer": "string",
                    "explanation": "string"
                }
            ]
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": json.dumps(prompt, ensure_ascii=False),
                "stream": False,
                "format": "json"
            },
            timeout=60
        )

        if response.status_code != 200:
            return []

        data = response.json()
        raw_output = data.get("response", "")

        parsed = json.loads(raw_output)

        tasks = parsed.get("tasks", [])

        return normalize_ai_trainer_tasks(
            tasks=tasks,
            context=context,
            web_context=web_context,
            source_mode="local_ai",
            ai_prompt=json.dumps(prompt, ensure_ascii=False),
            ai_raw_output=raw_output
        )

    except Exception:
        return []
    

def normalize_ai_trainer_tasks(tasks, context, web_context, source_mode, ai_prompt="", ai_raw_output=""):
    prepared = []

    topic_slug = context.get("topic_slug", "verilog_basics")
    main_error = context.get("main_error") or {}
    error_type = main_error.get("error_type", "")

    source = web_context[0] if web_context else {
        "source_title": "",
        "source_url": ""
    }

    for task in tasks:
        title = str(task.get("title", "")).strip()
        prompt = str(task.get("prompt", "")).strip()
        task_type = str(task.get("task_type", "single_choice")).strip()
        difficulty = str(task.get("difficulty", "basic")).strip()
        code_snippet = str(task.get("code_snippet", "")).strip()
        explanation = str(task.get("explanation", "")).strip()

        options = task.get("options", [])
        correct_answer = str(task.get("correct_answer", "")).strip()

        if task_type != "single_choice":
            continue

        if not title or not prompt:
            continue

        if not isinstance(options, list):
            continue

        options = [str(option).strip() for option in options if str(option).strip()]

        if len(options) < 2:
            continue

        if correct_answer not in options:
            continue

        if difficulty not in ["basic", "medium", "advanced"]:
            difficulty = "basic"

        # Ограничения длины, чтобы AI не вывел огромный текст.
        title = title[:160]
        prompt = prompt[:1000]
        code_snippet = code_snippet[:1500]
        explanation = explanation[:1000]
        options = options[:6]

        prepared.append({
            "topic_slug": topic_slug,
            "competency": topic_slug,
            "error_type": error_type,
            "title": title,
            "task_type": task_type,
            "difficulty": difficulty,
            "prompt": prompt,
            "code_snippet": code_snippet,
            "options": options,
            "correct_answer": correct_answer,
            "explanation": explanation,
            "source_title": source.get("source_title", ""),
            "source_url": source.get("source_url", ""),
            "source_mode": source_mode,
            "ai_prompt": ai_prompt,
            "ai_raw_output": ai_raw_output
        })

    return prepared[:5]

def generate_personal_trainer_tasks(username, count=5):
    context = get_student_trainer_context(username)
    web_context = collect_trainer_web_context(context["topic_slug"], limit=3)

    generated_tasks = []

    if TRAINER_AI_MODE == "local":
        generated_tasks = generate_trainer_tasks_with_ollama(
            context=context,
            web_context=web_context,
            count=count
        )

    # Позже сюда можно добавить openai-режим.
    # elif TRAINER_AI_MODE == "openai":
    #     generated_tasks = generate_trainer_tasks_with_openai(...)

    if not generated_tasks:
        generated_tasks = generate_template_trainer_tasks(
            context=context,
            web_context=web_context,
            count=count
        )

    return generated_tasks


def save_trainer_tasks(username, tasks):
    conn = get_db()

    saved_ids = []

    for task in tasks:
        cursor = conn.execute(
            """
            INSERT INTO trainer_tasks
            (username, source_mode, topic_slug, competency, error_type,
             title, task_type, difficulty, prompt, code_snippet,
             options_json, correct_answer_json, explanation,
             source_title, source_url, ai_prompt, ai_raw_output,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                task.get("source_mode", "template"),
                task.get("topic_slug", ""),
                task.get("competency", ""),
                task.get("error_type", ""),
                task.get("title", ""),
                task.get("task_type", "single_choice"),
                task.get("difficulty", "basic"),
                task.get("prompt", ""),
                task.get("code_snippet", ""),
                json.dumps(task.get("options", []), ensure_ascii=False),
                json.dumps(
                    {
                        "answer": task.get("correct_answer", "")
                    },
                    ensure_ascii=False
                ),
                task.get("explanation", ""),
                task.get("source_title", ""),
                task.get("source_url", ""),
                task.get("ai_prompt", ""),
                task.get("ai_raw_output", ""),
                "active",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        saved_ids.append(cursor.lastrowid)

    conn.commit()
    conn.close()

    return saved_ids


def create_trainer_session(username, tasks, context):
    conn = get_db()

    main_error = context.get("main_error") or {}

    topic_slug = context.get("topic_slug", "verilog_basics")
    error_type = main_error.get("error_type", "")
    error_title = main_error.get("error_title", "")

    if error_title:
        title = f"Тренировочный тест: {error_title}"
    else:
        title = "Тренировочный тест по Verilog/FPGA"

    source_mode = tasks[0].get("source_mode", "template") if tasks else "template"

    cursor = conn.execute(
        """
        INSERT INTO trainer_sessions
        (username, topic_slug, competency, error_type, error_title,
         title, source_mode, status, total_questions, correct_count,
         score, passed, created_at, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            topic_slug,
            topic_slug,
            error_type,
            error_title,
            title,
            source_mode,
            "active",
            len(tasks),
            0,
            0,
            0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ""
        )
    )

    session_id = cursor.lastrowid

    for index, task in enumerate(tasks, start=1):
        task_cursor = conn.execute(
            """
            INSERT INTO trainer_tasks
            (username, source_mode, topic_slug, competency, error_type,
             title, task_type, difficulty, prompt, code_snippet,
             options_json, correct_answer_json, explanation,
             source_title, source_url, ai_prompt, ai_raw_output,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                task.get("source_mode", "template"),
                task.get("topic_slug", ""),
                task.get("competency", ""),
                task.get("error_type", ""),
                task.get("title", ""),
                task.get("task_type", "single_choice"),
                task.get("difficulty", "basic"),
                task.get("prompt", ""),
                task.get("code_snippet", ""),
                json.dumps(task.get("options", []), ensure_ascii=False),
                json.dumps(
                    {"answer": task.get("correct_answer", "")},
                    ensure_ascii=False
                ),
                task.get("explanation", ""),
                task.get("source_title", ""),
                task.get("source_url", ""),
                task.get("ai_prompt", ""),
                task.get("ai_raw_output", ""),
                "active",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        task_id = task_cursor.lastrowid

        conn.execute(
            """
            INSERT INTO trainer_session_questions
            (session_id, task_id, order_number)
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                task_id,
                index
            )
        )

    conn.commit()
    conn.close()

    return session_id


@app.route("/student/trainer/generate", methods=["POST"])
@login_required
def student_trainer_generate():
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    active_session = conn.execute(
        """
        SELECT *
        FROM trainer_sessions
        WHERE username = ?
          AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (username,)
    ).fetchone()

    conn.close()

    if active_session:
        flash("У вас уже есть незавершённый тренировочный тест. Сначала завершите его.")
        return redirect(url_for("student_trainer_session", session_id=active_session["id"]))

    context = get_student_trainer_context(username)

    tasks = generate_personal_trainer_tasks(
        username=username,
        count=7
    )

    if not tasks:
        flash("Не удалось сгенерировать тренировочный тест.")
        return redirect(url_for("student_trainer"))

    session_id = create_trainer_session(
        username=username,
        tasks=tasks,
        context=context
    )

    flash("Сгенерирован тренировочный тест.")
    return redirect(url_for("student_trainer_session", session_id=session_id))


@app.route("/student/trainer/session/<int:session_id>")
@login_required
def student_trainer_session(session_id):
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    trainer_session = conn.execute(
        """
        SELECT *
        FROM trainer_sessions
        WHERE id = ?
          AND username = ?
        """,
        (
            session_id,
            username
        )
    ).fetchone()

    if not trainer_session:
        conn.close()
        abort(404)

    questions = conn.execute(
        """
        SELECT
            trainer_tasks.*,
            trainer_session_questions.order_number
        FROM trainer_session_questions
        JOIN trainer_tasks ON trainer_tasks.id = trainer_session_questions.task_id
        WHERE trainer_session_questions.session_id = ?
        ORDER BY trainer_session_questions.order_number ASC
        """,
        (session_id,)
    ).fetchall()

    answers = conn.execute(
        """
        SELECT *
        FROM trainer_session_answers
        WHERE session_id = ?
          AND username = ?
        """,
        (
            session_id,
            username
        )
    ).fetchall()

    conn.close()

    answers_map = {
        answer["task_id"]: answer
        for answer in answers
    }

    prepared_questions = []

    for question in questions:
        prepared_questions.append({
            "task": question,
            "options": json.loads(question["options_json"] or "[]"),
            "answer": answers_map.get(question["id"])
        })

    return render_template(
        "student/trainer_session.html",
        trainer_session=trainer_session,
        questions=prepared_questions
    )


@app.route("/student/trainer/task/<int:task_id>")
@login_required
def student_trainer_task(task_id):
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    task = conn.execute(
        """
        SELECT *
        FROM trainer_tasks
        WHERE id = ?
          AND username = ?
        """,
        (
            task_id,
            username
        )
    ).fetchone()

    conn.close()

    if not task:
        abort(404)

    options = json.loads(task["options_json"] or "[]")

    return render_template(
        "student/trainer_task.html",
        task=task,
        options=options
    )


@app.route("/student/trainer/task/<int:task_id>/submit", methods=["POST"])
@login_required
def student_trainer_task_submit(task_id):
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]
    selected_option = request.form.get("selected_option", "").strip()

    conn = get_db()

    task = conn.execute(
        """
        SELECT *
        FROM trainer_tasks
        WHERE id = ?
          AND username = ?
        """,
        (
            task_id,
            username
        )
    ).fetchone()

    if not task:
        conn.close()
        abort(404)

    correct_data = json.loads(task["correct_answer_json"] or "{}")
    correct_answer = str(correct_data.get("answer", "")).strip()

    is_correct = 1 if selected_option == correct_answer else 0
    score = 100 if is_correct else 0

    if is_correct:
        feedback = "Верно. " + (task["explanation"] or "")
    else:
        feedback = (
            "Неверно. Правильный ответ: "
            + correct_answer
            + ". "
            + (task["explanation"] or "")
        )

    conn.execute(
        """
        INSERT INTO trainer_attempts
        (username, task_id, answer_text, selected_option,
         is_correct, score, feedback, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            task_id,
            selected_option,
            selected_option,
            is_correct,
            score,
            feedback,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

    flash(feedback)

    return redirect(url_for("student_trainer_task", task_id=task_id))


@app.route("/student/trainer/session/<int:session_id>/submit", methods=["POST"])
@login_required
def student_trainer_session_submit(session_id):
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    trainer_session = conn.execute(
        """
        SELECT *
        FROM trainer_sessions
        WHERE id = ?
          AND username = ?
        """,
        (
            session_id,
            username
        )
    ).fetchone()

    if not trainer_session:
        conn.close()
        abort(404)

    if trainer_session["status"] == "completed":
        conn.close()
        flash("Этот тренировочный тест уже завершён. Ответы изменить нельзя.")
        return redirect(url_for("student_trainer_session", session_id=session_id))

    questions = conn.execute(
        """
        SELECT
            trainer_tasks.*,
            trainer_session_questions.order_number
        FROM trainer_session_questions
        JOIN trainer_tasks ON trainer_tasks.id = trainer_session_questions.task_id
        WHERE trainer_session_questions.session_id = ?
        ORDER BY trainer_session_questions.order_number ASC
        """,
        (session_id,)
    ).fetchall()

    correct_count = 0
    total_questions = len(questions)

    for question in questions:
        task_id = question["id"]
        selected_option = request.form.get(f"answer_{task_id}", "").strip()

        correct_data = json.loads(question["correct_answer_json"] or "{}")
        correct_answer = str(correct_data.get("answer", "")).strip()

        is_correct = 1 if selected_option == correct_answer else 0

        if is_correct:
            correct_count += 1
            feedback = "Верно. " + (question["explanation"] or "")
        else:
            feedback = (
                "Неверно. Правильный ответ: "
                + correct_answer
                + ". "
                + (question["explanation"] or "")
            )

        conn.execute(
            """
            INSERT OR REPLACE INTO trainer_session_answers
            (session_id, task_id, username, selected_option,
             is_correct, correct_answer, feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                task_id,
                username,
                selected_option,
                is_correct,
                correct_answer,
                feedback,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

    if total_questions > 0:
        score = round(correct_count * 100 / total_questions)
    else:
        score = 0

    passed = 1 if score >= 70 else 0

    conn.execute(
        """
        UPDATE trainer_sessions
        SET status = 'completed',
            total_questions = ?,
            correct_count = ?,
            score = ?,
            passed = ?,
            submitted_at = ?
        WHERE id = ?
          AND username = ?
        """,
        (
            total_questions,
            correct_count,
            score,
            passed,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id,
            username
        )
    )

    conn.commit()
    conn.close()

    if passed:
        flash(f"Тест завершён. Результат: {score}/100. Тест пройден.")
    else:
        flash(f"Тест завершён. Результат: {score}/100. Рекомендуется пройти новый тест.")

    return redirect(url_for("student_trainer_session", session_id=session_id))



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


@app.route("/student/competencies")
@login_required
def student_competencies():
    if session.get("role") != "student":
        flash("Карта компетенций доступна только студенту.")
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

    conn.close()

    if not student:
        flash("Студент не найден.")
        return redirect(url_for("index"))

    competency_map = calculate_student_competency_map(username)

    return render_template(
        "student/competencies.html",
        student=student,
        competency_map=competency_map
    )


@app.route("/student/learning-path-live")
@login_required
def student_learning_path_live():
    if session.get("role") != "student":
        flash("AI-траектория доступна только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    lab_id = request.args.get("lab_id", "").strip()
    refresh = request.args.get("refresh", "") == "1"

    current_lab_id = None

    if lab_id.isdigit():
        current_lab_id = int(lab_id)

    learning_path = build_live_learning_path(
        username=username,
        current_lab_id=current_lab_id,
        refresh=refresh
    )

    return render_template(
        "student/learning_path_live.html",
        learning_path=learning_path,
        current_lab_id=current_lab_id
    )


@app.route("/student/trainer")
@login_required
def student_trainer():
    if session.get("role") != "student":
        flash("Тренажёр доступен только студенту.")
        return redirect(url_for("index"))

    username = session["username"]

    conn = get_db()

    sessions = conn.execute(
        """
        SELECT *
        FROM trainer_sessions
        WHERE username = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (username,)
    ).fetchall()

    stats = conn.execute(
        """
        SELECT
            COUNT(*) AS total_sessions,
            SUM(passed) AS passed_sessions,
            AVG(score) AS avg_score
        FROM trainer_sessions
        WHERE username = ?
          AND status = 'completed'
        """,
        (username,)
    ).fetchone()

    active_session = conn.execute(
        """
        SELECT *
        FROM trainer_sessions
        WHERE username = ?
          AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (username,)
    ).fetchone()

    conn.close()

    context = get_student_trainer_context(username)

    return render_template(
        "student/trainer.html",
        sessions=sessions,
        stats=stats,
        active_session=active_session,
        context=context
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

    if file:
        file.stream.seek(0, os.SEEK_END)
        file_size = file.stream.tell()
        file.stream.seek(0)

        if file_size > 256 * 1024:
            flash("Файл слишком большой. Максимальный размер файла — 256 КБ.")
            return redirect(url_for("lab_detail", lab_id=lab_id))

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


# Перевіряємо кількість спроб студента по цій лабораторній роботі. Якщо кількість спроб досягла максимуму, закриваємо з'єднання та показуємо повідомлення про те, що ліміт спроб вичерпано.
    attempts_info = get_attempts_info(
        conn=conn,
        lab=lab,
        username=session["username"]
    )

    if attempts_info["is_limit_reached"]:
        flash(
            "Вы исчерпали количество попыток. "
            "Для дополнительной попытки обратитесь к преподавателю."
        )
        conn.close()
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

    attempt_number = attempts_info["used_attempts"] + 1

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

    with open(saved_path, "r", encoding="utf-8", errors="replace") as saved_file:
        uploaded_code = saved_file.read()

    uploaded_code = uploaded_code.replace("\r\n", "\n").replace("\r", "\n")

    if not uploaded_code.endswith("\n"):
        uploaded_code += "\n"

    with open(saved_path, "w", encoding="utf-8") as saved_file:
        saved_file.write(uploaded_code)

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

    lint_result = {
        "lint_status": "",
        "lint_score": 0,
        "lint_issues_count": 0,
        "lint_output": "",
        "lint_recommendation": "",
        "lint_issues": []
    }

    if (lab["checker_type"] or "hdl_testbench") == "hdl_testbench":
        lint_result = run_hdl_lint_check(saved_path)

    synth_result = {
        "synth_status": "",
        "synth_score": 0,
        "synth_cells_count": 0,
        "synth_wires_count": 0,
        "synth_wire_bits_count": 0,
        "synth_warnings_count": 0,
        "synth_output": "",
        "synth_recommendation": "",
        "synth_stats": {}
    }

    if (lab["checker_type"] or "hdl_testbench") == "hdl_testbench":
        synth_result = run_hdl_synthesis_check(saved_path, lab)

    status = check_result["status"]
    output = check_result["output"]
    score = check_result["score"]
    passed_tests = check_result["passed_tests"]
    total_tests = check_result["total_tests"]

    public_status = check_result.get("public_status", status)
    public_score = check_result.get("public_score", 0)
    public_passed_tests = check_result.get("public_passed_tests", 0)
    public_total_tests = check_result.get("public_total_tests", 0)
    public_output = check_result.get("public_output", "")

    hidden_status = check_result.get("hidden_status", "")
    hidden_score = check_result.get("hidden_score", 0)
    hidden_passed_tests = check_result.get("hidden_passed_tests", 0)
    hidden_total_tests = check_result.get("hidden_total_tests", 0)
    hidden_output = check_result.get("hidden_output", "")

    lint_status = lint_result.get("lint_status", "")
    lint_score = lint_result.get("lint_score", 0)
    lint_issues_count = lint_result.get("lint_issues_count", 0)
    lint_output = lint_result.get("lint_output", "")
    lint_recommendation = lint_result.get("lint_recommendation", "")
    lint_issues_json = json.dumps(
        lint_result.get("lint_issues", []),
        ensure_ascii=False
    )

    testbench_score = clamp_score(score)

    lint_score = clamp_score(lint_score)
    lint_status = lint_status or "OK"

    synth_score = clamp_score(synth_result.get("synth_score", 0))
    synth_status = synth_result.get("synth_status", "OK")

    has_questions = bool(lab["allow_extra_questions"])

    final_grade = build_lab_final_grade(
        testbench_score=testbench_score,
        lint_score=lint_score,
        synth_score=synth_score,
        questions_score=0,
        has_questions=has_questions,
        lint_status=lint_status,
        synth_status=synth_status
    )

# Читаємо код студента з збереженого файлу, щоб передати його в функцію класифікації помилки та формування діагностики.
    with open(saved_path, "r", encoding="utf-8", errors="replace") as code_file:
        student_code = code_file.read()

    if (
        hidden_total_tests > 0
        and hidden_passed_tests < hidden_total_tests
        and public_total_tests > 0
        and public_passed_tests == public_total_tests
    ):
        diagnostics = {
            "error_type": "HIDDEN_TEST_FAILED",
            "error_title": "Не пройдены скрытые тесты",
            "error_details": (
                "Решение прошло открытые тесты, но не прошло часть скрытых проверок. "
                "Это означает, что код работает для известных примеров, но ошибается на дополнительных или граничных случаях."
            ),
            "recommendation": (
                "Проверьте полную таблицу истинности, граничные комбинации входных сигналов и случаи, которые не были явно показаны в открытых тестах."
            ),
            "error_confidence": 85
        }
    else:
        if (
            hidden_total_tests > 0
            and hidden_passed_tests < hidden_total_tests
            and public_total_tests > 0
            and public_passed_tests == public_total_tests
        ):
            diagnostics = {
                "error_type": "HIDDEN_TEST_FAILED",
                "error_title": "Не пройдены скрытые тесты",
                "error_details": (
                    "Решение прошло открытые тесты, но не прошло часть скрытых проверок. "
                    "Это означает, что код работает для известных примеров, но ошибается на дополнительных или граничных случаях."
                ),
                "recommendation": (
                    "Проверьте полную таблицу истинности, граничные комбинации входных сигналов и случаи, которые не были явно показаны в открытых тестах."
                ),
                "error_confidence": 85
            }
        else:
            diagnostics = classify_solution_error(
                status=status,
                output=public_output or output,
                lab=lab,
                code=student_code
            )

# Зберігаємо результат відправки в базі даних, включаючи діагностику помилки, щоб потім використовувати цю інформацію для формування адаптивного навчального плану та надання студенту конкретних рекомендацій щодо виправлення помилки.
    submission_values = (
        lab_id,
        session["username"],
        saved_filename,
        waveform_filename,

        status,
        final_grade["final_score"],
        passed_tests,
        total_tests,

        lint_status,
        lint_score,
        lint_issues_count,
        lint_output,
        lint_recommendation,
        lint_issues_json,

        synth_status,
        synth_score,
        synth_result.get("synth_cells_count", 0),
        synth_result.get("synth_wires_count", 0),
        synth_result.get("synth_wire_bits_count", 0),
        synth_result.get("synth_warnings_count", 0),
        synth_result.get("synth_output", ""),
        synth_result.get("synth_recommendation", ""),
        json.dumps(synth_result.get("synth_stats", {}), ensure_ascii=False),

        public_status,
        public_score,
        public_passed_tests,
        public_total_tests,
        public_output,

        hidden_status,
        hidden_score,
        hidden_passed_tests,
        hidden_total_tests,
        hidden_output,

        diagnostics["error_type"],
        diagnostics["error_title"],
        diagnostics["error_details"],
        diagnostics["recommendation"],
        diagnostics["error_confidence"],

        output,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        attempt_number,
        0,
        0,

        testbench_score,
        0,
        final_grade["final_score"],
        final_grade["final_status"],
        final_grade["ects_grade"],
        final_grade["national_grade"],
        json.dumps(final_grade["grading_breakdown"], ensure_ascii=False)
    )

    submission_placeholders = ", ".join(["?"] * len(submission_values))

    conn.execute(
        f"""
        INSERT INTO submissions
        (lab_id, username, filename, waveform_filename,
        status, score, passed_tests, total_tests,
        lint_status, lint_score, lint_issues_count, lint_output, lint_recommendation, lint_issues_json,
        synth_status, synth_score, synth_cells_count, synth_wires_count,
        synth_wire_bits_count, synth_warnings_count, synth_output,
        synth_recommendation, synth_stats_json,
        public_status, public_score, public_passed_tests, public_total_tests, public_output,
        hidden_status, hidden_score, hidden_passed_tests, hidden_total_tests, hidden_output,
        error_type, error_title, error_details, recommendation, error_confidence,
        output, created_at, attempt_number, file_deleted, file_hidden_for_student,
        testbench_score, questions_score, final_score, final_status,
        ects_grade, national_grade, grading_breakdown)
        VALUES ({submission_placeholders})
        """,
        submission_values
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

    code_text = request.form.get("code_text", "")

    if len(code_text.encode("utf-8")) > MAX_EDITOR_CODE_LENGTH:
        flash("Код слишком большой. Максимальный размер кода в редакторе — 100 КБ.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    if not code_text.strip():
        conn.close()
        flash("Код решения не может быть пустым.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    code_text = code_text.replace("\r\n", "\n").replace("\r", "\n")

    if not code_text.endswith("\n"):
        code_text += "\n"

    attempts_info = get_attempts_info(
        conn=conn,
        lab=lab,
        username=session["username"]
    )

    if attempts_info["is_limit_reached"]:
        flash(
            "Вы исчерпали количество попыток. "
            "Для дополнительной попытки обратитесь к преподавателю."
        )
        conn.close()
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

    attempt_number = attempts_info["used_attempts"] + 1

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

    lint_result = {
        "lint_status": "",
        "lint_score": 0,
        "lint_issues_count": 0,
        "lint_output": "",
        "lint_recommendation": "",
        "lint_issues": []
    }

    if (lab["checker_type"] or "hdl_testbench") == "hdl_testbench":
        lint_result = run_hdl_lint_check(saved_path)

    synth_result = {
        "synth_status": "",
        "synth_score": 0,
        "synth_cells_count": 0,
        "synth_wires_count": 0,
        "synth_wire_bits_count": 0,
        "synth_warnings_count": 0,
        "synth_output": "",
        "synth_recommendation": "",
        "synth_stats": {}
    }

    if (lab["checker_type"] or "hdl_testbench") == "hdl_testbench":
        synth_result = run_hdl_synthesis_check(saved_path, lab)

    status = check_result["status"]
    output = check_result["output"]
    score = check_result["score"]
    passed_tests = check_result["passed_tests"]
    total_tests = check_result["total_tests"]

    public_status = check_result.get("public_status", status)
    public_score = check_result.get("public_score", 0)
    public_passed_tests = check_result.get("public_passed_tests", 0)
    public_total_tests = check_result.get("public_total_tests", 0)
    public_output = check_result.get("public_output", "")

    hidden_status = check_result.get("hidden_status", "")
    hidden_score = check_result.get("hidden_score", 0)
    hidden_passed_tests = check_result.get("hidden_passed_tests", 0)
    hidden_total_tests = check_result.get("hidden_total_tests", 0)
    hidden_output = check_result.get("hidden_output", "")

    lint_status = lint_result.get("lint_status", "")
    lint_score = lint_result.get("lint_score", 0)
    lint_issues_count = lint_result.get("lint_issues_count", 0)
    lint_output = lint_result.get("lint_output", "")
    lint_recommendation = lint_result.get("lint_recommendation", "")
    lint_issues_json = json.dumps(
        lint_result.get("lint_issues", []),
        ensure_ascii=False
    )

    testbench_score = clamp_score(score)

    lint_score = clamp_score(lint_score)
    lint_status = lint_status or "OK"

    synth_score = clamp_score(synth_result.get("synth_score", 0))
    synth_status = synth_result.get("synth_status", "OK")

    has_questions = bool(lab["allow_extra_questions"])

    final_grade = build_lab_final_grade(
        testbench_score=testbench_score,
        lint_score=lint_score,
        synth_score=synth_score,
        questions_score=0,
        has_questions=has_questions,
        lint_status=lint_status,
        synth_status=synth_status
    )

    if (
        hidden_total_tests > 0
        and hidden_passed_tests < hidden_total_tests
        and public_total_tests > 0
        and public_passed_tests == public_total_tests
    ):
        diagnostics = {
            "error_type": "HIDDEN_TEST_FAILED",
            "error_title": "Не пройдены скрытые тесты",
            "error_details": (
                "Решение прошло открытые тесты, но не прошло часть скрытых проверок. "
                "Это означает, что код работает для известных примеров, но ошибается на дополнительных или граничных случаях."
            ),
            "recommendation": (
                "Проверьте полную таблицу истинности, граничные комбинации входных сигналов и случаи, которые не были явно показаны в открытых тестах."
            ),
            "error_confidence": 85
        }
    else:
        diagnostics = classify_solution_error(
            status=status,
            output=public_output or output,
            lab=lab,
            code=code_text
        )

    submission_values = (
        lab_id,
        session["username"],
        saved_filename,
        waveform_filename,

        status,
        final_grade["final_score"],
        passed_tests,
        total_tests,

        lint_status,
        lint_score,
        lint_issues_count,
        lint_output,
        lint_recommendation,
        lint_issues_json,

        synth_status,
        synth_score,
        synth_result["synth_cells_count"],
        synth_result["synth_wires_count"],
        synth_result["synth_wire_bits_count"],
        synth_result["synth_warnings_count"],
        synth_result["synth_output"],
        synth_result["synth_recommendation"],
        json.dumps(synth_result["synth_stats"], ensure_ascii=False),

        public_status,
        public_score,
        public_passed_tests,
        public_total_tests,
        public_output,

        hidden_status,
        hidden_score,
        hidden_passed_tests,
        hidden_total_tests,
        hidden_output,

        diagnostics["error_type"],
        diagnostics["error_title"],
        diagnostics["error_details"],
        diagnostics["recommendation"],
        diagnostics["error_confidence"],

        output,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        attempt_number,
        0,
        0,

        testbench_score,
        0,
        final_grade["final_score"],
        final_grade["final_status"],
        final_grade["ects_grade"],
        final_grade["national_grade"],
        json.dumps(final_grade["grading_breakdown"], ensure_ascii=False)
    )

    submission_placeholders = ", ".join(["?"] * len(submission_values))

    conn.execute(
        f"""
        INSERT INTO submissions
        (lab_id, username, filename, waveform_filename,
        status, score, passed_tests, total_tests,
        lint_status, lint_score, lint_issues_count, lint_output, lint_recommendation, lint_issues_json,
        synth_status, synth_score, synth_cells_count, synth_wires_count,
        synth_wire_bits_count, synth_warnings_count, synth_output,
        synth_recommendation, synth_stats_json,
        public_status, public_score, public_passed_tests, public_total_tests, public_output,
        hidden_status, hidden_score, hidden_passed_tests, hidden_total_tests, hidden_output,
        error_type, error_title, error_details, recommendation, error_confidence,
        output, created_at, attempt_number, file_deleted, file_hidden_for_student,
        testbench_score, questions_score, final_score, final_status,
        ects_grade, national_grade, grading_breakdown)
        VALUES ({submission_placeholders})
        """,
        submission_values
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

    requested_level = request.args.get("level", type=int)

    if requested_level in [1, 2, 3]:
        adaptive_plan["hint_level"] = requested_level
        adaptive_plan["hint_text"] = generate_adaptive_hint(
            submission=submission,
            topic=adaptive_plan["topic"],
            failed_tests=adaptive_plan["failed_tests"],
            hint_level=requested_level
        )

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

        questions_score = round(correct_count * 100 / 3)

        score_before = int(submission["final_score"] or submission["score"] or 0)

        testbench_score = int(submission["testbench_score"] or submission["score"] or 0)
        lint_score = int(submission["lint_score"] or 0)
        synth_score = int(submission["synth_score"] or 0)

        lint_status = submission["lint_status"] or "OK"
        synth_status = submission["synth_status"] or "OK"

        final_grade = build_lab_final_grade(
            testbench_score=testbench_score,
            lint_score=lint_score,
            synth_score=synth_score,
            questions_score=questions_score,
            has_questions=True,
            lint_status=lint_status,
            synth_status=synth_status
        )

        score_after = final_grade["final_score"]

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

        updated_output = (
            submission["output"]
            + "\n\n---\n"
            + "Дополнительные вопросы учтены как компонент итоговой оценки.\n"
            + f"Правильных ответов: {correct_count} из 3.\n"
            + f"Оценка за дополнительные вопросы: {questions_score} / 100.\n"
            + f"Итоговый балл по формуле: {score_after} / 100.\n"
            + f"ECTS: {final_grade['ects_grade']}.\n"
            + f"Национальная оценка: {final_grade['national_grade']}.\n"
        )


        conn.execute(
            """
            UPDATE submissions
            SET questions_score = ?,
                score = ?,
                final_score = ?,
                final_status = ?,
                ects_grade = ?,
                national_grade = ?,
                grading_breakdown = ?,
                output = ?
            WHERE id = ?
            AND username = ?
            """,
            (
                questions_score,
                final_grade["final_score"],
                final_grade["final_score"],
                final_grade["final_status"],
                final_grade["ects_grade"],
                final_grade["national_grade"],
                json.dumps(final_grade["grading_breakdown"], ensure_ascii=False),
                updated_output,
                submission_id,
                session["username"]
            )
        )

        if correct_count >= 2:
            flash("Ответы приняты. Дополнительные вопросы учтены в итоговой оценке.")
        else:
            flash("Ответы сохранены, но оценка за дополнительные вопросы низкая.")

        conn.commit()
        conn.close()

        check_result = {
            "correct_count": correct_count,
            "bonus": bonus,
            "questions_score": questions_score,
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
# 13. Waveform routes - временные диаграммы
# =========================

@app.route("/waveform-view/<int:submission_id>")
@login_required
def view_waveform(submission_id):
    submission = get_waveform_submission_for_current_user(submission_id)

    if not submission["waveform_filename"]:
        flash("Для этой попытки временная диаграмма недоступна.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    waveform_path = os.path.join(WAVEFORM_DIR, submission["waveform_filename"])

    if not os.path.exists(waveform_path):
        flash("Файл временной диаграммы отсутствует на сервере.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    return render_template(
        "student/waveform_viewer.html",
        submission=submission
    )

@app.route("/waveform-data/<int:submission_id>")
@login_required
def waveform_data(submission_id):
    submission = get_waveform_submission_for_current_user(submission_id)

    if not submission["waveform_filename"]:
        return jsonify({
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": "Для этой попытки временная диаграмма недоступна."
        })

    waveform_path = os.path.join(WAVEFORM_DIR, submission["waveform_filename"])

    if not os.path.exists(waveform_path):
        return jsonify({
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": "VCD-файл не найден на сервере."
        })

    parsed = parse_vcd_file(waveform_path)

    return jsonify(parsed)

# =========================
# 15. Grade routes - оцінки
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
# 16. Teacher routes - викладач
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


@app.route("/teacher/analytics")
@login_required
def teacher_analytics():
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in ["teacher", "admin"]:
        flash("Аналитика доступна только преподавателю или администратору.")
        return redirect(url_for("index"))

    is_admin = current_role == "admin"

    selected_discipline = request.args.get("discipline", "").strip()
    selected_lab_id = request.args.get("lab_id", "").strip()
    selected_group = request.args.get("group", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    conn = get_db()

    # -------------------------------------------------
    # 1. Списки для фильтров
    # -------------------------------------------------

    if is_admin:
        disciplines = conn.execute(
            """
            SELECT DISTINCT discipline
            FROM labs
            WHERE discipline IS NOT NULL
              AND discipline != ''
            ORDER BY discipline ASC
            """
        ).fetchall()

        groups = conn.execute(
            """
            SELECT DISTINCT student_group
            FROM users
            WHERE role = 'student'
              AND student_group IS NOT NULL
              AND student_group != ''
            ORDER BY student_group ASC
            """
        ).fetchall()

        labs_for_filter = conn.execute(
            """
            SELECT id, title, discipline
            FROM labs
            ORDER BY discipline ASC, title ASC
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

        groups = conn.execute(
            """
            SELECT DISTINCT users.student_group
            FROM users
            WHERE users.role = 'student'
              AND users.student_group IS NOT NULL
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

    # -------------------------------------------------
    # 2. Основной запрос попыток
    # -------------------------------------------------

    sql = """
        SELECT
            submissions.id,
            submissions.lab_id,
            submissions.username,
            submissions.status,
            submissions.score,
            submissions.attempt_number,
            submissions.error_type,
            submissions.error_title,
            submissions.created_at,

            labs.title AS lab_title,
            labs.discipline AS discipline,
            labs.topic AS lab_topic,
            labs.created_by AS lab_created_by,

            users.full_name AS full_name,
            users.student_group AS student_group
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        LEFT JOIN users ON users.username = submissions.username
        WHERE 1 = 1
    """

    params = []

    if not is_admin:
        sql += """
            AND (
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
        params.extend([
            current_username,
            current_username
        ])

    if selected_discipline:
        sql += " AND labs.discipline = ?"
        params.append(selected_discipline)

    if selected_lab_id:
        sql += " AND labs.id = ?"
        params.append(selected_lab_id)

    if selected_group:
        sql += " AND users.student_group = ?"
        params.append(selected_group)

    if date_from:
        sql += " AND submissions.created_at >= ?"
        params.append(date_from + " 00:00:00")

    if date_to:
        sql += " AND submissions.created_at <= ?"
        params.append(date_to + " 23:59:59")

    sql += """
        ORDER BY submissions.created_at ASC, submissions.id ASC
    """

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    attempts = [dict(row) for row in rows]

    # -------------------------------------------------
    # 3. Группировка по студенту и лабораторной
    # -------------------------------------------------

    student_lab_map = {}

    for attempt in attempts:
        key = (attempt["username"], attempt["lab_id"])

        if key not in student_lab_map:
            student_lab_map[key] = {
                "username": attempt["username"],
                "full_name": attempt["full_name"] or attempt["username"],
                "student_group": attempt["student_group"] or "—",
                "lab_id": attempt["lab_id"],
                "lab_title": attempt["lab_title"],
                "discipline": attempt["discipline"] or "—",
                "topic": normalize_lab_topic_for_analytics(
                    attempt["lab_topic"],
                    attempt["lab_title"]
                ),
                "attempts": []
            }

        student_lab_map[key]["attempts"].append(attempt)

    student_lab_results = []

    for item in student_lab_map.values():
        item_attempts = item["attempts"]

        item_attempts.sort(
            key=lambda row: int(row["attempt_number"] or 1)
        )

        best_score = max(int(row["score"] or 0) for row in item_attempts)
        attempts_count = len(item_attempts)

        passed_attempts = [
            row for row in item_attempts
            if row["status"] == "PASSED"
        ]

        is_passed = len(passed_attempts) > 0

        first_attempt = item_attempts[0]
        first_try_passed = first_attempt["status"] == "PASSED"

        last_attempt = item_attempts[-1]

        student_lab_results.append({
            "username": item["username"],
            "full_name": item["full_name"],
            "student_group": item["student_group"],
            "lab_id": item["lab_id"],
            "lab_title": item["lab_title"],
            "discipline": item["discipline"],
            "topic": item["topic"],
            "topic_display": get_topic_display_name(item["topic"]),
            "best_score": best_score,
            "attempts_count": attempts_count,
            "is_passed": is_passed,
            "first_try_passed": first_try_passed,
            "last_status": last_attempt["status"],
            "last_created_at": last_attempt["created_at"]
        })

    # -------------------------------------------------
    # 4. Общие показатели
    # -------------------------------------------------

    total_students = len(set(row["username"] for row in attempts))
    total_submissions = len(attempts)
    total_student_lab_pairs = len(student_lab_results)

    if student_lab_results:
        average_score = round(
            sum(item["best_score"] for item in student_lab_results)
            / len(student_lab_results),
            1
        )

        average_attempts = round(
            sum(item["attempts_count"] for item in student_lab_results)
            / len(student_lab_results),
            2
        )

        success_count = sum(1 for item in student_lab_results if item["is_passed"])
        first_try_count = sum(1 for item in student_lab_results if item["first_try_passed"])

        success_percent = round(success_count * 100 / len(student_lab_results), 1)
        first_try_percent = round(first_try_count * 100 / len(student_lab_results), 1)

    else:
        average_score = 0
        average_attempts = 0
        success_count = 0
        first_try_count = 0
        success_percent = 0
        first_try_percent = 0

    overview = {
        "total_students": total_students,
        "total_submissions": total_submissions,
        "total_student_lab_pairs": total_student_lab_pairs,
        "average_score": average_score,
        "average_attempts": average_attempts,
        "success_count": success_count,
        "first_try_count": first_try_count,
        "success_percent": success_percent,
        "first_try_percent": first_try_percent
    }

    # -------------------------------------------------
    # 5. Аналитика по лабораторным
    # -------------------------------------------------

    lab_map = {}

    for result in student_lab_results:
        lab_id = result["lab_id"]

        if lab_id not in lab_map:
            lab_map[lab_id] = {
                "lab_id": lab_id,
                "lab_title": result["lab_title"],
                "discipline": result["discipline"],
                "topic": result["topic"],
                "topic_display": result["topic_display"],
                "students_count": 0,
                "best_scores": [],
                "attempts_counts": [],
                "passed_count": 0,
                "first_try_count": 0,
                "errors_count": 0
            }

        lab_item = lab_map[lab_id]
        lab_item["students_count"] += 1
        lab_item["best_scores"].append(result["best_score"])
        lab_item["attempts_counts"].append(result["attempts_count"])

        if result["is_passed"]:
            lab_item["passed_count"] += 1

        if result["first_try_passed"]:
            lab_item["first_try_count"] += 1

    for attempt in attempts:
        if attempt["error_type"] and attempt["error_type"] != "NO_ERROR":
            lab_id = attempt["lab_id"]

            if lab_id in lab_map:
                lab_map[lab_id]["errors_count"] += 1

    lab_analytics = []

    for lab_item in lab_map.values():
        students_count = lab_item["students_count"]

        if students_count > 0:
            avg_score = round(sum(lab_item["best_scores"]) / students_count, 1)
            avg_attempts = round(sum(lab_item["attempts_counts"]) / students_count, 2)
            success_percent_lab = round(lab_item["passed_count"] * 100 / students_count, 1)
            first_try_percent_lab = round(lab_item["first_try_count"] * 100 / students_count, 1)
        else:
            avg_score = 0
            avg_attempts = 0
            success_percent_lab = 0
            first_try_percent_lab = 0

        difficulty_index = round(
            (100 - avg_score)
            + avg_attempts * 10
            + lab_item["errors_count"] * 2,
            1
        )

        lab_analytics.append({
            "lab_id": lab_item["lab_id"],
            "lab_title": lab_item["lab_title"],
            "discipline": lab_item["discipline"],
            "topic_display": lab_item["topic_display"],
            "students_count": students_count,
            "avg_score": avg_score,
            "avg_attempts": avg_attempts,
            "success_percent": success_percent_lab,
            "first_try_percent": first_try_percent_lab,
            "errors_count": lab_item["errors_count"],
            "difficulty_index": difficulty_index
        })

    lab_analytics.sort(
        key=lambda item: item["difficulty_index"],
        reverse=True
    )

    hardest_lab = lab_analytics[0] if lab_analytics else None

    # -------------------------------------------------
    # 6. Ошибки по типам и темам
    # -------------------------------------------------

    error_map = {}
    topic_error_map = {}

    for attempt in attempts:
        error_type = attempt["error_type"] or ""
        error_title = attempt["error_title"] or ""

        if not error_type or error_type == "NO_ERROR":
            continue

        topic = normalize_lab_topic_for_analytics(
            attempt["lab_topic"],
            attempt["lab_title"]
        )

        error_key = (error_type, error_title)

        if error_key not in error_map:
            error_map[error_key] = {
                "error_type": error_type,
                "error_title": error_title or error_type,
                "count": 0
            }

        error_map[error_key]["count"] += 1

        topic_key = (topic, error_type, error_title)

        if topic_key not in topic_error_map:
            topic_error_map[topic_key] = {
                "topic": topic,
                "topic_display": get_topic_display_name(topic),
                "error_type": error_type,
                "error_title": error_title or error_type,
                "count": 0
            }

        topic_error_map[topic_key]["count"] += 1

    common_errors = sorted(
        error_map.values(),
        key=lambda item: item["count"],
        reverse=True
    )[:10]

    topic_error_rows = sorted(
        topic_error_map.values(),
        key=lambda item: item["count"],
        reverse=True
    )[:15]

    # -------------------------------------------------
    # 7. Динамика успеваемости
    # -------------------------------------------------

    dynamics_map = {}

    for attempt in attempts:
        created_at = attempt["created_at"] or ""

        if len(created_at) >= 10:
            day = created_at[:10]
        else:
            day = "—"

        if day not in dynamics_map:
            dynamics_map[day] = {
                "date": day,
                "scores": [],
                "submissions_count": 0,
                "passed_count": 0
            }

        dynamics_map[day]["scores"].append(int(attempt["score"] or 0))
        dynamics_map[day]["submissions_count"] += 1

        if attempt["status"] == "PASSED":
            dynamics_map[day]["passed_count"] += 1

    dynamics_rows = []

    for item in dynamics_map.values():
        if item["scores"]:
            avg_day_score = round(sum(item["scores"]) / len(item["scores"]), 1)
        else:
            avg_day_score = 0

        if item["submissions_count"] > 0:
            day_success_percent = round(
                item["passed_count"] * 100 / item["submissions_count"],
                1
            )
        else:
            day_success_percent = 0

        dynamics_rows.append({
            "date": item["date"],
            "avg_score": avg_day_score,
            "submissions_count": item["submissions_count"],
            "success_percent": day_success_percent
        })

    dynamics_rows.sort(key=lambda item: item["date"])

    # -------------------------------------------------
    # 8. Рендер страницы
    # -------------------------------------------------

    return render_template(
        "teacher/analytics.html",
        overview=overview,
        lab_analytics=lab_analytics,
        hardest_lab=hardest_lab,
        common_errors=common_errors,
        topic_error_rows=topic_error_rows,
        dynamics_rows=dynamics_rows,
        disciplines=disciplines,
        groups=groups,
        labs_for_filter=labs_for_filter,
        selected_discipline=selected_discipline,
        selected_lab_id=selected_lab_id,
        selected_group=selected_group,
        date_from=date_from,
        date_to=date_to
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

        attempts_info = get_attempts_info(
            conn=conn,
            lab=lab,
            username=student["username"]
        )

        cells.append({
            "lab_id": lab["id"],
            "display_score": display_score,
            "auto_score": auto_score,
            "manual_score": manual_score,
            "grade_source": grade_source,
            "manual_comment": manual_comment,
            "edited_by": edited_by,
            "edited_at": edited_at,

            "attempts_count": attempts_info["used_attempts"],
            "last_status": last_status,
            "last_created_at": last_created_at,

            "used_attempts": attempts_info["used_attempts"],
            "base_limit": attempts_info["base_limit"],
            "extra_attempts": attempts_info["extra_attempts"],
            "total_limit": attempts_info["total_limit"],
            "attempts_left": attempts_info["attempts_left"],
            "is_limit_reached": attempts_info["is_limit_reached"],
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


@app.route("/teacher/attempts/grant", methods=["POST"])
@teacher_required
def teacher_grant_extra_attempt():

    if session.get("role") not in ["teacher", "admin"]:
        flash("Выдавать дополнительные попытки может только преподаватель или администратор.")
        return redirect(url_for("index"))
    
    lab_id = request.form.get("lab_id", type=int) or request.args.get("lab_id", type=int)

    username = (
        request.form.get("username")
        or request.args.get("username")
        or ""
    ).strip()

    reason = (
        request.form.get("reason")
        or request.args.get("reason")
        or ""
    ).strip()

    if not lab_id or not username:
        flash("Не удалось определить лабораторную работу или студента.")
        return redirect(request.referrer or url_for("teacher_journal"))

    if not reason:
        reason = "Дополнительная попытка выдана преподавателем."

    conn = get_db()

    lab = conn.execute(
        """
        SELECT *
        FROM labs
        WHERE id = ?
        """,
        (lab_id,)
    ).fetchone()

    student = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
          AND role = 'student'
        """,
        (username,)
    ).fetchone()

    if not lab or not student:
        conn.close()
        flash("Лабораторная работа или студент не найдены.")
        return redirect(request.referrer or url_for("teacher_journal"))

    conn.execute(
        """
        INSERT INTO attempt_overrides
        (lab_id, username, extra_attempts, reason, granted_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            lab_id,
            username,
            1,
            reason,
            session["username"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

    flash(f"Студенту {username} добавлена 1 дополнительная попытка.")
    return redirect(request.referrer or url_for("teacher_journal"))


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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        student_group = request.form.get("student_group", "").strip()

        if not username or not password or not full_name or not student_group:
            conn.close()
            flash("Нужно заполнить все поля.")
            return redirect(url_for("manage_students"))

        password_ok, password_error = validate_password_strength(password, username)

        if not password_ok:
            conn.close()
            flash(password_error)
            return redirect(url_for("manage_students"))

        password_hash = hash_password(password)

        try:
            conn.execute(
                """
                INSERT INTO users (username, password, role, full_name, student_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password_hash, "student", full_name, student_group)
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
        username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        student_group = request.form.get("student_group", "").strip()

        if not username or not full_name or not student_group:
            conn.close()
            flash("Нужно заполнить логин, ФИО и группу.")
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

        if new_password:
            password_ok, password_error = validate_password_strength(
                new_password,
                username
            )

            if not password_ok:
                conn.close()
                flash(password_error)
                return redirect(url_for("edit_student", user_id=user_id))

            password_hash = hash_password(new_password)

            conn.execute(
                """
                UPDATE users
                SET username = ?,
                    password = ?,
                    full_name = ?,
                    student_group = ?
                WHERE id = ? AND role = 'student'
                """,
                (
                    username,
                    password_hash,
                    full_name,
                    student_group,
                    user_id
                )
            )

        else:
            conn.execute(
                """
                UPDATE users
                SET username = ?,
                    full_name = ?,
                    student_group = ?
                WHERE id = ? AND role = 'student'
                """,
                (
                    username,
                    full_name,
                    student_group,
                    user_id
                )
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

            conn.execute(
                """
                UPDATE extra_task_attempts
                SET username = ?
                WHERE username = ?
                """,
                (username, old_username)
            )

            conn.execute(
                """
                UPDATE grade_overrides
                SET username = ?
                WHERE username = ?
                """,
                (username, old_username)
            )

            conn.execute(
                """
                UPDATE subject_final_grades
                SET username = ?
                WHERE username = ?
                """,
                (username, old_username)
            )

            conn.execute(
                """
                UPDATE attempt_overrides
                SET username = ?
                WHERE username = ?
                """,
                (username, old_username)
            )

        conn.commit()
        conn.close()

        flash("Данные студента обновлены.")
        return redirect(url_for("manage_students"))


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
    public_testbench = request.form.get("public_testbench", "").strip()
    hidden_testbench = request.form.get("hidden_testbench", "").strip()
    show_hidden_details = 1 if request.form.get("show_hidden_details") == "on" else 0

    testbench = public_testbench

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

    if not title or not description or not public_testbench:
        flash("Нужно заполнить название, описание и открытый testbench.")
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
            public_testbench,
            hidden_testbench,
            show_hidden_details,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            testbench,
            public_testbench,
            hidden_testbench,
            show_hidden_details,
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
        public_testbench = request.form.get("public_testbench", "").strip()
        hidden_testbench = request.form.get("hidden_testbench", "").strip()
        show_hidden_details = 1 if request.form.get("show_hidden_details") == "on" else 0

        testbench = public_testbench

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

        if not title or not description or not public_testbench:
            conn.close()
            flash("Название, описание и открытый testbench обязательны для заполнения.")
            return redirect(url_for("edit_lab", lab_id=lab_id))

        conn.execute(
            """
            UPDATE labs
            SET title = ?,
                description = ?,
                testbench = ?,
                public_testbench = ?,
                hidden_testbench = ?,
                show_hidden_details = ?,
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
                public_testbench,
                hidden_testbench,
                show_hidden_details,
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

    lab = conn.execute(
        """
        SELECT *
        FROM labs
        WHERE id = ?
        """,
        (lab_id,)
    ).fetchone()

    if not lab:
        conn.close()
        flash("Лабораторная работа не найдена.")
        return redirect(url_for("teacher_panel"))

    submissions = conn.execute(
        """
        SELECT id, filename, waveform_filename
        FROM submissions
        WHERE lab_id = ?
        """,
        (lab_id,)
    ).fetchall()

    # 1. Сначала удаляем физические файлы решений и временных диаграмм.
    for submission in submissions:
        delete_uploaded_file(submission["filename"])
        delete_waveform_file(submission["waveform_filename"])

    # 2. Удаляем дополнительные ответы, связанные с попытками этой лабораторной.
    for submission in submissions:
        conn.execute(
            """
            DELETE FROM extra_task_attempts
            WHERE submission_id = ?
            """,
            (submission["id"],)
        )

    # 3. Удаляем ручные оценки по этой лабораторной.
    conn.execute(
        """
        DELETE FROM grade_overrides
        WHERE lab_id = ?
        """,
        (lab_id,)
    )

    # 4. Удаляем выданные дополнительные попытки по этой лабораторной.
    conn.execute(
        """
        DELETE FROM attempt_overrides
        WHERE lab_id = ?
        """,
        (lab_id,)
    )

    # 5. Удаляем сами попытки студентов.
    conn.execute(
        """
        DELETE FROM submissions
        WHERE lab_id = ?
        """,
        (lab_id,)
    )

    # 6. Удаляем лабораторную работу.
    conn.execute(
        """
        DELETE FROM labs
        WHERE id = ?
        """,
        (lab_id,)
    )

    conn.commit()
    conn.close()

    flash("Лабораторная работа удалена вместе с попытками, файлами решений и временными диаграммами.")
    return redirect(url_for("teacher_panel"))


# =========================
# 17. App start
# =========================

if __name__ == "__main__":
    init_db()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
