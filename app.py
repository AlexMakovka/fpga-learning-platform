import ast
import math
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus, urlparse
from urllib.parse import urljoin

import requests
from authlib.integrations.flask_client import OAuth
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Підтримка OpenAI є опціональною: система може працювати без цього пакета,
# наприклад, якщо для AI-функцій використовується інший провайдер.
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# Абсолютний шлях до каталогу, у якому розташований app.py.
# Використовується як базовий шлях для конфігураційних і локальних файлів.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Конфігурація зберігається поза вихідним кодом, щоб не розміщувати
# секретні ключі та інші параметри серед файлів програмної реалізації.
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

# Обмеження розміру HTTP-запиту зменшує ризик передавання надмірно великих
# файлів або фрагментів коду. 256 КБ достатньо для навчальних HDL/Python-файлів.
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

# Окреме обмеження застосовується до коду, переданого через вбудований редактор.
# Воно не залежить від загального обмеження HTTP-запиту та перевіряється
# на рівні прикладної логіки.
MAX_EDITOR_CODE_LENGTH = 100_000

# Мінімальний бал для зарахування лабораторної роботи в журналі.
JOURNAL_PASSING_SCORE = 60

# Секретний ключ Flask отримується лише з конфігурації середовища.
# Запуск без нього заборонено, оскільки ключ використовується для захисту сесій.
app.secret_key = os.getenv("SECRET_KEY", "").strip()

if not app.secret_key:
    raise RuntimeError("SECRET_KEY не задано у файлі .env")

# OAuth-клієнт використовується для інтеграції із зовнішніми
# постачальниками автентифікації, зокрема Google.
oauth = OAuth(app)

# Облікові дані Google OAuth отримуються з конфігурації середовища
# та не зберігаються безпосередньо у вихідному коді.
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


# Основні каталоги локального зберігання даних і артефактів.
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
WAVEFORM_DIR = os.path.join(BASE_DIR, "waveforms")

PROFILE_AVATAR_DIR = os.path.join(
    BASE_DIR,
    "profile_avatars",
)

PROFILE_AVATAR_MAX_BYTES = 220 * 1024

# ============================================================
# Профіль користувача / гейміфікація
# ============================================================

PROFILE_AVATARS = {
    "initials": {
        "name": "Стандартний",
        "description": "Ініціали користувача",
        "required_points": 0,
        "symbol": "",
        "css_class": "profile-avatar-default",
    },

    "chip": {
        "name": "Silicon Rookie",
        "description": "Перші кроки у FPGA",
        "required_points": 100,
        "symbol": "◈",
        "css_class": "profile-avatar-chip",
    },

    "pulse": {
        "name": "Signal Rider",
        "description": "Сигнали вже під контролем",
        "required_points": 250,
        "symbol": "⌁",
        "css_class": "profile-avatar-pulse",
    },

    "wizard": {
        "name": "HDL Wizard",
        "description": "Магія Verilog",
        "required_points": 500,
        "symbol": "⚡",
        "css_class": "profile-avatar-wizard",
    },

    "legend": {
        "name": "FPGA Legend",
        "description": "Легендарний профіль",
        "required_points": 1000,
        "symbol": "★",
        "css_class": "profile-avatar-legend",
    },
}


PROFILE_FRAMES = {
    "none": {
        "name": "Без рамки",
        "required_points": 0,
        "css_class": "profile-frame-none",
    },

    "signal": {
        "name": "Signal Blue",
        "required_points": 150,
        "css_class": "profile-frame-signal",
    },

    "neon": {
        "name": "Neon Circuit",
        "required_points": 400,
        "css_class": "profile-frame-neon",
    },

    "gold": {
        "name": "Golden FPGA",
        "required_points": 750,
        "css_class": "profile-frame-gold",
    },
}


PROFILE_BADGES = {
    "none": {
        "name": "Без значка",
        "required_points": 0,
        "symbol": "",
    },

    "rookie": {
        "name": "FPGA Rookie",
        "required_points": 100,
        "symbol": "R",
    },

    "debugger": {
        "name": "Bug Hunter",
        "required_points": 350,
        "symbol": "B",
    },

    "master": {
        "name": "HDL Master",
        "required_points": 800,
        "symbol": "M",
    },
}


# =========================
# Зовнішні API та AI-модулі
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

LEARNING_PATH_MODE = os.getenv(
    "LEARNING_PATH_MODE",
    "free",
).strip().lower()

TRAINER_AI_MODE = os.getenv(
    "TRAINER_AI_MODE",
    "template",
).strip().lower()

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5-coder:7b",
).strip()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate",
).strip()


# ==========================================
# Локальні інструменти HDL-перевірки Windows
# ==========================================

# Шляхи використовуються для локального запуску Verilator та Yosys.
# Значення можуть бути перевизначені через .env відповідно до середовища
# розгортання системи.
VERILATOR_PERL_PATH = os.getenv(
    "VERILATOR_PERL_PATH",
    r"Y:\MSYS2\usr\bin\perl.exe",
)

VERILATOR_SCRIPT_PATH = os.getenv(
    "VERILATOR_SCRIPT_PATH",
    r"Y:\MSYS2\ucrt64\bin\verilator",
)

VERILATOR_UCRT_BIN = os.getenv(
    "VERILATOR_UCRT_BIN",
    r"Y:\MSYS2\ucrt64\bin",
)

VERILATOR_USR_BIN = os.getenv(
    "VERILATOR_USR_BIN",
    r"Y:\MSYS2\usr\bin",
)

YOSYS_EXE_PATH = os.getenv(
    "YOSYS_EXE_PATH",
    r"Y:\MSYS2\ucrt64\bin\yosys.exe",
)

YOSYS_UCRT_BIN = os.getenv(
    "YOSYS_UCRT_BIN",
    r"Y:\MSYS2\ucrt64\bin",
)

YOSYS_USR_BIN = os.getenv(
    "YOSYS_USR_BIN",
    r"Y:\MSYS2\usr\bin",
)


# =========================
# Перевірка Python-коду
# =========================

# Docker-образ використовується для ізольованого виконання Python-коду.
PYTHON_DOCKER_IMAGE = "fpga-python-checker:latest"

# Максимальна тривалість однієї перевірки запобігає нескінченному
# або надмірно тривалому виконанню користувацького коду.
PYTHON_CHECK_TIMEOUT_SECONDS = 15


# =========================
# Перевірка HDL-коду
# =========================

# Режими визначають спосіб запуску основної HDL-перевірки та lint-аналізу.
# Docker-режим використовується для ізоляції виконання користувацького HDL-коду.
HDL_CHECK_MODE = os.getenv(
    "HDL_CHECK_MODE",
    "docker",
).strip().lower()

HDL_LINT_MODE = os.getenv(
    "HDL_LINT_MODE",
    "docker",
).strip().lower()

HDL_DOCKER_IMAGE = os.getenv(
    "HDL_DOCKER_IMAGE",
    "fpga-hdl-checker:latest",
).strip()


def get_int_env(name: str, default: int) -> int:
    """Повертає ціле значення змінної середовища або значення за замовчуванням."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# Окремі таймаути обмежують тривалість компіляції та моделювання HDL-коду.
# Це запобігає зависанню зовнішніх інструментів під час автоматичної перевірки.
HDL_COMPILE_TIMEOUT_SECONDS = get_int_env(
    "HDL_COMPILE_TIMEOUT_SECONDS",
    10,
)

HDL_SIM_TIMEOUT_SECONDS = get_int_env(
    "HDL_SIM_TIMEOUT_SECONDS",
    10,
)


# Каталоги створюються під час запуску застосунку. UPLOAD_DIR використовується
# для завантажених файлів, а WAVEFORM_DIR — для дозволених VCD-артефактів.
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(WAVEFORM_DIR, exist_ok=True)

os.makedirs(
    PROFILE_AVATAR_DIR,
    exist_ok=True,
)


# =========================
# 1. Робота з базою даних
# =========================

def get_db() -> sqlite3.Connection:
    """Створює з'єднання з локальною базою даних SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# Захист POST-запитів від CSRF
# ============================================================

def generate_csrf_token() -> str:
    """Створює та повертає CSRF-токен, пов'язаний із поточною сесією."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


@app.context_processor
def inject_csrf_token() -> dict:
    """Надає функцію формування CSRF-токена HTML-шаблонам."""
    return {"csrf_token": generate_csrf_token}


@app.before_request
def csrf_protect() -> None:
    """Перевіряє CSRF-токен для POST-запитів, що змінюють стан системи."""
    if request.method != "POST":
        return None

    session_token = session.get("csrf_token", "")
    form_token = request.form.get("csrf_token", "")
    header_token = request.headers.get("X-CSRFToken", "")

    # Для HTML-форм токен передається у полі форми, а для AJAX-запитів
    # може надходити через HTTP-заголовок X-CSRFToken.
    submitted_token = form_token or header_token

    if not session_token or not submitted_token:
        abort(400, description="CSRF-токен відсутній.")

    # compare_digest використовується замість звичайного порівняння,
    # щоб уникнути залежності часу виконання від збігу частини токена.
    if not hmac.compare_digest(session_token, submitted_token):
        abort(400, description="Недійсний CSRF-токен.")

    return None


# ============================================================
# Спроби виконання лабораторних робіт
# ============================================================

def get_extra_attempts_count(
    conn: sqlite3.Connection,
    lab_id: int,
    username: str,
) -> int:
    """Повертає кількість додаткових спроб, наданих користувачу для лабораторної роботи."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(extra_attempts), 0) AS extra_attempts
        FROM attempt_overrides
        WHERE lab_id = ?
          AND username = ?
        """,
        (lab_id, username),
    ).fetchone()

    if not row:
        return 0

    return int(row["extra_attempts"] or 0)


def get_used_attempts_count(
    conn: sqlite3.Connection,
    lab_id: int,
    username: str,
) -> int:
    """Повертає кількість збережених спроб користувача для лабораторної роботи."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS attempts_count
        FROM submissions
        WHERE lab_id = ?
          AND username = ?
        """,
        (lab_id, username),
    ).fetchone()

    if not row:
        return 0

    return int(row["attempts_count"] or 0)


def get_attempts_info(
    conn: sqlite3.Connection,
    lab,
    username: str,
) -> dict:
    """Формує поточний стан ліміту спроб для користувача та лабораторної роботи."""
    lab_id = lab["id"]
    base_limit = int(lab["max_attempts"] or 0)

    used_attempts = get_used_attempts_count(conn, lab_id, username)
    extra_attempts = get_extra_attempts_count(conn, lab_id, username)

    # Підсумковий ліміт складається з базової кількості спроб,
    # визначеної для лабораторної роботи, та додаткових спроб,
    # індивідуально наданих користувачу викладачем.
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
        "is_limit_reached": (
            total_limit > 0
            and used_attempts >= total_limit
        ),
    }


# ============================================================
# Робота з паролями
# ============================================================

def password_is_hashed(password_value: str) -> bool:
    """Перевіряє, чи має значення формат підтримуваного хешу пароля."""
    password_value = str(password_value or "")

    return (
        password_value.startswith("scrypt:")
        or password_value.startswith("pbkdf2:")
        or password_value.startswith("argon2:")
    )


def hash_password(raw_password: str) -> str:
    """Створює захищений хеш пароля засобами Werkzeug."""
    return generate_password_hash(str(raw_password))


def verify_password(stored_password: str, raw_password: str) -> bool:
    """Перевіряє введений пароль з урахуванням міграції застарілих записів."""
    stored_password = str(stored_password or "")
    raw_password = str(raw_password or "")

    if not stored_password or not raw_password:
        return False

    if password_is_hashed(stored_password):
        try:
            return check_password_hash(stored_password, raw_password)
        except Exception:
            return False

    # Тимчасова підтримка застарілих записів, у яких пароль зберігався
    # у відкритому вигляді. Після успішної автентифікації такий пароль
    # має бути замінений на його хешоване представлення.
    return stored_password == raw_password


def validate_password_strength(
    password: str,
    username: str = "",
) -> tuple[bool, str]:
    """Перевіряє пароль відповідно до базових вимог безпеки системи."""
    password = str(password or "")
    username = str(username or "").lower()

    errors = []

    if not password:
        errors.append("Пароль не може бути порожнім.")

    if password.strip() != password:
        errors.append(
            "Пароль не повинен починатися або закінчуватися пробілом."
        )

    if len(password) < 8:
        errors.append("Пароль повинен містити щонайменше 8 символів.")

    # isalpha() коректно враховує українські та інші Unicode-літери,
    # на відміну від явного переліку діапазонів латиниці й кирилиці.
    if not any(char.isalpha() for char in password):
        errors.append("Пароль повинен містити щонайменше одну літеру.")

    if not re.search(r"\d", password):
        errors.append("Пароль повинен містити щонайменше одну цифру.")

    if username and username in password.lower():
        errors.append("Пароль не повинен містити логін користувача.")

    if errors:
        return False, " ".join(errors)

    return True, ""

# ============================================================
# Розрахунок підсумкової оцінки за лабораторну роботу
# ============================================================

def clamp_score(value) -> int:
    """Перетворює значення оцінки на ціле число в діапазоні від 0 до 100."""
    try:
        value = int(round(float(value or 0)))
    except (TypeError, ValueError, OverflowError):
        value = 0

    return max(0, min(100, value))


def map_score_to_ukrainian_ects(score) -> dict:
    """Перетворює числову оцінку на оцінку ECTS і національну оцінку."""
    score = clamp_score(score)

    if score >= 90:
        return {
            "ects_grade": "A",
            "national_grade": "відмінно",
            "final_status": "Зараховано",
        }

    if score >= 82:
        return {
            "ects_grade": "B",
            "national_grade": "добре",
            "final_status": "Зараховано",
        }

    if score >= 74:
        return {
            "ects_grade": "C",
            "national_grade": "добре",
            "final_status": "Зараховано",
        }

    if score >= 64:
        return {
            "ects_grade": "D",
            "national_grade": "задовільно",
            "final_status": "Зараховано",
        }

    if score >= 60:
        return {
            "ects_grade": "E",
            "national_grade": "задовільно",
            "final_status": "Зараховано",
        }

    if score >= 35:
        return {
            "ects_grade": "FX",
            "national_grade": "незадовільно, потребує доопрацювання",
            "final_status": "Потребує доопрацювання",
        }

    return {
        "ects_grade": "F",
        "national_grade": "незадовільно, потребує повторного виконання",
        "final_status": "Не зараховано",
    }


def get_component_score(score, status=None):
    """Повертає оцінку компонента або None, якщо результат технічно недоступний."""
    score = clamp_score(score)

    if status in {"UNAVAILABLE", "SYSTEM_ERROR", "TIMEOUT"}:
        return None

    return score


def build_lab_final_grade(
    testbench_score,
    lint_score,
    synth_score,
    questions_score=0,
    has_questions=False,
    lint_status="OK",
    synth_status="OK",
) -> dict:
    """Формує підсумкову оцінку лабораторної роботи з окремих компонентів."""
    testbench_score = clamp_score(testbench_score)
    questions_score = clamp_score(questions_score)

    lint_component = get_component_score(lint_score, lint_status)
    synth_component = get_component_score(synth_score, synth_status)

    if has_questions:
        weights = {
            "testbench": 70,
            "lint": 10,
            "synthesis": 10,
            "questions": 10,
        }
    else:
        weights = {
            "testbench": 70,
            "lint": 15,
            "synthesis": 15,
            "questions": 0,
        }

    # Якщо lint або synthesis недоступні через системну відмову,
    # їхня вага переноситься до функціональної перевірки testbench.
    # Це запобігає зниженню оцінки студента через помилку інфраструктури.
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

    # Функціональна коректність є обов'язковою умовою зарахування:
    # якщо результат testbench нижчий за 60 балів, лабораторна робота
    # потребує доопрацювання незалежно від сумарної оцінки.
    if testbench_score < 60:
        mapped_grade["final_status"] = "Потребує доопрацювання"

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
        "testbench_rule_applied": testbench_score < 60,
    }

    return {
        "final_score": final_score,
        "ects_grade": mapped_grade["ects_grade"],
        "national_grade": mapped_grade["national_grade"],
        "final_status": mapped_grade["final_status"],
        "grading_breakdown": grading_breakdown,
    }


# ============================================================
# Ініціалізація структури бази даних
# ============================================================

def init_db():
    """
    Ініціалізує структуру бази даних і виконує сумісні міграції
    для баз даних, створених попередніми версіями системи.
    """
    conn = get_db()
    cur = conn.cursor()

    # Основна таблиця облікових записів студентів, викладачів
    # та адміністраторів системи.
    cur.execute(
        """
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
        """
    )

    # Перевірка фактичної схеми дає змогу оновлювати раніше створену
    # базу даних без видалення наявних облікових записів.
    user_columns = cur.execute("PRAGMA table_info(users)").fetchall()
    user_column_names = [column["name"] for column in user_columns]

    # Поля автентифікації через Google OAuth додаються для сумісності
    # з базами даних, створеними до впровадження зовнішньої авторизації.
    if "google_id" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN google_id TEXT DEFAULT ''"
        )

    if "auth_provider" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN auth_provider TEXT DEFAULT 'local'"
        )

    if "email" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''"
        )

    if "status" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'"
        )

    if "created_at" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT ''"
        )

    if "approved_by" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN approved_by TEXT DEFAULT ''"
        )

    if "full_name" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''"
        )

    if "student_group" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN student_group TEXT DEFAULT ''"
        )

    # Персональні параметри інтерфейсу також додаються через міграцію,
    # щоб оновлення застосунку не вимагало повторного створення бази даних.
    if "theme" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'light'"
        )

    if "palette" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN palette TEXT DEFAULT 'pastel'"
        )

    if "font_size" not in user_column_names:
        cur.execute(
            "ALTER TABLE users ADD COLUMN font_size TEXT DEFAULT 'normal'"
        )

    if "ui_density" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN ui_density TEXT DEFAULT 'comfortable'"
        )

    if "first_login_completed" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN first_login_completed INTEGER DEFAULT 0"
        )

    if "show_beginner_tips" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN show_beginner_tips INTEGER DEFAULT 1"
        )

    if "avatar_filename" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN avatar_filename TEXT DEFAULT ''"
        )

    if "profile_status" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_status TEXT DEFAULT ''"
        )

    if "profile_bio" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_bio TEXT DEFAULT ''"
        )

    if "profile_signature" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_signature TEXT DEFAULT ''"
        )

    if "profile_avatar" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_avatar TEXT DEFAULT 'initials'"
        )

    if "profile_frame" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_frame TEXT DEFAULT 'none'"
        )

    if "profile_badge" not in user_column_names:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN profile_badge TEXT DEFAULT 'none'"
        )


    # Нормалізація забезпечує коректні значення для користувачів,
    # створених до появи персональних параметрів інтерфейсу.
    cur.execute(
        """
        UPDATE users
        SET show_beginner_tips = 1
        WHERE show_beginner_tips IS NULL
        """
    )

    cur.execute(
        """
        UPDATE users
        SET theme = 'light'
        WHERE theme IS NULL OR theme = ''
        """
    )

    cur.execute(
        """
        UPDATE users
        SET palette = 'pastel'
        WHERE palette IS NULL OR palette = ''
        """
    )

    cur.execute(
        """
        UPDATE users
        SET font_size = 'normal'
        WHERE font_size IS NULL OR font_size = ''
        """
    )

    cur.execute(
        """
        UPDATE users
        SET ui_density = 'comfortable'
        WHERE ui_density IS NULL OR ui_density = ''
        """
    )

    cur.execute(
        """
        UPDATE users
        SET first_login_completed = 0
        WHERE first_login_completed IS NULL
        """
    )

    cur.execute(
        """
        UPDATE users
        SET avatar_filename = ''
        WHERE avatar_filename IS NULL
        """
    )

# ============================================================
# Таблиця лабораторних робіт
# ============================================================

# Таблиця зберігає опис лабораторної роботи, відкриті та приховані
# testbench, параметри перевірки й налаштування оцінювання.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            testbench TEXT NOT NULL,

            public_testbench TEXT DEFAULT '',
            hidden_testbench TEXT DEFAULT '',
            show_hidden_details INTEGER DEFAULT 0,

            discipline TEXT DEFAULT 'FPGA-проєктування',
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
        """
    )

# Перевірка фактичної схеми дає змогу оновлювати лабораторні роботи,
# створені попередніми версіями системи, без втрати наявних даних.
    columns = cur.execute("PRAGMA table_info(labs)").fetchall()
    column_names = [column["name"] for column in columns]

    if "public_testbench" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN public_testbench TEXT DEFAULT ''"
        )

    if "hidden_testbench" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN hidden_testbench TEXT DEFAULT ''"
        )

    if "show_hidden_details" not in column_names:
        cur.execute(
            "ALTER TABLE labs "
            "ADD COLUMN show_hidden_details INTEGER DEFAULT 0"
        )

    if "discipline" not in column_names:
        cur.execute(
            "ALTER TABLE labs "
            "ADD COLUMN discipline TEXT DEFAULT 'FPGA-проєктування'"
        )

    if "programming_language" not in column_names:
        cur.execute(
            "ALTER TABLE labs "
            "ADD COLUMN programming_language TEXT DEFAULT 'Verilog'"
        )

    if "checker_type" not in column_names:
        cur.execute(
            "ALTER TABLE labs "
            "ADD COLUMN checker_type TEXT DEFAULT 'hdl_testbench'"
        )

    if "topic" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN topic TEXT DEFAULT ''"
        )

    if "difficulty" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN difficulty TEXT DEFAULT 'basic'"
        )

    if "concepts" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN concepts TEXT DEFAULT ''"
        )

    if "grading_policy" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN grading_policy TEXT DEFAULT ''"
        )

    if "starter_code" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN starter_code TEXT DEFAULT ''"
        )

    if "max_attempts" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN max_attempts INTEGER DEFAULT 3"
        )

    if "allow_extra_questions" not in column_names:
        cur.execute(
            "ALTER TABLE labs "
            "ADD COLUMN allow_extra_questions INTEGER DEFAULT 1"
        )

    if "created_by" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN created_by TEXT DEFAULT ''"
        )

    if "created_at" not in column_names:
        cur.execute(
            "ALTER TABLE labs ADD COLUMN created_at TEXT DEFAULT ''"
        )


# Для лабораторних робіт, створених до розділення testbench на відкриту
# та приховану частини, попередній testbench використовується як відкритий.
    cur.execute(
        """
        UPDATE labs
        SET public_testbench = testbench
        WHERE (public_testbench IS NULL OR public_testbench = '')
        AND testbench IS NOT NULL
        AND testbench != ''
        """
    )

# Для старих записів, де автор ще не зберігався, використовується
# службове значення teacher для збереження сумісності з наявними даними.
    cur.execute(
        """
        UPDATE labs
        SET created_by = 'teacher'
        WHERE created_by IS NULL OR created_by = ''
        """
    )

# ============================================================
# Таблиця відправлених рішень студентів
# ============================================================

    cur.execute(
        """
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
        """
    )

# Схема submissions розширювалася разом із конвеєром HDL-перевірки.
# Відсутні поля додаються окремо, щоб зберегти історію попередніх спроб.
    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]


# Схема submissions розширювалася разом із конвеєром HDL-перевірки.
# Відсутні поля додаються окремо, щоб зберегти історію попередніх спроб.
    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]

    submission_columns = {
        "waveform_filename": "TEXT DEFAULT ''",

        "synth_status": "TEXT DEFAULT ''",
        "synth_score": "INTEGER DEFAULT 0",
        "synth_cells_count": "INTEGER DEFAULT 0",
        "synth_wires_count": "INTEGER DEFAULT 0",
        "synth_wire_bits_count": "INTEGER DEFAULT 0",
        "synth_warnings_count": "INTEGER DEFAULT 0",
        "synth_output": "TEXT DEFAULT ''",
        "synth_recommendation": "TEXT DEFAULT ''",
        "synth_stats_json": "TEXT DEFAULT ''",

        "public_status": "TEXT DEFAULT ''",
        "public_score": "INTEGER DEFAULT 0",
        "public_passed_tests": "INTEGER DEFAULT 0",
        "public_total_tests": "INTEGER DEFAULT 0",
        "public_output": "TEXT DEFAULT ''",

        "hidden_status": "TEXT DEFAULT ''",
        "hidden_score": "INTEGER DEFAULT 0",
        "hidden_passed_tests": "INTEGER DEFAULT 0",
        "hidden_total_tests": "INTEGER DEFAULT 0",
        "hidden_output": "TEXT DEFAULT ''",

        "lint_status": "TEXT DEFAULT ''",
        "lint_score": "INTEGER DEFAULT 0",
        "lint_issues_count": "INTEGER DEFAULT 0",
        "lint_output": "TEXT DEFAULT ''",
        "lint_recommendation": "TEXT DEFAULT ''",
        "lint_issues_json": "TEXT DEFAULT ''",

        "error_type": "TEXT DEFAULT ''",
        "error_title": "TEXT DEFAULT ''",
        "error_details": "TEXT DEFAULT ''",
        "recommendation": "TEXT DEFAULT ''",
        "error_confidence": "INTEGER DEFAULT 0",

        "attempt_number": "INTEGER DEFAULT 1",
        "file_deleted": "INTEGER DEFAULT 0",
        "file_hidden_for_student": "INTEGER DEFAULT 0",

        "testbench_score": "INTEGER DEFAULT 0",
        "questions_score": "INTEGER DEFAULT 0",
        "final_score": "INTEGER DEFAULT 0",
        "final_status": "TEXT DEFAULT ''",
        "ects_grade": "TEXT DEFAULT ''",
        "national_grade": "TEXT DEFAULT ''",
        "grading_breakdown": "TEXT DEFAULT ''",
    }

    for column_name, column_definition in submission_columns.items():
        if column_name not in column_names:
            cur.execute(
                f"ALTER TABLE submissions "
                f"ADD COLUMN {column_name} {column_definition}"
            )

# ============================================================
# Спроби відповідей на додаткові питання
# ============================================================

# Таблиця зберігає відповіді студента на додаткові питання,
# результат їх перевірки та зміну оцінки відповідної спроби.
    cur.execute(
        """
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
        """
    )


# ============================================================
# Кеш індивідуальної траєкторії навчання
# ============================================================

# Кеш зберігає результати зовнішнього пошуку, щоб не виконувати
# повторні мережеві запити під час кожного відкриття рекомендацій.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_path_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            lab_id INTEGER DEFAULT 0,
            cache_key TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


# ============================================================
# Тренажер і персоналізовані навчальні завдання
# ============================================================

# Завдання тренажера можуть формуватися із шаблонів або AI-модулем
# відповідно до теми, компетентності та типу виявленої помилки.
    cur.execute(
        """
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
        """
    )


# Окремі спроби виконання завдань використовуються для збереження
# відповіді студента, результату перевірки та сформованого зворотного зв'язку.
    cur.execute(
        """
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
        """
    )


# Тренувальна сесія об'єднує набір завдань в один тест
# і зберігає його агрегований результат.
    cur.execute(
        """
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
        """
    )


# Зв'язок визначає склад тренувальної сесії та порядок завдань у ній.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trainer_session_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            order_number INTEGER DEFAULT 1,

            FOREIGN KEY (session_id) REFERENCES trainer_sessions(id),
            FOREIGN KEY (task_id) REFERENCES trainer_tasks(id)
        )
        """
    )


# Для кожного завдання в межах сесії зберігається одна відповідь студента.
    cur.execute(
        """
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
        """
    )

# ============================================================
# Призначення викладачів, груп і дисциплін
# ============================================================


# Таблиця визначає, яку дисципліну викладач веде для конкретної
# навчальної групи, і використовується для розмежування доступу до даних.
    cur.execute(
        """
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
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS study_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS disciplines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT DEFAULT ''
        )
        """
    )

# ============================================================
# Ручне коригування та підсумкове оцінювання
# ============================================================

# Викладач може скоригувати автоматично сформовану оцінку
# за конкретну лабораторну роботу із збереженням автора та часу зміни.
    cur.execute(
        """
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
        """
    )

# Окрема таблиця використовується для ручного встановлення
# підсумкового результату студента з дисципліни.
    cur.execute(
        """
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
        """
    )


# ============================================================
# Додаткові спроби лабораторних робіт
# ============================================================

# Запис не є самою спробою виконання. Він фіксує окреме рішення
# викладача про надання студенту додаткових відправлень лабораторної роботи.
    cur.execute(
        """
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
        """
    )


# ============================================================
# Початкові облікові записи
# ============================================================

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Тестові студент і викладач створюються лише для порожньої бази даних.
# Це забезпечує можливість первинної перевірки основних сценаріїв системи.
    cur.execute("SELECT COUNT(*) AS count FROM users")

    if cur.fetchone()["count"] == 0:
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
                "Іван Іванов",
                "Група 101",
                "",
                "active",
                now,
            ),
        )

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
                "Викладач",
                "",
                "",
                "active",
                now,
            ),
        )
        

# Адміністративний обліковий запис створюється окремо, оскільки він
# потрібний і для баз даних, у яких уже існують студентські записи.
    admin_exists = cur.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",),
    ).fetchone()

    if not admin_exists:
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
                "admin",
                hash_password("admin123"),
                "admin",
                "Адміністратор системи",
                "",
                "",
                "active",
                now,
            ),
        )


# ============================================================
# Синхронізація довідників
# ============================================================

# Групи та дисципліни, які вже використовуються в облікових записах
# або лабораторних роботах, переносяться до відповідних довідників.
# Синхронізація виконується після створення початкових користувачів,
# щоб їхні групи були доступні вже після першого запуску системи.
    cur.execute(
        """
        INSERT OR IGNORE INTO study_groups (
            name,
            description,
            created_at,
            created_by
        )
        SELECT DISTINCT student_group, '', ?, 'system'
        FROM users
        WHERE student_group IS NOT NULL
        AND student_group != ''
        """,
        (now,),
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO disciplines (
            name,
            description,
            created_at,
            created_by
        )
        SELECT DISTINCT discipline, '', ?, 'system'
        FROM labs
        WHERE discipline IS NOT NULL
        AND discipline != ''
        """,
        (now,),
    )

# ============================================================
# Міграція застарілих паролів
# ============================================================

# Облікові записи, створені ранніми версіями системи з паролями
# у відкритому вигляді, одноразово переводяться на хешоване зберігання.
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
                    legacy_user["id"],
                ),
            )

# ============================================================
# Індекси для журналу, аналітики та історії спроб
# ============================================================

# Прискорює підрахунок і вибірку спроб конкретного студента
# для визначеної лабораторної роботи.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_submissions_lab_username
        ON submissions(lab_id, username)
        """
    )

# Використовується для отримання історії відправлень користувача
# у хронологічному порядку.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_submissions_username_created
        ON submissions(username, created_at)
        """
    )

# Прискорює вибірку користувачів за роллю та навчальною групою,
# зокрема під час формування журналу викладача.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_users_role_group
        ON users(role, student_group)
        """
    )

# Використовується для фільтрації лабораторних робіт за дисципліною.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_labs_discipline
        ON labs(discipline)
        """
    )

# Прискорює визначення кількості додаткових спроб, наданих
# конкретному користувачу для лабораторної роботи.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_attempt_overrides_lab_username
        ON attempt_overrides(lab_id, username)
        """
    )

# Використовується для отримання додаткових відповідей,
# пов'язаних із конкретною спробою лабораторної роботи.
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_extra_task_attempts_submission
        ON extra_task_attempts(submission_id)
        """
    )


# Зберігаємо всі зміни структури та початкових даних,
# виконані під час ініціалізації бази даних.
    conn.commit()
    conn.close()



# =========================
# 2. Декоратори доступу
# =========================

def get_current_session_user():
    """
    Повертає поточного користувача на основі даних сесії
    та актуального стану облікового запису в базі даних.
    """
    username = session.get("username")

    if not username:
        return None

    conn = get_db()

    try:
        user = conn.execute(
            """
            SELECT username, role, status
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
    finally:
        conn.close()

    # Сесія більше не вважається дійсною, якщо користувача видалено
    # або його обліковий запис деактивовано адміністратором.
    if not user or user["status"] != "active":
        session.clear()
        return None

    # Роль у сесії синхронізується з базою даних. Це запобігає
    # використанню застарілих прав після зміни ролі адміністратором.
    if session.get("role") != user["role"]:
        session["role"] = user["role"]

    return user


def login_required(func):
    """Обмежує доступ до маршруту неавторизованим користувачам."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_session_user()

        if user is None:
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return wrapper


def role_required(required_role: str, access_denied_message: str):
    """
    Створює декоратор доступу для маршруту,
    обмеженого визначеною роллю користувача.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_session_user()

            if user is None:
                return redirect(url_for("login"))

            if user["role"] != required_role:
                flash(access_denied_message)
                return redirect(url_for("index"))

            return func(*args, **kwargs)

        return wrapper

    return decorator


def teacher_required(func):
    """Обмежує доступ до маршруту користувачами з роллю викладача."""
    return role_required(
        "teacher",
        "Доступ дозволено лише викладачу.",
    )(func)


def admin_required(func):
    """Обмежує доступ до маршруту користувачами з роллю адміністратора."""
    return role_required(
        "admin",
        "Доступ дозволено лише адміністратору.",
    )(func)


# =========================
# Безпечне перенаправлення
# =========================

def get_safe_referrer(default_endpoint: str = "index") -> str:
    """
    Повертає попередню сторінку лише тоді, коли вона належить
    поточному застосунку. В інших випадках використовується
    внутрішній маршрут за замовчуванням.
    """
    referrer = request.referrer

    if not referrer:
        return url_for(default_endpoint)

    referrer_url = urlparse(referrer)
    host_url = urlparse(request.host_url)

    is_same_host = (
        referrer_url.scheme in {"http", "https"}
        and referrer_url.netloc == host_url.netloc
    )

    if is_same_host:
        return referrer

    return url_for(default_endpoint)


# =========================
# Обробка HTTP-помилок
# =========================

@app.errorhandler(413)
def request_entity_too_large(_error):
    """Обробляє перевищення максимально допустимого розміру HTTP-запиту."""
    max_size_kb = app.config["MAX_CONTENT_LENGTH"] // 1024

    flash(
        "Файл або надіслані дані мають надто великий розмір. "
        f"Максимально допустимий розмір — {max_size_kb} КБ."
    )

    return redirect(get_safe_referrer())



# =========================
# 3. Допоміжні функції для користувачів
# =========================

ALLOWED_UI_THEMES = frozenset({
    "light",
    "dark",
    "system",
})

ALLOWED_UI_PALETTES = frozenset({
    "pastel",
    "indigo",
    "burgundy",
    "green",
})

ALLOWED_FONT_SIZES = frozenset({
    "small",
    "normal",
    "large",
})

ALLOWED_UI_DENSITIES = frozenset({
    "comfortable",
    "compact",
})

ROLE_DEFAULT_ENDPOINTS = {
    "student": "index",
    "teacher": "teacher_panel",
    "admin": "admin_panel",
}


def get_row_value(row, key: str, default=""):
    """
    Безпечно повертає значення поля SQLite Row із підтримкою
    записів, створених попередніми версіями схеми бази даних.
    """
    if not row:
        return default

    if key not in row.keys():
        return default

    value = row[key]

    if value is None:
        return default

    return value


def normalize_user_ui_value(
    value,
    default_value: str,
    allowed_values,
) -> str:
    """Нормалізує значення параметра інтерфейсу за списком дозволених значень."""
    value = str(value or "").strip()

    if value not in allowed_values:
        return default_value

    return value


def normalize_binary_flag(value, default_value: int = 0) -> int:
    """
    Нормалізує значення логічного параметра, що зберігається
    в SQLite як ціле число 0 або 1.
    """
    try:
        normalized_value = int(value)
    except (TypeError, ValueError, OverflowError):
        return default_value

    if normalized_value not in {0, 1}:
        return default_value

    return normalized_value


def load_user_ui_settings_to_session(user) -> None:
    """
    Завантажує персональні параметри інтерфейсу користувача до Flask-сесії.

    Значення перевіряються перед збереженням у сесії, щоб застарілі
    або некоректні дані з бази не впливали на формування інтерфейсу.
    """
    theme = normalize_user_ui_value(
        get_row_value(user, "theme", "light"),
        "light",
        ALLOWED_UI_THEMES,
    )

    palette = normalize_user_ui_value(
        get_row_value(user, "palette", "pastel"),
        "pastel",
        ALLOWED_UI_PALETTES,
    )

    font_size = normalize_user_ui_value(
        get_row_value(user, "font_size", "normal"),
        "normal",
        ALLOWED_FONT_SIZES,
    )

    ui_density = normalize_user_ui_value(
        get_row_value(user, "ui_density", "comfortable"),
        "comfortable",
        ALLOWED_UI_DENSITIES,
    )

    avatar_filename = str(
        get_row_value(user, "avatar_filename", "") or ""
    ).strip()

    first_login_completed = normalize_binary_flag(
        get_row_value(user, "first_login_completed", 0),
        default_value=0,
    )

    show_beginner_tips = normalize_binary_flag(
        get_row_value(user, "show_beginner_tips", 1),
        default_value=1,
    )

    session.update({
        "theme": theme,
        "palette": palette,
        "font_size": font_size,
        "ui_density": ui_density,
        "avatar_filename": avatar_filename,
        "first_login_completed": first_login_completed,
        "show_beginner_tips": show_beginner_tips,
    })


def get_default_redirect_for_role(role: str) -> str:
    """Повертає початковий маршрут відповідно до ролі користувача."""
    endpoint = ROLE_DEFAULT_ENDPOINTS.get(role, "index")
    return url_for(endpoint)


def build_unique_username(
    conn: sqlite3.Connection,
    base_username: str,
) -> str:
    """
    Формує унікальний логін на основі переданого імені.

    Функція використовується, зокрема, для створення локального
    ідентифікатора користувача під час зовнішньої автентифікації.
    """
    base_username = str(base_username or "user").strip().lower()

    # Локальний логін обмежується латинськими літерами, цифрами
    # та символом підкреслення, незалежно від джерела автентифікації.
    base_username = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        base_username,
    ).strip("_")

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
            (username,),
        ).fetchone()

        if not existing:
            return username

        username = f"{base_username}_{counter}"
        counter += 1



# =========================
# 4. Допоміжні функції для файлів і завантажень
# =========================

CHECKER_ALLOWED_EXTENSIONS = {
    "hdl_testbench": [".v"],
    "python_unit_tests": [".py"],
    "sql_query": [".sql"],
    "cpp_tests": [".cpp", ".cc", ".cxx"],
}


def transliterate_cyrillic_to_latin(text) -> str:
    """
    Виконує технічну транслітерацію кириличних символів для формування
    переносних ASCII-імен файлів.
    """
    symbols = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "ґ": "g",
        "д": "d",
        "е": "e",
        "є": "ye",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "і": "i",
        "ї": "yi",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }

    result = []

    for char in str(text or ""):
        lower_char = char.lower()

        if lower_char not in symbols:
            result.append(char)
            continue

        value = symbols[lower_char]

        if char.isupper():
            value = value.capitalize()

        result.append(value)

    return "".join(result)


# Тимчасовий alias зберігає сумісність із попередніми викликами функції.
# Після перевірки всіх посилань у проєкті його можна видалити.
transliterate_ru_to_en = transliterate_cyrillic_to_latin


def make_safe_filename_part(
    text,
    default: str = "item",
    max_length: int = 30,
) -> str:
    """Формує безпечний ASCII-фрагмент імені файлу."""

    def normalize(value) -> str:
        value = transliterate_cyrillic_to_latin(value)
        value = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
        value = re.sub(r"-+", "-", value)
        return value.strip("-_")

    safe_text = normalize(text)

    if not safe_text:
        safe_text = normalize(default)

    if not safe_text:
        safe_text = "item"

    return safe_text[:max_length]


def build_student_short_name(student) -> str:
    """
    Формує компактне позначення студента для імені файлу
    на основі прізвища та ініціалів або логіна.
    """
    if not student:
        return "student"

    full_name = str(
        get_row_value(student, "full_name", "") or ""
    ).strip()

    username = str(
        get_row_value(student, "username", "student") or "student"
    ).strip()

    if not full_name:
        return make_safe_filename_part(
            username,
            default="student",
            max_length=24,
        )

    parts = full_name.split()

    if len(parts) >= 2:
        surname = parts[0]
        initials = "".join(
            part[0]
            for part in parts[1:]
            if part
        )

        return make_safe_filename_part(
            surname + initials,
            default=username,
            max_length=24,
        )

    return make_safe_filename_part(
        full_name,
        default=username,
        max_length=24,
    )


def get_checker_prefix_for_filename(lab) -> str:
    """Повертає короткий префікс типу лабораторної роботи для імені файлу."""
    checker_type = str(
        get_row_value(lab, "checker_type", "hdl_testbench")
        or "hdl_testbench"
    ).lower()

    programming_language = str(
        get_row_value(lab, "programming_language", "")
        or ""
    ).lower()

    # Порядок умов зберігає пріоритети, що використовувалися
    # у попередній реалізації формування імен файлів.
    if checker_type == "python_unit_tests" or programming_language == "python":
        return "PY"

    if checker_type == "hdl_testbench" or programming_language == "verilog":
        return "FPGA"

    if checker_type == "sql_query" or programming_language == "sql":
        return "SQL"

    if checker_type == "cpp_tests" or programming_language == "c++":
        return "CPP"

    return "LAB"


def get_lab_topic_for_filename(lab) -> str:
    """Формує коротке позначення теми лабораторної роботи для імені файлу."""
    lab_id = get_row_value(lab, "id", 0)
    topic = get_row_value(lab, "topic", "") or ""

    default_topic = f"lab{lab_id}"

    return make_safe_filename_part(
        topic,
        default=default_topic,
        max_length=24,
    )


def get_allowed_extensions_for_lab(lab) -> list[str]:
    """Повертає розширення файлів, дозволені для типу перевірки лабораторної."""
    checker_type = str(
        get_row_value(lab, "checker_type", "hdl_testbench")
        or "hdl_testbench"
    )

    return CHECKER_ALLOWED_EXTENSIONS.get(
        checker_type,
        [".txt"],
    ).copy()


def is_allowed_solution_file(filename, lab) -> bool:
    """Перевіряє відповідність розширення файлу типу лабораторної роботи."""
    extension = os.path.splitext(
        str(filename or "")
    )[1].lower()

    return extension in get_allowed_extensions_for_lab(lab)


def build_submission_filename(
    lab,
    student,
    attempt_number,
    original_filename,
) -> str:
    """
    Формує унікалізоване та читабельне ім'я файлу студентської спроби.

    Ім'я містить тип перевірки, лабораторну роботу, студента,
    навчальну групу, номер спроби та час відправлення.
    """
    prefix = get_checker_prefix_for_filename(lab)

    lab_id = get_row_value(lab, "id", 0)
    lab_id_part = f"L{lab_id}"
    topic_part = get_lab_topic_for_filename(lab)

    student_part = build_student_short_name(student)

    group_raw = get_row_value(
        student,
        "student_group",
        "group",
    ) if student else "group"

    group_part = make_safe_filename_part(
        group_raw or "group",
        default="group",
        max_length=20,
    )

    try:
        normalized_attempt = max(1, int(attempt_number))
    except (TypeError, ValueError, OverflowError):
        normalized_attempt = 1

    attempt_part = f"A{normalized_attempt:02d}"
    datetime_part = datetime.now().strftime("%Y%m%d_%H%M%S")

    allowed_extensions = get_allowed_extensions_for_lab(lab)

    extension = os.path.splitext(
        str(original_filename or "")
    )[1].lower()

    # Додаткова перевірка на цьому рівні не замінює валідацію завантаження,
    # але не дозволяє сформувати службове ім'я з неприпустимим розширенням.
    if extension not in allowed_extensions:
        extension = allowed_extensions[0]

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


def build_waveform_filename(submission_filename) -> str:
    """Формує безпечне ім'я VCD-артефакту для студентської спроби."""
    base_name = os.path.splitext(
        str(submission_filename or "")
    )[0]

    safe_base_name = make_safe_filename_part(
        base_name,
        default="waveform",
        max_length=120,
    )

    return f"{safe_base_name}.vcd"


def resolve_safe_storage_path(base_dir, filename):
    """
    Формує шлях до файла лише в межах дозволеного каталогу.

    Перевірка realpath запобігає використанню абсолютних шляхів,
    конструкцій ../ та переходу за межі каталогу через символічні посилання.
    """
    if not filename:
        return None

    base_path = os.path.realpath(base_dir)
    candidate_path = os.path.realpath(
        os.path.join(base_path, str(filename))
    )

    try:
        common_path = os.path.commonpath([
            base_path,
            candidate_path,
        ])
    except ValueError:
        return None

    if common_path != base_path:
        return None

    return candidate_path


def read_submission_code(filename) -> str:
    """Зчитує код студентської спроби з дозволеного каталогу завантажень."""
    file_path = resolve_safe_storage_path(
        UPLOAD_DIR,
        filename,
    )

    if file_path is None:
        return ""

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:
            return file.read()
    except FileNotFoundError:
        return ""


def delete_stored_file(base_dir, filename) -> None:
    """Видаляє файл лише в межах визначеного каталогу зберігання."""
    file_path = resolve_safe_storage_path(
        base_dir,
        filename,
    )

    if file_path is None:
        return

    try:
        os.remove(file_path)
    except FileNotFoundError:
        return


def delete_uploaded_file(filename) -> None:
    """Видаляє фізичний файл студентської спроби."""
    delete_stored_file(
        UPLOAD_DIR,
        filename,
    )


def delete_waveform_file(filename) -> None:
    """Видаляє VCD-артефакт студентської спроби."""
    delete_stored_file(
        WAVEFORM_DIR,
        filename,
    )


def mark_submission_file_deleted(submission_id) -> None:
    """
    Фізично видаляє файл спроби та зберігає факт видалення в базі даних.

    Запис самої спроби не видаляється, оскільки він використовується
    для журналу, аналітики та історії навчальної діяльності студента.
    """
    conn = get_db()

    try:
        submission = conn.execute(
            """
            SELECT filename
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()

        if not submission:
            return

        # Прапорець встановлюється лише після успішного фізичного
        # видалення або підтвердження відсутності файла.
        delete_uploaded_file(submission["filename"])

        conn.execute(
            """
            UPDATE submissions
            SET file_deleted = 1
            WHERE id = ?
            """,
            (submission_id,),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def hide_submission_file_from_student(submission_id) -> None:
    """
    Приховує файл від студента без фізичного видалення.

    Файл залишається доступним викладачу, а історія спроби
    та результати автоматичної перевірки зберігаються без змін.
    """
    conn = get_db()

    try:
        conn.execute(
            """
            UPDATE submissions
            SET file_hidden_for_student = 1
            WHERE id = ?
            """,
            (submission_id,),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    

# ============================================================
# 5. Допоміжні функції для спроб і відправлень
# ============================================================

def teacher_has_lab_access(
    conn: sqlite3.Connection,
    teacher_username: str,
    lab_id: int,
    student_username: str,
) -> bool:
    """
    Перевіряє доступ викладача до лабораторної роботи конкретного студента.

    Доступ надається, якщо викладач створив лабораторну роботу
    або призначений на відповідну дисципліну та навчальну групу.
    """
    access = conn.execute(
        """
        SELECT 1
        FROM labs
        JOIN users AS student
          ON student.username = ?
        WHERE labs.id = ?
          AND (
              labs.created_by = ?
              OR EXISTS (
                  SELECT 1
                  FROM teacher_subject_groups AS tsg
                  WHERE tsg.teacher_username = ?
                    AND tsg.discipline = labs.discipline
                    AND tsg.student_group = student.student_group
              )
          )
        """,
        (
            student_username,
            lab_id,
            teacher_username,
            teacher_username,
        ),
    ).fetchone()

    return access is not None


def teacher_can_access_submission(
    conn: sqlite3.Connection,
    teacher_username: str,
    submission_id: int,
) -> bool:
    """Перевіряє доступ викладача до конкретної студентської спроби."""
    submission = conn.execute(
        """
        SELECT lab_id, username
        FROM submissions
        WHERE id = ?
        """,
        (submission_id,),
    ).fetchone()

    if not submission:
        return False

    return teacher_has_lab_access(
        conn,
        teacher_username=teacher_username,
        lab_id=submission["lab_id"],
        student_username=submission["username"],
    )


def get_submission_for_current_user(submission_id: int):
    """
    Повертає студентську спробу разом із даними лабораторної роботи
    з урахуванням поточних прав доступу.

    Студент має доступ лише до власних спроб, викладач — до спроб
    у межах своїх лабораторних робіт або призначених груп і дисциплін,
    а адміністратор — до всіх спроб.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    if not current_username:
        abort(401)

    conn = get_db()

    try:
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
            JOIN labs
              ON submissions.lab_id = labs.id
            WHERE submissions.id = ?
            """,
            (submission_id,),
        ).fetchone()

        if not submission:
            abort(404)

        if current_role == "admin":
            return submission

        if current_role == "teacher":
            if not teacher_can_access_submission(
                conn,
                current_username,
                submission_id,
            ):
                abort(403)

            return submission

        if submission["username"] != current_username:
            abort(403)

        return submission

    finally:
        conn.close()


def get_student_attempts_count(
    username: str,
    lab_id: int,
) -> int:
    """Повертає кількість збережених спроб студента для лабораторної роботи."""
    conn = get_db()

    try:
        return get_used_attempts_count(
            conn,
            lab_id,
            username,
        )
    finally:
        conn.close()


def get_next_attempt_number(
    username: str,
    lab_id: int,
) -> int:
    """Визначає номер наступної спроби студента для лабораторної роботи."""
    return get_student_attempts_count(username, lab_id) + 1


def get_extra_task_attempt_count(submission_id: int) -> int:
    """Повертає кількість спроб виконання додаткових завдань."""
    conn = get_db()

    try:
        result = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM extra_task_attempts
            WHERE submission_id = ?
            """,
            (submission_id,),
        ).fetchone()

        return int(result["count"] or 0) if result else 0

    finally:
        conn.close()


def get_student_error_history(
    username: str,
    lab_id: int,
):
    """
    Повертає агреговану історію змістовних помилок студента
    для визначеної лабораторної роботи.

    Системні відмови не включаються до навчальної історії,
    оскільки вони не характеризують рівень компетентності студента.
    """
    conn = get_db()

    try:
        return conn.execute(
            """
            SELECT
                error_type,
                error_title,
                COUNT(*) AS count
            FROM submissions
            WHERE username = ?
              AND lab_id = ?
              AND error_type IS NOT NULL
              AND error_type != ''
              AND error_type NOT IN (
                  'NO_ERROR',
                  'SYSTEM_ERROR',
                  'TIMEOUT'
              )
            GROUP BY error_type, error_title
            ORDER BY count DESC
            """,
            (username, lab_id),
        ).fetchall()

    finally:
        conn.close()


def get_teacher_access_condition() -> str:
    """
    Повертає SQL-умову доступу викладача до лабораторної роботи.

    Умова призначена для запитів, де таблиця лабораторних робіт
    має ім'я labs, а таблиця студентів доступна через alias users.
    """
    return """
        (
            labs.created_by = ?
            OR EXISTS (
                SELECT 1
                FROM teacher_subject_groups AS tsg
                WHERE tsg.teacher_username = ?
                  AND tsg.discipline = labs.discipline
                  AND tsg.student_group = users.student_group
            )
        )
    """


def can_edit_lab_grade(
    conn: sqlite3.Connection,
    current_username: str,
    current_role: str,
    student_username: str,
    lab_id: int,
) -> bool:
    """
    Перевіряє право користувача змінювати оцінку за лабораторну роботу.

    Адміністратор має повний доступ, а викладач — лише до робіт,
    що належать до його зони відповідальності.
    """
    if current_role == "admin":
        return True

    if current_role != "teacher":
        return False

    return teacher_has_lab_access(
        conn,
        teacher_username=current_username,
        lab_id=lab_id,
        student_username=student_username,
    )


# =========================
# 6. Перевірка HDL/Verilog-рішень
# =========================

VERILATOR_LINT_TIMEOUT_SECONDS = get_int_env(
    "VERILATOR_LINT_TIMEOUT_SECONDS",
    10,
)


def get_verilator_base_command() -> list[str]:
    """
    Формує базову команду запуску Verilator відповідно до операційної системи.

    У середовищі Windows/MSYS2 Verilator запускається як Perl-скрипт.
    В інших середовищах використовується команда verilator із PATH.
    """
    if os.name == "nt":
        if (
            os.path.exists(VERILATOR_PERL_PATH)
            and os.path.exists(VERILATOR_SCRIPT_PATH)
        ):
            return [
                VERILATOR_PERL_PATH,
                VERILATOR_SCRIPT_PATH,
            ]

    return ["verilator"]


def get_verilator_environment() -> dict[str, str]:
    """
    Формує змінні середовища для локального запуску Verilator.

    Для Windows/MSYS2 до PATH додаються каталоги ucrt64/bin та usr/bin,
    необхідні для роботи Verilator і пов'язаних системних компонентів.
    """
    env = os.environ.copy()

    if os.name == "nt":
        path_parts = [
            VERILATOR_UCRT_BIN,
            VERILATOR_USR_BIN,
            env.get("PATH", ""),
        ]

        env["PATH"] = os.pathsep.join(
            path
            for path in path_parts
            if path
        )

        # MSYS2-обгортка самостійно визначає VERILATOR_ROOT.
        # Застаріле зовнішнє значення може спричинити пошук
        # системних файлів Verilator у неправильному каталозі.
        env.pop("VERILATOR_ROOT", None)

    return env


def normalize_path_for_verilator(file_path: str) -> str:
    """
    Нормалізує абсолютний шлях для передавання Verilator.

    Прямі слеші зменшують кількість проблем сумісності між
    Windows-шляхами та інструментами середовища MSYS2.
    """
    return os.path.abspath(file_path).replace("\\", "/")


def is_verilator_available() -> bool:
    """Перевіряє можливість запуску локального Verilator."""
    command = get_verilator_base_command() + ["--version"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=VERILATOR_LINT_TIMEOUT_SECONDS,
            env=get_verilator_environment(),
            check=False,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False


def strip_verilog_comments(code: str) -> str:
    """
    Видаляє коментарі Verilog без пошкодження рядкових літералів.

    Символи нового рядка всередині коментарів зберігаються,
    щоб не змінювати нумерацію рядків під час подальшого аналізу.
    """
    code = str(code or "")

    result = []
    index = 0

    in_string = False
    in_line_comment = False
    in_block_comment = False
    escaped = False

    while index < len(code):
        char = code[index]
        next_char = code[index + 1] if index + 1 < len(code) else ""

        if in_line_comment:
            if char == "\n":
                result.append("\n")
                in_line_comment = False

            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue

            if char == "\n":
                result.append("\n")

            index += 1
            continue

        if in_string:
            result.append(char)

            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False

            index += 1
            continue

        if char == '"':
            result.append(char)
            in_string = True
            index += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def run_hdl_lint_check_local(solution_path: str) -> dict:
    """
    Виконує локальний статичний аналіз HDL-коду за допомогою Verilator.

    Результати Verilator об'єднуються з власними перевірками стилю,
    після чого формується нормалізований статус, оцінка та рекомендація.
    """
    if not is_verilator_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Verilator не знайдено або його неможливо запустити. "
                "Перевірте встановлення Verilator та конфігурацію PATH."
            ),
            "lint_recommendation": (
                "Lint-перевірка HDL-коду недоступна через проблему "
                "локального середовища."
            ),
            "lint_issues": [],
        }

    try:
        with open(
            solution_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:
            solution_code = file.read()

        # Власні правила доповнюють Verilator перевірками,
        # орієнтованими на типові помилки студентських HDL-рішень.
        custom_issues = run_custom_hdl_style_checks(solution_code)

        verilator_solution_path = normalize_path_for_verilator(
            solution_path
        )

        command = get_verilator_base_command() + [
            "--lint-only",
            "-Wall",
            "-Wno-fatal",
            "-Wno-DECLFILENAME",
            "-sv",
            verilator_solution_path,
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=VERILATOR_LINT_TIMEOUT_SECONDS,
            env=get_verilator_environment(),
            check=False,
        )

        raw_output = "\n".join(
            part
            for part in (
                result.stdout,
                result.stderr,
            )
            if part
        ).strip()

        # Ці повідомлення свідчать про некоректну конфігурацію
        # локального Verilator, а не про помилку HDL-коду студента.
        if (
            "Cannot find verilated_std_waiver.vlt" in raw_output
            or "Cannot find verilated_std.sv" in raw_output
        ):
            return {
                "lint_status": "UNAVAILABLE",
                "lint_score": 0,
                "lint_issues_count": 0,
                "lint_output": (
                    "Verilator знайдено, але його системні файли "
                    "MSYS2 недоступні.\n\n"
                    "Це помилка конфігурації локального середовища, "
                    "а не HDL-коду студента.\n\n"
                    "--- Вивід Verilator ---\n"
                    f"{raw_output}"
                ),
                "lint_recommendation": (
                    "Lint-перевірка тимчасово недоступна. "
                    "Необхідно перевірити конфігурацію Verilator/MSYS2."
                ),
                "lint_issues": [],
            }

        verilator_issues = parse_verilator_lint_output(raw_output)
        all_issues = custom_issues + verilator_issues

        lint_score = calculate_hdl_lint_score(all_issues)
        lint_recommendation = build_hdl_lint_recommendation(
            all_issues
        )

        has_error = any(
            issue.get("severity") == "error"
            for issue in all_issues
        )

        # Ненульовий код завершення Verilator не можна трактувати
        # як успішну lint-перевірку, навіть якщо конкретне повідомлення
        # не було розпізнане парсером діагностики.
        if result.returncode != 0 or has_error:
            lint_status = "ERROR"
        elif all_issues:
            lint_status = "WARNING"
        else:
            lint_status = "OK"

        if not raw_output:
            raw_output = "Verilator не виявив попереджень або помилок."

        report_lines = [
            f"Статус lint-перевірки: {lint_status}",
            f"Якість HDL-коду: {lint_score} / 100",
            f"Кількість зауважень: {len(all_issues)}",
            "",
            "Рекомендація:",
            lint_recommendation,
            "",
        ]

        if all_issues:
            report_lines.append("Список зауважень:")

            for index, issue in enumerate(all_issues, start=1):
                source = issue.get("source", "unknown")
                issue_code = issue.get("code", "UNKNOWN")
                message = issue.get("message", "")

                report_lines.append(
                    f"{index}. [{source}] {issue_code}: {message}"
                )

            report_lines.append("")

        # Оригінальний текст Verilator зберігається без перекладу,
        # оскільки він використовується для технічної діагностики.
        report_lines.append("--- Вивід Verilator ---")
        report_lines.append(raw_output)

        return {
            "lint_status": lint_status,
            "lint_score": lint_score,
            "lint_issues_count": len(all_issues),
            "lint_output": "\n".join(report_lines),
            "lint_recommendation": lint_recommendation,
            "lint_issues": all_issues,
        }

    except subprocess.TimeoutExpired:
        return {
            "lint_status": "TIMEOUT",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Lint-перевірка перевищила встановлений ліміт часу "
                "та була примусово завершена."
            ),
            "lint_recommendation": (
                "Перевірте складність HDL-коду та наявність конструкцій, "
                "що ускладнюють статичний аналіз."
            ),
            "lint_issues": [],
        }

    except OSError as error:
        return {
            "lint_status": "SYSTEM_ERROR",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Не вдалося отримати доступ до HDL-файла або "
                f"запустити Verilator: {error}"
            ),
            "lint_recommendation": (
                "Перевірте файлове середовище та конфігурацію Verilator."
            ),
            "lint_issues": [],
        }

    except Exception as error:
        return {
            "lint_status": "SYSTEM_ERROR",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                f"Системна помилка lint-перевірки HDL-коду: {error}"
            ),
            "lint_recommendation": (
                "Перевірте конфігурацію Verilator та журнал роботи системи."
            ),
            "lint_issues": [],
        }


def run_hdl_lint_check_docker(solution_path: str) -> dict:
    """
    Виконує lint-перевірку HDL-коду за допомогою Verilator
    в ізольованому Docker-середовищі.
    """
    if not is_docker_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Docker недоступний.\n\n"
                "Lint-перевірку HDL-коду не виконано, оскільки "
                "середовище Docker неможливо використати."
            ),
            "lint_recommendation": (
                "Запустіть Docker і повторіть перевірку."
            ),
            "lint_issues": [],
        }

    if not is_hdl_docker_image_available():
        return {
            "lint_status": "UNAVAILABLE",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                f"Docker-образ {HDL_DOCKER_IMAGE} не знайдено.\n\n"
                "Створіть його командою:\n"
                f"docker build -t {HDL_DOCKER_IMAGE} docker/hdl-checker"
            ),
            "lint_recommendation": (
                "Створіть Docker-образ середовища HDL-перевірки."
            ),
            "lint_issues": [],
        }

    try:
        # TemporaryDirectory формує окремий робочий каталог для однієї
        # перевірки та автоматично видаляє його після завершення операції.
        with tempfile.TemporaryDirectory(
            prefix="hdl_lint_docker_"
        ) as temp_dir:
            temp_solution_path = os.path.join(
                temp_dir,
                "solution.v",
            )

            with open(
                solution_path,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:
                solution_code = file.read()

            # Завершальний символ нового рядка усуває технічне
            # попередження Verilator, яке не характеризує HDL-рішення.
            if not solution_code.endswith("\n"):
                solution_code += "\n"

            with open(
                temp_solution_path,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(solution_code)

            # Власні правила аналізу доповнюють Verilator перевірками,
            # орієнтованими на типові помилки студентських HDL-рішень.
            custom_issues = run_custom_hdl_style_checks(
                solution_code
            )

            command = build_hdl_docker_command(
                workspace_path=temp_dir,
                container_command=[
                    "verilator",
                    "--lint-only",
                    "-Wall",
                    "-Wno-fatal",
                    "-Wno-DECLFILENAME",
                    "-sv",
                    "solution.v",
                ],
            )

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=VERILATOR_LINT_TIMEOUT_SECONDS,
                check=False,
            )

            raw_output = get_process_output(result).strip()

            verilator_issues = parse_verilator_lint_output(
                raw_output
            )

            # Ненульовий код завершення завжди фіксується як помилка,
            # навіть якщо конкретне повідомлення Verilator ще не підтримується
            # парсером діагностики.
            if result.returncode != 0 and not verilator_issues:
                verilator_issues.append({
                    "severity": "error",
                    "code": "VERILATOR_ERROR",
                    "message": (
                        raw_output
                        or "Verilator завершив роботу з помилкою."
                    ),
                    "source": "verilator",
                })

            all_issues = custom_issues + verilator_issues

            lint_score = calculate_hdl_lint_score(
                all_issues
            )

            lint_recommendation = build_hdl_lint_recommendation(
                all_issues
            )

            if any(
                issue.get("severity") == "error"
                for issue in all_issues
            ):
                lint_status = "ERROR"
            elif all_issues:
                lint_status = "WARNING"
            else:
                lint_status = "OK"

            if not raw_output:
                raw_output = (
                    "Verilator не виявив попереджень або помилок."
                )

            report_lines = [
                "Середовище lint-перевірки: ізольований Docker-контейнер.",
                "",
                f"Статус lint-перевірки: {lint_status}",
                f"Якість HDL-коду: {lint_score} / 100",
                f"Кількість зауважень: {len(all_issues)}",
                "",
                "Рекомендація:",
                lint_recommendation,
                "",
            ]

            if all_issues:
                report_lines.append("Список зауважень:")

                for index, issue in enumerate(
                    all_issues,
                    start=1,
                ):
                    source = issue.get(
                        "source",
                        "unknown",
                    )
                    issue_code = issue.get(
                        "code",
                        "UNKNOWN",
                    )
                    message = issue.get(
                        "message",
                        "",
                    )

                    report_lines.append(
                        f"{index}. [{source}] "
                        f"{issue_code}: {message}"
                    )

                report_lines.append("")

            # Оригінальний вивід Verilator не перекладається,
            # оскільки він використовується для технічної діагностики.
            report_lines.append("--- Вивід Verilator ---")
            report_lines.append(raw_output)

            return {
                "lint_status": lint_status,
                "lint_score": lint_score,
                "lint_issues_count": len(all_issues),
                "lint_output": "\n".join(report_lines),
                "lint_recommendation": lint_recommendation,
                "lint_issues": all_issues,
            }

    except subprocess.TimeoutExpired:
        app.logger.warning(
            "Docker lint-перевірку HDL-коду зупинено "
            "через перевищення ліміту часу."
        )

        return {
            "lint_status": "TIMEOUT",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Lint-перевірка HDL-коду в Docker перевищила "
                "встановлений ліміт часу та була примусово завершена."
            ),
            "lint_recommendation": (
                "Перевірте складність HDL-коду та наявність конструкцій, "
                "що можуть ускладнювати статичний аналіз."
            ),
            "lint_issues": [],
        }

    except OSError as error:
        app.logger.exception(
            "Помилка файлового середовища або запуску Docker "
            "під час lint-перевірки HDL-коду."
        )

        return {
            "lint_status": "SYSTEM_ERROR",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                "Не вдалося підготувати файл або запустити "
                f"Docker lint-перевірку: {error}"
            ),
            "lint_recommendation": (
                "Перевірте файлове середовище, Docker "
                "та Docker-образ HDL-перевірки."
            ),
            "lint_issues": [],
        }

    except Exception as error:
        app.logger.exception(
            "Системна помилка Docker lint-перевірки HDL-коду."
        )

        return {
            "lint_status": "SYSTEM_ERROR",
            "lint_score": 0,
            "lint_issues_count": 0,
            "lint_output": (
                f"Системна помилка Docker lint-перевірки HDL-коду: {error}"
            ),
            "lint_recommendation": (
                "Перевірте конфігурацію Docker та журнал роботи системи."
            ),
            "lint_issues": [],
        }


def run_hdl_lint_check(solution_path: str) -> dict:
    """
    Вибирає спосіб виконання lint-перевірки відповідно
    до конфігурації системи.
    """
    if HDL_LINT_MODE == "local":
        return run_hdl_lint_check_local(solution_path)

    if HDL_LINT_MODE == "docker":
        return run_hdl_lint_check_docker(solution_path)

    app.logger.error(
        "Непідтримуване значення HDL_LINT_MODE: %s",
        HDL_LINT_MODE,
    )

    return {
        "lint_status": "SYSTEM_ERROR",
        "lint_score": 0,
        "lint_issues_count": 0,
        "lint_output": (
            "Lint-перевірку не виконано через помилку конфігурації "
            "режиму HDL_LINT_MODE."
        ),
        "lint_recommendation": (
            "Встановіть HDL_LINT_MODE у значення 'docker' або 'local'."
        ),
        "lint_issues": [],
    }


# =========================
# Локальна інтеграція з Yosys
# =========================

YOSYS_PROBE_TIMEOUT_SECONDS = get_int_env(
    "YOSYS_PROBE_TIMEOUT_SECONDS",
    10,
)


def get_yosys_base_command() -> list[str]:
    """Формує базову команду для локального запуску Yosys."""
    if os.name == "nt" and os.path.exists(YOSYS_EXE_PATH):
        return [YOSYS_EXE_PATH]

    return ["yosys"]


def get_yosys_environment() -> dict[str, str]:
    """
    Формує змінні середовища для локального запуску Yosys.

    У Windows до PATH додаються каталоги MSYS2, необхідні
    для запуску Yosys та його системних залежностей.
    """
    env = os.environ.copy()

    if os.name == "nt":
        path_parts = [
            YOSYS_UCRT_BIN,
            YOSYS_USR_BIN,
            env.get("PATH", ""),
        ]

        env["PATH"] = os.pathsep.join(
            path
            for path in path_parts
            if path
        )

    return env


def is_yosys_available() -> bool:
    """Перевіряє можливість запуску локального Yosys."""
    try:
        result = subprocess.run(
            get_yosys_base_command() + ["-V"],
            capture_output=True,
            text=True,
            timeout=YOSYS_PROBE_TIMEOUT_SECONDS,
            env=get_yosys_environment(),
            check=False,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False


def extract_yosys_number(
    output,
    label: str,
) -> int:
    """
    Витягує числову статистику з текстового звіту Yosys.

    Підтримуються обидва формати статистики, які можуть
    зустрічатися у виводі різних конфігурацій Yosys.
    """
    output = str(output or "")

    legacy_pattern = rf"{re.escape(label)}:\s+(\d+)"
    legacy_match = re.search(
        legacy_pattern,
        output,
    )

    if legacy_match:
        return int(legacy_match.group(1))

    compact_patterns = {
        "Number of wires": r"^\s*(\d+)\s+wires\s*$",
        "Number of wire bits": r"^\s*(\d+)\s+wire bits\s*$",
        "Number of cells": r"^\s*(\d+)\s+cells\s*$",
    }

    pattern = compact_patterns.get(label)

    if pattern:
        match = re.search(
            pattern,
            output,
            flags=re.MULTILINE,
        )

        if match:
            return int(match.group(1))

    return 0


def parse_yosys_warnings(output) -> list[str]:
    """Витягує попередження з оригінального текстового виводу Yosys."""
    warnings = []

    for line in str(output or "").splitlines():
        stripped = line.strip()

        if "Warning:" in stripped:
            warnings.append(stripped)

    return warnings

YOSYS_SYNTH_TIMEOUT_SECONDS = get_int_env(
    "YOSYS_SYNTH_TIMEOUT_SECONDS",
    15,
)


def extract_yosys_number(
    output,
    label: str,
) -> int:
    """
    Витягує останнє значення заданої статистичної метрики з виводу Yosys.

    Використання останнього блока статистики зменшує ризик отримання
    показників проміжного модуля у багатомодульних HDL-проєктах.
    """
    output = str(output or "")

    compact_patterns = {
        "Number of wires": r"^\s*(\d+)\s+wires\s*$",
        "Number of wire bits": r"^\s*(\d+)\s+wire bits\s*$",
        "Number of cells": r"^\s*(\d+)\s+cells\s*$",
    }

    legacy_pattern = re.compile(
        rf"{re.escape(label)}:\s+(\d+)"
    )

    compact_pattern = compact_patterns.get(label)
    last_value = None

    for line in output.splitlines():
        legacy_match = legacy_pattern.search(line)

        if legacy_match:
            last_value = int(legacy_match.group(1))
            continue

        if compact_pattern:
            compact_match = re.match(
                compact_pattern,
                line,
            )

            if compact_match:
                last_value = int(compact_match.group(1))

    return last_value if last_value is not None else 0


def parse_yosys_cells(output) -> dict[str, int]:
    """
    Витягує розподіл логічних комірок за типами з останнього
    статистичного блока Yosys.
    """
    sections = []
    current_section = None

    for line in str(output or "").splitlines():
        stripped = line.strip()

        if stripped.startswith("Number of cells:"):
            current_section = {}
            sections.append(current_section)
            continue

        if re.match(r"^\d+\s+cells\s*$", stripped):
            current_section = {}
            sections.append(current_section)
            continue

        if current_section is None:
            continue

        if (
            stripped.startswith("===")
            or stripped.startswith("End of script")
            or stripped.startswith("Warnings:")
            or stripped.startswith("Time spent")
        ):
            current_section = None
            continue

        if not stripped:
            continue

        legacy_match = re.match(
            r"^([A-Za-z0-9_$.\-]+)\s+(\d+)$",
            stripped,
        )

        if legacy_match:
            cell_name = legacy_match.group(1)
            cell_count = int(legacy_match.group(2))

            current_section[cell_name] = (
                current_section.get(cell_name, 0)
                + cell_count
            )
            continue

        compact_match = re.match(
            r"^(\d+)\s+([A-Za-z0-9_$.\-]+)$",
            stripped,
        )

        if compact_match:
            cell_count = int(compact_match.group(1))
            cell_name = compact_match.group(2)

            current_section[cell_name] = (
                current_section.get(cell_name, 0)
                + cell_count
            )

    return sections[-1] if sections else {}


def define_synthesis_complexity(
    cells_count: int,
    wire_bits_count: int,
) -> str:
    """Формує орієнтовну текстову характеристику складності синтезованої схеми."""
    if cells_count == 0 and wire_bits_count <= 8:
        return "дуже проста схема"

    if cells_count <= 5:
        return "проста схема"

    if cells_count <= 25:
        return "схема середньої складності"

    if cells_count <= 100:
        return "досить складна схема"

    return "складна схема"


def build_yosys_recommendation(
    synth_status: str,
    warnings_count: int,
    cells_count: int,
) -> str:
    """Формує навчальну рекомендацію за результатами синтезу Yosys."""
    if synth_status == "UNAVAILABLE":
        return (
            "Перевірку синтезованості не виконано, "
            "оскільки Yosys недоступний."
        )

    if synth_status == "TIMEOUT":
        return (
            "Синтез перевищив встановлений ліміт часу. "
            "Перевірте складність HDL-коду та використані конструкції."
        )

    if synth_status == "SYSTEM_ERROR":
        return (
            "Результат синтезу недоступний через системну помилку. "
            "Необхідно перевірити конфігурацію Yosys."
        )

    if synth_status == "ERROR":
        return (
            "Код не пройшов етап синтезу. Перевірте, чи використовуються "
            "синтезовані конструкції Verilog, чи відсутні testbench-конструкції, "
            "затримки #, невизначені модулі та непідтримувані оператори."
        )

    if warnings_count > 0:
        return (
            "Код синтезується, але Yosys сформував попередження. "
            "Перевірте невикористані сигнали, повноту присвоєнь "
            "і коректність опису апаратної логіки."
        )

    if cells_count == 0:
        return (
            "Код синтезується. Логічні комірки практично відсутні: "
            "схема може бути дуже простою або описувати безпосереднє "
            "з'єднання сигналів."
        )

    return (
        "Код успішно синтезується. Критичних проблем "
        "на етапі синтезу не виявлено."
    )


def run_hdl_synthesis_check(
    solution_path: str,
    lab=None,
) -> dict:
    """
    Перевіряє синтезованість HDL-рішення за допомогою Yosys.

    Код копіюється до тимчасового робочого каталогу, після чого
    Yosys виконує elaboration і базові етапи RTL-синтезу.
    Результат містить статус, оцінку, попередження та статистику схеми.
    """
    if not is_yosys_available():
        return {
            "synth_status": "UNAVAILABLE",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": (
                "Yosys не знайдено або його неможливо запустити."
            ),
            "synth_recommendation": (
                "Перевірте YOSYS_EXE_PATH, конфігурацію PATH "
                "та встановлення Yosys."
            ),
            "synth_stats": {},
        }

    try:
        # Для кожної операції синтезу використовується окремий робочий
        # каталог, який автоматично видаляється після завершення перевірки.
        with tempfile.TemporaryDirectory(
            prefix="yosys_synth_"
        ) as temp_dir:
            temp_solution_path = os.path.join(
                temp_dir,
                "solution.v",
            )

            shutil.copyfile(
                solution_path,
                temp_solution_path,
            )

            # Послідовність команд виконує читання HDL, перевірку ієрархії,
            # перетворення процесів у RTL-представлення, оптимізацію,
            # перевірку структури та формування статистики.
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
                yosys_script,
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=YOSYS_SYNTH_TIMEOUT_SECONDS,
                cwd=temp_dir,
                env=get_yosys_environment(),
                check=False,
            )

            raw_output = "\n".join(
                part
                for part in (
                    result.stdout,
                    result.stderr,
                )
                if part
            ).strip()

            warnings = parse_yosys_warnings(
                raw_output
            )

            wires_count = extract_yosys_number(
                raw_output,
                "Number of wires",
            )

            wire_bits_count = extract_yosys_number(
                raw_output,
                "Number of wire bits",
            )

            cells_count = extract_yosys_number(
                raw_output,
                "Number of cells",
            )

            cells_by_type = parse_yosys_cells(
                raw_output
            )

            # Ненульовий код завершення або явне повідомлення ERROR:
            # означає, що HDL-код не пройшов етап синтезу.
            has_error = (
                result.returncode != 0
                or re.search(
                    r"(?m)^\s*ERROR:",
                    raw_output,
                )
                is not None
            )

            if has_error:
                synth_status = "ERROR"
                synth_score = 0

            elif warnings:
                synth_status = "WARNING"

                # Поточна модель знижує оцінку на 10 балів за кожне
                # попередження, але не нижче 60 балів.
                synth_score = max(
                    60,
                    100 - len(warnings) * 10,
                )

            else:
                synth_status = "OK"
                synth_score = 100

            complexity = define_synthesis_complexity(
                cells_count,
                wire_bits_count,
            )

            synth_recommendation = build_yosys_recommendation(
                synth_status=synth_status,
                warnings_count=len(warnings),
                cells_count=cells_count,
            )

            synth_stats = {
                "wires_count": wires_count,
                "wire_bits_count": wire_bits_count,
                "cells_count": cells_count,
                "warnings_count": len(warnings),
                "cells_by_type": cells_by_type,
                "complexity": complexity,
            }

            report_lines = [
                f"Статус синтезу: {synth_status}",
                f"Оцінка синтезованості: {synth_score} / 100",
                f"Орієнтовна складність: {complexity}",
                "",
                "Статистика схеми:",
                f"- Кількість з'єднань (wires): {wires_count}",
                f"- Кількість бітів з'єднань: {wire_bits_count}",
                f"- Кількість логічних комірок: {cells_count}",
            ]

            if cells_by_type:
                report_lines.extend([
                    "",
                    "Типи логічних комірок:",
                ])

                for cell_name, cell_count in cells_by_type.items():
                    report_lines.append(
                        f"- {cell_name}: {cell_count}"
                    )

            report_lines.extend([
                "",
                "Попередження синтезу:",
            ])

            if warnings:
                for warning in warnings:
                    # Оригінальний текст Yosys не перекладається,
                    # оскільки використовується для технічної діагностики.
                    report_lines.append(
                        f"- {warning}"
                    )
            else:
                report_lines.append(
                    "- Попереджень не виявлено."
                )

            report_lines.extend([
                "",
                "Рекомендація:",
                synth_recommendation,
                "",
                "--- Повний вивід Yosys ---",
                raw_output,
            ])

            return {
                "synth_status": synth_status,
                "synth_score": synth_score,
                "synth_cells_count": cells_count,
                "synth_wires_count": wires_count,
                "synth_wire_bits_count": wire_bits_count,
                "synth_warnings_count": len(warnings),
                "synth_output": "\n".join(report_lines),
                "synth_recommendation": synth_recommendation,
                "synth_stats": synth_stats,
            }

    except subprocess.TimeoutExpired:
        app.logger.warning(
            "Синтез HDL-коду в Yosys зупинено через перевищення "
            "встановленого ліміту часу."
        )

        return {
            "synth_status": "TIMEOUT",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": (
                "Перевірка синтезованості перевищила встановлений "
                "ліміт часу та була примусово завершена."
            ),
            "synth_recommendation": (
                "Перевірте складність HDL-коду та наявність конструкцій, "
                "що можуть ускладнювати синтез."
            ),
            "synth_stats": {},
        }

    except OSError as error:
        app.logger.exception(
            "Помилка файлового середовища або запуску Yosys "
            "під час перевірки синтезованості."
        )

        return {
            "synth_status": "SYSTEM_ERROR",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": (
                "Не вдалося підготувати HDL-файл або запустити Yosys: "
                f"{error}"
            ),
            "synth_recommendation": (
                "Перевірте файлове середовище та конфігурацію Yosys."
            ),
            "synth_stats": {},
        }

    except Exception as error:
        app.logger.exception(
            "Системна помилка перевірки синтезованості HDL-коду."
        )

        return {
            "synth_status": "SYSTEM_ERROR",
            "synth_score": 0,
            "synth_cells_count": 0,
            "synth_wires_count": 0,
            "synth_wire_bits_count": 0,
            "synth_warnings_count": 0,
            "synth_output": (
                f"Системна помилка перевірки синтезованості HDL-коду: {error}"
            ),
            "synth_recommendation": (
                "Перевірте конфігурацію Yosys та журнал роботи системи."
            ),
            "synth_stats": {},
        }


# ============================================================
# Формування звіту функціонального тестування HDL
# ============================================================

def format_hdl_report(raw_output):
    """
    Формує структурований звіт за результатами testbench.

    Testbench передає результати окремих перевірок у службовому форматі:
    CASE|номер|входи|очікуване|фактичне|результат.
    """
    lines = str(raw_output or "").splitlines()
    test_cases = []

    for line in lines:
        stripped_line = line.strip()

        if not stripped_line.startswith("CASE|"):
            continue

        parts = [
            part.strip()
            for part in stripped_line.split("|")
        ]

        # Некоректно сформований службовий рядок не використовується
        # для оцінювання, щоб не інтерпретувати пошкоджений вивід як тест.
        if len(parts) != 6:
            continue

        test_number = parts[1]
        inputs = parts[2]
        expected = parts[3]
        actual = parts[4]
        result = parts[5].upper()

        test_cases.append({
            "number": test_number,
            "inputs": inputs,
            "expected": expected,
            "actual": actual,
            "result": result,
        })

    if not test_cases:
        return str(raw_output or ""), 0, 0, 0

    passed_count = sum(
        1
        for test in test_cases
        if test["result"] == "PASS"
    )

    total_count = len(test_cases)

    score = round(
        (passed_count / total_count) * 100
    )

    report_lines = [
        f"Результат: {score} / 100 балів",
        f"Пройдено тестів: {passed_count} із {total_count}",
        "",
    ]

    for test in test_cases:
        if test["result"] == "PASS":
            status_text = "пройдено"
        else:
            status_text = "не пройдено"

        report_lines.append(
            f"Тест {test['number']}: "
            f"{test['inputs']} — {status_text}"
        )
        report_lines.append(
            f"Очікувалося: {test['expected']}"
        )
        report_lines.append(
            f"Отримано:    {test['actual']}"
        )
        report_lines.append("")

    if passed_count == total_count:
        report_lines.append(
            "Підсумковий статус: усі тести успішно пройдено."
        )
    elif passed_count > 0:
        report_lines.append(
            "Підсумковий статус: частину тестів пройдено, "
            "рішення потребує доопрацювання."
        )
    else:
        report_lines.append(
            "Підсумковий статус: тести не пройдено."
        )

    return (
        "\n".join(report_lines),
        score,
        passed_count,
        total_count,
    )


# ============================================================
# Локальна функціональна перевірка HDL
# ============================================================

def run_hdl_check_local(
    user_code_path,
    testbench_text,
    waveform_save_path=None,
):
    """
    Виконує локальну компіляцію та моделювання HDL-рішення
    за допомогою Icarus Verilog і VVP.

    Локальний режим призначений насамперед для розробки та діагностики.
    Виконання недовіреного студентського HDL-коду в робочій системі
    має здійснюватися в ізольованому Docker-середовищі.
    """
    try:
        # Кожна перевірка виконується в окремому тимчасовому каталозі.
        # Після завершення компіляції та моделювання його вміст
        # автоматично видаляється.
        with tempfile.TemporaryDirectory(
            prefix="hdl_check_local_"
        ) as temp_dir:
            solution_path = os.path.join(
                temp_dir,
                "solution.v",
            )

            testbench_path = os.path.join(
                temp_dir,
                "testbench.v",
            )

            output_path = os.path.join(
                temp_dir,
                "simulation.out",
            )

            preferred_waveform_path = os.path.join(
                temp_dir,
                "wave.vcd",
            )

            shutil.copyfile(
                user_code_path,
                solution_path,
            )

            with open(
                testbench_path,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    str(testbench_text or "")
                )

            compile_command = [
                "iverilog",
                "-o",
                output_path,
                solution_path,
                testbench_path,
            ]

            try:
                compile_result = subprocess.run(
                    compile_command,
                    capture_output=True,
                    text=True,
                    timeout=HDL_COMPILE_TIMEOUT_SECONDS,
                    check=False,
                )

            except FileNotFoundError:
                app.logger.exception(
                    "Не вдалося запустити Icarus Verilog."
                )

                return (
                    "SYSTEM_ERROR",
                    (
                        "Icarus Verilog недоступний. "
                        "Перевірте встановлення iverilog "
                        "та конфігурацію PATH."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            except subprocess.TimeoutExpired:
                app.logger.warning(
                    "Компіляцію HDL-коду зупинено через "
                    "перевищення ліміту часу."
                )

                return (
                    "TIMEOUT",
                    (
                        "Компіляція HDL-коду перевищила "
                        "встановлений ліміт часу."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            # Ненульовий код завершення iverilog характеризує
            # помилку компіляції HDL-рішення, а не системну відмову.
            if compile_result.returncode != 0:
                compile_output = "\n".join(
                    part
                    for part in (
                        compile_result.stdout,
                        compile_result.stderr,
                    )
                    if part
                ).strip()

                return (
                    "COMPILE_ERROR",
                    compile_output,
                    0,
                    0,
                    0,
                    False,
                )

            run_command = [
                "vvp",
                output_path,
            ]

            try:
                run_result = subprocess.run(
                    run_command,
                    capture_output=True,
                    text=True,
                    timeout=HDL_SIM_TIMEOUT_SECONDS,
                    cwd=temp_dir,
                    check=False,
                )

            except FileNotFoundError:
                app.logger.exception(
                    "Не вдалося запустити VVP."
                )

                return (
                    "SYSTEM_ERROR",
                    (
                        "VVP недоступний. Перевірте встановлення "
                        "Icarus Verilog та конфігурацію PATH."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            except subprocess.TimeoutExpired:
                app.logger.warning(
                    "Моделювання HDL-коду зупинено через "
                    "перевищення ліміту часу."
                )

                return (
                    "TIMEOUT",
                    (
                        "Моделювання HDL-коду перевищило "
                        "встановлений ліміт часу."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            full_output = "\n".join(
                part
                for part in (
                    run_result.stdout,
                    run_result.stderr,
                )
                if part
            ).strip()

            waveform_created = False

            if waveform_save_path:
                source_vcd_path = None

                # За можливості використовується стандартне ім'я wave.vcd.
                # Якщо testbench формує VCD з іншим ім'ям, вибирається
                # перший файл у стабільно відсортованому списку.
                if os.path.isfile(preferred_waveform_path):
                    source_vcd_path = preferred_waveform_path
                else:
                    vcd_files = sorted(
                        file_name
                        for file_name in os.listdir(temp_dir)
                        if file_name.lower().endswith(".vcd")
                    )

                    if vcd_files:
                        source_vcd_path = os.path.join(
                            temp_dir,
                            vcd_files[0],
                        )

                if source_vcd_path:
                    shutil.copyfile(
                        source_vcd_path,
                        waveform_save_path,
                    )
                    waveform_created = True

            if run_result.returncode != 0:
                return (
                    "SIMULATION_ERROR",
                    full_output,
                    0,
                    0,
                    0,
                    False,
                )

            if "CASE|" in full_output:
                (
                    formatted_report,
                    score,
                    passed_tests,
                    total_tests,
                ) = format_hdl_report(full_output)

                # Важливо перевіряти total_tests окремо:
                # пошкоджений CASE-рядок не повинен давати стан PASSED
                # лише через рівність 0 == 0.
                if total_tests <= 0:
                    return (
                        "FAILED",
                        (
                            full_output
                            or "Testbench сформував некоректний "
                               "формат результатів CASE."
                        ),
                        0,
                        0,
                        0,
                        waveform_created,
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
                    waveform_created,
                )

            if "ALL_TESTS_PASSED" in full_output:
                return (
                    "PASSED",
                    full_output,
                    100,
                    1,
                    1,
                    waveform_created,
                )

            return (
                "FAILED",
                (
                    full_output
                    or (
                        "Тести не пройдено або testbench "
                        "не сформував результат перевірки."
                    )
                ),
                0,
                0,
                0,
                waveform_created,
            )

    except OSError as error:
        app.logger.exception(
            "Помилка файлового середовища під час "
            "локальної HDL-перевірки."
        )

        return (
            "SYSTEM_ERROR",
            (
                "Не вдалося підготувати файли для HDL-перевірки: "
                f"{error}"
            ),
            0,
            0,
            0,
            False,
        )

    except Exception as error:
        app.logger.exception(
            "Системна помилка локальної HDL-перевірки."
        )

        return (
            "SYSTEM_ERROR",
            (
                "Системна помилка локальної HDL-перевірки: "
                f"{error}"
            ),
            0,
            0,
            0,
            False,
        )


DOCKER_PROBE_TIMEOUT_SECONDS = get_int_env(
    "DOCKER_PROBE_TIMEOUT_SECONDS",
    5,
)

DOCKER_CLEANUP_TIMEOUT_SECONDS = get_int_env(
    "DOCKER_CLEANUP_TIMEOUT_SECONDS",
    5,
)


def is_hdl_docker_image_available() -> bool:
    """Перевіряє наявність локального Docker-образу для HDL-перевірки."""
    try:
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                HDL_DOCKER_IMAGE,
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
            check=False,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False


def build_hdl_docker_command(
    workspace_path: str,
    container_command: list[str],
    container_name: str | None = None,
) -> list[str]:
    """
    Формує команду запуску HDL-інструмента в ізольованому Docker-контейнері.

    Контейнер працює без мережі, з обмеженнями CPU, пам'яті та кількості
    процесів, read-only кореневою файловою системою і без Linux capabilities.
    """
    host_workspace = os.path.abspath(workspace_path)

    command = [
        "docker",
        "run",
        "--rm",

        # Мережевий доступ користувацького HDL-коду повністю вимикається.
        "--network",
        "none",

        # Обмеження обчислювальних ресурсів запобігають надмірному
        # використанню CPU та оперативної пам'яті.
        "--cpus",
        "0.5",

        "--memory",
        "128m",

        # Обмеження кількості процесів зменшує ризик виснаження
        # ресурсів хост-системи через створення великої кількості процесів.
        "--pids-limit",
        "64",

        # Коренева файлова система контейнера доступна лише для читання.
        "--read-only",

        # Тимчасовий каталог доступний для запису тільки всередині контейнера
        # та має окреме обмеження розміру.
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",

        # Процеси всередині контейнера не можуть отримувати
        # додаткові привілеї під час виконання.
        "--security-opt",
        "no-new-privileges",

        # Видаляються всі Linux capabilities, які не потрібні
        # Icarus Verilog, VVP, Verilator або Yosys.
        "--cap-drop",
        "ALL",
    ]

    if container_name:
        command.extend([
            "--name",
            container_name,
        ])

    # Робочий каталог навмисно монтується в режимі rw:
    # iverilog створює simulation.out, а VVP може формувати VCD.
    # Каталог є одноразовим TemporaryDirectory і видаляється після перевірки.
    command.extend([
        "-v",
        f"{host_workspace}:/workspace:rw",
        "-w",
        "/workspace",
        HDL_DOCKER_IMAGE,
    ])

    return command + list(container_command)


def force_remove_docker_container(container_name: str) -> None:
    """
    Примусово завершує та видаляє контейнер після перерваної перевірки.

    Це додатково гарантує очищення ресурсів, якщо процес docker run
    був зупинений Python через перевищення таймауту.
    """
    if not container_name:
        return

    try:
        subprocess.run(
            [
                "docker",
                "rm",
                "-f",
                container_name,
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS,
            check=False,
        )

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        app.logger.warning(
            "Не вдалося примусово видалити Docker-контейнер %s.",
            container_name,
        )


def get_process_output(result) -> str:
    """Об'єднує stdout і stderr зовнішнього процесу в один текстовий звіт."""
    return "\n".join(
        part
        for part in (
            result.stdout,
            result.stderr,
        )
        if part
    ).strip()


def run_hdl_check_docker(
    user_code_path: str,
    testbench_text,
    waveform_save_path=None,
):
    """
    Виконує компіляцію та моделювання HDL-рішення в Docker-середовищі.

    Перевірка складається з двох ізольованих етапів:
    компіляції через Icarus Verilog та моделювання через VVP.
    """
    if not is_docker_available():
        return (
            "SYSTEM_ERROR",
            (
                "Docker недоступний.\n\n"
                "Перевірте, чи встановлено та запущено Docker."
            ),
            0,
            0,
            0,
            False,
        )

    if not is_hdl_docker_image_available():
        return (
            "SYSTEM_ERROR",
            (
                f"Docker-образ {HDL_DOCKER_IMAGE} не знайдено.\n\n"
                "Створіть його командою:\n"
                f"docker build -t {HDL_DOCKER_IMAGE} "
                "checks/docker/hdl-checker"
            ),
            0,
            0,
            0,
            False,
        )

    try:
        # Кожна студентська перевірка отримує окремий робочий каталог.
        # Після завершення запиту всі тимчасові файли автоматично видаляються.
        with tempfile.TemporaryDirectory(
            prefix="hdl_docker_check_"
        ) as temp_dir:
            solution_path = os.path.join(
                temp_dir,
                "solution.v",
            )

            testbench_path = os.path.join(
                temp_dir,
                "testbench.v",
            )

            shutil.copyfile(
                user_code_path,
                solution_path,
            )

            with open(
                testbench_path,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    str(testbench_text or "")
                )

            # Унікальне ім'я дає змогу гарантовано знайти контейнер
            # і примусово завершити його у випадку таймауту docker run.
            compile_container_name = (
                f"fpga-hdl-compile-{secrets.token_hex(8)}"
            )

            compile_command = build_hdl_docker_command(
                workspace_path=temp_dir,
                container_name=compile_container_name,
                container_command=[
                    "iverilog",
                    "-o",
                    "simulation.out",
                    "solution.v",
                    "testbench.v",
                ],
            )

            try:
                compile_result = subprocess.run(
                    compile_command,
                    capture_output=True,
                    text=True,
                    timeout=HDL_COMPILE_TIMEOUT_SECONDS,
                    check=False,
                )

            except FileNotFoundError:
                app.logger.exception(
                    "Не вдалося запустити Docker для компіляції HDL-коду."
                )

                return (
                    "SYSTEM_ERROR",
                    (
                        "Docker недоступний або команда docker "
                        "відсутня в PATH."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            except subprocess.TimeoutExpired:
                force_remove_docker_container(
                    compile_container_name
                )

                app.logger.warning(
                    "Docker-компіляцію HDL-коду зупинено через "
                    "перевищення ліміту часу."
                )

                return (
                    "TIMEOUT",
                    (
                        "Компіляція HDL-коду в Docker перевищила "
                        "встановлений ліміт часу."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            if compile_result.returncode != 0:
                return (
                    "COMPILE_ERROR",
                    get_process_output(compile_result),
                    0,
                    0,
                    0,
                    False,
                )

            simulation_container_name = (
                f"fpga-hdl-sim-{secrets.token_hex(8)}"
            )

            run_command = build_hdl_docker_command(
                workspace_path=temp_dir,
                container_name=simulation_container_name,
                container_command=[
                    "vvp",
                    "simulation.out",
                ],
            )

            try:
                run_result = subprocess.run(
                    run_command,
                    capture_output=True,
                    text=True,
                    timeout=HDL_SIM_TIMEOUT_SECONDS,
                    check=False,
                )

            except FileNotFoundError:
                app.logger.exception(
                    "Не вдалося запустити Docker для моделювання HDL-коду."
                )

                return (
                    "SYSTEM_ERROR",
                    (
                        "Docker недоступний або команда docker "
                        "відсутня в PATH."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            except subprocess.TimeoutExpired:
                force_remove_docker_container(
                    simulation_container_name
                )

                app.logger.warning(
                    "HDL-моделювання в Docker зупинено через "
                    "перевищення ліміту часу."
                )

                return (
                    "TIMEOUT",
                    (
                        "HDL-моделювання в Docker перевищило "
                        "встановлений ліміт часу."
                    ),
                    0,
                    0,
                    0,
                    False,
                )

            full_output = get_process_output(
                run_result
            )

            waveform_created = False

            # VCD є додатковим артефактом. Помилка його копіювання
            # не повинна скасовувати вже отриманий результат моделювання.
            if waveform_save_path:
                try:
                    preferred_vcd_path = os.path.join(
                        temp_dir,
                        "wave.vcd",
                    )

                    source_vcd_path = None

                    if os.path.isfile(preferred_vcd_path):
                        source_vcd_path = preferred_vcd_path
                    else:
                        vcd_files = sorted(
                            file_name
                            for file_name in os.listdir(temp_dir)
                            if file_name.lower().endswith(".vcd")
                        )

                        if vcd_files:
                            source_vcd_path = os.path.join(
                                temp_dir,
                                vcd_files[0],
                            )

                    if source_vcd_path:
                        shutil.copyfile(
                            source_vcd_path,
                            waveform_save_path,
                        )
                        waveform_created = True

                except OSError:
                    app.logger.exception(
                        "Не вдалося зберегти VCD-артефакт "
                        "після HDL-моделювання."
                    )

                    waveform_created = False

            # Ненульовий код VVP означає помилку моделювання.
            # Сформований до цього VCD може зберігатися як
            # діагностичний артефакт, якщо його вдалося отримати.
            if run_result.returncode != 0:
                return (
                    "SIMULATION_ERROR",
                    full_output,
                    0,
                    0,
                    0,
                    waveform_created,
                )

            if "CASE|" in full_output:
                (
                    formatted_report,
                    score,
                    passed_tests,
                    total_tests,
                ) = format_hdl_report(
                    full_output
                )

                # Пошкоджений службовий CASE-вивід не повинен
                # інтерпретуватися як успішне проходження 0 із 0 тестів.
                if total_tests <= 0:
                    return (
                        "FAILED",
                        (
                            "Середовище перевірки: "
                            "ізольований Docker-контейнер HDL.\n\n"
                            + (
                                full_output
                                or (
                                    "Testbench сформував некоректний "
                                    "формат результатів CASE."
                                )
                            )
                        ),
                        0,
                        0,
                        0,
                        waveform_created,
                    )

                formatted_report = (
                    "Середовище перевірки: "
                    "ізольований Docker-контейнер HDL.\n\n"
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
                    waveform_created,
                )

            if "ALL_TESTS_PASSED" in full_output:
                return (
                    "PASSED",
                    (
                        "Середовище перевірки: "
                        "ізольований Docker-контейнер HDL.\n\n"
                        + full_output
                    ),
                    100,
                    1,
                    1,
                    waveform_created,
                )

            return (
                "FAILED",
                (
                    "Середовище перевірки: "
                    "ізольований Docker-контейнер HDL.\n\n"
                    + (
                        full_output
                        or (
                            "Тести не пройдено або testbench "
                            "не сформував результат перевірки."
                        )
                    )
                ),
                0,
                0,
                0,
                waveform_created,
            )

    except OSError as error:
        app.logger.exception(
            "Помилка файлового середовища під час "
            "Docker-перевірки HDL-коду."
        )

        return (
            "SYSTEM_ERROR",
            (
                "Не вдалося підготувати файли для HDL-перевірки: "
                f"{error}"
            ),
            0,
            0,
            0,
            False,
        )

    except Exception as error:
        app.logger.exception(
            "Системна помилка Docker-перевірки HDL-коду."
        )

        return (
            "SYSTEM_ERROR",
            (
                "Системна помилка Docker-перевірки HDL-коду: "
                f"{error}"
            ),
            0,
            0,
            0,
            False,
        )


def run_hdl_check(
    user_code_path: str,
    testbench_text,
    waveform_save_path=None,
):
    """
    Виконує функціональну HDL-перевірку у вибраному середовищі.

    Docker використовується як основний ізольований режим,
    а локальний запуск призначений для розробки та діагностики.
    """
    if HDL_CHECK_MODE == "local":
        return run_hdl_check_local(
            user_code_path=user_code_path,
            testbench_text=testbench_text,
            waveform_save_path=waveform_save_path,
        )

    if HDL_CHECK_MODE == "docker":
        return run_hdl_check_docker(
            user_code_path=user_code_path,
            testbench_text=testbench_text,
            waveform_save_path=waveform_save_path,
        )

    app.logger.error(
        "Непідтримуване значення HDL_CHECK_MODE: %s",
        HDL_CHECK_MODE,
    )

    return (
        "SYSTEM_ERROR",
        (
            "HDL-перевірку не виконано через некоректну "
            "конфігурацію HDL_CHECK_MODE. "
            "Допустимі значення: 'docker' або 'local'."
        ),
        0,
        0,
        0,
        False,
    )


# ============================================================
# Обробка VCD-артефактів
# ============================================================

def normalize_vcd_value(value) -> str:
    """Нормалізує текстове представлення значення сигналу VCD."""
    value = str(value or "").strip()

    if not value:
        return "x"

    return value.lower()


def append_vcd_change(
    signal: dict,
    current_time: int,
    value: str,
    max_changes: int,
) -> None:
    """
    Додає зміну сигналу, якщо значення відрізняється від попереднього.

    Послідовні дублікати відсіюються одразу, тому встановлений ліміт
    застосовується до змістовних переходів сигналу, а не до повторів.
    """
    changes = signal["changes"]

    if changes and changes[-1]["value"] == value:
        return

    if len(changes) >= max_changes:
        return

    changes.append({
        "time": current_time,
        "value": value,
    })


def parse_vcd_file(
    vcd_path: str,
    max_changes_per_signal: int = 5000,
) -> dict:
    """
    Виконує потоковий розбір VCD-файла для відображення часових діаграм.

    Підтримуються:
    - скалярні значення 0, 1, x, z;
    - векторні значення виду b1010 або bxxxx;
    - ієрархічні імена сигналів через $scope;
    - параметр $timescale.

    Real-значення навмисно не обробляються, оскільки поточні
    FPGA-лабораторні роботи орієнтовані на цифрові HDL-сигнали.
    """
    try:
        max_changes_per_signal = int(max_changes_per_signal)
    except (TypeError, ValueError, OverflowError):
        max_changes_per_signal = 5000

    if max_changes_per_signal <= 0:
        max_changes_per_signal = 5000

    timescale = ""
    scope_stack = []

    signal_defs = []
    code_to_signal_indexes = {}

    current_time = 0
    max_time = 0

    collecting_timescale = False
    timescale_parts = []

    try:
        # VCD обробляється потоково, без readlines(), щоб розмір файла
        # не визначав безпосередньо обсяг оперативної пам'яті парсера.
        with open(
            vcd_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:
            for raw_line in file:
                line = raw_line.strip()

                if collecting_timescale:
                    if "$end" in line:
                        content = line.split(
                            "$end",
                            maxsplit=1,
                        )[0].strip()

                        if content:
                            timescale_parts.append(content)

                        timescale = " ".join(
                            timescale_parts
                        ).strip()

                        timescale_parts = []
                        collecting_timescale = False
                    elif line:
                        timescale_parts.append(line)

                    continue

                if not line:
                    continue

                # $timescale може бути записаний в одному рядку
                # або як багаторядкова секція VCD.
                if line.startswith("$timescale"):
                    content = line[len("$timescale"):].strip()

                    if "$end" in content:
                        timescale = content.split(
                            "$end",
                            maxsplit=1,
                        )[0].strip()
                    else:
                        collecting_timescale = True

                        if content:
                            timescale_parts.append(content)

                    continue

                if line.startswith("$scope"):
                    parts = line.split()

                    # Формат:
                    # $scope module tb_mux2to1 $end
                    if len(parts) >= 3:
                        scope_stack.append(
                            parts[2]
                        )

                    continue

                if line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()

                    continue

                if line.startswith("$var"):
                    parts = line.split()

                    # Типовий формат:
                    # $var wire 1 ! clk $end
                    if len(parts) >= 6:
                        var_type = parts[1]

                        try:
                            size = int(parts[2])
                        except ValueError:
                            size = 1

                        code = parts[3]
                        reference = " ".join(
                            parts[4:-1]
                        )

                        full_name = ".".join(
                            scope_stack + [reference]
                        )

                        signal = {
                            "index": len(signal_defs),
                            "code": code,
                            "name": full_name,
                            "short_name": reference,
                            "type": var_type,
                            "size": size,
                            "changes": [],
                        }

                        signal_defs.append(signal)

                        code_to_signal_indexes.setdefault(
                            code,
                            [],
                        ).append(
                            signal["index"]
                        )

                    continue

                if line.startswith("$enddefinitions"):
                    continue

                # Часова мітка VCD задається у форматі #<число>.
                if line.startswith("#"):
                    try:
                        current_time = int(
                            line[1:]
                        )
                        max_time = max(
                            max_time,
                            current_time,
                        )
                    except ValueError:
                        pass

                    continue

                # Директиви $dumpvars та інші службові секції
                # не є безпосередніми змінами значень сигналів.
                if line.startswith("$"):
                    continue

                first_char = line[0]

                # Скалярні зміни:
                # 0!
                # 1!
                # x!
                # z!
                if first_char in {
                    "0",
                    "1",
                    "x",
                    "X",
                    "z",
                    "Z",
                }:
                    value = normalize_vcd_value(
                        first_char
                    )

                    code = line[1:].strip()

                    for signal_index in code_to_signal_indexes.get(
                        code,
                        [],
                    ):
                        append_vcd_change(
                            signal_defs[signal_index],
                            current_time=current_time,
                            value=value,
                            max_changes=max_changes_per_signal,
                        )

                    continue

                # Векторні зміни:
                # b1010 "
                # bxxxx #
                if first_char in {"b", "B"}:
                    parts = line.split(
                        maxsplit=1
                    )

                    if len(parts) != 2:
                        continue

                    value = normalize_vcd_value(
                        parts[0][1:]
                    )

                    code = parts[1].strip()

                    for signal_index in code_to_signal_indexes.get(
                        code,
                        [],
                    ):
                        append_vcd_change(
                            signal_defs[signal_index],
                            current_time=current_time,
                            value=value,
                            max_changes=max_changes_per_signal,
                        )

                    continue

                # Real-значення виду r3.14 наразі не використовуються
                # в навчальних цифрових FPGA-сценаріях.

    except FileNotFoundError:
        return {
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": "VCD-файл не знайдено.",
        }

    except OSError:
        app.logger.exception(
            "Не вдалося прочитати VCD-файл."
        )

        return {
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": (
                "Не вдалося прочитати VCD-файл через "
                "помилку файлової системи."
            ),
        }

    except Exception:
        app.logger.exception(
            "Системна помилка під час обробки VCD-файла."
        )

        return {
            "timescale": "",
            "max_time": 0,
            "signals": [],
            "error": (
                "Не вдалося обробити VCD-файл через "
                "внутрішню помилку системи."
            ),
        }

    # Сигнал без зафіксованих змін відображається як невизначений
    # від початку моделювання.
    for signal in signal_defs:
        if not signal["changes"]:
            signal["changes"].append({
                "time": 0,
                "value": "x",
            })

    return {
        "timescale": timescale or "1ns",
        "max_time": max_time,
        "signals": signal_defs,
        "error": "",
    }

def get_waveform_submission_for_current_user(submission_id: int):
    """
    Повертає спробу, для якої дозволено перегляд VCD-артефакту.

    Студент має доступ лише до власних спроб, викладач — до спроб
    у межах своїх лабораторних робіт або призначених груп і дисциплін,
    а адміністратор — до всіх спроб.
    """
    current_user = get_current_session_user()

    if current_user is None:
        abort(401)

    current_role = current_user["role"]
    current_username = current_user["username"]

    conn = get_db()

    try:
        submission = conn.execute(
            """
            SELECT
                submissions.*,
                labs.title AS lab_title,
                labs.discipline AS lab_discipline,
                users.full_name AS student_full_name,
                users.student_group AS student_group
            FROM submissions
            JOIN labs
              ON labs.id = submissions.lab_id
            LEFT JOIN users
              ON users.username = submissions.username
            WHERE submissions.id = ?
            """,
            (submission_id,),
        ).fetchone()

        if not submission:
            abort(404)

        if current_role == "admin":
            return submission

        if current_role == "teacher":
            if not teacher_can_access_submission(
                conn,
                teacher_username=current_username,
                submission_id=submission_id,
            ):
                abort(403)

            return submission

        if submission["username"] != current_username:
            abort(403)

        return submission

    finally:
        conn.close()


# =========================
# 6.1. HDL lint / статичний аналіз Verilog-коду
# =========================

def parse_verilator_lint_output(output) -> list[dict]:
    """
    Перетворює діагностичний вивід Verilator
    на уніфікований список lint-зауважень.
    """
    issues = []
    seen_issues = set()

    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        warning_match = re.match(
            r"%Warning-([A-Z0-9_-]+):\s*(.*)",
            line,
        )

        error_match = re.match(
            r"%Error-([A-Z0-9_-]+):\s*(.*)",
            line,
        )

        generic_warning_match = re.match(
            r"%Warning:\s*(.*)",
            line,
        )

        generic_error_match = re.match(
            r"%Error:\s*(.*)",
            line,
        )

        issue = None

        if warning_match:
            issue = {
                "severity": "warning",
                "code": warning_match.group(1),
                "message": warning_match.group(2),
                "source": "verilator",
            }

        elif error_match:
            issue = {
                "severity": "error",
                "code": error_match.group(1),
                "message": error_match.group(2),
                "source": "verilator",
            }

        elif generic_warning_match:
            issue = {
                "severity": "warning",
                "code": "WARNING",
                "message": generic_warning_match.group(1),
                "source": "verilator",
            }

        elif generic_error_match:
            issue = {
                "severity": "error",
                "code": "ERROR",
                "message": generic_error_match.group(1),
                "source": "verilator",
            }

        if issue is None:
            continue

        # Однакові діагностичні рядки не повинні кілька разів
        # впливати на підсумкову lint-оцінку.
        issue_key = (
            issue["severity"],
            issue["code"],
            issue["message"],
            issue["source"],
        )

        if issue_key in seen_issues:
            continue

        seen_issues.add(issue_key)
        issues.append(issue)

    return issues


def remove_control_conditions(code: str) -> str:
    """
    Видаляє прості умови керувальних конструкцій перед пошуком
    процедурних присвоєнь.

    Функція використовується лише як допоміжна евристика custom lint
    і не замінює повноцінний синтаксичний аналіз Verilog.
    """
    return re.sub(
        r"\b(?:if|while)\s*\([^)]*\)",
        "",
        code,
        flags=re.IGNORECASE,
    )


def contains_nonblocking_assignment(block: str) -> bool:
    """
    Евристично визначає наявність неблокирувального присвоєння
    в процедурному HDL-блоці.
    """
    block_without_conditions = remove_control_conditions(block)

    return re.search(
        r"\b[A-Za-z_][A-Za-z0-9_$]*"
        r"(?:\s*\[[^\]]+\])?\s*<=",
        block_without_conditions,
    ) is not None


def contains_blocking_assignment(block: str) -> bool:
    """
    Евристично визначає наявність блокувального присвоєння
    в процедурному HDL-блоці.
    """
    block_without_conditions = remove_control_conditions(block)

    return re.search(
        r"(?<![<>=!])=(?!=)",
        block_without_conditions,
    ) is not None


def run_custom_hdl_style_checks(code) -> list[dict]:
    """
    Виконує додаткові евристичні перевірки типових помилок HDL-коду.

    Ці правила доповнюють Verilator і орієнтовані насамперед
    на навчальні помилки у невеликих Verilog/RTL-рішеннях.
    """
    clean_code = strip_verilog_comments(code)
    code_lower = clean_code.lower()

    issues = []

    # Кожний case-блок аналізується окремо. Наявність default
    # в одному case не приховує проблему в іншому.
    case_blocks = re.findall(
        r"\bcase(?:x|z)?\s*\([^)]*\)(.*?)\bendcase\b",
        clean_code,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for case_block in case_blocks:
        if not re.search(
            r"\bdefault\s*:",
            case_block,
            flags=re.IGNORECASE,
        ):
            issues.append({
                "severity": "warning",
                "code": "CASE_WITHOUT_DEFAULT",
                "message": (
                    "У конструкції case відсутня гілка default. "
                    "Для комбінаційної логіки це може призвести "
                    "до неповного опису поведінки."
                ),
                "source": "custom",
            })

    # Аналізуємо прості always-блоки та окремо визначаємо
    # комбінаційну або послідовнісну природу sensitivity list.
    always_blocks = re.findall(
        r"\balways\s*@\s*"
        r"(?:\((.*?)\)|(\*))\s*"
        r"begin(.*?)\bend\b",
        clean_code,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for sensitivity_list, star_sensitivity, block in always_blocks:
        sensitivity = (
            sensitivity_list
            or star_sensitivity
            or ""
        ).lower()

        is_sequential = (
            "posedge" in sensitivity
            or "negedge" in sensitivity
        )

        if is_sequential:
            if contains_blocking_assignment(block):
                issues.append({
                    "severity": "warning",
                    "code": "BLOCKING_IN_SEQ",
                    "message": (
                        "У послідовнісній логіці виявлено блокувальне "
                        "присвоєння =. Для опису регістрів зазвичай "
                        "використовується неблокирувальне присвоєння <=."
                    ),
                    "source": "custom",
                })

            continue

        if (
            re.search(r"\bif\s*\(", block, flags=re.IGNORECASE)
            and not re.search(r"\belse\b", block, flags=re.IGNORECASE)
        ):
            issues.append({
                "severity": "warning",
                "code": "IF_WITHOUT_ELSE_COMB",
                "message": (
                    "У комбінаційному always-блоці виявлено if без else. "
                    "За неповного присвоєння виходів це може призвести "
                    "до виведення latch."
                ),
                "source": "custom",
            })

        if contains_nonblocking_assignment(block):
            issues.append({
                "severity": "warning",
                "code": "NONBLOCKING_IN_COMB",
                "message": (
                    "У комбінаційній логіці виявлено неблокирувальне "
                    "присвоєння <=. Для always @(*) зазвичай "
                    "використовується блокувальне присвоєння =."
                ),
                "source": "custom",
            })

    # SystemVerilog always_comb також належить до комбінаційної логіки.
    always_comb_blocks = re.findall(
        r"\balways_comb\s*begin(.*?)\bend\b",
        clean_code,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for block in always_comb_blocks:
        if (
            re.search(r"\bif\s*\(", block, flags=re.IGNORECASE)
            and not re.search(r"\belse\b", block, flags=re.IGNORECASE)
        ):
            issues.append({
                "severity": "warning",
                "code": "IF_WITHOUT_ELSE_COMB",
                "message": (
                    "У блоці always_comb виявлено if без else. "
                    "За неповного присвоєння сигналів це може "
                    "призвести до виведення latch."
                ),
                "source": "custom",
            })

        if contains_nonblocking_assignment(block):
            issues.append({
                "severity": "warning",
                "code": "NONBLOCKING_IN_COMB",
                "message": (
                    "У блоці always_comb виявлено неблокирувальне "
                    "присвоєння <=. Для комбінаційної логіки "
                    "зазвичай використовується присвоєння =."
                ),
                "source": "custom",
            })

    # Перевірка сигналів reset має евристичний характер:
    # враховуються типові назви reset, rst, reset_n та rst_n.
    reset_signal_pattern = (
        r"\b(?:reset|rst|reset_n|rst_n)\b"
    )

    has_reset_signal = re.search(
        reset_signal_pattern,
        code_lower,
    ) is not None

    has_sequential_logic = re.search(
        r"\b(?:posedge|negedge)\b",
        code_lower,
    ) is not None

    if has_reset_signal and has_sequential_logic:
        reset_used_in_condition = re.search(
            rf"\bif\s*\([^)]*{reset_signal_pattern}[^)]*\)",
            code_lower,
        ) is not None

        if not reset_used_in_condition:
            issues.append({
                "severity": "warning",
                "code": "RESET_NOT_HANDLED",
                "message": (
                    "У HDL-коді виявлено сигнал reset/rst, але "
                    "не знайдено його явної обробки в умові if."
                ),
                "source": "custom",
            })

    # Затримки # характерні для testbench і зазвичай не повинні
    # використовуватися в синтезованому студентському RTL-коді.
    delay_pattern = (
        r"#\s*(?:"
        r"\([^)]*\)"
        r"|[A-Za-z_][A-Za-z0-9_$]*"
        r"|\d+(?:\.\d+)?"
        r")"
    )

    if re.search(delay_pattern, clean_code):
        issues.append({
            "severity": "warning",
            "code": "DELAY_IN_DESIGN",
            "message": (
                "У HDL-рішенні виявлено часову затримку через #. "
                "У синтезованому FPGA-коді такі конструкції "
                "зазвичай не використовуються."
            ),
            "source": "custom",
        })

    if re.search(
        r"\binitial\b",
        code_lower,
    ):
        issues.append({
            "severity": "warning",
            "code": "INITIAL_IN_DESIGN",
            "message": (
                "У рішенні виявлено блок initial. Він є типовим "
                "для testbench, однак допустимість його використання "
                "в синтезованому FPGA-модулі залежить від цільового "
                "середовища та вимог лабораторної роботи."
            ),
            "source": "custom",
        })

    return issues


def calculate_hdl_lint_score(issues) -> int:
    """
    Обчислює lint-оцінку HDL-коду на основі типів
    і рівнів важливості виявлених проблем.
    """
    score = 100

    severity_penalties = {
        "error": 40,
        "warning": 10,
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
        "BLKSEQ": 15,
    }

    seen_issues = set()

    for issue in issues:
        issue_code = str(
            issue.get("code", "")
        ).strip()

        severity = str(
            issue.get("severity", "warning")
        ).strip().lower()

        message = str(
            issue.get("message", "")
        ).strip()

        source = str(
            issue.get("source", "")
        ).strip()

        # Точне дублювання одного діагностичного повідомлення
        # не повинно призводити до повторного штрафу.
        issue_key = (
            source,
            issue_code,
            severity,
            message,
        )

        if issue_key in seen_issues:
            continue

        seen_issues.add(issue_key)

        penalty = code_specific_penalties.get(
            issue_code,
            severity_penalties.get(
                severity,
                10,
            ),
        )

        score -= penalty

    return max(0, min(100, score))


def build_hdl_lint_recommendation(issues) -> str:
    """Формує навчальні рекомендації за результатами HDL lint-аналізу."""
    if not issues:
        return (
            "HDL-код не містить суттєвих стилістичних зауважень. "
            "Структура опису виглядає коректно."
        )

    recommendations = []
    codes = {
        str(issue.get("code", "")).strip()
        for issue in issues
    }

    if "CASE_WITHOUT_DEFAULT" in codes:
        recommendations.append(
            "Перевірте повноту case-конструкції та за потреби "
            "додайте гілку default."
        )

    if (
        "IF_WITHOUT_ELSE_COMB" in codes
        or "LATCH" in codes
    ):
        recommendations.append(
            "Перевірте повноту присвоєнь у комбінаційній логіці, "
            "щоб уникнути ненавмисного виведення latch."
        )

    if (
        "BLOCKING_IN_SEQ" in codes
        or "BLKSEQ" in codes
    ):
        recommendations.append(
            "У послідовнісній логіці для опису регістрів "
            "зазвичай використовуйте неблокирувальні присвоєння <=."
        )

    if "NONBLOCKING_IN_COMB" in codes:
        recommendations.append(
            "У комбінаційній логіці зазвичай використовуйте "
            "блокувальні присвоєння =."
        )

    if "UNUSEDSIGNAL" in codes:
        recommendations.append(
            "Перевірте оголошені, але невикористані сигнали: "
            "видаліть їх або використайте відповідно до логіки модуля."
        )

    if "UNDRIVEN" in codes:
        recommendations.append(
            "Перевірте сигнали, для яких не формується значення."
        )

    if "RESET_NOT_HANDLED" in codes:
        recommendations.append(
            "Перевірте явну обробку сигналу reset/rst "
            "у послідовнісній логіці."
        )

    if "DELAY_IN_DESIGN" in codes:
        recommendations.append(
            "Перевірте використання затримок #. У синтезованому "
            "RTL-коді такі конструкції зазвичай не використовуються."
        )

    if "INITIAL_IN_DESIGN" in codes:
        recommendations.append(
            "Перевірте необхідність блока initial та його підтримку "
            "обраним середовищем синтезу і цільовою FPGA."
        )

    if not recommendations:
        recommendations.append(
            "Проаналізуйте повідомлення Verilator і скоригуйте "
            "HDL-опис відповідно до виявлених зауважень."
        )

    return " ".join(recommendations)


# =========================
# 7. Перевірка Python-рішень
# =========================

def is_docker_available() -> bool:
    """
    Перевіряє доступність Docker CLI та з'єднання з Docker daemon.

    На відміну від docker --version, команда docker info підтверджує,
    що середовище Docker не лише встановлене, а й готове до запуску
    контейнерів.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "info",
                "--format",
                "{{.ServerVersion}}",
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
            check=False,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False


def is_docker_image_available(image_name: str) -> bool:
    """Перевіряє наявність визначеного Docker-образу в локальному сховищі."""
    if not image_name:
        return False

    try:
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                image_name,
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
            check=False,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
    ):
        return False


def is_python_checker_image_available() -> bool:
    """Перевіряє наявність Docker-образу для виконання Python-перевірок."""
    return is_docker_image_available(
        PYTHON_DOCKER_IMAGE
    )


def contains_dangerous_python_code(code) -> tuple[bool, str]:
    """
    Виконує попередню AST-перевірку очевидно небажаних конструкцій Python.

    Ця перевірка є додатковим фільтром і не використовується як межа
    безпеки. Ізоляція недовіреного Python-коду забезпечується Docker.
    """
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
        "multiprocessing",
        "importlib",
    }

    forbidden_calls = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
    }

    try:
        tree = ast.parse(
            str(code or "")
        )

    except SyntaxError:
        # Синтаксичні помилки обробляються під час основної
        # Python/pytest-перевірки, а не security-фільтром.
        return False, ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(
                    ".",
                    maxsplit=1,
                )[0]

                if module_name in forbidden_imports:
                    return (
                        True,
                        f"import {module_name}",
                    )

        elif isinstance(node, ast.ImportFrom):
            module_name = (
                node.module or ""
            ).split(
                ".",
                maxsplit=1,
            )[0]

            if module_name in forbidden_imports:
                return (
                    True,
                    f"from {module_name} import ...",
                )

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                function_name = node.func.id

                if function_name in forbidden_calls:
                    return (
                        True,
                        f"{function_name}(...)",
                    )

        elif isinstance(node, ast.While):
            # Очевидно нескінченні цикли відхиляються ще до запуску.
            # Основним захистом від зависання залишається timeout Docker.
            if (
                isinstance(node.test, ast.Constant)
                and bool(node.test.value) is True
            ):
                return True, "while <постійно істинна умова>"

    return False, ""


def parse_pytest_result(output) -> tuple[int, int]:
    """Витягує кількість успішних і загальну кількість тестів із pytest-звіту."""
    output_lower = str(
        output or ""
    ).lower()

    passed_match = re.search(
        r"\b(\d+)\s+passed\b",
        output_lower,
    )

    failed_match = re.search(
        r"\b(\d+)\s+failed\b",
        output_lower,
    )

    error_match = re.search(
        r"\b(\d+)\s+errors?\b",
        output_lower,
    )

    passed = (
        int(passed_match.group(1))
        if passed_match
        else 0
    )

    failed = (
        int(failed_match.group(1))
        if failed_match
        else 0
    )

    errors = (
        int(error_match.group(1))
        if error_match
        else 0
    )

    total = passed + failed + errors

    return passed, total


def format_python_report(
    raw_output,
    passed_tests: int,
    total_tests: int,
    include_pytest_output: bool = True,
) -> str:
    """
    Формує звіт про результати Python/pytest-перевірки.

    Детальний вивід pytest можна приховати для сценаріїв,
    у яких він містить інформацію про закриті тести.
    """
    if total_tests > 0:
        score = round(
            (passed_tests / total_tests) * 100
        )
    else:
        score = 0

    report = [
        f"Результат: {score} / 100 балів",
        f"Пройдено тестів: {passed_tests} із {total_tests}",
    ]

    if include_pytest_output:
        report.extend([
            "",
            "Звіт pytest:",
            str(raw_output or "").strip(),
        ])

    return "\n".join(report)


def build_python_docker_command(
    workspace_path: str,
    container_name: str,
) -> list[str]:
    """
    Формує команду запуску pytest у захищеному Docker-контейнері.

    Робочий каталог монтується лише для читання, оскільки студентський
    код і тести не повинні змінюватися під час автоматичної перевірки.
    """
    host_workspace = os.path.abspath(
        workspace_path
    )

    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,

        # Код студента не потребує мережевого доступу під час перевірки.
        "--network",
        "none",

        # Обмеження ресурсів захищають сервер від надмірного
        # використання CPU, пам'яті та кількості процесів.
        "--cpus",
        "0.5",

        "--memory",
        "128m",

        "--pids-limit",
        "64",

        # Коренева файлова система контейнера залишається незмінною.
        "--read-only",

        # Тимчасові файли дозволено створювати лише в окремому
        # обмеженому tmpfs-каталозі.
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",

        "--security-opt",
        "no-new-privileges",

        "--cap-drop",
        "ALL",

        # Python не створює __pycache__ у read-only workspace.
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",

        # Сторонні pytest-плагіни не завантажуються автоматично,
        # що робить середовище перевірки більш передбачуваним.
        "-e",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",

        # На відміну від HDL-перевірки, pytest не потребує запису
        # до workspace, тому рішення і тести монтуються read-only.
        "-v",
        f"{host_workspace}:/workspace:ro",

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
        "test_solution.py",
    ]


def run_python_unit_tests_check(
    solution_path: str,
    lab,
) -> dict:
    """
    Виконує автоматичну перевірку Python-рішення за допомогою pytest
    в ізольованому Docker-контейнері.

    Перед запуском виконується додаткова AST-перевірка очевидно
    небажаних конструкцій. Основну межу безпеки забезпечують
    обмеження Docker, а не статичний аналіз Python-коду.
    """
    if not is_docker_available():
        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Docker недоступний.\n\n"
                "Перевірте, чи встановлено та запущено Docker."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

    if not is_python_checker_image_available():
        return {
            "status": "SYSTEM_ERROR",
            "output": (
                f"Docker-образ {PYTHON_DOCKER_IMAGE} не знайдено.\n\n"
                "Створіть його командою:\n"
                f"docker build -t {PYTHON_DOCKER_IMAGE} "
                "docker/python-checker"
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

    testbench_text = str(
        get_row_value(
            lab,
            "testbench",
            "",
        )
        or ""
    )

    if not testbench_text.strip():
        app.logger.error(
            "Для Python-лабораторної роботи відсутній testbench."
        )

        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Автоматичну перевірку неможливо виконати: "
                "для лабораторної роботи не налаштовано тести."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

    try:
        # Окремий каталог ізолює файли конкретної перевірки
        # та автоматично очищується після завершення операції.
        with tempfile.TemporaryDirectory(
            prefix="python_check_"
        ) as temp_dir:
            with open(
                solution_path,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:
                student_code = file.read()

            (
                is_dangerous,
                dangerous_fragment,
            ) = contains_dangerous_python_code(
                student_code
            )

            if is_dangerous:
                return {
                    "status": "SECURITY_BLOCK",
                    "output": (
                        "Код не було запущено, оскільки система "
                        "виявила потенційно небажану конструкцію.\n\n"
                        f"Виявлений фрагмент: {dangerous_fragment}\n\n"
                        "У навчальному середовищі обмежено доступ "
                        "до файлової системи, системних команд, мережі "
                        "та динамічного виконання коду."
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": 0,
                }

            solution_file = os.path.join(
                temp_dir,
                "solution.py",
            )

            test_file = os.path.join(
                temp_dir,
                "test_solution.py",
            )

            shutil.copyfile(
                solution_path,
                solution_file,
            )

            with open(
                test_file,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    testbench_text
                )

            container_name = (
                f"fpga-python-check-{secrets.token_hex(8)}"
            )

            docker_command = build_python_docker_command(
                workspace_path=temp_dir,
                container_name=container_name,
            )

            try:
                result = subprocess.run(
                    docker_command,
                    capture_output=True,
                    text=True,
                    timeout=PYTHON_CHECK_TIMEOUT_SECONDS,
                    check=False,
                )

            except subprocess.TimeoutExpired:
                force_remove_docker_container(
                    container_name
                )

                app.logger.warning(
                    "Python-перевірку в Docker зупинено через "
                    "перевищення встановленого ліміту часу."
                )

                return {
                    "status": "TIMEOUT",
                    "output": (
                        "Перевищено допустимий час виконання "
                        "Python-коду.\n\n"
                        "Перевірте цикли, рекурсію або складність алгоритму."
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": 0,
                }

            output = get_process_output(
                result
            )

            passed_tests, total_tests = parse_pytest_result(
                output
            )

            output_lower = output.lower()

            # Синтаксичні помилки належать до рішення студента,
            # а не до інфраструктурних помилок системи.
            if (
                "syntaxerror" in output_lower
                or "indentationerror" in output_lower
            ):
                return {
                    "status": "COMPILE_ERROR",
                    "output": format_python_report(
                        output,
                        0,
                        total_tests,
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": total_tests,
                }

            # pytest використовує код 3 для INTERNAL_ERROR,
            # а код 4 — для помилки використання або конфігурації.
            if result.returncode in {3, 4}:
                app.logger.error(
                    "pytest завершився з інфраструктурним кодом %s. "
                    "Вивід: %s",
                    result.returncode,
                    output,
                )

                return {
                    "status": "SYSTEM_ERROR",
                    "output": (
                        "Python-перевірку не завершено через "
                        "внутрішню помилку середовища pytest."
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": 0,
                }

            # Код 5 означає, що pytest не знайшов жодного тесту.
            # За наявності testbench це є проблемою конфігурації
            # лабораторної роботи, а не помилкою студента.
            if result.returncode == 5:
                app.logger.error(
                    "pytest не зібрав жодного тесту для Python-лабораторної."
                )

                return {
                    "status": "SYSTEM_ERROR",
                    "output": (
                        "Автоматичну перевірку неможливо виконати: "
                        "pytest не знайшов тестів у конфігурації "
                        "лабораторної роботи."
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": 0,
                }

            if total_tests <= 0:
                app.logger.warning(
                    "Не вдалося визначити кількість pytest-тестів. "
                    "Код завершення: %s. Вивід: %s",
                    result.returncode,
                    output,
                )

                return {
                    "status": "FAILED",
                    "output": format_python_report(
                        (
                            output
                            + "\n\n"
                            + (
                                "Не вдалося визначити кількість "
                                "виконаних тестів."
                            )
                        ),
                        0,
                        0,
                    ),
                    "score": 0,
                    "passed_tests": 0,
                    "total_tests": 0,
                }

            score = round(
                (passed_tests / total_tests) * 100
            )

            if (
                result.returncode == 0
                and passed_tests == total_tests
            ):
                status = "PASSED"

            elif passed_tests > 0:
                status = "PARTIAL"

            else:
                status = "FAILED"

            return {
                "status": status,
                "output": format_python_report(
                    output,
                    passed_tests,
                    total_tests,
                ),
                "score": score,
                "passed_tests": passed_tests,
                "total_tests": total_tests,
            }

    except OSError:
        app.logger.exception(
            "Помилка файлового середовища під час "
            "Docker-перевірки Python-рішення."
        )

        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Не вдалося підготувати файли для автоматичної "
                "перевірки Python-рішення."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

    except Exception:
        app.logger.exception(
            "Системна помилка перевірки Python-рішення."
        )

        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Виникла внутрішня помилка системи під час "
                "перевірки Python-рішення."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }


def run_sql_query_check(
    solution_path,
    lab,
) -> dict:
    """
    Повертає контрольований результат для ще не реалізованого
    механізму автоматичної перевірки SQL-рішень.
    """
    return {
        "status": "SYSTEM_ERROR",
        "output": (
            "Автоматичну перевірку SQL-завдань наразі не реалізовано."
        ),
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0,
    }


def run_cpp_tests_check(
    solution_path,
    lab,
) -> dict:
    """
    Повертає контрольований результат для ще не реалізованого
    механізму автоматичної перевірки C++-рішень.
    """
    return {
        "status": "SYSTEM_ERROR",
        "output": (
            "Автоматичну перевірку C++-завдань наразі не реалізовано."
        ),
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0,
    }


def build_student_visible_hdl_output(
    public_result,
    hidden_result,
    final_score,
    show_hidden_details: bool = False,
) -> str:
    """
    Формує звіт HDL-перевірки з окремим відображенням
    відкритих і прихованих тестів.

    Детальний вивід прихованого testbench не повинен передаватися
    студенту; параметр show_hidden_details призначений лише для
    авторизованого перегляду викладачем або адміністратором.
    """
    public_passed = int(
        public_result.get(
            "passed_tests",
            0,
        )
        or 0
    )

    public_total = int(
        public_result.get(
            "total_tests",
            0,
        )
        or 0
    )

    hidden_passed = int(
        hidden_result.get(
            "passed_tests",
            0,
        )
        or 0
    )

    hidden_total = int(
        hidden_result.get(
            "total_tests",
            0,
        )
        or 0
    )

    output_lines = [
        (
            f"Відкриті тести: "
            f"{public_passed} із {public_total}"
        ),
    ]

    if hidden_total > 0:
        output_lines.append(
            f"Приховані тести: "
            f"{hidden_passed} із {hidden_total}"
        )
    else:
        output_lines.append(
            "Приховані тести: не задано"
        )

    output_lines.extend([
        f"Підсумковий бал: {final_score} / 100",
        "",
        "--- Відкритий звіт перевірки ---",
        str(
            public_result.get(
                "output",
                "",
            )
            or ""
        ),
    ])

    if hidden_total > 0:
        output_lines.extend([
            "",
            "--- Приховані тести ---",
        ])

        if show_hidden_details:
            output_lines.append(
                str(
                    hidden_result.get(
                        "output",
                        "",
                    )
                    or ""
                )
            )
        else:
            output_lines.append(
                "Деталі прихованих тестів не відображаються студенту. "
                "Вони використовуються лише для формування "
                "підсумкової оцінки."
            )

    return "\n".join(
        output_lines
    )


HDL_CRITICAL_CHECK_STATUSES = frozenset({
    "COMPILE_ERROR",
    "SYSTEM_ERROR",
    "TIMEOUT",
    "SIMULATION_ERROR",
})


def build_student_visible_hdl_output(
    public_result,
    hidden_result,
    final_score,
    show_hidden_details: bool = False,
) -> str:
    """
    Формує звіт HDL-перевірки, безпечний для відображення студенту.

    Детальний результат прихованих тестів навмисно не включається
    до студентського звіту незалежно від параметрів лабораторної роботи.
    Повний hidden_output залишається в службовому результаті перевірки
    та може використовуватися в авторизованому інтерфейсі викладача.
    """
    if show_hidden_details:
        # Параметр тимчасово зберігається для сумісності зі старими
        # викликами, але не може розкривати приховані тести студенту.
        app.logger.warning(
            "Спроба сформувати студентський HDL-звіт "
            "із show_hidden_details=True була проігнорована."
        )

    public_passed = int(
        public_result.get("passed_tests", 0) or 0
    )
    public_total = int(
        public_result.get("total_tests", 0) or 0
    )

    hidden_passed = int(
        hidden_result.get("passed_tests", 0) or 0
    )
    hidden_total = int(
        hidden_result.get("total_tests", 0) or 0
    )

    hidden_status = str(
        hidden_result.get("status", "") or ""
    ).strip()

    output_lines = [
        f"Відкриті тести: {public_passed} із {public_total}",
    ]

    if hidden_status == "NOT_CONFIGURED":
        output_lines.append(
            "Приховані тести: не задано"
        )

    elif hidden_status == "NOT_RUN":
        output_lines.append(
            "Приховані тести: не виконувалися"
        )

    elif hidden_status == "SYSTEM_ERROR":
        output_lines.append(
            "Приховані тести: перевірка тимчасово недоступна"
        )

    elif hidden_status == "TIMEOUT":
        output_lines.append(
            "Приховані тести: перевищено ліміт часу перевірки"
        )

    elif hidden_status == "COMPILE_ERROR":
        output_lines.append(
            "Приховані тести: перевірку не завершено "
            "через помилку компіляції"
        )

    elif hidden_status == "SIMULATION_ERROR":
        output_lines.append(
            "Приховані тести: перевірку не завершено "
            "через помилку моделювання"
        )

    elif hidden_total > 0:
        output_lines.append(
            f"Приховані тести: {hidden_passed} із {hidden_total}"
        )

    else:
        output_lines.append(
            "Приховані тести: результат відсутній"
        )

    output_lines.extend([
        f"Підсумковий бал: {final_score} / 100",
        "",
        "--- Відкритий звіт перевірки ---",
        str(
            public_result.get("output", "") or ""
        ),
    ])

    if hidden_status != "NOT_CONFIGURED":
        output_lines.extend([
            "",
            "--- Приховані тести ---",
            (
                "Деталі прихованих тестів не відображаються студенту. "
                "Вони використовуються для автоматичного оцінювання "
                "та доступні лише авторизованому викладачу "
                "або адміністратору."
            ),
        ])

    return "\n".join(output_lines)


def run_hdl_public_hidden_check(
    solution_path,
    lab,
    waveform_save_path=None,
) -> dict:
    """
    Виконує послідовну перевірку HDL-рішення відкритим
    і прихованим testbench.

    Відкриті тести формують детальний студентський звіт.
    Приховані тести впливають на підсумкову оцінку, але їхній
    детальний вивід не передається студенту.
    """
    public_testbench = str(
        get_row_value(
            lab,
            "public_testbench",
            "",
        )
        or ""
    ).strip()

    # Для лабораторних робіт, створених до появи окремих public/hidden
    # testbench, поле testbench використовується як відкритий набір тестів.
    if not public_testbench:
        public_testbench = str(
            get_row_value(
                lab,
                "testbench",
                "",
            )
            or ""
        ).strip()

    hidden_testbench = str(
        get_row_value(
            lab,
            "hidden_testbench",
            "",
        )
        or ""
    ).strip()

    # Відсутність основного testbench є помилкою конфігурації
    # лабораторної роботи, а не помилкою студентського HDL-рішення.
    if not public_testbench:
        app.logger.error(
            "Для HDL-лабораторної роботи відсутній public_testbench/testbench."
        )

        return {
            "status": "SYSTEM_ERROR",
            "output": (
                "Автоматичну HDL-перевірку неможливо виконати: "
                "для лабораторної роботи не налаштовано відкриті тести."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,

            "public_status": "SYSTEM_ERROR",
            "public_score": 0,
            "public_passed_tests": 0,
            "public_total_tests": 0,
            "public_output": (
                "Відкритий testbench не налаштовано."
            ),

            "hidden_status": (
                "NOT_RUN"
                if hidden_testbench
                else "NOT_CONFIGURED"
            ),
            "hidden_score": 0,
            "hidden_passed_tests": 0,
            "hidden_total_tests": 0,
            "hidden_output": (
                "Приховані тести не виконувалися."
                if hidden_testbench
                else "Приховані тести не задано."
            ),

            "waveform_created": False,
        }

    # 1. Відкритий testbench виконується першим, оскільки саме його
    # результат може бути детально показаний студенту.
    (
        public_status,
        public_output,
        public_score,
        public_passed,
        public_total,
        waveform_created,
    ) = run_hdl_check(
        user_code_path=solution_path,
        testbench_text=public_testbench,
        waveform_save_path=waveform_save_path,
    )

    public_result = {
        "status": public_status,
        "output": public_output,
        "score": public_score,
        "passed_tests": public_passed,
        "total_tests": public_total,
    }

    # Якщо основний етап завершився критичною помилкою,
    # повторний запуск того самого рішення зі hidden testbench
    # не надасть корисного навчального результату.
    if public_status in HDL_CRITICAL_CHECK_STATUSES:
        hidden_result = {
            "status": "NOT_RUN",
            "output": (
                "Приховані тести не виконувалися, оскільки "
                "відкрита перевірка завершилася критичною помилкою."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

        final_score = 0

        student_output = build_student_visible_hdl_output(
            public_result=public_result,
            hidden_result=hidden_result,
            final_score=final_score,
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

            "waveform_created": waveform_created,
        }

    # 2. За відсутності hidden testbench результат відкритої перевірки
    # безпосередньо стає результатом функціонального тестування.
    if not hidden_testbench:
        hidden_result = {
            "status": "NOT_CONFIGURED",
            "output": (
                "Приховані тести для цієї лабораторної роботи не задано."
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

        final_passed = public_passed
        final_total = public_total
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

            "waveform_created": waveform_created,
        }

    # 3. Hidden testbench запускається окремо без збереження VCD.
    # Це запобігає заміні відкритого waveform артефактом прихованих тестів.
    (
        hidden_status,
        hidden_output,
        hidden_score,
        hidden_passed,
        hidden_total,
        _hidden_waveform_created,
    ) = run_hdl_check(
        user_code_path=solution_path,
        testbench_text=hidden_testbench,
        waveform_save_path=None,
    )

    hidden_result = {
        "status": hidden_status,
        "output": hidden_output,
        "score": hidden_score,
        "passed_tests": hidden_passed,
        "total_tests": hidden_total,
    }

    # 4. Відкриті та приховані тести мають однакову вагу на рівні
    # окремого test case, тому підсумковий бал обчислюється за їх
    # сумарною кількістю.
    final_passed = (
        public_passed
        + hidden_passed
    )

    final_total = (
        public_total
        + hidden_total
    )

    if final_total > 0:
        final_score = round(
            (final_passed / final_total) * 100
        )
    else:
        final_score = 0

    # Інфраструктурна або критична помилка hidden-етапу
    # має бути збережена у фінальному статусі та не маскуватися
    # частково успішним результатом відкритих тестів.
    if hidden_status in HDL_CRITICAL_CHECK_STATUSES:
        final_status = hidden_status

    elif (
        final_total > 0
        and final_passed == final_total
    ):
        final_status = "PASSED"

    elif final_passed > 0:
        final_status = "PARTIAL"

    else:
        final_status = "FAILED"

    # Студентський звіт ніколи не отримує детальний hidden_output.
    # Повний результат залишається окремим службовим полем нижче.
    student_output = build_student_visible_hdl_output(
        public_result=public_result,
        hidden_result=hidden_result,
        final_score=final_score,
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

        "waveform_created": waveform_created,
    }


def add_default_check_fields(result: dict) -> dict:
    """
    Доповнює результат перевірки стандартними полями public/hidden,
    щоб різні checker-модулі повертали сумісну структуру даних.
    """
    result.setdefault(
        "public_status",
        "",
    )
    result.setdefault(
        "public_score",
        0,
    )
    result.setdefault(
        "public_passed_tests",
        0,
    )
    result.setdefault(
        "public_total_tests",
        0,
    )
    result.setdefault(
        "public_output",
        "",
    )

    result.setdefault(
        "hidden_status",
        "",
    )
    result.setdefault(
        "hidden_score",
        0,
    )
    result.setdefault(
        "hidden_passed_tests",
        0,
    )
    result.setdefault(
        "hidden_total_tests",
        0,
    )
    result.setdefault(
        "hidden_output",
        "",
    )

    result.setdefault(
        "waveform_created",
        False,
    )

    return result


def run_solution_check(
    solution_path,
    lab,
    waveform_save_path=None,
) -> dict:
    """
    Вибирає модуль автоматичної перевірки відповідно
    до checker_type лабораторної роботи.

    Усі checker-модулі нормалізуються до єдиного формату результату,
    що використовується подальшими компонентами оцінювання й аналітики.
    """
    checker_type = str(
        get_row_value(
            lab,
            "checker_type",
            "hdl_testbench",
        )
        or "hdl_testbench"
    ).strip().lower()

    if checker_type == "hdl_testbench":
        result = run_hdl_public_hidden_check(
            solution_path=solution_path,
            lab=lab,
            waveform_save_path=waveform_save_path,
        )

    elif checker_type == "python_unit_tests":
        result = run_python_unit_tests_check(
            solution_path,
            lab,
        )

    elif checker_type == "sql_query":
        result = run_sql_query_check(
            solution_path,
            lab,
        )

    elif checker_type == "cpp_tests":
        result = run_cpp_tests_check(
            solution_path,
            lab,
        )

    else:
        app.logger.error(
            "Непідтримуваний checker_type лабораторної роботи: %s",
            checker_type,
        )

        result = {
            "status": "SYSTEM_ERROR",
            "output": (
                "Автоматичну перевірку неможливо виконати через "
                f"невідомий тип перевірки: {checker_type}"
            ),
            "score": 0,
            "passed_tests": 0,
            "total_tests": 0,
        }

    return add_default_check_fields(
        result
    )



# =========================
# 8. Діагностика помилок рішень
# =========================

def detect_lab_topic_for_diagnostics(lab, code) -> str:
    """
    Визначає узагальнену тему лабораторної роботи для вибору
    контекстних правил діагностики HDL-помилок.
    """
    explicit_topic = str(
        get_row_value(
            lab,
            "topic",
            "",
        )
        or ""
    ).strip().lower()

    if explicit_topic in {
        "mux",
        "adder",
        "counter",
        "register",
        "fsm",
    }:
        return explicit_topic

    diagnostic_parts = [
        get_row_value(lab, "title", ""),
        get_row_value(lab, "description", ""),
        get_row_value(lab, "public_testbench", ""),
        get_row_value(lab, "hidden_testbench", ""),
        get_row_value(lab, "testbench", ""),
        code,
    ]

    text = " ".join(
        str(part or "")
        for part in diagnostic_parts
    ).lower()

    topic_keywords = {
        "mux": {
            "mux",
            "multiplexer",
            "мультиплексор",
            "селектор",
        },
        "adder": {
            "adder",
            "sum",
            "carry",
            "суматор",
            "додавання",
        },
        "counter": {
            "counter",
            "count",
            "лічильник",
        },
        "register": {
            "register",
            "регістр",
        },
        "fsm": {
            "fsm",
            "state machine",
            "state",
            "автомат станів",
            "скінченний автомат",
        },
    }

    for topic, keywords in topic_keywords.items():
        if any(
            keyword in text
            for keyword in keywords
        ):
            return topic

    return "general"


def has_any(text, keywords) -> bool:
    """Перевіряє наявність хоча б одного ключового фрагмента в тексті."""
    normalized_text = str(
        text or ""
    ).casefold()

    return any(
        str(keyword).casefold() in normalized_text
        for keyword in keywords
    )


def code_has_incomplete_condition(code) -> bool:
    """
    Евристично визначає ризик неповного опису комбінаційної логіки.

    Використовуються ті самі custom lint-правила, що й під час
    статичного HDL-аналізу, щоб не дублювати різні евристики.
    """
    issues = run_custom_hdl_style_checks(
        str(code or "")
    )

    incomplete_condition_codes = {
        "CASE_WITHOUT_DEFAULT",
        "IF_WITHOUT_ELSE_COMB",
    }

    return any(
        issue.get("code") in incomplete_condition_codes
        for issue in issues
    )


def output_has_undefined_signal_value(output) -> bool:
    """
    Виявляє явні невизначені значення x/z у результатах testbench.

    Окремі символи x та z не шукаються по всьому тексту,
    оскільки це створювало велику кількість хибних спрацьовувань.
    """
    text = str(
        output or ""
    )

    patterns = [
        r"(?im)^\s*отримано\s*:\s*[b]?[01xz_]*[xz][01xz_]*\s*$",
        r"(?im)^\s*actual\s*:\s*[b]?[01xz_]*[xz][01xz_]*\s*$",
        r"\bundefined\b",
        r"\bunknown value\b",
        r"\blatch\b",
    ]

    return any(
        re.search(pattern, text) is not None
        for pattern in patterns
    )


def get_failed_test_blocks(output) -> list[str]:
    """
    Витягує з testbench-звіту фрагменти тестів,
    які завершилися невдалим результатом.
    """
    lines = str(
        output or ""
    ).splitlines()

    failed_blocks = []

    for index, line in enumerate(lines):
        stripped_line = line.strip()
        line_lower = stripped_line.casefold()

        # Службовий формат CASE також підтримується, якщо класифікатор
        # отримав необроблений вивід моделювання.
        if stripped_line.startswith("CASE|"):
            parts = [
                part.strip()
                for part in stripped_line.split("|")
            ]

            if (
                len(parts) == 6
                and parts[5].upper() != "PASS"
            ):
                failed_blocks.append(
                    stripped_line
                )

            continue

        # Формат студентського звіту:
        # Тест 2: ... — не пройдено
        # Очікувалося: ...
        # Отримано: ...
        if (
            line_lower.startswith("тест ")
            and "не пройдено" in line_lower
        ):
            block = [
                stripped_line
            ]

            for offset in (1, 2):
                next_index = index + offset

                if next_index < len(lines):
                    block.append(
                        lines[next_index].strip()
                    )

            failed_blocks.append(
                "\n".join(block)
            )

    return failed_blocks


def classify_hdl_error(
    status,
    output,
    lab,
    code,
) -> dict:
    """
    Класифікує результат HDL-перевірки та формує навчальну рекомендацію.

    Класифікація поєднує фактичний статус конвеєра, повідомлення
    інструментів, результат testbench і додаткові евристичні ознаки.
    Системні відмови відокремлюються від помилок студентського коду.
    """
    normalized_status = str(
        status or ""
    ).strip().upper()

    output_text = str(
        output or ""
    )

    output_lower = output_text.casefold()

    code_text = str(
        code or ""
    )

    topic = detect_lab_topic_for_diagnostics(
        lab,
        code_text,
    )

    failed_blocks = get_failed_test_blocks(
        output_text
    )

    failed_text = "\n".join(
        failed_blocks
    ).casefold()

    # Успішне проходження функціональної перевірки.
    if normalized_status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Помилок не виявлено",
            "error_details": (
                "HDL-рішення успішно пройшло всі виконані "
                "функціональні тести."
            ),
            "recommendation": (
                "Додаткові дії не потрібні."
            ),
            "error_confidence": 100,
        }

    # Системна відмова не характеризує якість рішення студента
    # і не повинна потрапляти до його навчального профілю як HDL-помилка.
    if normalized_status == "SYSTEM_ERROR":
        return {
            "error_type": "SYSTEM_ERROR",
            "error_title": "Системна помилка перевірки",
            "error_details": (
                "Автоматичну HDL-перевірку не вдалося завершити "
                "через проблему середовища або інфраструктури."
            ),
            "recommendation": (
                "Повторіть перевірку після відновлення роботи "
                "середовища. Якщо проблема повторюється, зверніться "
                "до викладача або адміністратора."
            ),
            "error_confidence": 100,
        }

    if normalized_status == "TIMEOUT":
        return {
            "error_type": "TIMEOUT",
            "error_title": "Перевищено ліміт часу перевірки",
            "error_details": (
                "Компіляція або моделювання HDL-рішення не завершилися "
                "в межах встановленого ліміту часу."
            ),
            "recommendation": (
                "Перевірте HDL-код на наявність комбінаційних циклів "
                "або іншої логіки, що може призводити до надмірно "
                "тривалого моделювання. Якщо проблема не пов'язана "
                "з рішенням, повторіть перевірку."
            ),
            "error_confidence": 100,
        }

    if normalized_status == "SIMULATION_ERROR":
        return {
            "error_type": "SIMULATION_ERROR",
            "error_title": "Помилка HDL-моделювання",
            "error_details": (
                "Код було скомпільовано, але VVP не зміг коректно "
                "завершити моделювання."
            ),
            "recommendation": (
                "Проаналізуйте діагностичний вивід моделювання. "
                "Перевірте часову поведінку схеми, коректність сигналів "
                "і конструкції, що виконуються під час simulation."
            ),
            "error_confidence": 95,
        }

    # Помилки elaboration можуть бути спричинені невідповідністю
    # інтерфейсу студентського модуля testbench викладача.
    if (
        normalized_status == "COMPILE_ERROR"
        and has_any(
            output_lower,
            {
                "unknown module",
                "module not found",
                "unable to bind",
                "unknown module type",
                "root module",
            },
        )
    ):
        return {
            "error_type": "MODULE_NAME_MISMATCH",
            "error_title": "Невідповідність імені модуля",
            "error_details": (
                "Testbench не зміг підключити модуль студента. "
                "Ймовірною причиною є невідповідність імені модуля "
                "імені, визначеному в умові лабораторної роботи."
            ),
            "recommendation": (
                "Перевірте ім'я після ключового слова module. "
                "Воно має точно відповідати імені, яке очікує testbench."
            ),
            "error_confidence": 95,
        }

    if (
        normalized_status == "COMPILE_ERROR"
        and has_any(
            output_lower,
            {
                "is not a port",
                "cannot bind",
                "failed to elaborate port",
                "no port named",
                "port ",
            },
        )
    ):
        return {
            "error_type": "PORT_MISMATCH",
            "error_title": "Невідповідність портів модуля",
            "error_details": (
                "Інтерфейс HDL-модуля не відповідає інтерфейсу, "
                "який використовує testbench. Один або кілька портів "
                "можуть мати неправильне ім'я, напрям або бути відсутніми."
            ),
            "recommendation": (
                "Порівняйте список input/output-портів у завданні "
                "та у своєму Verilog-модулі. Особливо перевірте "
                "імена сигналів і розрядність."
            ),
            "error_confidence": 90,
        }

    if normalized_status == "COMPILE_ERROR":
        return {
            "error_type": "COMPILE_ERROR",
            "error_title": "Помилка компіляції HDL-коду",
            "error_details": (
                "HDL-код не пройшов компіляцію або elaboration. "
                "Причиною можуть бути синтаксичні помилки, неправильні "
                "оголошення сигналів або порушення структури модуля."
            ),
            "recommendation": (
                "Перевірте синтаксис Verilog: крапки з комою, "
                "оголошення input/output, конструкції assign та always, "
                "пари begin/end і завершення module через endmodule."
            ),
            "error_confidence": 85,
        }

    # Подальші правила застосовуються лише до функціонально
    # виконаних рішень, які повністю або частково не пройшли testbench.
    if normalized_status not in {
        "FAILED",
        "PARTIAL",
    }:
        app.logger.warning(
            "Класифікатор HDL отримав невідомий статус: %s",
            normalized_status,
        )

        return {
            "error_type": "SYSTEM_ERROR",
            "error_title": "Невідомий результат перевірки",
            "error_details": (
                "Система отримала непідтримуваний статус HDL-перевірки "
                "та не може достовірно класифікувати результат."
            ),
            "recommendation": (
                "Повторіть перевірку або зверніться до адміністратора."
            ),
            "error_confidence": 100,
        }

    diagnostic_text = (
        failed_text
        + "\n"
        + output_lower
    )

    # Для послідовнісних схем проблеми clock/reset мають вищий
    # діагностичний пріоритет за загальну функціональну помилку.
    if (
        topic in {
            "counter",
            "register",
            "fsm",
        }
        and has_any(
            diagnostic_text,
            {
                "reset",
                "reset_n",
                "rst",
                "rst_n",
                "clock",
                "clk",
                "posedge",
                "negedge",
                "скидання",
                "такт",
            },
        )
    ):
        return {
            "error_type": "RESET_CLOCK_ERROR",
            "error_title": (
                "Помилка clock/reset у послідовнісній логіці"
            ),
            "error_details": (
                "Результати тестування вказують на можливу проблему "
                "з тактовим сигналом, сигналом скидання або переходом "
                "схеми між станами."
            ),
            "recommendation": (
                "Перевірте sensitivity list блока always, фронт clock, "
                "активний рівень reset та значення регістрів після скидання."
            ),
            "error_confidence": 88,
        }

    if (
        topic == "mux"
        and has_any(
            diagnostic_text,
            {
                "sel",
                "select",
                "вибір",
                "керуваль",
            },
        )
    ):
        return {
            "error_type": "CONTROL_SIGNAL_ERROR",
            "error_title": "Помилка обробки керувального сигналу",
            "error_details": (
                "Результати тестування вказують, що при одному "
                "зі значень керувального сигналу вибирається "
                "неправильний вхід."
            ),
            "recommendation": (
                "Перевірте відповідність значень sel потрібним входам "
                "згідно з умовою лабораторної роботи та testbench."
            ),
            "error_confidence": 92,
        }

    # Граничні випадки перевіряються до загальної категорії
    # WRONG_COMBINATIONAL_LOGIC, інакше ця гілка була б недосяжною
    # для більшості комбінаційних лабораторних робіт.
    boundary_patterns = {
        "boundary",
        "гранич",
        "maximum",
        "minimum",
        "max value",
        "min value",
        "all zeros",
        "all ones",
        "усі нулі",
        "усі одиниці",
        "0000",
        "1111",
    }

    if has_any(
        failed_text,
        boundary_patterns,
    ):
        return {
            "error_type": "BOUNDARY_TEST_FAILED",
            "error_title": "Не пройдено граничні тести",
            "error_details": (
                "Рішення працює для частини вхідних комбінацій, "
                "але не проходить один або кілька граничних випадків."
            ),
            "recommendation": (
                "Окремо перевірте мінімальні та максимальні значення, "
                "комбінації з усіма нулями або одиницями, а для "
                "послідовнісних схем — початкові та перехідні стани."
            ),
            "error_confidence": 70,
        }

    if (
        code_has_incomplete_condition(code_text)
        or output_has_undefined_signal_value(output_text)
    ):
        return {
            "error_type": "INCOMPLETE_CONDITION",
            "error_title": "Неповний опис умов",
            "error_details": (
                "У комбінаційній логіці може бути описано не всі "
                "можливі варіанти керувальних умов. Це може спричиняти "
                "невизначені значення або ненавмисне збереження "
                "попереднього стану сигналу."
            ),
            "recommendation": (
                "Перевірте повноту присвоєнь у всіх гілках. "
                "За потреби додайте else до if або default до case "
                "та переконайтеся, що виходи отримують значення "
                "для кожної комбінації входів."
            ),
            "error_confidence": 80,
        }

    if (
        topic in {
            "mux",
            "adder",
            "general",
        }
        and normalized_status in {
            "FAILED",
            "PARTIAL",
        }
    ):
        return {
            "error_type": "WRONG_COMBINATIONAL_LOGIC",
            "error_title": "Некоректна комбінаційна логіка",
            "error_details": (
                "HDL-код компілюється і моделюється, але фактичні "
                "вихідні значення не відповідають очікуваним "
                "результатам testbench."
            ),
            "recommendation": (
                "Побудуйте або перевірте таблицю істинності для "
                "завдання та порівняйте її з виразами assign "
                "або логікою блока always."
            ),
            "error_confidence": 78,
        }

    return {
        "error_type": "FUNCTIONAL_ERROR",
        "error_title": "Функціональна помилка HDL-рішення",
        "error_details": (
            "HDL-рішення пройшло компіляцію та моделювання, "
            "але один або кілька функціональних тестів завершилися "
            "з неправильним результатом."
        ),
        "recommendation": (
            "Проаналізуйте вхідні дані невдалих тестів і порівняйте "
            "очікувані та фактичні значення сигналів. Визначте, "
            "для яких комбінацій або станів поведінка модуля "
            "відрізняється від заданої."
        ),
        "error_confidence": 60,
    }


def output_contains_python_exception(
    output,
    exception_name: str,
) -> bool:
    """
    Перевіряє наявність назви Python-винятку в діагностичному
    виводі pytest.

    Перевірка має евристичний характер і використовується
    для формування навчальної категорії помилки.
    """
    pattern = rf"\b{re.escape(exception_name)}\b"

    return re.search(
        pattern,
        str(output or ""),
        flags=re.IGNORECASE,
    ) is not None


def classify_python_error(
    status,
    output,
    lab,
    code,
) -> dict:
    """
    Класифікує результат автоматичної перевірки Python-рішення.

    Статуси інфраструктури та безпеки обробляються до аналізу
    pytest-виводу, щоб вони не потрапляли до навчальної історії
    як помилки програмного коду студента.
    """
    normalized_status = str(
        status or ""
    ).strip().upper()

    output_text = str(
        output or ""
    )

    # Параметри lab і code зберігаються в сигнатурі для єдиного
    # інтерфейсу класифікаторів різних типів лабораторних робіт.
    _ = lab
    _ = code

    if normalized_status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Помилок не виявлено",
            "error_details": (
                "Python-рішення успішно пройшло всі виконані unit-тести."
            ),
            "recommendation": (
                "Додаткові дії не потрібні."
            ),
            "error_confidence": 100,
        }

    # Інфраструктурні помилки не характеризують якість
    # студентського рішення і не повинні формувати профіль компетентностей.
    if normalized_status == "SYSTEM_ERROR":
        return {
            "error_type": "SYSTEM_ERROR",
            "error_title": "Системна помилка перевірки",
            "error_details": (
                "Автоматичну перевірку Python-рішення не вдалося "
                "завершити через проблему середовища або конфігурації."
            ),
            "recommendation": (
                "Повторіть перевірку після відновлення роботи системи. "
                "Якщо проблема повторюється, зверніться до викладача "
                "або адміністратора."
            ),
            "error_confidence": 100,
        }

    if normalized_status == "TIMEOUT":
        return {
            "error_type": "TIMEOUT",
            "error_title": "Перевищено ліміт часу виконання",
            "error_details": (
                "Виконання Python-рішення не завершилося "
                "в межах встановленого ліміту часу."
            ),
            "recommendation": (
                "Перевірте цикли, рекурсивні виклики та складність "
                "алгоритму. Особливу увагу приділіть умовам завершення."
            ),
            "error_confidence": 95,
        }

    if normalized_status == "SECURITY_BLOCK":
        return {
            "error_type": "SECURITY_BLOCK",
            "error_title": "Виконання коду заблоковано",
            "error_details": (
                "Попередня перевірка виявила конструкцію, використання "
                "якої обмежено політикою навчального середовища."
            ),
            "recommendation": (
                "Видаліть заборонену конструкцію та реалізуйте рішення "
                "лише засобами, дозволеними умовою лабораторної роботи."
            ),
            "error_confidence": 100,
        }

    # Синтаксична помилка визначається насамперед за статусом,
    # сформованим основним модулем Python-перевірки.
    if (
        normalized_status == "COMPILE_ERROR"
        or output_contains_python_exception(
            output_text,
            "SyntaxError",
        )
        or output_contains_python_exception(
            output_text,
            "IndentationError",
        )
    ):
        return {
            "error_type": "PYTHON_SYNTAX_ERROR",
            "error_title": "Синтаксична помилка Python",
            "error_details": (
                "Python-код не вдалося коректно виконати через "
                "синтаксичну помилку або неправильні відступи."
            ),
            "recommendation": (
                "Перевірте двокрапки, відступи, дужки, лапки "
                "та написання ключових слів Python."
            ),
            "error_confidence": 95,
        }

    if output_contains_python_exception(
        output_text,
        "AssertionError",
    ):
        return {
            "error_type": "PYTHON_LOGIC_ERROR",
            "error_title": "Логічна помилка Python-рішення",
            "error_details": (
                "Код виконується, але отриманий результат "
                "не відповідає очікуваному результату unit-тесту."
            ),
            "recommendation": (
                "Порівняйте очікуваний результат тесту зі значенням, "
                "яке повертає ваша функція, та перевірте алгоритм "
                "для невдалих вхідних даних."
            ),
            "error_confidence": 85,
        }

    if output_contains_python_exception(
        output_text,
        "NameError",
    ):
        return {
            "error_type": "PYTHON_NAME_ERROR",
            "error_title": "Помилка імені змінної або функції",
            "error_details": (
                "Під час виконання використано ім'я змінної, "
                "функції або іншого об'єкта, яке не було визначено."
            ),
            "recommendation": (
                "Перевірте назви змінних і функцій, область їх видимості "
                "та порядок створення об'єктів."
            ),
            "error_confidence": 90,
        }

    if output_contains_python_exception(
        output_text,
        "TypeError",
    ):
        return {
            "error_type": "PYTHON_RUNTIME_ERROR",
            "error_title": "Помилка типів під час виконання",
            "error_details": (
                "Під час виконання Python-коду операція або функція "
                "отримала значення несумісного типу."
            ),
            "recommendation": (
                "Перевірте типи аргументів, значень змінних "
                "і операцій, що виконуються над ними."
            ),
            "error_confidence": 85,
        }

    if (
        output_contains_python_exception(
            output_text,
            "IndexError",
        )
        or output_contains_python_exception(
            output_text,
            "KeyError",
        )
    ):
        return {
            "error_type": "PYTHON_RUNTIME_ERROR",
            "error_title": "Помилка доступу до елементів даних",
            "error_details": (
                "Код намагається звернутися до індексу або ключа, "
                "який відсутній у відповідній структурі даних."
            ),
            "recommendation": (
                "Перевірте межі індексів та наявність ключів "
                "перед зверненням до елементів колекції."
            ),
            "error_confidence": 85,
        }

    if output_contains_python_exception(
        output_text,
        "ZeroDivisionError",
    ):
        return {
            "error_type": "PYTHON_RUNTIME_ERROR",
            "error_title": "Ділення на нуль",
            "error_details": (
                "Під час виконання рішення виникла операція "
                "ділення на нуль."
            ),
            "recommendation": (
                "Перевірте значення дільника та обробіть випадок, "
                "коли він дорівнює нулю."
            ),
            "error_confidence": 90,
        }

    if output_contains_python_exception(
        output_text,
        "RecursionError",
    ):
        return {
            "error_type": "PYTHON_RUNTIME_ERROR",
            "error_title": "Перевищено глибину рекурсії",
            "error_details": (
                "Рекурсивні виклики не завершилися до досягнення "
                "максимально допустимої глибини рекурсії Python."
            ),
            "recommendation": (
                "Перевірте базову умову рекурсії та переконайтеся, "
                "що кожний рекурсивний виклик наближає алгоритм "
                "до завершення."
            ),
            "error_confidence": 90,
        }

    if normalized_status in {
        "FAILED",
        "PARTIAL",
    }:
        return {
            "error_type": "PYTHON_RUNTIME_ERROR",
            "error_title": "Помилка виконання Python-рішення",
            "error_details": (
                "Python-рішення не пройшло один або кілька unit-тестів, "
                "але точнішу категорію помилки визначити не вдалося."
            ),
            "recommendation": (
                "Проаналізуйте звіт pytest, вхідні дані невдалих тестів "
                "і логіку реалізованого алгоритму."
            ),
            "error_confidence": 70,
        }

    app.logger.warning(
        "Класифікатор Python отримав невідомий статус: %s",
        normalized_status,
    )

    return {
        "error_type": "SYSTEM_ERROR",
        "error_title": "Невідомий результат перевірки",
        "error_details": (
            "Система отримала непідтримуваний статус Python-перевірки "
            "та не може достовірно класифікувати результат."
        ),
        "recommendation": (
            "Повторіть перевірку або зверніться до адміністратора."
        ),
        "error_confidence": 100,
    }


def classify_solution_error(
    status,
    output,
    lab,
    code,
) -> dict:
    """
    Вибирає класифікатор помилки відповідно до типу
    автоматичної перевірки лабораторної роботи.
    """
    normalized_status = str(
        status or ""
    ).strip().upper()

    checker_type = str(
        get_row_value(
            lab,
            "checker_type",
            "hdl_testbench",
        )
        or "hdl_testbench"
    ).strip().lower()

    if checker_type == "hdl_testbench":
        return classify_hdl_error(
            status=normalized_status,
            output=output,
            lab=lab,
            code=code,
        )

    if checker_type == "python_unit_tests":
        return classify_python_error(
            status=normalized_status,
            output=output,
            lab=lab,
            code=code,
        )

    # Для ще не реалізованих або інших checker-модулів
    # інфраструктурний статус не повинен перетворюватися
    # на функціональну помилку студентського рішення.
    if normalized_status == "SYSTEM_ERROR":
        return {
            "error_type": "SYSTEM_ERROR",
            "error_title": "Системна помилка перевірки",
            "error_details": (
                "Автоматичну перевірку не вдалося завершити "
                "через проблему конфігурації або середовища."
            ),
            "recommendation": (
                "Повторіть перевірку після усунення системної проблеми."
            ),
            "error_confidence": 100,
        }

    if normalized_status == "TIMEOUT":
        return {
            "error_type": "TIMEOUT",
            "error_title": "Перевищено ліміт часу перевірки",
            "error_details": (
                "Автоматичну перевірку не завершено "
                "в межах встановленого ліміту часу."
            ),
            "recommendation": (
                "Перевірте рішення та повторіть автоматичну перевірку."
            ),
            "error_confidence": 90,
        }

    if normalized_status == "SECURITY_BLOCK":
        return {
            "error_type": "SECURITY_BLOCK",
            "error_title": "Виконання рішення заблоковано",
            "error_details": (
                "Рішення містить конструкцію, заборонену "
                "політикою навчального середовища."
            ),
            "recommendation": (
                "Видаліть заборонену конструкцію та повторіть перевірку."
            ),
            "error_confidence": 100,
        }

    if normalized_status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Помилок не виявлено",
            "error_details": (
                "Рішення успішно пройшло автоматичну перевірку."
            ),
            "recommendation": (
                "Додаткові дії не потрібні."
            ),
            "error_confidence": 100,
        }

    if checker_type not in {
        "sql_query",
        "cpp_tests",
    }:
        app.logger.warning(
            "Немає класифікатора для checker_type=%s.",
            checker_type,
        )

    return {
        "error_type": "FUNCTIONAL_ERROR",
        "error_title": "Помилка виконання завдання",
        "error_details": (
            "Рішення не пройшло автоматичну перевірку, "
            "але для цього типу завдання не реалізовано "
            "спеціалізовану класифікацію."
        ),
        "recommendation": (
            "Проаналізуйте звіт автоматичної перевірки "
            "та скоригуйте рішення."
        ),
        "error_confidence": 60,
    }

    
# =========================
# 9. Адаптивний ШІ-модуль та підказки
# =========================

LAB_TOPIC_KEYWORDS = {
    "mux": {
        "mux",
        "multiplexer",
        "мультиплексор",
        "селектор",
        "select",
        "sel",
    },
    "adder": {
        "adder",
        "sum",
        "carry",
        "суматор",
        "додавання",
    },
    "counter": {
        "counter",
        "count",
        "лічильник",
    },
    "register": {
        "register",
        "регістр",
    },
    "fsm": {
        "fsm",
        "finite state machine",
        "state machine",
        "state",
        "автомат станів",
        "скінченний автомат",
    },
}

LAB_TOPIC_DISPLAY_NAMES = {
    "mux": "Мультиплексор",
    "adder": "Суматор",
    "counter": "Лічильник",
    "register": "Регістр",
    "fsm": "FSM",
    "general": "Загальна тема",
}


def detect_normalized_lab_topic(*text_parts) -> str:
    """
    Визначає нормалізовану тему лабораторної роботи
    за набором текстових ознак.

    Єдина функція використовується аналітичним та адаптивним
    компонентами, щоб правила визначення теми не відрізнялися.
    """
    text = " ".join(
        str(part or "")
        for part in text_parts
    ).casefold()

    for topic, keywords in LAB_TOPIC_KEYWORDS.items():
        if any(
            keyword.casefold() in text
            for keyword in keywords
        ):
            return topic

    return "general"


def normalize_lab_topic_for_analytics(
    topic,
    title="",
) -> str:
    """Нормалізує тему лабораторної роботи для аналітичних показників."""
    normalized_topic = str(
        topic or ""
    ).strip().lower()

    if normalized_topic in LAB_TOPIC_KEYWORDS:
        return normalized_topic

    return detect_normalized_lab_topic(
        topic,
        title,
    )


def get_topic_display_name(topic) -> str:
    """Повертає україномовну назву нормалізованої теми."""
    normalized_topic = str(
        topic or "general"
    ).strip().lower()

    return LAB_TOPIC_DISPLAY_NAMES.get(
        normalized_topic,
        normalized_topic,
    )


def extract_failed_tests(output) -> list[str]:
    """
    Витягує блоки невдалих тестів із результату HDL-перевірки.

    Використовується спільний парсер діагностичного модуля,
    щоб формат звіту не аналізувався кількома різними способами.
    """
    return get_failed_test_blocks(
        str(output or "")
    )


def extract_failed_tests_for_adaptive_module(output) -> list[dict]:
    """
    Формує структурований опис невдалих тестів для адаптивного модуля.

    Функція повинна отримувати лише відкритий або вже підготовлений
    для студента звіт. Деталі прихованих тестів передавати ШІ-модулю
    через цю функцію не слід.
    """
    lines = str(
        output or ""
    ).splitlines()

    failed_tests = []

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()

        if not line:
            continue

        # Підтримка необробленого службового формату testbench:
        # CASE|номер|входи|очікуване|фактичне|результат
        if line.startswith("CASE|"):
            parts = [
                part.strip()
                for part in line.split("|")
            ]

            if (
                len(parts) == 6
                and parts[5].upper() != "PASS"
            ):
                failed_tests.append({
                    "test_line": (
                        f"Тест {parts[1]}: "
                        f"{parts[2]} — не пройдено"
                    ),
                    "expected": (
                        f"Очікувалося: {parts[3]}"
                    ),
                    "actual": (
                        f"Отримано: {parts[4]}"
                    ),
                })

            continue

        line_lower = line.casefold()

        # Формат, сформований функцією format_hdl_report().
        if (
            line_lower.startswith("тест ")
            and "не пройдено" in line_lower
        ):
            test_block = {
                "test_line": line,
                "expected": "",
                "actual": "",
            }

            for offset in (1, 2):
                next_index = index + offset

                if next_index >= len(lines):
                    continue

                next_line = lines[next_index].strip()
                next_line_lower = next_line.casefold()

                if next_line_lower.startswith("очікувалося:"):
                    test_block["expected"] = next_line

                elif next_line_lower.startswith("отримано:"):
                    test_block["actual"] = next_line

            failed_tests.append(
                test_block
            )

    return failed_tests


def detect_lab_topic_adaptive(
    submission,
    code,
) -> str:
    """
    Визначає тему поточної лабораторної роботи для адаптивного модуля.
    """
    explicit_topic = str(
        get_row_value(
            submission,
            "lab_topic",
            "",
        )
        or ""
    ).strip().lower()

    if explicit_topic in LAB_TOPIC_KEYWORDS:
        return explicit_topic

    return detect_normalized_lab_topic(
        explicit_topic,
        get_row_value(
            submission,
            "lab_title",
            "",
        ),
        get_row_value(
            submission,
            "lab_description",
            "",
        ),
        get_row_value(
            submission,
            "lab_testbench",
            "",
        ),
        code,
    )


def define_hint_level(
    submission,
    error_history,
) -> int:
    """
    Визначає рівень деталізації підказки за номером спроби
    та кількістю повторень однакової помилки.

    Рівень 1 містить загальний напрям пошуку, рівень 2 — більш
    конкретну рекомендацію, а рівень 3 може містити детальний
    алгоритм перевірки рішення без надання готової відповіді.
    """
    try:
        attempt_number = int(
            get_row_value(
                submission,
                "attempt_number",
                1,
            )
            or 1
        )
    except (TypeError, ValueError, OverflowError):
        attempt_number = 1

    attempt_number = max(
        1,
        attempt_number,
    )

    current_error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip()

    repeated_error_count = 0

    for row in error_history or []:
        row_error_type = str(
            get_row_value(
                row,
                "error_type",
                "",
            )
            or ""
        ).strip()

        if row_error_type != current_error_type:
            continue

        try:
            repeated_error_count = int(
                get_row_value(
                    row,
                    "count",
                    0,
                )
                or 0
            )
        except (TypeError, ValueError, OverflowError):
            repeated_error_count = 0

        repeated_error_count = max(
            0,
            repeated_error_count,
        )

        break

    if (
        attempt_number <= 1
        and repeated_error_count <= 1
    ):
        return 1

    if (
        attempt_number <= 2
        and repeated_error_count <= 2
    ):
        return 2

    return 3


def build_recommendations_to_repeat(
    topic,
    error_type,
) -> list[str]:
    """
    Формує перелік тем для повторення відповідно
    до категорії помилки та теми лабораторної роботи.
    """
    normalized_topic = str(
        topic or "general"
    ).strip().lower()

    normalized_error_type = str(
        error_type or ""
    ).strip().upper()

    # Системні відмови та успішні результати не повинні
    # формувати хибний профіль навчальних прогалин студента.
    if normalized_error_type in {
        "",
        "NO_ERROR",
        "SYSTEM_ERROR",
    }:
        return []

    recommendations = []

    error_recommendations = {
        "MODULE_NAME_MISMATCH": [
            "структура Verilog-модуля та ім'я module",
            "відповідність імені модуля testbench",
        ],
        "PORT_MISMATCH": [
            "оголошення вхідних і вихідних портів input/output",
            "відповідність портів модуля перевірочному testbench",
        ],
        "COMPILE_ERROR": [
            "синтаксис Verilog",
            "крапки з комою, assign, module та endmodule",
        ],
        "CONTROL_SIGNAL_ERROR": [
            "керувальні сигнали в комбінаційній логіці",
            "умовні конструкції Verilog",
            "таблиця істинності мультиплексора",
        ],
        "INCOMPLETE_CONDITION": [
            "повний опис умов if-else",
            "гілка default у case-конструкціях",
            "запобігання невизначеним значенням сигналів",
        ],
        "RESET_CLOCK_ERROR": [
            "послідовнісна логіка",
            "clock і reset",
            "always-блоки та зміна стану",
        ],
        "BOUNDARY_TEST_FAILED": [
            "граничні тестові випадки",
            "перевірка характерних комбінацій вхідних сигналів",
        ],
        "WRONG_COMBINATIONAL_LOGIC": [
            "комбінаційна логіка",
            "оператор assign",
            "таблиці істинності",
        ],
        "FUNCTIONAL_ERROR": [
            "аналіз testbench",
            "порівняння очікуваних і фактичних значень",
        ],
        "SIMULATION_ERROR": [
            "моделювання HDL-коду",
            "часова поведінка сигналів",
        ],
        "PYTHON_SYNTAX_ERROR": [
            "синтаксис Python",
            "відступи, двокрапки та структуру блоків Python",
        ],
        "PYTHON_LOGIC_ERROR": [
            "логіка алгоритму",
            "аналіз очікуваних і фактичних результатів unit-тестів",
        ],
        "PYTHON_NAME_ERROR": [
            "імена змінних і функцій",
            "області видимості Python",
        ],
        "PYTHON_RUNTIME_ERROR": [
            "обробка помилок під час виконання Python",
            "перевірка типів і допустимих значень даних",
        ],
        "SECURITY_BLOCK": [
            "обмеження навчального середовища",
            "дозволені конструкції Python-завдання",
        ],
        "TIMEOUT": [
            "умови завершення алгоритму або моделювання",
            "цикли, рекурсія та складність виконання",
        ],
    }

    recommendations.extend(
        error_recommendations.get(
            normalized_error_type,
            [
                "аналіз звіту автоматичної перевірки",
                "порівняння очікуваних і фактичних результатів",
            ],
        )
    )

    topic_recommendations = {
        "mux": "мультиплексор 2:1",
        "adder": "логіка суми та перенесення",
        "counter": "лічильники та зміна значення за тактовим сигналом",
        "register": "регістри та збереження стану",
        "fsm": "скінченні автомати та переходи між станами",
    }

    topic_recommendation = topic_recommendations.get(
        normalized_topic
    )

    if topic_recommendation:
        recommendations.append(
            topic_recommendation
        )

    # dict зберігає порядок елементів, тому дублікати можна
    # видалити без зміни пріоритету рекомендацій.
    return list(
        dict.fromkeys(
            recommendations
        )
    )


def build_task(
    field,
    title,
    text,
    required_groups,
    min_length=25,
) -> dict:
    """
    Формує стандартизований опис додаткового навчального завдання.
    """
    try:
        normalized_min_length = int(
            min_length
        )
    except (TypeError, ValueError, OverflowError):
        normalized_min_length = 25

    normalized_min_length = max(
        1,
        normalized_min_length,
    )

    if required_groups is None:
        normalized_required_groups = []

    elif isinstance(
        required_groups,
        str,
    ):
        normalized_required_groups = [
            required_groups
        ]

    else:
        normalized_required_groups = list(
            required_groups
        )

    return {
        "field": str(field or "").strip(),
        "title": str(title or "").strip(),
        "text": str(text or "").strip(),
        "required_groups": normalized_required_groups,
        "min_length": normalized_min_length,
    }


ADAPTIVE_HINT_TEMPLATES = {
    "MODULE_NAME_MISMATCH": {
        1: (
            "Проблема пов'язана не з функціональною логікою схеми, "
            "а з підключенням модуля до testbench. Перевірте, чи "
            "відповідає ім'я вашого module вимогам лабораторної роботи."
        ),
        2: (
            "Testbench створює екземпляр модуля з конкретним іменем. "
            "Порівняйте ім'я після ключового слова module у своєму коді "
            "з іменем, визначеним в умові завдання."
        ),
        3: (
            "Перевірте заголовок Verilog-модуля. Він має починатися "
            "конструкцією module з тим самим іменем, яке очікує testbench. "
            "Не змінюйте ім'я модуля довільно."
        ),
    },

    "PORT_MISMATCH": {
        1: (
            "Перевірте інтерфейс модуля. Імена входів і виходів "
            "мають відповідати портам, які використовує testbench."
        ),
        2: (
            "Порівняйте список input/output-портів у завданні "
            "та у своєму module. Зверніть увагу на точне написання "
            "імен, напрям сигналів і їхню розрядність."
        ),
        3: (
            "Послідовно перевірте кожний порт модуля: його ім'я, "
            "напрям input/output та ширину шини. Навіть одна "
            "невідповідність може призвести до помилки elaboration."
        ),
    },

    "COMPILE_ERROR": {
        1: (
            "HDL-код не пройшов компіляцію. Спочатку перевірте "
            "синтаксис і структуру Verilog-модуля."
        ),
        2: (
            "Перевірте крапки з комою, оголошення input/output, "
            "конструкції assign та always, а також відповідність "
            "begin/end і module/endmodule."
        ),
        3: (
            "Проаналізуйте перше повідомлення Icarus Verilog про помилку "
            "та відповідний рядок коду. Виправляйте помилки послідовно, "
            "починаючи з першої, оскільки наступні повідомлення можуть "
            "бути її наслідком."
        ),
    },

    "CONTROL_SIGNAL_ERROR": {
        1: (
            "Помилка пов'язана з керувальним сигналом. Перевірте, "
            "як його значення впливає на вибір вихідного сигналу."
        ),
        2: (
            "Для кожного можливого значення керувального сигналу "
            "визначте очікуваний вихід за умовою завдання та порівняйте "
            "його з реалізованою логікою."
        ),
        3: (
            "Побудуйте таблицю істинності для керувального сигналу "
            "та порівняйте кожний її рядок з умовним виразом "
            "або конструкцією assign/always у вашому коді."
        ),
    },

    "RESET_CLOCK_ERROR": {
        1: (
            "Проблема пов'язана з послідовнісною логікою. Перевірте "
            "clock, reset і момент зміни стану схеми."
        ),
        2: (
            "Перевірте, за яким фронтом clock змінюється стан і який "
            "активний рівень має reset. Після скидання регістри повинні "
            "отримувати значення, визначені умовою завдання."
        ),
        3: (
            "Проаналізуйте sensitivity list блока always і порядок "
            "умов усередині нього. Окремо перевірте поведінку під час "
            "reset та під час наступного активного фронту clock."
        ),
    },

    "INCOMPLETE_CONDITION": {
        1: (
            "У комбінаційній логіці може бути описано не всі можливі "
            "варіанти вхідних або керувальних сигналів."
        ),
        2: (
            "Перевірте повноту присвоєнь у if/else та case. "
            "Зверніть увагу на гілку else або default там, "
            "де вона потрібна для повного опису логіки."
        ),
        3: (
            "Перевірте, чи отримує кожний вихід значення за кожного "
            "можливого шляху виконання комбінаційного блока. Неповне "
            "присвоєння може спричинити невизначене значення або latch."
        ),
    },

    "BOUNDARY_TEST_FAILED": {
        1: (
            "Рішення не проходить один або кілька граничних випадків. "
            "Перевірте поведінку схеми на крайніх значеннях входів."
        ),
        2: (
            "Окремо протестуйте мінімальні та максимальні значення, "
            "комбінації з усіма нулями й одиницями та інші характерні "
            "випадки відповідно до умови завдання."
        ),
        3: (
            "Порівняйте кожний невдалий граничний тест із вашим HDL-описом "
            "і визначте, яка операція або умова неправильно обробляє "
            "конкретну крайню комбінацію."
        ),
    },

    "WRONG_COMBINATIONAL_LOGIC": {
        1: (
            "Код компілюється та моделюється, але логіка схеми "
            "не відповідає очікуваній поведінці."
        ),
        2: (
            "Порівняйте таблицю істинності завдання з виразами assign "
            "або логікою блока always у своєму коді."
        ),
        3: (
            "Зосередьтеся на тих комбінаціях входів, для яких testbench "
            "показує різницю між очікуваним і фактичним значенням. "
            "Знайдіть спільну умову для цих невдалих випадків."
        ),
    },

    "FUNCTIONAL_ERROR": {
        1: (
            "Рішення компілюється, але не всі функціональні тести "
            "завершуються успішно."
        ),
        2: (
            "Порівняйте вхідні дані невдалих тестів з очікуваними "
            "та фактичними результатами й визначте, для яких випадків "
            "поведінка рішення відрізняється."
        ),
        3: (
            "Згрупуйте невдалі тестові випадки за спільними вхідними "
            "умовами та перевірте відповідну частину HDL-логіки. "
            "Це допоможе локалізувати помилкову умову або вираз."
        ),
    },

    "SIMULATION_ERROR": {
        1: (
            "Компіляція завершилася успішно, але під час HDL-моделювання "
            "виникла помилка."
        ),
        2: (
            "Проаналізуйте вивід VVP і перевірте конструкції, "
            "що виконуються під час simulation, а також часову "
            "поведінку сигналів."
        ),
        3: (
            "Використайте діагностичний вивід і, якщо доступний, VCD "
            "для визначення моменту, після якого моделювання перестає "
            "відповідати очікуваній поведінці."
        ),
    },

    "PYTHON_SYNTAX_ERROR": {
        1: (
            "Python-код містить синтаксичну помилку або неправильні відступи."
        ),
        2: (
            "Перевірте двокрапки, дужки, лапки, відступи та структуру "
            "блоків if, for, while і функцій."
        ),
        3: (
            "Знайдіть перше повідомлення SyntaxError або IndentationError "
            "у звіті pytest та виправте вказаний рядок перед аналізом "
            "наступних помилок."
        ),
    },

    "PYTHON_LOGIC_ERROR": {
        1: (
            "Python-код виконується, але результат не відповідає "
            "очікуваному значенню unit-тесту."
        ),
        2: (
            "Порівняйте вхідні дані невдалого тесту з результатом, "
            "який повертає ваша функція."
        ),
        3: (
            "Пройдіть алгоритм вручну для одного невдалого тесту "
            "та перевірте проміжні значення й умови, які визначають "
            "кінцевий результат."
        ),
    },

    "PYTHON_NAME_ERROR": {
        1: (
            "Під час виконання використовується ім'я, яке Python "
            "не може знайти."
        ),
        2: (
            "Перевірте написання назв змінних і функцій та місце, "
            "де вони оголошуються."
        ),
        3: (
            "Перевірте область видимості проблемного імені та переконайтеся, "
            "що воно визначене до моменту використання."
        ),
    },

    "PYTHON_RUNTIME_ERROR": {
        1: (
            "Під час виконання Python-рішення виникає помилка."
        ),
        2: (
            "Проаналізуйте тип винятку у звіті pytest та перевірте "
            "операцію, на якій переривається виконання."
        ),
        3: (
            "Відтворіть один невдалий випадок вручну та перевірте "
            "типи даних, індекси, ключі, умови й проміжні значення "
            "безпосередньо перед виникненням винятку."
        ),
    },

    "TIMEOUT": {
        1: (
            "Перевірка перевищила встановлений ліміт часу."
        ),
        2: (
            "Перевірте умови завершення циклів, рекурсії або HDL-моделювання "
            "та переконайтеся, що виконання може завершитися."
        ),
        3: (
            "Визначте ділянку рішення, яка може виконуватися необмежено "
            "або надмірно довго, та перевірте умову її завершення."
        ),
    },

    "SECURITY_BLOCK": {
        1: (
            "Виконання рішення заблоковано політикою навчального середовища."
        ),
        2: (
            "Перевірте виявлену конструкцію та переконайтеся, що рішення "
            "не використовує заборонений доступ до системних ресурсів."
        ),
        3: (
            "Перепишіть відповідну частину рішення засобами, дозволеними "
            "умовою лабораторної роботи, без системних команд, мережевого "
            "доступу або динамічного виконання коду."
        ),
    },
}


ADAPTIVE_HINT_TEST_CONTEXT_ERRORS = frozenset({
    "CONTROL_SIGNAL_ERROR",
    "BOUNDARY_TEST_FAILED",
    "WRONG_COMBINATIONAL_LOGIC",
    "FUNCTIONAL_ERROR",
    "PYTHON_LOGIC_ERROR",
})


def build_failed_test_hint_context(failed_tests) -> str:
    """
    Формує короткий контекст одного невдалого відкритого тесту.

    Функція повинна отримувати лише дані, дозволені для відображення
    студенту. Результати hidden testbench передавати сюди не можна.
    """
    if not failed_tests:
        return ""

    first_failed = failed_tests[0]

    if not isinstance(first_failed, dict):
        return ""

    test_line = str(
        first_failed.get("test_line", "") or ""
    ).strip()

    expected = str(
        first_failed.get("expected", "") or ""
    ).strip()

    actual = str(
        first_failed.get("actual", "") or ""
    ).strip()

    details = [
        value
        for value in (
            test_line,
            expected,
            actual,
        )
        if value
    ]

    if not details:
        return ""

    return (
        "\n\nПриклад невдалого відкритого тесту:\n"
        + "\n".join(details)
    )


def generate_adaptive_hint(
    submission,
    topic,
    failed_tests,
    hint_level,
) -> str:
    """
    Формує адаптивну навчальну підказку за типом помилки,
    темою лабораторної роботи та рівнем деталізації.

    Функція використовує детерміновані правила та шаблони.
    Вона не виконує безпосереднього звернення до OpenAI/Ollama;
    зовнішній ШІ-компонент, якщо він використовується, є окремим
    етапом адаптивного модуля.
    """
    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    normalized_topic = str(
        topic or "general"
    ).strip().lower()

    try:
        normalized_hint_level = int(
            hint_level
        )
    except (TypeError, ValueError, OverflowError):
        normalized_hint_level = 1

    normalized_hint_level = max(
        1,
        min(
            3,
            normalized_hint_level,
        ),
    )

    if error_type == "NO_ERROR":
        return (
            "Адаптивна підказка не потрібна: "
            "поточне рішення успішно пройшло перевірку."
        )

    if error_type == "SYSTEM_ERROR":
        return (
            "Адаптивну підказку не сформовано, оскільки перевірка "
            "завершилася системною помилкою. Повторіть перевірку "
            "після відновлення роботи середовища."
        )

    templates = ADAPTIVE_HINT_TEMPLATES.get(
        error_type
    )

    if templates is None:
        hint_text = (
            "Проаналізуйте звіт автоматичної перевірки та порівняйте "
            "очікувані й фактичні результати. Зосередьтеся на першому "
            "невдалому випадку та визначте, яка частина рішення "
            "відповідає за його обробку."
        )
    else:
        hint_text = templates[
            normalized_hint_level
        ]

    # Для помилки керувального сигналу в темі mux додається
    # предметний контекст без надання готової реалізації рішення.
    if (
        error_type == "CONTROL_SIGNAL_ERROR"
        and normalized_topic == "mux"
    ):
        if normalized_hint_level == 1:
            hint_text += (
                " Для мультиплексора перевірте зв'язок між "
                "керувальним сигналом і вибраним входом."
            )
        elif normalized_hint_level == 2:
            hint_text += (
                " Порівняйте поведінку схеми для кожного значення sel "
                "з таблицею істинності, наведеною в завданні."
            )
        else:
            hint_text += (
                " Послідовно зіставте кожний рядок таблиці істинності "
                "мультиплексора з реалізованим умовним виразом."
            )

    failed_context = ""

    if error_type in ADAPTIVE_HINT_TEST_CONTEXT_ERRORS:
        failed_context = build_failed_test_hint_context(
            failed_tests
        )

    return (
        f"Адаптивна підказка рівня "
        f"{normalized_hint_level}:\n\n"
        f"{hint_text}"
        f"{failed_context}"
    )


def normalize_adaptive_question_level(hint_level) -> int:
    """Нормалізує рівень складності адаптивних питань до діапазону 1–3."""
    try:
        level = int(
            hint_level
        )
    except (TypeError, ValueError, OverflowError):
        level = 1

    return max(
        1,
        min(3, level),
    )


def build_failed_test_question_context(failed_tests) -> str:
    """
    Формує контекст одного невдалого відкритого тесту для питання.

    Функція повинна отримувати лише результати, дозволені для
    відображення студенту. Дані hidden testbench сюди передавати не можна.
    """
    if not failed_tests:
        return ""

    first_failed = failed_tests[0]

    if not isinstance(first_failed, dict):
        return ""

    test_line = str(
        first_failed.get(
            "test_line",
            "",
        )
        or ""
    ).strip()

    expected = str(
        first_failed.get(
            "expected",
            "",
        )
        or ""
    ).strip()

    actual = str(
        first_failed.get(
            "actual",
            "",
        )
        or ""
    ).strip()

    details = [
        value
        for value in (
            test_line,
            expected,
            actual,
        )
        if value
    ]

    if not details:
        return ""

    return (
        "\n\nВідкритий тест для аналізу:\n"
        + "\n".join(details)
    )


def build_adaptive_analysis_question(
    hint_level: int,
    level_1_text: str,
    level_2_text: str,
    level_3_text: str,
    failed_test_context: str = "",
) -> str:
    """
    Вибирає формулювання аналітичного питання відповідно
    до рівня адаптивної підтримки.
    """
    texts = {
        1: level_1_text,
        2: level_2_text,
        3: level_3_text,
    }

    text = texts.get(
        hint_level,
        level_1_text,
    )

    # Конкретний невдалий тест використовується лише на вищих
    # рівнях підтримки, коли студенту потрібна детальніша діагностика.
    if (
        failed_test_context
        and hint_level >= 2
    ):
        text += failed_test_context

    return text


def generate_adaptive_questions(
    submission,
    topic,
    failed_tests,
    hint_level,
) -> list[dict]:
    """
    Формує індивідуальні додаткові питання відповідно до теми,
    типу помилки та рівня адаптивної підтримки.

    На вищих рівнях питання стають конкретнішими та можуть містити
    контекст одного невдалого відкритого тесту, але не готове рішення.
    """
    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    normalized_topic = str(
        topic or "general"
    ).strip().lower()

    normalized_hint_level = normalize_adaptive_question_level(
        hint_level
    )

    failed_test_context = build_failed_test_question_context(
        failed_tests
    )

    # Успішне рішення або системна відмова не повинні
    # створювати хибні додаткові навчальні завдання.
    if error_type in {
        "",
        "NO_ERROR",
        "SYSTEM_ERROR",
    }:
        return []

    # ---------------------------------------------------------
    # Помилки структури HDL-модуля мають вищий пріоритет за тему.
    # ---------------------------------------------------------

    if error_type == "MODULE_NAME_MISMATCH":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Чому ім'я Verilog-модуля має відповідати імені, "
                "яке використовує testbench?"
            ),
            (
                "Порівняйте ім'я module у своєму коді з інтерфейсом "
                "testbench. Яка невідповідність може завадити elaboration?"
            ),
            (
                "Опишіть послідовність перевірки імені модуля, яку "
                "потрібно виконати перед повторним надсиланням рішення."
            ),
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Структура Verilog-модуля",
                (
                    "Яке призначення ключових слів module та endmodule "
                    "у Verilog?"
                ),
                [
                    ["module"],
                    ["endmodule"],
                    ["модул", "опис"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Ім'я модуля",
                (
                    "Чому ім'я модуля в рішенні повинно відповідати "
                    "імені, яке очікує testbench?"
                ),
                [
                    ["ім'я", "назв"],
                    ["module"],
                    ["testbench", "перевір"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз помилки",
                analysis_question,
                [
                    ["ім'я", "назв"],
                    ["module", "testbench"],
                    ["перевір", "порівн", "відповід"],
                ],
            ),
        ]

    if error_type == "PORT_MISMATCH":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які характеристики портів модуля потрібно перевірити "
                "перед повторним надсиланням?"
            ),
            (
                "Порівняйте порти модуля з testbench. На які відмінності "
                "в іменах, напрямах і розрядності потрібно звернути увагу?"
            ),
            (
                "Опишіть покрокову перевірку інтерфейсу модуля: "
                "ім'я порту, напрям input/output та ширина сигналу."
            ),
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Порти модуля",
                (
                    "Яку роль виконують input та output у Verilog-модулі?"
                ),
                [
                    ["input", "вхід"],
                    ["output", "вихід"],
                    ["сигнал", "порт"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Відповідність testbench",
                (
                    "Чому імена та розрядність портів повинні "
                    "відповідати інтерфейсу testbench?"
                ),
                [
                    ["ім'я", "назв"],
                    ["розряд", "ширин"],
                    ["testbench", "порт"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз інтерфейсу",
                analysis_question,
                [
                    ["порт"],
                    ["input", "output"],
                    ["ім'я", "розряд", "ширин"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Python
    # ---------------------------------------------------------

    if error_type == "PYTHON_SYNTAX_ERROR":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які основні синтаксичні елементи Python потрібно "
                "перевірити перед повторним запуском?"
            ),
            (
                "Як за повідомленням SyntaxError або IndentationError "
                "визначити рядок, з якого варто почати виправлення?"
            ),
            (
                "Опишіть порядок пошуку синтаксичної помилки: "
                "повідомлення pytest, номер рядка, конструкція Python "
                "та перевірка її структури."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Синтаксис Python",
                (
                    "Назвіть типові причини SyntaxError "
                    "або IndentationError у Python."
                ),
                [
                    ["синтакс", "SyntaxError", "IndentationError"],
                    ["відступ", "двокрап", "дужк", "лапк"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Відступи",
                (
                    "Чому відступи мають синтаксичне значення у Python?"
                ),
                [
                    ["відступ"],
                    ["блок", "структур"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. План виправлення",
                analysis_question,
                [
                    ["помил", "SyntaxError", "IndentationError"],
                    ["ряд"],
                    ["перевір", "виправ"],
                ],
            ),
        ]

    if error_type in {
        "PYTHON_LOGIC_ERROR",
        "PYTHON_RUNTIME_ERROR",
        "PYTHON_NAME_ERROR",
    }:
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які дані зі звіту pytest допомагають визначити "
                "причину невдалого тесту?"
            ),
            (
                "Порівняйте вхідні дані, очікуваний результат "
                "і фактичну поведінку функції. Де може виникати "
                "відмінність?"
            ),
            (
                "Пройдіть виконання одного невдалого тесту вручну "
                "та визначте, на якому кроці значення починають "
                "відрізнятися від очікуваних."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Результат unit-тесту",
                (
                    "Яку інформацію про помилку можна отримати "
                    "зі звіту pytest?"
                ),
                [
                    ["pytest", "тест"],
                    ["помил", "результат", "винят"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Аналіз алгоритму",
                (
                    "Як порівняння очікуваного та фактичного результату "
                    "допомагає знайти логічну помилку?"
                ),
                [
                    ["очікуван"],
                    ["фактич", "отриман"],
                    ["логік", "алгоритм", "помил"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз невдалого тесту",
                analysis_question,
                [
                    ["тест"],
                    ["очікуван", "фактич", "отриман"],
                    ["перевір", "значен", "алгоритм"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Мультиплексор
    # ---------------------------------------------------------

    if normalized_topic == "mux":
        if error_type == "CONTROL_SIGNAL_ERROR":
            analysis_question = build_adaptive_analysis_question(
                normalized_hint_level,
                (
                    "Яку частину логіки вибору потрібно перевірити, "
                    "якщо вихід залежить від неправильного входу?"
                ),
                (
                    "Порівняйте поведінку виходу для різних значень sel "
                    "з таблицею істинності. Яку невідповідність "
                    "потрібно шукати?"
                ),
                (
                    "Проаналізуйте невдалий відкритий тест і поясніть, "
                    "як перевірити відповідність керувального сигналу "
                    "реалізованому вибору входу."
                ),
                failed_test_context,
            )

            return [
                build_task(
                    "answer_1",
                    "Питання 1. Роль керувального сигналу",
                    (
                        "Поясніть, яку роль виконує сигнал sel "
                        "у мультиплексорі 2:1."
                    ),
                    [
                        ["sel"],
                        ["виб", "керув"],
                        ["d0", "d1", "вхід"],
                    ],
                ),
                build_task(
                    "answer_2",
                    "Питання 2. Поведінка виходу",
                    (
                        "Поясніть, як значення sel визначає, "
                        "який із входів d0 або d1 передається на вихід y."
                    ),
                    [
                        ["sel"],
                        ["d0"],
                        ["d1"],
                        ["y", "вихід"],
                    ],
                ),
                build_task(
                    "answer_3",
                    "Питання 3. Аналіз помилки",
                    analysis_question,
                    [
                        ["sel"],
                        ["d0", "d1"],
                        ["виб", "умов", "логік"],
                    ],
                ),
            ]

        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Яку частину HDL-опису мультиплексора ви перевірите "
                "перед повторним надсиланням?"
            ),
            (
                "Порівняйте таблицю істинності мультиплексора "
                "з реалізованою логікою. Які рядки потрібно "
                "перевірити в першу чергу?"
            ),
            (
                "Проаналізуйте невдалий відкритий тест і визначте, "
                "яка умова або логічний вираз може формувати "
                "неправильний вихід."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Призначення мультиплексора",
                (
                    "Поясніть, для чого використовується "
                    "мультиплексор 2:1."
                ),
                [
                    ["мультиплексор", "mux"],
                    ["виб"],
                    ["вхід", "вихід"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Таблиця істинності",
                (
                    "Опишіть, як вихід y залежить "
                    "від входів d0, d1 та сигналу sel."
                ),
                [
                    ["y", "вихід"],
                    ["sel"],
                    ["d0", "d1"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. План перевірки",
                analysis_question,
                [
                    ["перевір", "аналіз"],
                    ["assign", "always", "умов", "sel"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Суматор
    # ---------------------------------------------------------

    if normalized_topic == "adder":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які випадки роботи суматора потрібно перевірити "
                "перед повторним надсиланням?"
            ),
            (
                "Перевірте комбінації входів, для яких формується "
                "перенесення. Як пов'язані sum і carry?"
            ),
            (
                "Проаналізуйте невдалий відкритий тест і визначте, "
                "чи проблема пов'язана з формуванням sum, carry "
                "або обох сигналів."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Сума та перенесення",
                (
                    "Поясніть різницю між виходами sum і carry "
                    "у двійковому суматорі."
                ),
                [
                    ["sum", "сума"],
                    ["carry", "перенес"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Граничний випадок",
                (
                    "Що відбувається з sum і carry "
                    "під час додавання двох одиниць?"
                ),
                [
                    ["1"],
                    ["carry", "перенес"],
                    ["sum", "сума"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз реалізації",
                analysis_question,
                [
                    ["sum", "carry"],
                    ["перевір", "аналіз"],
                    ["логік", "операц", "вхід"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Лічильник
    # ---------------------------------------------------------

    if normalized_topic == "counter":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які сигнали визначають зміну стану лічильника?"
            ),
            (
                "Перевірте поведінку лічильника під час активного "
                "фронту clock і під час reset. Які два режими "
                "потрібно розглядати окремо?"
            ),
            (
                "Проаналізуйте невдалий відкритий тест і визначте, "
                "чи помилка виникає під час reset, на фронті clock "
                "або під час оновлення значення лічильника."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Робота лічильника",
                (
                    "Поясніть, як має змінюватися стан лічильника "
                    "під дією тактового сигналу."
                ),
                [
                    ["clock", "clk", "такт"],
                    ["змін", "збільш", "ліч"],
                    ["значен", "стан"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Reset",
                (
                    "Яке призначення reset і як він впливає "
                    "на стан лічильника?"
                ),
                [
                    ["reset", "rst", "скидан"],
                    ["початков", "0", "нуль"],
                    ["стан", "значен"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз послідовнісної логіки",
                analysis_question,
                [
                    ["clock", "clk", "такт"],
                    ["reset", "rst", "скидан"],
                    ["стан", "значен", "always"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Регістр
    # ---------------------------------------------------------

    if normalized_topic == "register":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "За яких умов регістр повинен зберігати "
                "або змінювати своє значення?"
            ),
            (
                "Порівняйте поведінку регістра під час clock і reset. "
                "Який момент визначає оновлення його стану?"
            ),
            (
                "Проаналізуйте невдалий тест і визначте, "
                "чи значення регістра змінюється не на тому фронті "
                "або неправильно обробляється reset."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Призначення регістра",
                (
                    "Поясніть, для чого у цифровій схемі "
                    "використовується регістр."
                ),
                [
                    ["регістр", "register"],
                    ["збер", "стан", "значен"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Тактовий сигнал",
                (
                    "Як clock визначає момент оновлення "
                    "значення регістра?"
                ),
                [
                    ["clock", "clk", "такт"],
                    ["фронт"],
                    ["змін", "онов"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз поведінки",
                analysis_question,
                [
                    ["регістр", "стан", "значен"],
                    ["clock", "clk", "reset", "rst"],
                    ["перевір", "аналіз"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # FSM
    # ---------------------------------------------------------

    if normalized_topic == "fsm":
        analysis_question = build_adaptive_analysis_question(
            normalized_hint_level,
            (
                "Які складові FSM потрібно перевірити, "
                "якщо схема переходить у неправильний стан?"
            ),
            (
                "Порівняйте поточний стан, вхідні умови "
                "та очікуваний наступний стан. Де може виникати "
                "невідповідність?"
            ),
            (
                "Проаналізуйте невдалий тест і визначте, "
                "чи проблема міститься в логіці переходів, "
                "оновленні стану або формуванні виходів."
            ),
            failed_test_context,
        )

        return [
            build_task(
                "answer_1",
                "Питання 1. Стани FSM",
                (
                    "Що таке поточний і наступний стан "
                    "у скінченному автоматі?"
                ),
                [
                    ["стан"],
                    ["поточн"],
                    ["наступн", "перехід"],
                ],
            ),
            build_task(
                "answer_2",
                "Питання 2. Переходи між станами",
                (
                    "Від чого залежить перехід FSM "
                    "з одного стану до іншого?"
                ),
                [
                    ["стан"],
                    ["вхід", "умов", "сигнал"],
                    ["перехід"],
                ],
            ),
            build_task(
                "answer_3",
                "Питання 3. Аналіз FSM",
                analysis_question,
                [
                    ["стан"],
                    ["перехід", "наступн"],
                    ["перевір", "логік", "вихід"],
                ],
            ),
        ]

    # ---------------------------------------------------------
    # Загальний HDL-випадок
    # ---------------------------------------------------------

    analysis_question = build_adaptive_analysis_question(
        normalized_hint_level,
        (
            "Яку частину HDL-рішення потрібно перевірити "
            "перед повторним надсиланням?"
        ),
        (
            "Порівняйте очікувані та фактичні результати "
            "відкритих тестів. Які сигнали або умови "
            "потрібно перевірити?"
        ),
        (
            "Проаналізуйте наведений невдалий тест і визначте, "
            "яка частина HDL-логіки відповідає за отриманий результат."
        ),
        failed_test_context,
    )

    return [
        build_task(
            "answer_1",
            "Питання 1. Призначення модуля",
            (
                "Опишіть призначення HDL-модуля "
                "у цій лабораторній роботі."
            ),
            [
                ["модул", "module"],
                ["вхід", "вихід", "сигнал"],
            ],
        ),
        build_task(
            "answer_2",
            "Питання 2. Аналіз результатів",
            (
                "Як порівняння очікуваних і фактичних значень "
                "допомагає знайти помилку в HDL-рішенні?"
            ),
            [
                ["очікуван"],
                ["фактич", "отриман"],
                ["помил", "невідповід", "логік"],
            ],
        ),
        build_task(
            "answer_3",
            "Питання 3. План виправлення",
            analysis_question,
            [
                ["перевір", "аналіз", "виправ"],
                ["код", "логік", "умов", "сигнал"],
            ],
        ),
    ]


# =========================
# Сумісність зі старим інтерфейсом адаптивних підказок
# =========================

def get_fallback_error_type_from_status(status) -> str:
    """
    Визначає базову категорію помилки за статусом перевірки,
    якщо детальна класифікація ще не збережена у submission.
    """
    normalized_status = str(
        status or ""
    ).strip().upper()

    status_mapping = {
        "PASSED": "NO_ERROR",
        "COMPILE_ERROR": "COMPILE_ERROR",
        "SIMULATION_ERROR": "SIMULATION_ERROR",
        "SYSTEM_ERROR": "SYSTEM_ERROR",
        "TIMEOUT": "TIMEOUT",
        "SECURITY_BLOCK": "SECURITY_BLOCK",
    }

    return status_mapping.get(
        normalized_status,
        "FUNCTIONAL_ERROR",
    )


def generate_ai_hint(
    submission,
    code,
    level,
) -> str:
    """
    Зберігає сумісність зі старими викликами generate_ai_hint().

    Фактичне формування підказки виконує єдиний адаптивний
    rule-based механізм generate_adaptive_hint(). Звернення
    до OpenAI/Ollama ця функція не виконує.
    """
    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    if not error_type:
        error_type = get_fallback_error_type_from_status(
            get_row_value(
                submission,
                "status",
                "",
            )
        )

    topic = detect_lab_topic(
        submission,
        code,
    )

    # Для студентських підказок використовуються насамперед
    # результати відкритих тестів. Hidden output не передається
    # адаптивному модулю.
    public_output = str(
        get_row_value(
            submission,
            "public_output",
            "",
        )
        or ""
    )

    # Підтримка старих записів БД, у яких public_output
    # ще не зберігався окремо.
    if not public_output.strip():
        public_output = str(
            get_row_value(
                submission,
                "output",
                "",
            )
            or ""
        )

    failed_tests = extract_failed_tests_for_adaptive_module(
        public_output
    )

    # generate_adaptive_hint() використовує з submission
    # лише класифікований тип помилки. Окремий словник запобігає
    # залежності від структури sqlite3.Row у старих записах.
    hint_submission = {
        "error_type": error_type,
    }

    return generate_adaptive_hint(
        submission=hint_submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=level,
    )


def detect_lab_topic(
    submission,
    code,
) -> str:
    """
    Визначає нормалізовану тему лабораторної роботи.

    Функція зберігається для сумісності зі старими викликами,
    але використовує спільний механізм визначення теми.
    """
    explicit_topic = str(
        get_row_value(
            submission,
            "lab_topic",
            "",
        )
        or ""
    ).strip().lower()

    if explicit_topic in LAB_TOPIC_KEYWORDS:
        return explicit_topic

    return detect_normalized_lab_topic(
        explicit_topic,
        get_row_value(
            submission,
            "lab_title",
            "",
        ),
        get_row_value(
            submission,
            "lab_description",
            "",
        ),
        code,
    )

# =========================
# Фокус помилки та додаткові адаптивні завдання
# =========================

def detect_error_focus(
    submission,
    code,
    topic,
) -> str:
    """
    Визначає додатковий діагностичний фокус помилки.

    Основним джерелом є вже класифікований error_type.
    Вивід відкритих тестів використовується лише для уточнення
    окремих функціональних випадків.
    """
    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    normalized_topic = str(
        topic or "general"
    ).strip().lower()

    public_output = str(
        get_row_value(
            submission,
            "public_output",
            "",
        )
        or ""
    )

    # Сумісність зі старими записами, у яких public_output
    # ще не зберігався окремо.
    if not public_output.strip():
        public_output = str(
            get_row_value(
                submission,
                "output",
                "",
            )
            or ""
        )

    output_lower = public_output.casefold()
    code_lower = str(
        code or ""
    ).casefold()

    if error_type == "MODULE_NAME_MISMATCH":
        return "module_name"

    if error_type == "PORT_MISMATCH":
        return "ports"

    if error_type == "COMPILE_ERROR":
        return "syntax"

    if error_type == "RESET_CLOCK_ERROR":
        if "reset" in output_lower or "rst" in output_lower:
            return f"{normalized_topic}_reset"

        if (
            "clock" in output_lower
            or "clk" in output_lower
            or "posedge" in output_lower
            or "negedge" in output_lower
        ):
            return f"{normalized_topic}_clock"

        return f"{normalized_topic}_sequential"

    failed_tests = extract_failed_tests_for_adaptive_module(
        public_output
    )

    failed_text = "\n".join(
        " ".join(
            str(test.get(field, "") or "")
            for field in (
                "test_line",
                "expected",
                "actual",
            )
        )
        for test in failed_tests
        if isinstance(test, dict)
    ).casefold()

    if normalized_topic == "mux":
        if (
            "sel=0" in failed_text
            or "sel = 0" in failed_text
        ):
            return "mux_sel_0"

        if (
            "sel=1" in failed_text
            or "sel = 1" in failed_text
        ):
            return "mux_sel_1"

        if (
            "d0" in failed_text
            and "d1" in failed_text
        ):
            return "mux_logic"

        return "mux_general"

    if normalized_topic == "adder":
        if "carry" in failed_text:
            return "adder_carry"

        if "sum" in failed_text:
            return "adder_sum"

        return "adder_general"

    if normalized_topic == "counter":
        if (
            "reset" in failed_text
            or "rst" in failed_text
        ):
            return "counter_reset"

        if (
            "clk" in code_lower
            or "clock" in code_lower
        ):
            return "counter_clock"

        return "counter_general"

    if normalized_topic == "register":
        if (
            "reset" in failed_text
            or "rst" in failed_text
        ):
            return "register_reset"

        return "register_general"

    if normalized_topic == "fsm":
        if (
            "state" in failed_text
            or "стан" in failed_text
        ):
            return "fsm_state"

        return "fsm_general"

    return "general_logic"


def get_submission_attempt_number(
    submission,
) -> int:
    """
    Повертає нормалізований номер поточної спроби.

    Значення зі submission використовується замість додаткового
    запиту до БД, оскільки воно безпосередньо характеризує
    поточну спробу, для якої формуються завдання.
    """
    try:
        attempt_number = int(
            get_row_value(
                submission,
                "attempt_number",
                1,
            )
            or 1
        )
    except (TypeError, ValueError, OverflowError):
        attempt_number = 1

    return max(
        1,
        attempt_number,
    )


def get_question_adaptation_level(
    attempt_number,
) -> int:
    """
    Визначає рівень конкретності додаткових питань
    за номером поточної спроби.
    """
    try:
        normalized_attempt = int(
            attempt_number
        )
    except (TypeError, ValueError, OverflowError):
        normalized_attempt = 1

    normalized_attempt = max(
        1,
        normalized_attempt,
    )

    if normalized_attempt <= 1:
        return 1

    if normalized_attempt == 2:
        return 2

    return 3


def strengthen_retry_task(
    tasks,
    attempt_number,
) -> list[dict]:
    """
    Посилює вимоги до аналітичного питання після кількох спроб.

    Починаючи з третьої спроби студент має не лише описати
    причину помилки, а й сформулювати конкретний план її виправлення.
    """
    if (
        attempt_number < 3
        or len(tasks) < 3
    ):
        return tasks

    third_task = tasks[2]

    third_task["text"] = (
        str(
            third_task.get(
                "text",
                "",
            )
            or ""
        ).rstrip()
        + (
            " Це вже щонайменше третя спроба виконання "
            "лабораторної роботи. У відповіді також зазначте, "
            "яку саме частину рішення ви плануєте перевірити "
            "або змінити перед наступним надсиланням."
        )
    )

    required_groups = third_task.setdefault(
        "required_groups",
        [],
    )

    required_groups.append([
        "виправ",
        "змін",
        "перевір",
        "план",
    ])

    return tasks


def generate_extra_tasks(
    submission,
    code,
) -> list[dict]:
    """
    Формує набір додаткових навчальних завдань
    для поточної спроби студента.

    Функція використовує єдиний механізм
    generate_adaptive_questions(), щоб додаткові завдання,
    підказки та аналітика спиралися на однакову модель
    тем, типів помилок і рівнів адаптації.
    """
    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    if not error_type:
        error_type = get_fallback_error_type_from_status(
            get_row_value(
                submission,
                "status",
                "",
            )
        )

    # Системні відмови, успішні результати та блокування
    # політикою безпеки не повинні формувати хибні
    # додаткові завдання з предметної теми.
    if error_type in {
        "NO_ERROR",
        "SYSTEM_ERROR",
        "SECURITY_BLOCK",
        "TIMEOUT",
    }:
        return []

    topic = detect_lab_topic(
        submission,
        code,
    )

    public_output = str(
        get_row_value(
            submission,
            "public_output",
            "",
        )
        or ""
    )

    # Для старих записів використовується student-visible output.
    # Hidden output до адаптивного модуля не передається.
    if not public_output.strip():
        public_output = str(
            get_row_value(
                submission,
                "output",
                "",
            )
            or ""
        )

    failed_tests = extract_failed_tests_for_adaptive_module(
        public_output
    )

    attempt_number = get_submission_attempt_number(
        submission
    )

    question_level = get_question_adaptation_level(
        attempt_number
    )

    adaptive_submission = {
        "error_type": error_type,
    }

    tasks = generate_adaptive_questions(
        submission=adaptive_submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=question_level,
    )

    return strengthen_retry_task(
        tasks=tasks,
        attempt_number=attempt_number,
    )


# =========================
# Нормалізація та оцінювання відповідей на додаткові завдання
# =========================

BAD_ANSWER_PHRASES = frozenset({
    "не знаю",
    "гадки не маю",
    "без відповіді",
    "не зрозумів",
    "не зрозуміла",
    "не розумію",
    "asdf",
    "qwerty",
})


def normalize_text(text) -> str:
    """
    Нормалізує текст студентської відповіді для rule-based перевірки.

    Нормалізація не змінює зміст відповіді, а лише усуває відмінності
    регістру, типографічних апострофів і надлишкових пробілів.
    """
    if text is None:
        return ""

    normalized = str(text).casefold()

    # Різні типографічні варіанти апострофа приводяться
    # до одного представлення для стабільного порівняння.
    normalized = (
        normalized
        .replace("’", "'")
        .replace("ʼ", "'")
        .replace("`", "'")
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def compact_text(text) -> str:
    """
    Повертає нормалізований текст без пробілів.

    Представлення використовується для технічних конструкцій
    на кшталт sel=0, які студент може записувати з різними пробілами.
    """
    return normalize_text(
        text
    ).replace(
        " ",
        "",
    )


def is_bad_answer(text) -> bool:
    """
    Виявляє явно недостатню або беззмістовну текстову відповідь.

    Перевірка є попереднім евристичним фільтром і не використовується
    як повноцінна семантична оцінка змісту відповіді.
    """
    normalized = normalize_text(
        text
    )

    if len(normalized) < 20:
        return True

    if any(
        phrase in normalized
        for phrase in BAD_ANSWER_PHRASES
    ):
        return True

    alphabetic_chars = [
        char
        for char in normalized
        if char.isalpha()
    ]

    # Додаткові завдання передбачають пояснення природною мовою.
    # Рядок без літер не вважається змістовною відповіддю.
    if not alphabetic_chars:
        return True

    alphanumeric_chars = [
        char
        for char in normalized
        if char.isalnum()
    ]

    # Захист від відповідей, утворених тривалим повторенням
    # одного або кількох символів.
    if (
        alphanumeric_chars
        and len(set(alphanumeric_chars)) <= 3
    ):
        return True

    return False


def answer_matches_task(
    answer,
    task,
) -> bool:
    """
    Перевіряє відповідь за мінімальною довжиною
    та набором обов'язкових понятійних груп.

    Для кожної required group достатньо знайти хоча б один
    із її ключових варіантів. Між різними групами діє умова AND.
    """
    normalized = normalize_text(
        answer
    )

    compact = compact_text(
        answer
    )

    if is_bad_answer(answer):
        return False

    try:
        min_length = int(
            task.get(
                "min_length",
                25,
            )
        )
    except (TypeError, ValueError, OverflowError):
        min_length = 25

    min_length = max(
        1,
        min_length,
    )

    if len(normalized) < min_length:
        return False

    required_groups = task.get(
        "required_groups",
        [],
    )

    if required_groups is None:
        required_groups = []

    if isinstance(
        required_groups,
        str,
    ):
        required_groups = [
            [required_groups]
        ]

    for group in required_groups:
        if isinstance(
            group,
            str,
        ):
            group = [
                group
            ]

        normalized_keywords = []

        for keyword in group or []:
            keyword_normalized = normalize_text(
                keyword
            )

            keyword_compact = compact_text(
                keyword
            )

            if (
                keyword_normalized
                or keyword_compact
            ):
                normalized_keywords.append(
                    (
                        keyword_normalized,
                        keyword_compact,
                    )
                )

        # Порожня група не створює неможливої умови
        # для прийняття студентської відповіді.
        if not normalized_keywords:
            continue

        group_matched = any(
            (
                keyword_normalized
                and keyword_normalized in normalized
            )
            or (
                keyword_compact
                and keyword_compact in compact
            )
            for (
                keyword_normalized,
                keyword_compact,
            ) in normalized_keywords
        )

        if not group_matched:
            return False

    return True


def evaluate_extra_task_answers(
    submission,
    answers,
):
    """
    Оцінює відповіді на додаткові адаптивні завдання.

    Результатом є кількість прийнятих відповідей, бонусний бал
    і текстовий зворотний зв'язок для студента.
    """
    filename = str(
        get_row_value(
            submission,
            "filename",
            "",
        )
        or ""
    ).strip()

    if filename:
        code = read_submission_code(
            filename
        ) or ""
    else:
        code = ""

        app.logger.warning(
            "Не знайдено ім'я файла рішення під час "
            "оцінювання додаткових завдань."
        )

    tasks = generate_extra_tasks(
        submission,
        code,
    )

    correct_count = 0
    feedback_lines = []

    for task in tasks:
        field = str(
            task.get(
                "field",
                "",
            )
            or ""
        )

        answer = (
            answers.get(
                field,
                "",
            )
            if isinstance(answers, dict)
            else ""
        )

        if answer_matches_task(
            answer,
            task,
        ):
            correct_count += 1

            feedback_lines.append(
                f"{task['title']}: відповідь прийнято."
            )
        else:
            feedback_lines.append(
                (
                    f"{task['title']}: відповідь не прийнято. "
                    "Перевірте повноту пояснення та наявність "
                    "ключових понять, пов'язаних із завданням."
                )
            )

    # Поточна модель бонусу зберігається без зміни:
    # три прийняті відповіді — 20 балів, дві — 10 балів.
    if correct_count == 3:
        bonus = 20
    elif correct_count == 2:
        bonus = 10
    else:
        bonus = 0

    return (
        correct_count,
        bonus,
        "\n".join(feedback_lines),
    )


# =========================
# Паспорт лабораторної роботи
# =========================

def get_lab_concepts(
    lab_or_submission,
) -> list[str]:
    """
    Повертає перелік ключових понять із паспорта лабораторної роботи.
    """
    concepts = str(
        get_row_value(
            lab_or_submission,
            "concepts",
            "",
        )
        or get_row_value(
            lab_or_submission,
            "lab_concepts",
            "",
        )
        or ""
    )

    concept_items = [
        concept.strip()
        for concept in re.split(
            r"[,;\n]+",
            concepts,
        )
        if concept.strip()
    ]

    # Порядок понять зберігається, а випадкові дублікати видаляються.
    return list(
        dict.fromkeys(
            concept_items
        )
    )


def get_lab_topic_from_passport(
    lab_or_submission,
    code="",
) -> str:
    """
    Визначає тему лабораторної роботи.

    Пріоритет має явно задана тема з паспорта. Якщо її немає,
    використовується спільний механізм визначення теми за назвою,
    описом і кодом рішення.
    """
    explicit_topic = str(
        get_row_value(
            lab_or_submission,
            "topic",
            "",
        )
        or get_row_value(
            lab_or_submission,
            "lab_topic",
            "",
        )
        or ""
    ).strip().lower()

    title = str(
        get_row_value(
            lab_or_submission,
            "title",
            "",
        )
        or get_row_value(
            lab_or_submission,
            "lab_title",
            "",
        )
        or ""
    )

    description = str(
        get_row_value(
            lab_or_submission,
            "description",
            "",
        )
        or get_row_value(
            lab_or_submission,
            "lab_description",
            "",
        )
        or ""
    )

    if explicit_topic:
        if explicit_topic in {
            "general",
            "python_loops",
            *LAB_TOPIC_KEYWORDS.keys(),
        }:
            return explicit_topic

        detected_topic = detect_normalized_lab_topic(
            explicit_topic,
            title,
        )

        # Нестандартне значення паспорта не втрачається,
        # якщо воно не належить до відомих HDL-тем.
        if detected_topic != "general":
            return detected_topic

        return explicit_topic

    checker_type = str(
        get_row_value(
            lab_or_submission,
            "checker_type",
            "",
        )
        or ""
    ).strip().lower()

    code_text = str(
        code or ""
    )

    # Для Python-завдань зберігається окрема навчальна тема,
    # якщо код явно містить конструкції циклічної обробки.
    if (
        checker_type == "python_unit_tests"
        and (
            re.search(
                r"\b(?:for|while)\b",
                code_text,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\brange\s*\(",
                code_text,
                flags=re.IGNORECASE,
            )
        )
    ):
        return "python_loops"

    return detect_normalized_lab_topic(
        title,
        description,
        code_text,
    )


def get_adaptive_module_output(
    submission,
) -> str:
    """
    Повертає діагностичний вивід, дозволений для адаптивного модуля.

    Для HDL використовуються виключно результати відкритих тестів,
    щоб hidden testbench не міг потрапити до студентських підказок.
    Для інших checker-модулів використовується звичайний output.
    """
    checker_type = str(
        get_row_value(
            submission,
            "checker_type",
            "hdl_testbench",
        )
        or "hdl_testbench"
    ).strip().lower()

    if checker_type == "hdl_testbench":
        return str(
            get_row_value(
                submission,
                "public_output",
                "",
            )
            or ""
        )

    return str(
        get_row_value(
            submission,
            "output",
            "",
        )
        or ""
    )


# =========================
# Побудова адаптивного навчального плану
# =========================

def build_adaptive_learning_plan(
    submission,
    code,
) -> dict:
    """
    Формує адаптивний навчальний план за результатом поточної спроби.

    План поєднує класифікований тип помилки, тему лабораторної роботи,
    історію попередніх помилок, рівень підказки, відкриті результати
    тестування, додаткові питання та теми, рекомендовані для повторення.
    """
    topic = get_lab_topic_from_passport(
        submission,
        code,
    )

    concepts = get_lab_concepts(
        submission
    )

    adaptive_output = get_adaptive_module_output(
        submission
    )

    failed_tests = extract_failed_tests_for_adaptive_module(
        adaptive_output
    )

    username = str(
        get_row_value(
            submission,
            "username",
            "",
        )
        or ""
    )

    lab_id = get_row_value(
        submission,
        "lab_id",
        None,
    )

    error_history = get_student_error_history(
        username,
        lab_id,
    )

    hint_level = define_hint_level(
        submission,
        error_history,
    )

    error_type = str(
        get_row_value(
            submission,
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    error_title = str(
        get_row_value(
            submission,
            "error_title",
            "",
        )
        or ""
    )

    hint_text = generate_adaptive_hint(
        submission=submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=hint_level,
    )

    questions = generate_adaptive_questions(
        submission=submission,
        topic=topic,
        failed_tests=failed_tests,
        hint_level=hint_level,
    )

    repeat_topics = build_recommendations_to_repeat(
        topic=topic,
        error_type=error_type,
    )

    return {
        "topic": topic,
        "concepts": concepts,
        "error_type": error_type,
        "error_title": error_title,
        "hint_level": hint_level,
        "hint_text": hint_text,
        "questions": questions,
        "repeat_topics": repeat_topics,
        "failed_tests": failed_tests,
        "error_history": error_history,
    }


# =========================
# 10. Автентифікація: вхід, реєстрація та OAuth
# =========================

REGISTER_ALLOWED_ROLES = frozenset({
    "student",
    "teacher",
})

ACCOUNT_STATUS_MESSAGES = {
    "pending": (
        "Ваш обліковий запис очікує підтвердження адміністратором."
    ),
    "blocked": (
        "Ваш обліковий запис заблоковано."
    ),
}


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Виконує локальну автентифікацію користувача.

    Після успішної перевірки облікових даних до сесії
    завантажуються роль користувача та налаштування інтерфейсу.
    Для старих записів із відкритим паролем виконується
    автоматична міграція до поточного формату хешування.
    """
    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        if not username or not password:
            flash(
                "Введіть логін і пароль."
            )
            return redirect(
                url_for("login")
            )

        conn = get_db()

        try:
            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

            if (
                not user
                or not verify_password(
                    user["password"],
                    password,
                )
            ):
                flash(
                    "Неправильний логін або пароль."
                )
                return redirect(
                    url_for("login")
                )

            user_status = str(
                user["status"] or ""
            ).strip().lower()

            if user_status != "active":
                flash(
                    ACCOUNT_STATUS_MESSAGES.get(
                        user_status,
                        "Вхід до облікового запису тимчасово недоступний.",
                    )
                )

                return redirect(
                    url_for("login")
                )

            # Під час успішної авторизації старий відкритий пароль
            # замінюється поточним безпечним хешем. Помилка цієї
            # допоміжної міграції не повинна скасовувати вже
            # підтверджену автентифікацію користувача.
            if not password_is_hashed(
                user["password"]
            ):
                try:
                    conn.execute(
                        """
                        UPDATE users
                        SET password = ?
                        WHERE id = ?
                        """,
                        (
                            hash_password(password),
                            user["id"],
                        ),
                    )

                    conn.commit()

                except sqlite3.Error:
                    conn.rollback()

                    app.logger.exception(
                        "Не вдалося оновити legacy-пароль "
                        "користувача %s до хешованого формату.",
                        user["username"],
                    )

            # Попередній вміст сесії видаляється перед створенням
            # нового автентифікованого контексту користувача.
            session.clear()

            session["username"] = user["username"]
            session["role"] = user["role"]

            load_user_ui_settings_to_session(
                user
            )

            needs_setup = (
                int(
                    session.get(
                        "first_login_completed",
                        0,
                    )
                    or 0
                )
                == 0
            )

            if needs_setup:
                redirect_url = url_for(
                    "setup_appearance"
                )
            else:
                redirect_url = get_default_redirect_for_role(
                    user["role"]
                )

            return redirect(
                redirect_url
            )

        except sqlite3.Error:
            app.logger.exception(
                "Помилка SQLite під час локальної автентифікації "
                "користувача."
            )

            flash(
                "Не вдалося виконати вхід через внутрішню помилку системи."
            )

            return redirect(
                url_for("login")
            )

        finally:
            conn.close()

    return render_template(
        "auth/login.html"
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Реєструє нового студента або викладача.

    Новий обліковий запис створюється зі статусом pending
    і стає доступним для входу лише після підтвердження
    адміністратором системи.
    """
    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        role = request.form.get(
            "role",
            "",
        ).strip().lower()

        full_name = request.form.get(
            "full_name",
            "",
        ).strip()

        student_group = request.form.get(
            "student_group",
            "",
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip()

        if role not in REGISTER_ALLOWED_ROLES:
            flash(
                "Зареєструватися можна лише як студент або викладач."
            )

            return redirect(
                url_for("register")
            )

        if (
            not username
            or not password
            or not full_name
        ):
            flash(
                "Необхідно вказати логін, пароль і ПІБ."
            )

            return redirect(
                url_for("register")
            )

        (
            password_ok,
            password_error,
        ) = validate_password_strength(
            password,
            username,
        )

        if not password_ok:
            flash(
                password_error
            )

            return redirect(
                url_for("register")
            )

        if (
            role == "student"
            and not student_group
        ):
            flash(
                "Для студента необхідно вказати навчальну групу."
            )

            return redirect(
                url_for("register")
            )

        if role == "teacher":
            student_group = ""

        password_hash = hash_password(
            password
        )

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
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                ),
            )

            conn.commit()

            flash(
                "Заявку на реєстрацію надіслано. "
                "Дочекайтеся підтвердження адміністратора."
            )

        except sqlite3.IntegrityError:
            conn.rollback()

            flash(
                "Користувач із таким логіном уже існує."
            )

        except sqlite3.Error:
            conn.rollback()

            app.logger.exception(
                "Помилка SQLite під час реєстрації "
                "нового користувача."
            )

            flash(
                "Не вдалося завершити реєстрацію через "
                "внутрішню помилку системи."
            )

        finally:
            conn.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/register.html"
    )


@app.route("/auth/google")
def google_login():
    """
    Ініціює автентифікацію через Google OAuth.

    URI повернення формується засобами Flask, після чого
    керування передається OAuth-клієнту.
    """
    redirect_uri = url_for(
        "google_callback",
        _external=True,
    )

    return google.authorize_redirect(
        redirect_uri
    )



def google_email_is_verified(google_user) -> bool:
    """
    Перевіряє, чи підтверджено адресу email постачальником Google.

    Для автентифікації та створення облікового запису використовується
    лише підтверджена адреса, отримана безпосередньо від Google.
    """
    value = google_user.get(
        "email_verified"
    )

    if value is True:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
        }

    return value == 1


@app.route("/auth/google/callback")
def google_callback():
    """
    Обробляє результат Google OAuth-автентифікації.

    Ідентифікація наявного користувача виконується за google_id.
    Автоматичне пов'язування за одним лише збігом email не
    використовується, оскільки локальна адреса email окремо
    не підтверджує володіння Google-обліковим записом.
    """
    try:
        token = google.authorize_access_token()

        google_user = token.get(
            "userinfo"
        )

        if not google_user:
            google_user = google.parse_id_token(
                token
            )

    except Exception:
        app.logger.exception(
            "Помилка під час обробки Google OAuth callback."
        )

        session.pop(
            "google_registration",
            None,
        )

        flash(
            "Не вдалося виконати вхід через Google."
        )

        return redirect(
            url_for("login")
        )

    if not google_user:
        app.logger.warning(
            "Google OAuth не повернув дані користувача."
        )

        flash(
            "Google не передав необхідні дані користувача."
        )

        return redirect(
            url_for("login")
        )

    google_id = str(
        google_user.get(
            "sub",
            "",
        )
        or ""
    ).strip()

    email = str(
        google_user.get(
            "email",
            "",
        )
        or ""
    ).strip().lower()

    full_name = str(
        google_user.get(
            "name",
            "",
        )
        or ""
    ).strip()

    if not google_id or not email:
        app.logger.warning(
            "Google OAuth повернув неповні ідентифікаційні дані."
        )

        flash(
            "Google не передав необхідні дані користувача."
        )

        return redirect(
            url_for("login")
        )

    if not google_email_is_verified(
        google_user
    ):
        app.logger.warning(
            "Відхилено Google OAuth-вхід із непідтвердженою "
            "адресою email: %s",
            email,
        )

        flash(
            "Для входу через Google потрібна підтверджена адреса email."
        )

        return redirect(
            url_for("login")
        )

    conn = get_db()

    try:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE google_id = ?
            """,
            (google_id,),
        ).fetchone()

        if user:
            user_status = str(
                user["status"] or ""
            ).strip().lower()

            if user_status != "active":
                flash(
                    ACCOUNT_STATUS_MESSAGES.get(
                        user_status,
                        (
                            "Вхід до облікового запису "
                            "тимчасово недоступний."
                        ),
                    )
                )

                return redirect(
                    url_for("login")
                )

            # Після успішної OAuth-автентифікації формується
            # новий сесійний контекст без залишкових даних
            # попередньої сесії.
            session.clear()

            session["username"] = user["username"]
            session["role"] = user["role"]

            load_user_ui_settings_to_session(
                user
            )

            needs_setup = (
                int(
                    session.get(
                        "first_login_completed",
                        0,
                    )
                    or 0
                )
                == 0
            )

            if needs_setup:
                redirect_url = url_for(
                    "setup_appearance"
                )
            else:
                redirect_url = get_default_redirect_for_role(
                    user["role"]
                )

            return redirect(
                redirect_url
            )

        # Збіг email не використовується для автоматичного
        # пов'язування з локальним акаунтом. Для цього потрібен
        # окремий підтверджений сценарій зв'язування облікових записів.
        existing_email_user = conn.execute(
            """
            SELECT id, username, status
            FROM users
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (email,),
        ).fetchone()

        if existing_email_user:
            app.logger.info(
                "Google OAuth не пов'язано автоматично з існуючим "
                "локальним користувачем %s через збіг email.",
                existing_email_user["username"],
            )

            session.pop(
                "google_registration",
                None,
            )

            flash(
                "Обліковий запис із цією адресою email уже існує. "
                "Автоматичне пов'язування з Google не виконується. "
                "Увійдіть до наявного облікового запису або зверніться "
                "до адміністратора."
            )

            return redirect(
                url_for("login")
            )

        # У сесії зберігається лише мінімальний набір даних,
        # необхідний для завершення реєстрації. OAuth token
        # до реєстраційного контексту не копіюється.
        session.clear()

        session["google_registration"] = {
            "google_id": google_id,
            "email": email,
            "full_name": full_name,
        }

        return redirect(
            url_for(
                "complete_google_registration"
            )
        )

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час обробки Google OAuth-входу."
        )

        flash(
            "Не вдалося завершити вхід через внутрішню помилку системи."
        )

        return redirect(
            url_for("login")
        )

    finally:
        conn.close()


@app.route(
    "/auth/google/complete",
    methods=["GET", "POST"],
)
def complete_google_registration():
    """
    Завершує створення облікового запису після Google OAuth.

    Користувач обирає дозволену роль і, для студента,
    навчальну групу. Новий обліковий запис створюється
    зі статусом pending та потребує підтвердження адміністратора.
    """
    google_data = session.get(
        "google_registration"
    )

    if not isinstance(
        google_data,
        dict,
    ):
        flash(
            "Дані Google-реєстрації не знайдено."
        )

        return redirect(
            url_for("login")
        )

    google_id = str(
        google_data.get(
            "google_id",
            "",
        )
        or ""
    ).strip()

    email = str(
        google_data.get(
            "email",
            "",
        )
        or ""
    ).strip().lower()

    google_full_name = str(
        google_data.get(
            "full_name",
            "",
        )
        or ""
    ).strip()

    if not google_id or not email:
        app.logger.warning(
            "У сесії виявлено неповні дані Google-реєстрації."
        )

        session.pop(
            "google_registration",
            None,
        )

        flash(
            "Дані Google-реєстрації пошкоджено або застаріли. "
            "Повторіть вхід через Google."
        )

        return redirect(
            url_for("login")
        )

    if request.method == "POST":
        role = request.form.get(
            "role",
            "",
        ).strip().lower()

        student_group = request.form.get(
            "student_group",
            "",
        ).strip()

        full_name = request.form.get(
            "full_name",
            "",
        ).strip()

        if role not in REGISTER_ALLOWED_ROLES:
            flash(
                "Можна вибрати лише роль студента або викладача."
            )

            return redirect(
                url_for(
                    "complete_google_registration"
                )
            )

        if not full_name:
            flash(
                "Вкажіть ПІБ."
            )

            return redirect(
                url_for(
                    "complete_google_registration"
                )
            )

        if (
            role == "student"
            and not student_group
        ):
            flash(
                "Для студента необхідно вказати навчальну групу."
            )

            return redirect(
                url_for(
                    "complete_google_registration"
                )
            )

        if role == "teacher":
            student_group = ""

        conn = get_db()

        try:
            existing = conn.execute(
                """
                SELECT
                    id,
                    username,
                    google_id,
                    email
                FROM users
                WHERE google_id = ?
                   OR LOWER(email) = LOWER(?)
                LIMIT 1
                """,
                (
                    google_id,
                    email,
                ),
            ).fetchone()

            if existing:
                session.pop(
                    "google_registration",
                    None,
                )

                flash(
                    "Обліковий запис із цим Google-акаунтом "
                    "або адресою email уже існує."
                )

                return redirect(
                    url_for("login")
                )

            email_prefix = email.split(
                "@",
                maxsplit=1,
            )[0]

            username = build_unique_username(
                conn,
                email_prefix,
            )

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
                    email,
                    "pending",
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    google_id,
                    "google",
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()

            app.logger.warning(
                "Конфлікт унікальності під час створення "
                "Google-користувача для email %s.",
                email,
            )

            session.pop(
                "google_registration",
                None,
            )

            flash(
                "Обліковий запис із такими даними вже існує. "
                "Повторіть вхід або зверніться до адміністратора."
            )

            return redirect(
                url_for("login")
            )

        except sqlite3.Error:
            conn.rollback()

            app.logger.exception(
                "Помилка SQLite під час завершення "
                "Google-реєстрації."
            )

            flash(
                "Не вдалося завершити реєстрацію через "
                "внутрішню помилку системи."
            )

            return redirect(
                url_for(
                    "complete_google_registration"
                )
            )

        finally:
            conn.close()

        session.pop(
            "google_registration",
            None,
        )

        flash(
            "Заявку через Google створено. "
            "Дочекайтеся підтвердження адміністратора."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/google_complete.html",
        google_data={
            "google_id": google_id,
            "email": email,
            "full_name": google_full_name,
        },
    )


@app.route("/logout")
def logout():
    """Завершує поточну користувацьку сесію."""
    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# Налаштування зовнішнього вигляду користувача
# ============================================================

APPEARANCE_THEMES = [
    "light",
    "dark",
    "system",
]

APPEARANCE_PALETTES = [
    "pastel",
    "indigo",
    "burgundy",
    "green",
]

APPEARANCE_FONT_SIZES = [
    "small",
    "normal",
    "large",
]

APPEARANCE_DENSITIES = [
    "comfortable",
    "compact",
]

APPEARANCE_DEFAULTS = {
    "theme": "light",
    "palette": "pastel",
    "font_size": "normal",
    "ui_density": "comfortable",
}


def normalize_ui_flag(
    value,
    default=0,
) -> int:
    """
    Нормалізує двійкове значення налаштування інтерфейсу.

    Підтримується стандартне значення checkbox "on",
    а також числове представлення 0/1.
    """
    if value is None:
        return 1 if default else 0

    if isinstance(value, bool):
        return int(value)

    normalized = str(
        value
    ).strip().lower()

    return 1 if normalized in {
        "1",
        "true",
        "on",
        "yes",
    } else 0


def get_user_appearance_settings(
    user,
    include_beginner_tips=False,
) -> dict:
    """
    Формує нормалізований набір налаштувань зовнішнього вигляду
    з даних користувача.

    Значення, що не входять до дозволених наборів, замінюються
    безпечними значеннями за замовчуванням.
    """
    settings = {
        "theme": normalize_user_ui_value(
            get_row_value(
                user,
                "theme",
                APPEARANCE_DEFAULTS["theme"],
            ),
            APPEARANCE_DEFAULTS["theme"],
            APPEARANCE_THEMES,
        ),
        "palette": normalize_user_ui_value(
            get_row_value(
                user,
                "palette",
                APPEARANCE_DEFAULTS["palette"],
            ),
            APPEARANCE_DEFAULTS["palette"],
            APPEARANCE_PALETTES,
        ),
        "font_size": normalize_user_ui_value(
            get_row_value(
                user,
                "font_size",
                APPEARANCE_DEFAULTS["font_size"],
            ),
            APPEARANCE_DEFAULTS["font_size"],
            APPEARANCE_FONT_SIZES,
        ),
        "ui_density": normalize_user_ui_value(
            get_row_value(
                user,
                "ui_density",
                APPEARANCE_DEFAULTS["ui_density"],
            ),
            APPEARANCE_DEFAULTS["ui_density"],
            APPEARANCE_DENSITIES,
        ),
    }

    if include_beginner_tips:
        settings["show_beginner_tips"] = normalize_ui_flag(
            get_row_value(
                user,
                "show_beginner_tips",
                1,
            ),
            default=1,
        )

    return settings


def get_appearance_settings_from_form(
    include_beginner_tips=False,
) -> dict:
    """
    Зчитує та нормалізує налаштування зовнішнього вигляду
    з поточної HTML-форми.
    """
    settings = {
        "theme": normalize_user_ui_value(
            request.form.get(
                "theme"
            ),
            APPEARANCE_DEFAULTS["theme"],
            APPEARANCE_THEMES,
        ),
        "palette": normalize_user_ui_value(
            request.form.get(
                "palette"
            ),
            APPEARANCE_DEFAULTS["palette"],
            APPEARANCE_PALETTES,
        ),
        "font_size": normalize_user_ui_value(
            request.form.get(
                "font_size"
            ),
            APPEARANCE_DEFAULTS["font_size"],
            APPEARANCE_FONT_SIZES,
        ),
        "ui_density": normalize_user_ui_value(
            request.form.get(
                "ui_density"
            ),
            APPEARANCE_DEFAULTS["ui_density"],
            APPEARANCE_DENSITIES,
        ),
    }

    if include_beginner_tips:
        settings["show_beginner_tips"] = normalize_ui_flag(
            request.form.get(
                "show_beginner_tips"
            ),
            default=0,
        )

    return settings


def update_user_appearance_settings(
    conn,
    username,
    settings,
    update_beginner_tips=False,
):
    """
    Зберігає налаштування зовнішнього вигляду користувача.

    Після успішного збереження первинне налаштування вважається
    завершеним незалежно від того, з якої сторінки виконано зміну.
    """
    if update_beginner_tips:
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
                settings["theme"],
                settings["palette"],
                settings["font_size"],
                settings["ui_density"],
                settings["show_beginner_tips"],
                username,
            ),
        )

        return

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
            settings["theme"],
            settings["palette"],
            settings["font_size"],
            settings["ui_density"],
            username,
        ),
    )


def get_user_by_username(
    conn,
    username,
):
    """Повертає запис користувача за його логіном."""
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()


def get_student_profile_points(
    conn,
    username,
):
    """
    Повертає суму найкращих результатів студента
    за всіма лабораторними роботами.

    Для кожної лабораторної враховується лише один,
    найкращий результат.
    """

    row = conn.execute(
        """
        SELECT
            COALESCE(
                SUM(best_score),
                0
            ) AS total_points
        FROM (
            SELECT
                lab_id,
                MAX(
                    COALESCE(
                        final_score,
                        score,
                        0
                    )
                ) AS best_score
            FROM submissions
            WHERE username = ?
              AND status <> 'SYSTEM_ERROR'
            GROUP BY lab_id
        )
        """,
        (username,),
    ).fetchone()

    if not row:
        return 0

    try:
        return max(
            0,
            int(
                round(
                    float(
                        row["total_points"]
                        or 0
                    )
                )
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0


def normalize_profile_text(
    value,
    max_length,
):
    """
    Нормалізує користувацький текст профілю.
    HTML не обробляється як розмітка.
    """

    value = str(
        value or ""
    ).strip()

    value = value.replace(
        "\x00",
        "",
    )

    return value[:max_length]


def build_profile_ui(
    user,
    points=0,
):
    """
    Формує безпечний набір даних для відображення
    аватара, рамки та значка користувача.
    """

    username = str(
        user["username"]
        or ""
    )

    initials = (
        username[:2].upper()
        if username
        else "U"
    )

    avatar_filename = str(
        user["avatar_filename"]
        or ""
    ).strip()

    avatar_key = str(
        user["profile_avatar"]
        or "initials"
    ).strip()

    frame_key = str(
        user["profile_frame"]
        or "none"
    ).strip()

    badge_key = str(
        user["profile_badge"]
        or "none"
    ).strip()


    # -----------------------------
    # Avatar
    # -----------------------------

    avatar_kind = "initials"
    avatar_symbol = initials
    avatar_url = ""
    avatar_css_class = (
        "profile-avatar-default"
    )

    if (
        avatar_key == "uploaded"
        and avatar_filename
    ):
        avatar_kind = "image"

        avatar_url = url_for(
            "profile_avatar_file",
            filename=avatar_filename,
        )

    elif avatar_key in PROFILE_AVATARS:
        avatar_data = (
            PROFILE_AVATARS[
                avatar_key
            ]
        )

        required_points = int(
            avatar_data[
                "required_points"
            ]
        )

        allowed = (
            user["role"] != "student"
            or points >= required_points
        )

        if allowed:
            avatar_kind = "special"

            avatar_symbol = (
                avatar_data[
                    "symbol"
                ]
                or initials
            )

            avatar_css_class = (
                avatar_data[
                    "css_class"
                ]
            )


    # -----------------------------
    # Frame
    # -----------------------------

    if frame_key not in PROFILE_FRAMES:
        frame_key = "none"

    frame_data = PROFILE_FRAMES[
        frame_key
    ]

    if (
        user["role"] == "student"
        and points
        < int(
            frame_data[
                "required_points"
            ]
        )
    ):
        frame_key = "none"

        frame_data = (
            PROFILE_FRAMES["none"]
        )


    # -----------------------------
    # Badge
    # -----------------------------

    if badge_key not in PROFILE_BADGES:
        badge_key = "none"

    badge_data = PROFILE_BADGES[
        badge_key
    ]

    if (
        user["role"] == "student"
        and points
        < int(
            badge_data[
                "required_points"
            ]
        )
    ):
        badge_key = "none"

        badge_data = (
            PROFILE_BADGES["none"]
        )


    return {
        "avatar_kind": avatar_kind,
        "avatar_url": avatar_url,
        "avatar_symbol": avatar_symbol,
        "avatar_css_class": avatar_css_class,

        "frame_key": frame_key,
        "frame_css_class": (
            frame_data[
                "css_class"
            ]
        ),

        "badge_key": badge_key,
        "badge_name": (
            badge_data[
                "name"
            ]
        ),
        "badge_symbol": (
            badge_data[
                "symbol"
            ]
        ),

        "status": str(
            user["profile_status"]
            or ""
        ),
    }


def detect_profile_avatar_extension(
    data,
):
    """
    Визначає дозволений тип зображення
    за сигнатурою файла, а не лише за його назвою.
    """

    if data.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return ".png"

    if data.startswith(
        b"\xff\xd8\xff"
    ):
        return ".jpg"

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return ".webp"

    return None


def save_profile_avatar(
    file_storage,
    username,
):
    """
    Перевіряє та зберігає користувацький аватар.
    """

    if (
        not file_storage
        or not file_storage.filename
    ):
        return ""

    data = file_storage.read(
        PROFILE_AVATAR_MAX_BYTES + 1
    )

    if len(data) > PROFILE_AVATAR_MAX_BYTES:
        raise ValueError(
            "Аватар завеликий. "
            "Максимальний розмір — 220 КБ."
        )

    extension = (
        detect_profile_avatar_extension(
            data
        )
    )

    if not extension:
        raise ValueError(
            "Підтримуються лише PNG, JPG та WEBP."
        )

    safe_username = secure_filename(
        str(username)
    )

    if not safe_username:
        safe_username = "user"

    filename = (
        f"{safe_username}_"
        f"{secrets.token_hex(8)}"
        f"{extension}"
    )

    path = os.path.join(
        PROFILE_AVATAR_DIR,
        filename,
    )

    with open(
        path,
        "xb",
    ) as avatar_file:
        avatar_file.write(
            data
        )

    return filename


@app.route(
    "/setup/appearance",
    methods=["GET", "POST"],
)
@login_required
def setup_appearance():
    """
    Виконує первинне налаштування зовнішнього вигляду.

    Після збереження параметрів система позначає початкове
    налаштування завершеним і перенаправляє користувача
    на стартову сторінку відповідно до його ролі.
    """
    username = str(
        session.get(
            "username",
            "",
        )
        or ""
    ).strip()

    if not username:
        session.clear()

        flash(
            "Сесію користувача не знайдено. Виконайте вхід повторно."
        )

        return redirect(
            url_for("login")
        )

    conn = get_db()

    try:
        user = get_user_by_username(
            conn,
            username,
        )

        if not user:
            session.clear()

            flash(
                "Користувача не знайдено. Виконайте вхід повторно."
            )

            return redirect(
                url_for("login")
            )

        first_login_completed = normalize_ui_flag(
            get_row_value(
                user,
                "first_login_completed",
                0,
            ),
            default=0,
        )

        if (
            request.method == "GET"
            and first_login_completed == 1
        ):
            return redirect(
                get_default_redirect_for_role(
                    user["role"]
                )
            )

        if request.method == "POST":
            settings = get_appearance_settings_from_form(
                include_beginner_tips=True,
            )

            update_user_appearance_settings(
                conn=conn,
                username=username,
                settings=settings,
                update_beginner_tips=True,
            )

            conn.commit()

            updated_user = get_user_by_username(
                conn,
                username,
            )

            if not updated_user:
                session.clear()

                app.logger.warning(
                    "Користувача %s не знайдено після "
                    "збереження початкових UI-налаштувань.",
                    username,
                )

                flash(
                    "Не вдалося оновити налаштування користувача. "
                    "Виконайте вхід повторно."
                )

                return redirect(
                    url_for("login")
                )

            load_user_ui_settings_to_session(
                updated_user
            )

            redirect_url = get_default_redirect_for_role(
                updated_user["role"]
            )

            flash(
                "Початкове налаштування завершено."
            )

            return redirect(
                redirect_url
            )

        settings = get_user_appearance_settings(
            user,
            include_beginner_tips=True,
        )

        return render_template(
            "setup/appearance.html",
            settings=settings,
        )

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час початкового "
            "налаштування зовнішнього вигляду."
        )

        flash(
            "Не вдалося зберегти налаштування через "
            "внутрішню помилку системи."
        )

        return redirect(
            url_for("login")
        )

    finally:
        conn.close()


@app.route(
    "/settings/appearance",
    methods=["GET", "POST"],
)
@login_required
def appearance_settings():
    """
    Відображає та змінює персональні налаштування
    зовнішнього вигляду авторизованого користувача.
    """
    username = str(
        session.get(
            "username",
            "",
        )
        or ""
    ).strip()

    if not username:
        session.clear()

        flash(
            "Сесію користувача не знайдено. Виконайте вхід повторно."
        )

        return redirect(
            url_for("login")
        )

    conn = get_db()

    try:
        user = get_user_by_username(
            conn,
            username,
        )

        if not user:
            session.clear()

            flash(
                "Користувача не знайдено. Виконайте вхід повторно."
            )

            return redirect(
                url_for("login")
            )

        if request.method == "POST":
            settings = get_appearance_settings_from_form(
                include_beginner_tips=False,
            )

            update_user_appearance_settings(
                conn=conn,
                username=username,
                settings=settings,
                update_beginner_tips=False,
            )

            conn.commit()

            updated_user = get_user_by_username(
                conn,
                username,
            )

            if not updated_user:
                session.clear()

                app.logger.warning(
                    "Користувача %s не знайдено після "
                    "збереження UI-налаштувань.",
                    username,
                )

                flash(
                    "Не вдалося оновити налаштування користувача. "
                    "Виконайте вхід повторно."
                )

                return redirect(
                    url_for("login")
                )

            load_user_ui_settings_to_session(
                updated_user
            )

            flash(
                "Налаштування зовнішнього вигляду збережено."
            )

            return redirect(
                url_for(
                    "appearance_settings"
                )
            )

        settings = get_user_appearance_settings(
            user,
            include_beginner_tips=False,
        )

        return render_template(
            "settings/appearance.html",
            settings=settings,
        )

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час зміни "
            "налаштувань зовнішнього вигляду."
        )

        flash(
            "Не вдалося зберегти налаштування через "
            "внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "appearance_settings"
            )
        )

    finally:
        conn.close()


@app.route(
    "/profile/avatar/<path:filename>"
)
@login_required
def profile_avatar_file(
    filename,
):
    return send_from_directory(
        PROFILE_AVATAR_DIR,
        filename,
        as_attachment=False,
    )


@app.route(
    "/profile",
    methods=["GET", "POST"],
)
@login_required
def profile():
    current_user = (
        get_current_session_user()
    )

    if not current_user:
        return redirect(
            url_for("login")
        )

    username = (
        current_user["username"]
    )

    conn = get_db()

    new_avatar_filename = ""
    old_avatar_filename = ""

    try:
        user = get_user_by_username(
            conn,
            username,
        )

        if not user:
            session.clear()

            flash(
                "Користувача не знайдено."
            )

            return redirect(
                url_for("login")
            )

        old_avatar_filename = str(
            user["avatar_filename"]
            or ""
        ).strip()

        points = 0

        if user["role"] == "student":
            points = (
                get_student_profile_points(
                    conn,
                    username,
                )
            )


        # ====================================================
        # POST
        # ====================================================

        if request.method == "POST":

            profile_status = (
                normalize_profile_text(
                    request.form.get(
                        "profile_status"
                    ),
                    80,
                )
            )

            profile_signature = (
                normalize_profile_text(
                    request.form.get(
                        "profile_signature"
                    ),
                    120,
                )
            )

            profile_bio = (
                normalize_profile_text(
                    request.form.get(
                        "profile_bio"
                    ),
                    600,
                )
            )


            # -----------------------------
            # Avatar upload
            # -----------------------------

            uploaded_file = (
                request.files.get(
                    "avatar_file"
                )
            )

            avatar_filename = (
                old_avatar_filename
            )

            if (
                uploaded_file
                and uploaded_file.filename
            ):
                try:
                    new_avatar_filename = (
                        save_profile_avatar(
                            uploaded_file,
                            username,
                        )
                    )
                except ValueError as exc:
                    flash(
                        str(exc)
                    )

                    return redirect(
                        url_for("profile")
                    )

                avatar_filename = (
                    new_avatar_filename
                )


            # -----------------------------
            # Selected avatar
            # -----------------------------

            selected_avatar = str(
                request.form.get(
                    "profile_avatar",
                    "initials",
                )
                or "initials"
            ).strip()


            # Завантаження нового файла автоматично
            # робить його активним аватаром.
            if new_avatar_filename:
                selected_avatar = "uploaded"

            if selected_avatar == "uploaded":
                if not avatar_filename:
                    selected_avatar = "initials"

            elif selected_avatar not in PROFILE_AVATARS:
                selected_avatar = "initials"

            elif user["role"] == "student":
                avatar_data = (
                    PROFILE_AVATARS[
                        selected_avatar
                    ]
                )

                if points < int(
                    avatar_data[
                        "required_points"
                    ]
                ):
                    flash(
                        "Цей аватар ще не розблоковано."
                    )

                    return redirect(
                        url_for("profile")
                    )


            # -----------------------------
            # Frame
            # -----------------------------

            selected_frame = str(
                request.form.get(
                    "profile_frame",
                    "none",
                )
                or "none"
            ).strip()

            if selected_frame not in PROFILE_FRAMES:
                selected_frame = "none"

            if user["role"] == "student":
                frame_data = (
                    PROFILE_FRAMES[
                        selected_frame
                    ]
                )

                if points < int(
                    frame_data[
                        "required_points"
                    ]
                ):
                    flash(
                        "Цю рамку ще не розблоковано."
                    )

                    return redirect(
                        url_for("profile")
                    )
            else:
                selected_frame = "none"


            # -----------------------------
            # Badge
            # -----------------------------

            selected_badge = str(
                request.form.get(
                    "profile_badge",
                    "none",
                )
                or "none"
            ).strip()

            if selected_badge not in PROFILE_BADGES:
                selected_badge = "none"

            if user["role"] == "student":
                badge_data = (
                    PROFILE_BADGES[
                        selected_badge
                    ]
                )

                if points < int(
                    badge_data[
                        "required_points"
                    ]
                ):
                    flash(
                        "Цей значок ще не розблоковано."
                    )

                    return redirect(
                        url_for("profile")
                    )
            else:
                selected_badge = "none"


            # -----------------------------
            # Save
            # -----------------------------

            conn.execute(
                """
                UPDATE users
                SET profile_status = ?,
                    profile_signature = ?,
                    profile_bio = ?,
                    avatar_filename = ?,
                    profile_avatar = ?,
                    profile_frame = ?,
                    profile_badge = ?
                WHERE username = ?
                """,
                (
                    profile_status,
                    profile_signature,
                    profile_bio,
                    avatar_filename,
                    selected_avatar,
                    selected_frame,
                    selected_badge,
                    username,
                ),
            )

            conn.commit()


            # Старий avatar видаляється лише після
            # успішного запису нового до БД.
            if (
                new_avatar_filename
                and old_avatar_filename
                and old_avatar_filename
                != new_avatar_filename
            ):
                old_path = os.path.join(
                    PROFILE_AVATAR_DIR,
                    old_avatar_filename,
                )

                try:
                    os.remove(
                        old_path
                    )
                except FileNotFoundError:
                    pass
                except OSError:
                    app.logger.exception(
                        "Не вдалося видалити "
                        "старий аватар %s.",
                        old_avatar_filename,
                    )

            flash(
                "Профіль оновлено."
            )

            return redirect(
                url_for("profile")
            )


        # ====================================================
        # GET
        # ====================================================

        profile_data = dict(
            user
        )

        is_student = (
            user["role"] == "student"
        )


        avatar_options = []

        if is_student:
            for key, data in (
                PROFILE_AVATARS.items()
            ):
                avatar_options.append({
                    "key": key,
                    **data,
                    "unlocked": (
                        points
                        >= int(
                            data[
                                "required_points"
                            ]
                        )
                    ),
                })


        frame_options = []

        if is_student:
            for key, data in (
                PROFILE_FRAMES.items()
            ):
                frame_options.append({
                    "key": key,
                    **data,
                    "unlocked": (
                        points
                        >= int(
                            data[
                                "required_points"
                            ]
                        )
                    ),
                })


        badge_options = []

        if is_student:
            for key, data in (
                PROFILE_BADGES.items()
            ):
                badge_options.append({
                    "key": key,
                    **data,
                    "unlocked": (
                        points
                        >= int(
                            data[
                                "required_points"
                            ]
                        )
                    ),
                })


        thresholds = sorted({
            int(data["required_points"])
            for data in (
                list(
                    PROFILE_AVATARS.values()
                )
                + list(
                    PROFILE_FRAMES.values()
                )
                + list(
                    PROFILE_BADGES.values()
                )
            )
            if int(
                data["required_points"]
            ) > 0
        })

        next_unlock = next(
            (
                value
                for value in thresholds
                if value > points
            ),
            None,
        )

        if next_unlock:
            progress_percent = min(
                100,
                round(
                    points
                    / next_unlock
                    * 100
                ),
            )
        else:
            progress_percent = 100


        return render_template(
            "profile/index.html",

            profile=profile_data,

            points=points,
            is_student=is_student,

            avatar_options=avatar_options,
            frame_options=frame_options,
            badge_options=badge_options,

            next_unlock=next_unlock,
            progress_percent=(
                progress_percent
            ),
        )

    except sqlite3.Error:
        conn.rollback()

        # Якщо файл уже був записаний,
        # але DB-транзакція завершилась помилкою,
        # видаляємо новий файл.
        if new_avatar_filename:
            path = os.path.join(
                PROFILE_AVATAR_DIR,
                new_avatar_filename,
            )

            try:
                os.remove(path)
            except OSError:
                pass

        app.logger.exception(
            "Помилка під час роботи "
            "з профілем %s.",
            username,
        )

        flash(
            "Не вдалося оновити профіль."
        )

        return redirect(
            url_for("index")
        )

    finally:
        conn.close()


@app.context_processor
def inject_profile_ui():
    username = str(
        session.get(
            "username",
            "",
        )
        or ""
    ).strip()

    if not username:
        return {
            "profile_ui": None,
        }

    conn = get_db()

    try:
        user = get_user_by_username(
            conn,
            username,
        )

        if not user:
            return {
                "profile_ui": None,
            }

        points = 0

        if user["role"] == "student":
            points = (
                get_student_profile_points(
                    conn,
                    username,
                )
            )

        return {
            "profile_ui": build_profile_ui(
                user,
                points,
            ),
        }

    except sqlite3.Error:
        return {
            "profile_ui": None,
        }

    finally:
        conn.close()


def get_safe_referrer_url(
    fallback_endpoint="index",
) -> str:
    """
    Повертає безпечну внутрішню адресу для перенаправлення.

    Значення HTTP Referer використовується лише тоді, коли воно
    належить тому самому хосту. Це запобігає перенаправленню
    користувача на зовнішню адресу через неперевірений referrer.
    """
    referrer = str(
        request.referrer or ""
    ).strip()

    if not referrer:
        return url_for(
            fallback_endpoint
        )

    try:
        referrer_url = urlparse(
            referrer
        )

        host_url = urlparse(
            request.host_url
        )

    except ValueError:
        return url_for(
            fallback_endpoint
        )

    if (
        referrer_url.scheme not in {"http", "https"}
        or referrer_url.netloc != host_url.netloc
    ):
        return url_for(
            fallback_endpoint
        )

    return referrer


@app.route(
    "/settings/appearance/toggle-theme",
    methods=["POST"],
)
@login_required
def appearance_toggle_theme():
    """
    Перемикає світлу та темну тему для поточного користувача.

    Налаштування зберігається в SQLite та одразу синхронізується
    із сесією, щоб нова тема застосовувалася без повторного входу.
    """
    username = str(
        session.get(
            "username",
            "",
        )
        or ""
    ).strip()

    if not username:
        session.clear()

        flash(
            "Сесію користувача не знайдено. Виконайте вхід повторно."
        )

        return redirect(
            url_for("login")
        )

    redirect_url = get_safe_referrer_url(
        fallback_endpoint="index"
    )

    conn = get_db()

    try:
        user = get_user_by_username(
            conn,
            username,
        )

        if not user:
            session.clear()

            flash(
                "Користувача не знайдено. Виконайте вхід повторно."
            )

            return redirect(
                url_for("login")
            )

        current_theme = normalize_user_ui_value(
            get_row_value(
                user,
                "theme",
                APPEARANCE_DEFAULTS["theme"],
            ),
            APPEARANCE_DEFAULTS["theme"],
            APPEARANCE_THEMES,
        )

        # Швидке перемикання працює лише між light і dark.
        # Значення system при першому натисканні переходить у dark.
        if current_theme == "dark":
            next_theme = "light"
        else:
            next_theme = "dark"

        cursor = conn.execute(
            """
            UPDATE users
            SET theme = ?
            WHERE username = ?
            """,
            (
                next_theme,
                username,
            ),
        )

        if cursor.rowcount == 0:
            conn.rollback()

            session.clear()

            app.logger.warning(
                "Не вдалося знайти користувача %s "
                "під час перемикання теми.",
                username,
            )

            flash(
                "Не вдалося змінити тему. Виконайте вхід повторно."
            )

            return redirect(
                url_for("login")
            )

        conn.commit()

        updated_user = get_user_by_username(
            conn,
            username,
        )

        if not updated_user:
            session.clear()

            app.logger.warning(
                "Користувача %s не знайдено після "
                "збереження нової теми.",
                username,
            )

            flash(
                "Тему збережено, але не вдалося оновити "
                "поточну сесію. Виконайте вхід повторно."
            )

            return redirect(
                url_for("login")
            )

        load_user_ui_settings_to_session(
            updated_user
        )

        return redirect(
            redirect_url
        )

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час перемикання "
            "теми користувача %s.",
            username,
        )

        flash(
            "Не вдалося змінити тему через "
            "внутрішню помилку системи."
        )

        return redirect(
            redirect_url
        )

    finally:
        conn.close()


# =========================
# 11. Спільні сторінки
# =========================

# SYSTEM_ERROR не враховується як навчальна спроба,
# оскільки характеризує відмову інфраструктури, а не якість рішення.
NON_COUNTABLE_ATTEMPT_STATUS = "SYSTEM_ERROR"


@app.route("/")
def index():
    """
    Відображає публічну стартову сторінку або персональну
    інформаційну панель авторизованого користувача.

    Для студентської панелі формуються прогрес лабораторних робіт,
    останні відправлення та агреговані показники успішності.
    Інфраструктурні відмови SYSTEM_ERROR не впливають
    на статистику навчальних спроб і середній бал.
    """
    current_user = get_current_session_user()

    if not current_user:
        return render_template(
            "common/index.html",
            is_landing=True,
            labs=[],
            my_submissions=[],
        )

    username = current_user["username"]

    conn = get_db()

    try:
        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        # Агрегована статистика лабораторних робіт не враховує
        # SYSTEM_ERROR як реальну навчальну спробу студента.
        labs_rows = conn.execute(
            """
            SELECT
                labs.*,

                COUNT(
                    CASE
                        WHEN submissions.status <> :system_error
                        THEN 1
                    END
                ) AS attempts_count,

                COALESCE(
                    MAX(
                        CASE
                            WHEN submissions.status <> :system_error
                            THEN submissions.score
                        END
                    ),
                    0
                ) AS best_score,

                MAX(
                    CASE
                        WHEN submissions.status = 'PASSED'
                        THEN 1
                        ELSE 0
                    END
                ) AS is_passed,

                MAX(
                    CASE
                        WHEN submissions.status <> :system_error
                        THEN submissions.created_at
                    END
                ) AS last_attempt_at,

                (
                    SELECT s2.status
                    FROM submissions AS s2
                    WHERE s2.lab_id = labs.id
                      AND s2.username = :username
                      AND s2.status <> :system_error
                    ORDER BY
                        s2.created_at DESC,
                        s2.id DESC
                    LIMIT 1
                ) AS last_status

            FROM labs

            LEFT JOIN submissions
                ON submissions.lab_id = labs.id
               AND submissions.username = :username

            GROUP BY labs.id

            ORDER BY labs.id DESC
            """,
            {
                "username": username,
                "system_error": NON_COUNTABLE_ATTEMPT_STATUS,
            },
        ).fetchall()

        # Історія відправлень зберігає також системні помилки,
        # оскільки студент має бачити факт і результат такої перевірки.
        my_submissions = conn.execute(
            """
            SELECT
                submissions.*,
                labs.title AS lab_title
            FROM submissions

            JOIN labs
                ON submissions.lab_id = labs.id

            WHERE submissions.username = ?

            ORDER BY
                submissions.created_at DESC,
                submissions.id DESC

            LIMIT 6
            """,
            (username,),
        ).fetchall()

        stats_row = conn.execute(
            """
            SELECT
                ROUND(
                    AVG(
                        CASE
                            WHEN status <> :system_error
                            THEN score
                        END
                    ),
                    1
                ) AS average_score,

                COUNT(
                    DISTINCT CASE
                        WHEN status = 'PASSED'
                        THEN lab_id
                    END
                ) AS completed_labs,

                COUNT(
                    CASE
                        WHEN status <> :system_error
                        THEN 1
                    END
                ) AS total_attempts,

                (
                    SELECT latest.score
                    FROM submissions AS latest
                    WHERE latest.username = :username
                      AND latest.status <> :system_error
                    ORDER BY
                        latest.created_at DESC,
                        latest.id DESC
                    LIMIT 1
                ) AS latest_score

            FROM submissions

            WHERE username = :username
            """,
            {
                "username": username,
                "system_error": NON_COUNTABLE_ATTEMPT_STATUS,
            },
        ).fetchone()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час формування "
            "головної інформаційної панелі користувача %s.",
            username,
        )

        flash(
            "Не вдалося завантажити інформаційну панель "
            "через внутрішню помилку системи."
        )

        return render_template(
            "common/index.html",
            is_landing=False,
            labs=[],
            my_submissions=[],
            student=current_user,
            dashboard_stats={
                "average_score": 0,
                "completed_labs": 0,
                "total_attempts": 0,
                "latest_score": "—",
            },
            active_lab=None,
        )

    finally:
        conn.close()

    labs = []

    for lab_row in labs_rows:
        lab = dict(
            lab_row
        )

        attempts_count = int(
            lab.get(
                "attempts_count",
                0,
            )
            or 0
        )

        best_score = int(
            lab.get(
                "best_score",
                0,
            )
            or 0
        )

        is_passed = (
            int(
                lab.get(
                    "is_passed",
                    0,
                )
                or 0
            )
            == 1
        )

        if is_passed:
            status_code = "passed"
            status_label = "Пройдено"
            progress_percent = 100

        elif attempts_count > 0:
            status_code = "in_progress"
            status_label = "У процесі"

            progress_percent = max(
                0,
                min(
                    best_score,
                    100,
                ),
            )

        else:
            status_code = "not_started"
            status_label = "Не розпочато"
            progress_percent = 0

        lab["attempts_count"] = attempts_count
        lab["best_score"] = best_score
        lab["status_code"] = status_code
        lab["status_label"] = status_label
        lab["progress_percent"] = progress_percent

        labs.append(
            lab
        )

    active_lab = None

    in_progress_labs = [
        lab
        for lab in labs
        if lab["status_code"] == "in_progress"
    ]

    if in_progress_labs:
        active_lab = max(
            in_progress_labs,
            key=lambda item: (
                item.get("last_attempt_at")
                or ""
            ),
        )

    else:
        not_started_labs = [
            lab
            for lab in labs
            if lab["status_code"] == "not_started"
        ]

        if not_started_labs:
            active_lab = not_started_labs[0]

        elif labs:
            active_lab = labs[0]

    average_score = get_row_value(
        stats_row,
        "average_score",
        0,
    )

    completed_labs = get_row_value(
        stats_row,
        "completed_labs",
        0,
    )

    total_attempts = get_row_value(
        stats_row,
        "total_attempts",
        0,
    )

    latest_score = get_row_value(
        stats_row,
        "latest_score",
        None,
    )

    dashboard_stats = {
        "average_score": (
            average_score
            if average_score is not None
            else 0
        ),
        "completed_labs": int(
            completed_labs
            or 0
        ),
        "total_attempts": int(
            total_attempts
            or 0
        ),
        "latest_score": (
            latest_score
            if latest_score is not None
            else "—"
        ),
    }

    return render_template(
        "common/index.html",
        is_landing=False,
        labs=labs,
        my_submissions=my_submissions,
        student=student,
        dashboard_stats=dashboard_stats,
        active_lab=active_lab,
    )

# =========================
# 11. Спільні сторінки
# =========================

def teacher_has_lab_overview_access(
    conn,
    teacher_username,
    lab,
) -> bool:
    """
    Перевіряє право викладача переглядати лабораторну роботу.

    Автор лабораторної роботи має повний доступ до її результатів.
    Інший викладач отримує доступ лише за наявності призначення
    на відповідну дисципліну хоча б для однієї навчальної групи.
    """
    teacher_username = str(
        teacher_username or ""
    ).strip()

    if not teacher_username:
        return False

    created_by = str(
        get_row_value(
            lab,
            "created_by",
            "",
        )
        or ""
    ).strip()

    if created_by == teacher_username:
        return True

    discipline = str(
        get_row_value(
            lab,
            "discipline",
            "",
        )
        or ""
    ).strip()

    if not discipline:
        return False

    access = conn.execute(
        """
        SELECT 1
        FROM teacher_subject_groups
        WHERE teacher_username = ?
          AND discipline = ?
        LIMIT 1
        """,
        (
            teacher_username,
            discipline,
        ),
    ).fetchone()

    return access is not None


def staff_has_full_lab_scope(
    role,
    username,
    lab,
) -> bool:
    """
    Визначає, чи може користувач бачити результати всіх студентів
    для лабораторної роботи без обмеження за навчальною групою.
    """
    if role == "admin":
        return True

    if role != "teacher":
        return False

    return (
        str(
            get_row_value(
                lab,
                "created_by",
                "",
            )
            or ""
        ).strip()
        == str(username or "").strip()
    )


@app.route("/lab/<int:lab_id>")
@login_required
def lab_detail(lab_id):
    """
    Відображає лабораторну роботу та пов'язані з нею результати.

    Студент бачить лише власну історію відправлень.
    Викладач бачить результати студентів тих навчальних груп,
    для яких він призначений на дисципліну, або всі результати,
    якщо є автором лабораторної роботи. Адміністратор має
    повний доступ до результатів лабораторної роботи.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    current_username = current_user["username"]
    current_role = current_user["role"]

    conn = get_db()

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        if not lab:
            abort(404)

        attempts_info = None
        attempts_count = None

        if current_role == "student":
            attempts_info = get_attempts_info(
                conn=conn,
                lab=lab,
                username=current_username,
            )

            submissions = conn.execute(
                """
                SELECT
                    submissions.*,
                    (
                        SELECT COUNT(*)
                        FROM extra_task_attempts
                        WHERE extra_task_attempts.submission_id =
                              submissions.id
                    ) AS extra_attempts_count
                FROM submissions
                WHERE lab_id = ?
                  AND username = ?
                ORDER BY
                    created_at DESC,
                    id DESC
                """,
                (
                    lab_id,
                    current_username,
                ),
            ).fetchall()

            student_results = []

            attempts_count = (
                attempts_info["used_attempts"]
                if attempts_info
                else 0
            )

        elif current_role in {
            "teacher",
            "admin",
        }:
            if (
                current_role == "teacher"
                and not teacher_has_lab_overview_access(
                    conn=conn,
                    teacher_username=current_username,
                    lab=lab,
                )
            ):
                flash(
                    "У вас немає доступу до цієї лабораторної роботи."
                )

                return redirect(
                    url_for("teacher_panel")
                )

            full_scope = staff_has_full_lab_scope(
                role=current_role,
                username=current_username,
                lab=lab,
            )

            discipline = str(
                get_row_value(
                    lab,
                    "discipline",
                    "",
                )
                or ""
            ).strip()

            staff_query_params = {
                "lab_id": lab_id,
                "system_error": "SYSTEM_ERROR",
                "full_scope": 1 if full_scope else 0,
                "teacher_username": current_username,
                "discipline": discipline,
            }

            # Детальний журнал зберігає всі відправлення, включно
            # із SYSTEM_ERROR. Обмеження за групами застосовується
            # до викладача, який не є автором лабораторної роботи.
            submissions = conn.execute(
                """
                SELECT
                    submissions.*,
                    users.full_name,
                    users.student_group,

                    (
                        SELECT MAX(s2.score)
                        FROM submissions AS s2
                        WHERE s2.username = submissions.username
                          AND s2.lab_id = submissions.lab_id
                          AND s2.status <> :system_error
                    ) AS best_score

                FROM submissions

                LEFT JOIN users
                    ON users.username = submissions.username

                WHERE submissions.lab_id = :lab_id

                  AND (
                        :full_scope = 1

                        OR EXISTS (
                            SELECT 1
                            FROM teacher_subject_groups AS tsg
                            WHERE tsg.teacher_username = :teacher_username
                              AND tsg.discipline = :discipline
                              AND tsg.student_group =
                                  COALESCE(users.student_group, '')
                        )
                  )

                ORDER BY
                    submissions.created_at DESC,
                    submissions.id DESC
                """,
                staff_query_params,
            ).fetchall()

            # Агрегована академічна статистика не враховує
            # SYSTEM_ERROR як навчальну спробу студента.
            student_results = conn.execute(
                """
                SELECT
                    submissions.username,

                    COALESCE(
                        users.full_name,
                        submissions.username
                    ) AS full_name,

                    COALESCE(
                        users.student_group,
                        ''
                    ) AS student_group,

                    COUNT(
                        CASE
                            WHEN submissions.status <> :system_error
                            THEN 1
                        END
                    ) AS attempts_count,

                    COALESCE(
                        MAX(
                            CASE
                                WHEN submissions.status <> :system_error
                                THEN submissions.score
                            END
                        ),
                        0
                    ) AS best_score,

                    (
                        SELECT s2.status
                        FROM submissions AS s2
                        WHERE s2.lab_id = submissions.lab_id
                          AND s2.username = submissions.username
                          AND s2.status <> :system_error
                        ORDER BY
                            s2.created_at DESC,
                            s2.id DESC
                        LIMIT 1
                    ) AS last_status,

                    (
                        SELECT s2.filename
                        FROM submissions AS s2
                        WHERE s2.lab_id = submissions.lab_id
                          AND s2.username = submissions.username
                          AND s2.status <> :system_error
                        ORDER BY
                            s2.created_at DESC,
                            s2.id DESC
                        LIMIT 1
                    ) AS last_filename,

                    (
                        SELECT s2.id
                        FROM submissions AS s2
                        WHERE s2.lab_id = submissions.lab_id
                          AND s2.username = submissions.username
                          AND s2.status <> :system_error
                        ORDER BY
                            s2.created_at DESC,
                            s2.id DESC
                        LIMIT 1
                    ) AS last_submission_id,

                    (
                        SELECT s2.created_at
                        FROM submissions AS s2
                        WHERE s2.lab_id = submissions.lab_id
                          AND s2.username = submissions.username
                          AND s2.status <> :system_error
                        ORDER BY
                            s2.created_at DESC,
                            s2.id DESC
                        LIMIT 1
                    ) AS last_created_at

                FROM submissions

                LEFT JOIN users
                    ON users.username = submissions.username

                WHERE submissions.lab_id = :lab_id

                  AND (
                        :full_scope = 1

                        OR EXISTS (
                            SELECT 1
                            FROM teacher_subject_groups AS tsg
                            WHERE tsg.teacher_username = :teacher_username
                              AND tsg.discipline = :discipline
                              AND tsg.student_group =
                                  COALESCE(users.student_group, '')
                        )
                  )

                GROUP BY
                    submissions.username,
                    users.full_name,
                    users.student_group

                ORDER BY
                    best_score DESC,
                    attempts_count DESC,
                    full_name ASC
                """,
                staff_query_params,
            ).fetchall()

        else:
            app.logger.warning(
                "Користувач %s має непідтримувану роль %s "
                "для перегляду лабораторної роботи %s.",
                current_username,
                current_role,
                lab_id,
            )

            abort(403)

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "лабораторної роботи %s для користувача %s.",
            lab_id,
            current_username,
        )

        flash(
            "Не вдалося завантажити лабораторну роботу "
            "через внутрішню помилку системи."
        )

        return redirect(
            get_default_redirect_for_role(
                current_role
            )
        )

    finally:
        conn.close()

    return render_template(
        "student/lab_detail.html",
        lab=lab,
        submissions=submissions,
        student_results=student_results,
        attempts_count=attempts_count,
        attempts_info=attempts_info,
    )


# ============================================================
# Доступ до файлів рішень та VCD-артефактів
# ============================================================

def get_submission_for_artifact_access(
    submission_id,
):
    """
    Повертає відправлення після перевірки прав доступу до його артефактів.

    Адміністратор має повний доступ, викладач — лише до доступних
    йому студентських відправлень, а студент — лише до власних.
    """
    current_user = get_current_session_user()

    if not current_user:
        return None, None

    current_username = current_user["username"]
    current_role = current_user["role"]

    conn = get_db()

    try:
        submission = conn.execute(
            """
            SELECT *
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()

        if not submission:
            abort(404)

        if current_role == "admin":
            allow = True

        elif current_role == "teacher":
            allow = teacher_can_access_submission(
                conn=conn,
                teacher_username=current_username,
                submission_id=submission_id,
            )

        elif current_role == "student":
            allow = (
                submission["username"]
                == current_username
            )

        else:
            allow = False

        if not allow:
            abort(403)

        return current_user, submission

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час перевірки доступу "
            "до артефактів відправлення %s.",
            submission_id,
        )

        abort(500)

    finally:
        conn.close()


@app.route("/download/<int:submission_id>")
@login_required
def download_submission(submission_id):
    """
    Завантажує збережений файл студентського рішення
    після перевірки ролі, власника та стану артефакту.
    """
    current_user, submission = get_submission_for_artifact_access(
        submission_id
    )

    if not current_user or not submission:
        return redirect(
            url_for("login")
        )

    current_role = current_user["role"]

    if normalize_binary_flag(
        get_row_value(
            submission,
            "file_deleted",
            0,
        )
    ):
        flash(
            "Файл цієї спроби недоступний."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    if (
        current_role == "student"
        and normalize_binary_flag(
            get_row_value(
                submission,
                "file_hidden_for_student",
                0,
            )
        )
    ):
        flash(
            "Файл цієї спроби приховано після повторного надсилання."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    filename = str(
        get_row_value(
            submission,
            "filename",
            "",
        )
        or ""
    ).strip()

    file_path = resolve_safe_storage_path(
        UPLOAD_DIR,
        filename,
    )

    # Ім'я файла з БД не використовується безпосередньо як шлях.
    # Перевірка гарантує, що артефакт залишається всередині UPLOAD_DIR.
    if (
        not filename
        or file_path is None
        or not os.path.isfile(file_path)
    ):
        app.logger.warning(
            "Файл рішення відправлення %s відсутній "
            "або має небезпечний шлях.",
            submission_id,
        )

        flash(
            "Файл цієї спроби відсутній на сервері."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    return send_from_directory(
        UPLOAD_DIR,
        filename,
        as_attachment=True,
    )


@app.route("/waveform/<int:submission_id>")
@login_required
def download_waveform(submission_id):
    """
    Завантажує VCD-артефакт відправлення після перевірки
    прав доступу та безпечності шляху до файла.
    """
    current_user, submission = get_submission_for_artifact_access(
        submission_id
    )

    if not current_user or not submission:
        return redirect(
            url_for("login")
        )

    waveform_filename = str(
        get_row_value(
            submission,
            "waveform_filename",
            "",
        )
        or ""
    ).strip()

    if not waveform_filename:
        flash(
            "Для цієї спроби часова діаграма недоступна."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    waveform_path = resolve_safe_storage_path(
        WAVEFORM_DIR,
        waveform_filename,
    )

    # VCD створюється лише для дозволеного етапу перевірки,
    # а фізичний шлях додатково обмежується каталогом WAVEFORM_DIR.
    if (
        waveform_path is None
        or not os.path.isfile(waveform_path)
    ):
        app.logger.warning(
            "VCD-файл відправлення %s відсутній "
            "або має небезпечний шлях.",
            submission_id,
        )

        flash(
            "Файл часової діаграми відсутній на сервері."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    return send_from_directory(
        WAVEFORM_DIR,
        waveform_filename,
        as_attachment=True,
    )


# ============================================================
# Карта компетентностей студента
# ============================================================

COMPETENCY_CATALOG = {
    "combinational_logic": {
        "title": "Комбінаційна логіка",
        "description": (
            "Мультиплексори, суматори, логічні вирази, "
            "assign та always @(*)."
        ),
    },
    "testbench_work": {
        "title": "Робота з testbench",
        "description": (
            "Розуміння перевірочного сценарію, відповідність "
            "імені модуля та його портів."
        ),
    },
    "sequential_logic": {
        "title": "Послідовнісна логіка",
        "description": (
            "Регістри, лічильники та зміна стану "
            "за тактовим сигналом."
        ),
    },
    "fsm": {
        "title": "FSM",
        "description": (
            "Скінченні автомати, стани, переходи "
            "та обробка вхідних умов."
        ),
    },
    "reset_clock": {
        "title": "Reset/clock",
        "description": (
            "Коректна робота зі скиданням, clock, "
            "posedge/negedge та початковими станами."
        ),
    },
    "hdl_syntax_structure": {
        "title": "Структура HDL-модуля",
        "description": (
            "Синтаксис Verilog, module/endmodule, "
            "input/output та wire/reg."
        ),
    },
}


TOPIC_COMPETENCY_MAP = {
    "mux": (
        "combinational_logic",
        "testbench_work",
    ),
    "adder": (
        "combinational_logic",
        "testbench_work",
    ),
    "counter": (
        "sequential_logic",
        "reset_clock",
        "testbench_work",
    ),
    "register": (
        "sequential_logic",
        "reset_clock",
        "testbench_work",
    ),
    "fsm": (
        "fsm",
        "sequential_logic",
        "reset_clock",
        "testbench_work",
    ),
    "general": (
        "hdl_syntax_structure",
        "testbench_work",
    ),
}


def get_competency_catalog() -> dict:
    """
    Повертає каталог компетентностей, що використовується
    для формування студентської карти навчального прогресу.
    """
    return {
        competency_slug: dict(
            competency_data
        )
        for (
            competency_slug,
            competency_data,
        ) in COMPETENCY_CATALOG.items()
    }


def normalize_topic_for_competencies(
    topic,
    title="",
) -> str:
    """
    Нормалізує тему лабораторної роботи для карти компетентностей.

    Використовується спільний механізм визначення тем,
    щоб аналітика, діагностика та адаптивний модуль
    не мали різних наборів правил.
    """
    normalized_topic = str(
        topic or ""
    ).strip().lower()

    if normalized_topic in TOPIC_COMPETENCY_MAP:
        return normalized_topic

    return detect_normalized_lab_topic(
        topic,
        title,
    )


def get_competencies_for_topic(
    topic,
) -> list[str]:
    """
    Повертає компетентності, пов'язані з нормалізованою
    темою лабораторної роботи.
    """
    normalized_topic = normalize_topic_for_competencies(
        topic
    )

    competencies = TOPIC_COMPETENCY_MAP.get(
        normalized_topic,
        TOPIC_COMPETENCY_MAP["general"],
    )

    return list(
        competencies
    )


# ============================================================
# Розрахунок карти компетентностей студента
# ============================================================

COMPETENCY_ATTEMPT_PENALTY_PER_RETRY = 4
COMPETENCY_MAX_ATTEMPT_PENALTY = 15

COMPETENCY_ERROR_PENALTY_POINTS = 6
COMPETENCY_MAX_ERROR_PENALTY = 30

COMPETENCY_HIGH_LEVEL_THRESHOLD = 85
COMPETENCY_GOOD_LEVEL_THRESHOLD = 70
COMPETENCY_BASIC_LEVEL_THRESHOLD = 50

COMPETENCY_IGNORED_STATUSES = frozenset({
    "SYSTEM_ERROR",
})

COMPETENCY_IGNORED_ERROR_TYPES = frozenset({
    "",
    "NO_ERROR",
    "SYSTEM_ERROR",
})


def get_competencies_for_error(
    error_type,
    topic="general",
) -> list[str]:
    """
    Визначає компетентності, пов'язані з категорією помилки.

    Для помилок, зміст яких залежить від теми лабораторної роботи,
    використовується нормалізована тема. Системні та невідомі
    помилки не створюють штучного негативного впливу на компетентності.
    """
    normalized_error_type = str(
        error_type or ""
    ).strip().upper()

    normalized_topic = normalize_topic_for_competencies(
        topic
    )

    if normalized_error_type in COMPETENCY_IGNORED_ERROR_TYPES:
        return []

    direct_mapping = {
        "MODULE_NAME_MISMATCH": [
            "testbench_work",
            "hdl_syntax_structure",
        ],
        "PORT_MISMATCH": [
            "testbench_work",
            "hdl_syntax_structure",
        ],
        "COMPILE_ERROR": [
            "hdl_syntax_structure",
        ],
        "CONTROL_SIGNAL_ERROR": [
            "combinational_logic",
        ],
        "WRONG_COMBINATIONAL_LOGIC": [
            "combinational_logic",
        ],
        "RESET_CLOCK_ERROR": [
            "reset_clock",
            "sequential_logic",
        ],
        "SIMULATION_ERROR": [
            "testbench_work",
        ],
    }

    if normalized_error_type in direct_mapping:
        return list(
            direct_mapping[
                normalized_error_type
            ]
        )

    # Неповний опис умов у FSM впливає і на компетентність
    # моделювання станів, тоді як для інших тем це насамперед
    # проблема комбінаційної логіки.
    if normalized_error_type == "INCOMPLETE_CONDITION":
        if normalized_topic == "fsm":
            return [
                "fsm",
                "combinational_logic",
            ]

        return [
            "combinational_logic",
        ]

    # Гранична помилка інтерпретується в контексті типу схеми,
    # а не одночасно як проблема всіх видів цифрової логіки.
    if normalized_error_type == "BOUNDARY_TEST_FAILED":
        if normalized_topic in {
            "counter",
            "register",
        }:
            return [
                "sequential_logic",
            ]

        if normalized_topic == "fsm":
            return [
                "fsm",
                "sequential_logic",
            ]

        return [
            "combinational_logic",
        ]

    # Загальна функціональна помилка пов'язується з предметними
    # компетентностями конкретної лабораторної роботи.
    if normalized_error_type in {
        "FUNCTIONAL_ERROR",
        "HIDDEN_TEST_FAILED",
    }:
        topic_mapping = {
            "mux": [
                "combinational_logic",
            ],
            "adder": [
                "combinational_logic",
            ],
            "counter": [
                "sequential_logic",
            ],
            "register": [
                "sequential_logic",
            ],
            "fsm": [
                "fsm",
                "sequential_logic",
            ],
        }

        return list(
            topic_mapping.get(
                normalized_topic,
                [],
            )
        )

    # Невідома категорія не повинна автоматично знижувати
    # testbench_work або іншу компетентність без достатніх підстав.
    return []


def get_competency_level_title(
    score,
) -> str:
    """Повертає текстову інтерпретацію рівня компетентності."""
    if score is None:
        return "Недостатньо даних"

    if score >= COMPETENCY_HIGH_LEVEL_THRESHOLD:
        return "Високий рівень"

    if score >= COMPETENCY_GOOD_LEVEL_THRESHOLD:
        return "Добрий рівень"

    if score >= COMPETENCY_BASIC_LEVEL_THRESHOLD:
        return "Базовий рівень"

    return "Проблемна зона"


def get_competency_badge_class(
    score,
) -> str:
    """
    Повертає CSS-клас Bootstrap для візуального
    представлення рівня компетентності.
    """
    if score is None:
        return "bg-secondary"

    if score >= COMPETENCY_HIGH_LEVEL_THRESHOLD:
        return "bg-success"

    if score >= COMPETENCY_GOOD_LEVEL_THRESHOLD:
        return "bg-primary"

    if score >= COMPETENCY_BASIC_LEVEL_THRESHOLD:
        return "bg-warning text-dark"

    return "bg-danger"


def append_frequent_error_context(
    recommendation,
    frequent_errors,
) -> str:
    """
    Доповнює рекомендацію інформацією про найчастішу
    зафіксовану помилку студента.
    """
    if not frequent_errors:
        return recommendation

    first_error = frequent_errors[0]

    title = str(
        first_error.get(
            "title",
            "",
        )
        or ""
    ).strip()

    try:
        count = int(
            first_error.get(
                "count",
                0,
            )
            or 0
        )
    except (TypeError, ValueError, OverflowError):
        count = 0

    if not title or count <= 0:
        return recommendation

    return (
        f"{recommendation} "
        f"Найчастіше зафіксована помилка: "
        f"«{title}» (кількість: {count})."
    )


def build_competency_recommendation(
    competency_id,
    score,
    frequent_errors,
) -> str:
    """
    Формує навчальну рекомендацію відповідно до рівня
    конкретної компетентності та історії типових помилок.
    """
    if score is None:
        return (
            "Поки недостатньо даних. Виконайте більше "
            "лабораторних робіт, пов'язаних із цією компетентністю."
        )

    if score >= COMPETENCY_HIGH_LEVEL_THRESHOLD:
        return (
            "Компетентність сформована на високому рівні. "
            "Можна переходити до складніших завдань."
        )

    recommendations = {
        "combinational_logic": (
            "Повторіть таблиці істинності, умовні конструкції, "
            "оператор assign та принцип повного опису "
            "всіх комбінацій вхідних сигналів."
        ),
        "testbench_work": (
            "Перевірте принципи взаємодії HDL-модуля з testbench, "
            "відповідність імені модуля, портів та очікуваного "
            "формату результатів."
        ),
        "sequential_logic": (
            "Повторіть принципи роботи регістрів і лічильників, "
            "а також зміну стану за активним фронтом "
            "тактового сигналу."
        ),
        "fsm": (
            "Повторіть опис станів, переходів, next_state "
            "та обробку всіх передбачених вхідних умов."
        ),
        "reset_clock": (
            "Повторіть організацію always-блоків із posedge/negedge "
            "та коректну обробку сигналів reset/rst."
        ),
        "hdl_syntax_structure": (
            "Повторіть структуру Verilog-модуля: module, "
            "input/output, wire/reg, assign, always та endmodule."
        ),
    }

    recommendation = recommendations.get(
        competency_id,
        (
            "Проаналізуйте помилки в останніх спробах "
            "та повторіть відповідний розділ навчального матеріалу."
        ),
    )

    return append_frequent_error_context(
        recommendation,
        frequent_errors,
    )


def normalize_competency_numeric_score(
    value,
) -> int:
    """
    Нормалізує числовий бал відправлення до діапазону 0–100.
    """
    try:
        numeric_value = float(
            value or 0
        )
    except (TypeError, ValueError, OverflowError):
        numeric_value = 0.0

    if not math.isfinite(
        numeric_value
    ):
        numeric_value = 0.0

    return round(
        max(
            0.0,
            min(
                100.0,
                numeric_value,
            ),
        )
    )


def normalize_attempt_number(
    value,
) -> int:
    """Нормалізує номер спроби до додатного цілого значення."""
    try:
        attempt_number = int(
            value or 1
        )
    except (TypeError, ValueError, OverflowError):
        attempt_number = 1

    return max(
        1,
        attempt_number,
    )


def calculate_student_competency_map(
    username,
) -> dict:
    """
    Формує карту HDL-компетентностей студента за історією відправлень.

    Для кожної лабораторної роботи враховується найкращий результат
    і кількість навчальних спроб. Пов'язані з помилками компетентності
    отримують додатковий обмежений штраф. SYSTEM_ERROR не використовується
    як доказ рівня знань студента.

    Карта охоплює лише HDL-лабораторні роботи, оскільки поточний
    каталог компетентностей описує саме цифрове проєктування.
    """
    normalized_username = str(
        username or ""
    ).strip()

    if not normalized_username:
        return {
            "competencies": [],
            "weak_competencies": [],
            "strong_competencies": [],
            "attempted_labs_count": 0,
            "completed_labs_count": 0,
            "total_attempts_count": 0,
            "average_competency_score": None,
        }

    conn = get_db()

    try:
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
                labs.discipline AS lab_discipline,
                labs.checker_type AS lab_checker_type

            FROM submissions

            JOIN labs
                ON submissions.lab_id = labs.id

            WHERE submissions.username = ?

              AND submissions.status <> 'SYSTEM_ERROR'

              AND COALESCE(
                    NULLIF(labs.checker_type, ''),
                    'hdl_testbench'
                  ) = 'hdl_testbench'

            ORDER BY
                submissions.lab_id ASC,
                submissions.attempt_number ASC,
                submissions.id ASC
            """,
            (normalized_username,),
        ).fetchall()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час формування "
            "карти компетентностей студента %s.",
            normalized_username,
        )

        raise

    finally:
        conn.close()

    catalog = get_competency_catalog()

    competency_data = {}

    for competency_id, item in catalog.items():
        competency_data[competency_id] = {
            "id": competency_id,
            "title": item["title"],
            "description": item["description"],
            "values": [],
            "error_penalty_points": 0,
            "errors": {},
            "labs": [],
        }

    # Відправлення групуються за лабораторними роботами,
    # оскільки одна лабораторна формує одне базове свідчення
    # рівня відповідних компетентностей.
    lab_attempts = {}

    for row in rows:
        row_dict = dict(
            row
        )

        lab_id = row_dict["lab_id"]

        lab_attempts.setdefault(
            lab_id,
            [],
        ).append(
            row_dict
        )

    completed_labs_count = 0

    for lab_id, attempts in lab_attempts.items():
        attempts.sort(
            key=lambda item: (
                normalize_attempt_number(
                    item.get(
                        "attempt_number"
                    )
                ),
                int(
                    item.get(
                        "id"
                    )
                    or 0
                ),
            )
        )

        first_attempt = attempts[0]
        last_attempt = attempts[-1]

        normalized_scores = [
            normalize_competency_numeric_score(
                item.get(
                    "score"
                )
            )
            for item in attempts
        ]

        best_score = max(
            normalized_scores,
            default=0,
        )

        attempts_count = len(
            attempts
        )

        topic = normalize_topic_for_competencies(
            first_attempt.get(
                "lab_topic"
            ),
            first_attempt.get(
                "lab_title"
            ),
        )

        topic_competencies = get_competencies_for_topic(
            topic
        )

        # Повторні навчальні спроби знижують базову оцінку
        # компетентності, але величина штрафу обмежена,
        # щоб кількість спроб не могла повністю перекрити результат.
        attempt_penalty = min(
            COMPETENCY_MAX_ATTEMPT_PENALTY,
            max(
                0,
                attempts_count - 1,
            )
            * COMPETENCY_ATTEMPT_PENALTY_PER_RETRY,
        )

        base_value = max(
            0,
            best_score - attempt_penalty,
        )

        if any(
            str(
                attempt.get(
                    "status",
                    "",
                )
                or ""
            ).strip().upper()
            == "PASSED"
            for attempt in attempts
        ):
            completed_labs_count += 1

        for competency_id in topic_competencies:
            if competency_id not in competency_data:
                continue

            competency_data[
                competency_id
            ]["values"].append(
                base_value
            )

            competency_data[
                competency_id
            ]["labs"].append({
                "lab_id": lab_id,
                "lab_title": first_attempt.get(
                    "lab_title",
                    "",
                ),
                "topic": topic,
                "best_score": best_score,
                "attempts_count": attempts_count,
                "last_status": last_attempt.get(
                    "status",
                    "",
                ),
            })

        # Історія помилок використовується як додаткове свідчення,
        # але системні відмови та NO_ERROR не впливають на карту.
        for attempt in attempts:
            error_type = str(
                attempt.get(
                    "error_type",
                    "",
                )
                or ""
            ).strip().upper()

            if error_type in COMPETENCY_IGNORED_ERROR_TYPES:
                continue

            error_title = str(
                attempt.get(
                    "error_title",
                    "",
                )
                or error_type
            ).strip()

            related_competencies = get_competencies_for_error(
                error_type=error_type,
                topic=topic,
            )

            for competency_id in related_competencies:
                if competency_id not in competency_data:
                    continue

                competency_item = competency_data[
                    competency_id
                ]

                # Якщо компетентність не була безпосередньо пов'язана
                # з темою лабораторної, сама зафіксована помилка
                # створює обережне нейтрально-низьке evidence-значення.
                if not competency_item["values"]:
                    competency_item["values"].append(
                        50
                    )

                competency_item[
                    "error_penalty_points"
                ] += COMPETENCY_ERROR_PENALTY_POINTS

                competency_item[
                    "errors"
                ].setdefault(
                    error_title,
                    0,
                )

                competency_item[
                    "errors"
                ][error_title] += 1

    competency_rows = []

    for competency_id, item in competency_data.items():
        values = item[
            "values"
        ]

        errors_sorted = sorted(
            item["errors"].items(),
            key=lambda pair: (
                -pair[1],
                pair[0],
            ),
        )

        frequent_errors = [
            {
                "title": title,
                "count": count,
            }
            for title, count in errors_sorted[:3]
        ]

        if values:
            average_value = (
                sum(values)
                / len(values)
            )

            # Штраф за помилки нормалізується кількістю evidence-значень.
            # Це не дозволяє абсолютній кількості старих помилок
            # непропорційно знижувати компетентність при накопиченні
            # великої історії лабораторних робіт.
            normalized_error_penalty = (
                item["error_penalty_points"]
                / max(
                    1,
                    len(values),
                )
            )

            normalized_error_penalty = min(
                COMPETENCY_MAX_ERROR_PENALTY,
                normalized_error_penalty,
            )

            score = round(
                max(
                    0,
                    min(
                        100,
                        average_value
                        - normalized_error_penalty,
                    ),
                )
            )

        else:
            score = None

        competency_rows.append({
            "id": competency_id,
            "title": item["title"],
            "description": item["description"],
            "score": score,
            "level_title": get_competency_level_title(
                score
            ),
            "badge_class": get_competency_badge_class(
                score
            ),
            "recommendation": build_competency_recommendation(
                competency_id=competency_id,
                score=score,
                frequent_errors=frequent_errors,
            ),
            "frequent_errors": frequent_errors,
            "labs": item["labs"][:5],
        })

    # Спочатку відображаються компетентності, що потребують уваги,
    # після них — сильні сторони та компетентності без достатніх даних.
    competency_rows.sort(
        key=lambda item: (
            item["score"] is None,
            (
                item["score"]
                if item["score"] is not None
                else 101
            ),
        )
    )

    weak_competencies = [
        item
        for item in competency_rows
        if (
            item["score"] is not None
            and item["score"]
            < COMPETENCY_GOOD_LEVEL_THRESHOLD
        )
    ]

    strong_competencies = [
        item
        for item in competency_rows
        if (
            item["score"] is not None
            and item["score"]
            >= COMPETENCY_HIGH_LEVEL_THRESHOLD
        )
    ]

    scored_competencies = [
        item["score"]
        for item in competency_rows
        if item["score"] is not None
    ]

    if scored_competencies:
        average_competency_score = round(
            sum(
                scored_competencies
            )
            / len(
                scored_competencies
            ),
            1,
        )
    else:
        average_competency_score = None

    return {
        "competencies": competency_rows,
        "weak_competencies": weak_competencies,
        "strong_competencies": strong_competencies,
        "attempted_labs_count": len(
            lab_attempts
        ),
        "completed_labs_count": completed_labs_count,
        "total_attempts_count": len(
            rows
        ),
        "average_competency_score": average_competency_score,
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

# ============================================================
# Резервна навчальна траєкторія на основі відкритих ресурсів
# ============================================================

DIRECT_RESOURCE_ERROR_TOPIC_MAP = {
    "MODULE_NAME_MISMATCH": "hdl_syntax_structure",
    "PORT_MISMATCH": "hdl_syntax_structure",
    "COMPILE_ERROR": "hdl_syntax_structure",

    "SIMULATION_ERROR": "testbench_work",

    "CONTROL_SIGNAL_ERROR": "combinational_logic",
    "WRONG_COMBINATIONAL_LOGIC": "combinational_logic",
    "LATCH_RISK": "combinational_logic",

    "RESET_CLOCK_ERROR": "reset_clock",

    "FSM_STATE_ERROR": "fsm",
    "FSM_TRANSITION_ERROR": "fsm",

    "DELAY_IN_DESIGN": "synthesis",
    "INITIAL_IN_DESIGN": "synthesis",
    "NON_SYNTHESIZABLE_CONSTRUCT": "synthesis",
    "SYNTHESIS_ERROR": "synthesis",

    "WIDTH_MISMATCH": "hdl_syntax_structure",
    "UNDRIVEN_SIGNAL": "hdl_syntax_structure",
    "UNUSED_SIGNAL": "hdl_syntax_structure",
}


FALLBACK_LEARNING_PATH_CONTENT = {
    "reset_clock": {
        "topic_title": "Reset/clock і послідовнісна логіка",
        "mini_theory": (
            "Помилка пов'язана з оновленням стану цифрової схеми "
            "в часі. Перевірте always-блоки, активний фронт clock, "
            "обробку reset та використання неблокувальних присвоєнь <=."
        ),
        "what_to_repeat": [
            "always @(posedge clk)",
            "синхронний та асинхронний reset",
            "неблокувальне присвоєння <=",
            "регістри та лічильники",
        ],
        "control_question": (
            "Чим синхронний reset відрізняється від асинхронного reset?"
        ),
        "next_topic": "Лічильники та FSM",
    },

    "sequential_logic": {
        "topic_title": "Послідовнісна логіка Verilog",
        "mini_theory": (
            "У послідовнісних схемах поточний результат залежить "
            "не лише від входів, а й від попереднього стану. "
            "Особливу увагу слід приділити clock, регістрам, "
            "неблокувальним присвоєнням та умовам оновлення стану."
        ),
        "what_to_repeat": [
            "регістри",
            "лічильники",
            "always @(posedge clk)",
            "неблокувальне присвоєння <=",
            "збереження та оновлення стану",
        ],
        "control_question": (
            "Чому у послідовнісній логіці зазвичай використовують "
            "неблокувальні присвоєння?"
        ),
        "next_topic": "Reset/clock та FSM",
    },

    "fsm": {
        "topic_title": "Скінченні автомати FSM",
        "mini_theory": (
            "Помилка може бути пов'язана з описом станів "
            "і переходів. Перевірте state, next_state, case "
            "за станами та обробку всіх передбачених "
            "комбінацій вхідних умов."
        ),
        "what_to_repeat": [
            "state та next_state",
            "case за станами",
            "default-перехід",
            "умови переходів між станами",
            "обробка всіх вхідних варіантів",
        ],
        "control_question": (
            "Яку роль виконує default-гілка під час опису FSM?"
        ),
        "next_topic": "Складніші керувальні автомати",
    },

    "testbench_work": {
        "topic_title": "Взаємодія HDL-модуля з testbench",
        "mini_theory": (
            "Автоматизована перевірка залежить не лише від логіки "
            "модуля, а й від коректної взаємодії рішення з testbench. "
            "Необхідно враховувати очікуваний інтерфейс, порядок "
            "сигналів та результати симуляції."
        ),
        "what_to_repeat": [
            "принцип роботи testbench",
            "вхідні та вихідні сигнали модуля",
            "аналіз результатів симуляції",
            "Icarus Verilog та VVP",
        ],
        "control_question": (
            "Яку інформацію testbench використовує для перевірки "
            "поведінки HDL-модуля?"
        ),
        "next_topic": "Налагодження HDL-коду за VCD",
    },

    "hdl_syntax_structure": {
        "topic_title": "Структура та синтаксис Verilog-модуля",
        "mini_theory": (
            "Навіть правильна функціональна логіка не може бути "
            "перевірена, якщо модуль не компілюється або його "
            "інтерфейс не відповідає testbench. Перевірте ім'я "
            "module, оголошення input/output, ширину сигналів "
            "та завершення конструкції endmodule."
        ),
        "what_to_repeat": [
            "module та endmodule",
            "input/output",
            "імена та ширина портів",
            "wire/reg або відповідні типи SystemVerilog",
            "аналіз повідомлень компілятора",
        ],
        "control_question": (
            "Чому правильна логіка модуля не пройде перевірку, "
            "якщо його ім'я або список портів не відповідає testbench?"
        ),
        "next_topic": "Налагодження HDL-коду за результатами симуляції",
    },

    "synthesis": {
        "topic_title": "Синтезовність HDL-коду",
        "mini_theory": (
            "Синтезовність означає можливість перетворення HDL-опису "
            "на апаратну структуру. Деякі конструкції допустимі "
            "під час симуляції або в testbench, але не повинні "
            "використовуватися в синтезовному design-коді."
        ),
        "what_to_repeat": [
            "синтезовний Verilog",
            "відмінність між testbench і design-кодом",
            "затримки #",
            "синтез у Yosys",
            "несинтезовні конструкції",
        ],
        "control_question": (
            "Чому конструкція із затримкою #10 може використовуватися "
            "в testbench, але не повинна визначати апаратну поведінку "
            "синтезовного модуля?"
        ),
        "next_topic": "Аналіз та оптимізація HDL після синтезу",
    },

    "combinational_logic": {
        "topic_title": "Комбінаційна логіка Verilog",
        "mini_theory": (
            "У комбінаційній схемі вихід визначається поточними "
            "значеннями вхідних сигналів. Важливо коректно описати "
            "всі передбачені комбінації входів і не залишати "
            "невизначених гілок логіки."
        ),
        "what_to_repeat": [
            "таблиці істинності",
            "assign та тернарний оператор",
            "if/else",
            "case/default",
            "мультиплексори та суматори",
        ],
        "control_question": (
            "Чому в комбінаційній логіці важливо визначити "
            "значення виходу для всіх можливих гілок умов?"
        ),
        "next_topic": "Послідовнісна логіка",
    },

    "general": {
        "topic_title": "Основи HDL-проєктування",
        "mini_theory": (
            "Для подальшого виправлення рішення варто послідовно "
            "перевірити структуру HDL-модуля, відповідність його "
            "інтерфейсу testbench та функціональну поведінку "
            "на відкритих тестах."
        ),
        "what_to_repeat": [
            "структура Verilog-модуля",
            "input/output",
            "комбінаційна та послідовнісна логіка",
            "принцип роботи testbench",
            "аналіз результатів симуляції",
        ],
        "control_question": (
            "Які етапи доцільно перевірити перед повторним "
            "надсиланням HDL-рішення?"
        ),
        "next_topic": "Базові практичні завдання з Verilog",
    },
}


def detect_direct_resource_topic(
    context,
) -> str:
    """
    Визначає категорію відкритих навчальних ресурсів
    за типом помилки та тематичним контекстом студента.

    Класифікована помилка має вищий пріоритет за пошуковий
    topic_key. Невідомі та системні категорії не відносяться
    автоматично до комбінаційної логіки.
    """
    if not isinstance(
        context,
        dict,
    ):
        context = {}

    topic_key = str(
        context.get(
            "topic_key",
            "",
        )
        or ""
    ).strip().lower()

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    error_type = str(
        main_error.get(
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    if error_type in {
        "",
        "NO_ERROR",
        "SYSTEM_ERROR",
    }:
        error_type = ""

    direct_topic = DIRECT_RESOURCE_ERROR_TOPIC_MAP.get(
        error_type
    )

    if direct_topic:
        return direct_topic

    # Для помилок, значення яких залежить від типу цифрової схеми,
    # категорія ресурсів уточнюється за поточною тематикою.
    if error_type == "INCOMPLETE_CONDITION":
        if (
            "fsm" in topic_key
            or "state" in topic_key
        ):
            return "fsm"

        return "combinational_logic"

    if error_type == "BOUNDARY_TEST_FAILED":
        if (
            "fsm" in topic_key
            or "state" in topic_key
        ):
            return "fsm"

        if any(
            keyword in topic_key
            for keyword in (
                "counter",
                "register",
                "sequential",
                "clock",
            )
        ):
            return "sequential_logic"

        return "combinational_logic"

    # Legacy-категорія hidden test не розкриває зміст прихованого
    # тесту, а лише використовує загальну тему лабораторної роботи.
    if error_type == "HIDDEN_TEST_FAILED":
        if (
            "fsm" in topic_key
            or "state" in topic_key
        ):
            return "fsm"

        if any(
            keyword in topic_key
            for keyword in (
                "counter",
                "register",
                "sequential",
            )
        ):
            return "sequential_logic"

        if any(
            keyword in topic_key
            for keyword in (
                "mux",
                "adder",
                "combinational",
            )
        ):
            return "combinational_logic"

        return "general"

    if (
        "reset" in topic_key
        or "clock" in topic_key
    ):
        return "reset_clock"

    if (
        "fsm" in topic_key
        or "state" in topic_key
    ):
        return "fsm"

    if any(
        keyword in topic_key
        for keyword in (
            "counter",
            "register",
            "sequential",
        )
    ):
        return "sequential_logic"

    if (
        "yosys" in topic_key
        or "synthesis" in topic_key
        or "synthesizable" in topic_key
    ):
        return "synthesis"

    if any(
        keyword in topic_key
        for keyword in (
            "testbench",
            "simulation",
            "vvp",
        )
    ):
        return "testbench_work"

    if any(
        keyword in topic_key
        for keyword in (
            "module",
            "port",
            "syntax",
            "compile",
            "icarus",
        )
    ):
        return "hdl_syntax_structure"

    if any(
        keyword in topic_key
        for keyword in (
            "mux",
            "multiplexer",
            "adder",
            "carry",
            "combinational",
        )
    ):
        return "combinational_logic"

    return "general"


def build_open_search_fallback_learning_path(
    context,
    reason="",
) -> dict:
    """
    Формує резервну навчальну траєкторію без залежності
    від зовнішньої генеративної моделі.

    Траєкторія використовує детерміновані навчальні пояснення
    та перевірений статичний каталог відкритих ресурсів.
    Внутрішня причина переходу до fallback-режиму не передається
    користувачу як необроблений технічний текст.
    """
    if not isinstance(
        context,
        dict,
    ):
        context = {}

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    error_type = str(
        main_error.get(
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    error_title = str(
        main_error.get(
            "error_title",
            "",
        )
        or error_type
    ).strip()

    topic_slug = detect_direct_resource_topic(
        context
    )

    path_content = FALLBACK_LEARNING_PATH_CONTENT.get(
        topic_slug,
        FALLBACK_LEARNING_PATH_CONTENT["general"],
    )

    topic_title = path_content[
        "topic_title"
    ]

    if error_title:
        summary = (
            f"За результатами аналізу помилки «{error_title}» "
            f"сформовано резервну навчальну траєкторію. "
            f"Рекомендована тема для повторення: «{topic_title}»."
        )
    else:
        summary = (
            "Сформовано резервну навчальну траєкторію "
            f"за темою «{topic_title}»."
        )

    direct_resources = get_direct_learning_resources(
        topic_slug
    )

    lectures = list(
        direct_resources.get(
            "lectures",
            [],
        )
    )

    articles = list(
        direct_resources.get(
            "articles",
            [],
        )
    )

    practice = list(
        direct_resources.get(
            "practice",
            [],
        )
    )

    videos = list(
        direct_resources.get(
            "videos",
            [],
        )
    )

    # Технічна причина fallback-режиму зберігається лише в журналі.
    # Це запобігає витоку деталей API, винятків або конфігурації
    # зовнішнього ШІ-сервісу до студентського інтерфейсу.
    normalized_reason = str(
        reason or ""
    ).strip()

    if normalized_reason:
        app.logger.info(
            "Використано резервну навчальну траєкторію. Причина: %s",
            normalized_reason,
        )

    return {
        "status": "FREE_DIRECT_LINKS",
        "summary": summary,
        "topic_title": topic_title,
        "mini_theory": path_content[
            "mini_theory"
        ],
        "what_to_repeat": list(
            path_content[
                "what_to_repeat"
            ]
        ),
        "lectures": lectures,
        "articles": articles,
        "practice": practice,
        "videos": videos,
        "control_question": path_content[
            "control_question"
        ],
        "next_topic": path_content[
            "next_topic"
        ],
        "ai_note": (
            "Використовується резервний режим "
            "із прямими відкритими навчальними ресурсами."
        ),
        "resource_topic": topic_slug,
        "from_cache": False,
        "context": context,
    }


# ============================================================
# Генерація та кешування персоналізованої навчальної траєкторії
# ============================================================

LEARNING_PATH_ALLOWED_MODES = frozenset({
    "openai",
    "direct",
})

LEARNING_PATH_MAX_WEB_RESOURCES_PER_GROUP = 5

LEARNING_PATH_RESOURCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {
            "type": "string",
        },
        "url": {
            "type": "string",
        },
        "description": {
            "type": "string",
        },
        "why_useful": {
            "type": "string",
        },
    },
    "required": [
        "title",
        "url",
        "description",
        "why_useful",
    ],
}


LEARNING_PATH_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "OK",
            ],
        },
        "summary": {
            "type": "string",
        },
        "topic_title": {
            "type": "string",
        },
        "mini_theory": {
            "type": "string",
        },
        "what_to_repeat": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "lectures": {
            "type": "array",
            "items": LEARNING_PATH_RESOURCE_SCHEMA,
        },
        "articles": {
            "type": "array",
            "items": LEARNING_PATH_RESOURCE_SCHEMA,
        },
        "practice": {
            "type": "array",
            "items": LEARNING_PATH_RESOURCE_SCHEMA,
        },
        "videos": {
            "type": "array",
            "items": LEARNING_PATH_RESOURCE_SCHEMA,
        },
        "control_question": {
            "type": "string",
        },
        "next_topic": {
            "type": "string",
        },
        "ai_note": {
            "type": "string",
        },
    },
    "required": [
        "status",
        "summary",
        "topic_title",
        "mini_theory",
        "what_to_repeat",
        "lectures",
        "articles",
        "practice",
        "videos",
        "control_question",
        "next_topic",
        "ai_note",
    ],
}


OPENAI_LEARNING_PATH_SYSTEM_PROMPT = """
Ти є ШІ-наставником з FPGA-проєктування та Verilog HDL.

Твоє завдання:
1. Проаналізувати наданий знеособлений навчальний контекст.
2. Обов'язково виконати web search для пошуку актуальних відкритих
   навчальних матеріалів за визначеною проблемною темою.
3. Сформувати коротку індивідуальну навчальну траєкторію.
4. Підібрати лекційні матеріали, статті, практичні завдання та відео.

Вимоги:
- використовуй лише URL ресурсів, які реально знайдено під час web search;
- не вигадуй назви сторінок або URL;
- надавай перевагу відкритим освітнім та технічним джерелам:
  HDLBits, Nandland, Project F, документації Yosys,
  університетським матеріалам та якісним навчальним відео;
- не рекомендуй випадкові рекламні або нерелевантні сторінки;
- не намагайся відновити hidden testbench або приховані тестові дані;
- не додавай персональні дані студента;
- пояснення для студента формуй українською мовою;
- назви технологій, інструментів, HDL-конструкцій та англомовні
  назви джерел залишай в оригінальному вигляді;
- mini_theory має містити загальне навчальне пояснення,
  а не готове HDL-рішення лабораторної роботи;
- контрольне питання повинно перевіряти розуміння теми,
  але не розкривати готову відповідь на поточне завдання.
""".strip()


def build_openai_learning_context(
    context,
) -> dict:
    """
    Формує мінімальний діагностичний контекст для зовнішнього ШІ-сервісу.

    До зовнішнього запиту не передаються username, HDL-код,
    hidden output, testbench, raw output або інші дані,
    які не потрібні для побудови навчальної траєкторії.
    """
    if not isinstance(
        context,
        dict,
    ):
        context = {}

    current_lab = context.get(
        "current_lab"
    )

    if not isinstance(
        current_lab,
        dict,
    ):
        current_lab = {}

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    repeated_errors = context.get(
        "repeated_errors",
        [],
    )

    if not isinstance(
        repeated_errors,
        list,
    ):
        repeated_errors = []

    recent_attempts = context.get(
        "recent_attempts",
        [],
    )

    if not isinstance(
        recent_attempts,
        list,
    ):
        recent_attempts = []

    return {
        "topic_key": str(
            context.get(
                "topic_key",
                "",
            )
            or ""
        ),
        "current_lab": {
            "title": str(
                current_lab.get(
                    "title",
                    "",
                )
                or ""
            ),
            "topic": str(
                current_lab.get(
                    "topic",
                    "",
                )
                or ""
            ),
            "difficulty": str(
                current_lab.get(
                    "difficulty",
                    "",
                )
                or ""
            ),
            "discipline": str(
                current_lab.get(
                    "discipline",
                    "",
                )
                or ""
            ),
        },
        "main_error": {
            "error_type": str(
                main_error.get(
                    "error_type",
                    "",
                )
                or ""
            ),
            "error_title": str(
                main_error.get(
                    "error_title",
                    "",
                )
                or ""
            ),
            "count": int(
                main_error.get(
                    "count",
                    0,
                )
                or 0
            ),
            "last_recommendation": str(
                main_error.get(
                    "last_recommendation",
                    "",
                )
                or ""
            ),
        },
        "repeated_errors": [
            {
                "error_type": str(
                    item.get(
                        "error_type",
                        "",
                    )
                    or ""
                ),
                "error_title": str(
                    item.get(
                        "error_title",
                        "",
                    )
                    or ""
                ),
                "count": int(
                    item.get(
                        "count",
                        0,
                    )
                    or 0
                ),
            }
            for item in repeated_errors[:5]
            if isinstance(
                item,
                dict,
            )
        ],
        "recent_attempts": [
            {
                "lab_title": str(
                    item.get(
                        "lab_title",
                        "",
                    )
                    or ""
                ),
                "status": str(
                    item.get(
                        "status",
                        "",
                    )
                    or ""
                ),
                "score": item.get(
                    "score"
                ),
                "attempt_number": item.get(
                    "attempt_number"
                ),
                "error_type": str(
                    item.get(
                        "error_type",
                        "",
                    )
                    or ""
                ),
                "error_title": str(
                    item.get(
                        "error_title",
                        "",
                    )
                    or ""
                ),
            }
            for item in recent_attempts[:10]
            if isinstance(
                item,
                dict,
            )
        ],
    }


def extract_openai_web_source_urls(
    response,
) -> list[str]:
    """
    Витягує URL джерел, фактично використаних web search.

    Список використовується для аудиту походження рекомендацій
    і не залежить від текстового пояснення моделі.
    """
    source_urls = []

    for output_item in (
        getattr(
            response,
            "output",
            None,
        )
        or []
    ):
        if (
            getattr(
                output_item,
                "type",
                "",
            )
            != "web_search_call"
        ):
            continue

        action = getattr(
            output_item,
            "action",
            None,
        )

        if action is None:
            continue

        sources = getattr(
            action,
            "sources",
            None,
        ) or []

        for source in sources:
            url = str(
                getattr(
                    source,
                    "url",
                    "",
                )
                or ""
            ).strip()

            if url:
                source_urls.append(
                    url
                )

    return list(
        dict.fromkeys(
            source_urls
        )
    )


def normalize_learning_resource(
    resource,
) -> dict | None:
    """
    Нормалізує один навчальний інтернет-ресурс.

    До результату допускаються лише абсолютні HTTP/HTTPS URL.
    """
    if not isinstance(
        resource,
        dict,
    ):
        return None

    title = str(
        resource.get(
            "title",
            "",
        )
        or ""
    ).strip()

    url = str(
        resource.get(
            "url",
            "",
        )
        or ""
    ).strip()

    description = str(
        resource.get(
            "description",
            "",
        )
        or ""
    ).strip()

    why_useful = str(
        resource.get(
            "why_useful",
            "",
        )
        or ""
    ).strip()

    try:
        parsed_url = urlparse(
            url
        )
    except ValueError:
        return None

    if (
        parsed_url.scheme not in {
            "http",
            "https",
        }
        or not parsed_url.netloc
    ):
        return None

    if not title:
        return None

    return {
        "title": title,
        "url": url,
        "description": description,
        "why_useful": why_useful,
    }


def normalize_learning_resource_list(
    resources,
    limit=LEARNING_PATH_MAX_WEB_RESOURCES_PER_GROUP,
) -> list[dict]:
    """
    Нормалізує, дедуплікує та обмежує список навчальних ресурсів.
    """
    if not isinstance(
        resources,
        list,
    ):
        return []

    normalized_resources = []
    seen_urls = set()

    for resource in resources:
        normalized = normalize_learning_resource(
            resource
        )

        if not normalized:
            continue

        url_key = normalized[
            "url"
        ].rstrip("/").casefold()

        if url_key in seen_urls:
            continue

        seen_urls.add(
            url_key
        )

        normalized_resources.append(
            normalized
        )

        if (
            len(normalized_resources)
            >= limit
        ):
            break

    return normalized_resources


def normalize_generated_learning_path(
    result,
) -> dict | None:
    """
    Виконує фінальну захисну нормалізацію результату ШІ-модуля
    перед використанням у UI та збереженням у кеші.
    """
    if not isinstance(
        result,
        dict,
    ):
        return None

    what_to_repeat = result.get(
        "what_to_repeat",
        [],
    )

    if not isinstance(
        what_to_repeat,
        list,
    ):
        what_to_repeat = []

    return {
        "status": "OK",
        "summary": str(
            result.get(
                "summary",
                "",
            )
            or ""
        ).strip(),
        "topic_title": str(
            result.get(
                "topic_title",
                "",
            )
            or ""
        ).strip(),
        "mini_theory": str(
            result.get(
                "mini_theory",
                "",
            )
            or ""
        ).strip(),
        "what_to_repeat": [
            str(item).strip()
            for item in what_to_repeat
            if str(
                item or ""
            ).strip()
        ][:10],
        "lectures": normalize_learning_resource_list(
            result.get(
                "lectures",
                [],
            )
        ),
        "articles": normalize_learning_resource_list(
            result.get(
                "articles",
                [],
            )
        ),
        "practice": normalize_learning_resource_list(
            result.get(
                "practice",
                [],
            )
        ),
        "videos": normalize_learning_resource_list(
            result.get(
                "videos",
                [],
            )
        ),
        "control_question": str(
            result.get(
                "control_question",
                "",
            )
            or ""
        ).strip(),
        "next_topic": str(
            result.get(
                "next_topic",
                "",
            )
            or ""
        ).strip(),
        "ai_note": str(
            result.get(
                "ai_note",
                "",
            )
            or ""
        ).strip(),
    }


def generate_live_learning_path_with_openai(
    context,
) -> dict:
    """
    Генерує персоналізовану навчальну траєкторію через OpenAI.

    Web search є обов'язковим етапом для динамічного добору
    відкритих навчальних ресурсів. Відповідь формується
    відповідно до заданої JSON Schema.
    """
    client = get_openai_client()

    if client is None:
        return build_open_search_fallback_learning_path(
            context=context,
            reason=(
                "OpenAI API не налаштовано; "
                "використано резервний режим."
            ),
        )

    safe_context = build_openai_learning_context(
        context
    )

    user_prompt = {
        "task": (
            "Сформуй індивідуальну навчальну траєкторію "
            "з Verilog/FPGA та добери актуальні відкриті "
            "інтернет-ресурси."
        ),
        "student_context": safe_context,
    }

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            tools=[
                {
                    "type": "web_search",
                }
            ],
            tool_choice="required",
            include=[
                "web_search_call.action.sources",
            ],
            input=[
                {
                    "role": "system",
                    "content": OPENAI_LEARNING_PATH_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        user_prompt,
                        ensure_ascii=False,
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "fpga_learning_path",
                    "strict": True,
                    "schema": LEARNING_PATH_RESPONSE_SCHEMA,
                }
            },
            # Діагностичний контекст не потребує збереження
            # як окрема серверна conversation state в OpenAI.
            store=False,
        )

        output_text = str(
            getattr(
                response,
                "output_text",
                "",
            )
            or ""
        ).strip()

        if not output_text:
            app.logger.warning(
                "OpenAI повернув порожню відповідь "
                "для навчальної траєкторії."
            )

            return build_open_search_fallback_learning_path(
                context=context,
                reason=(
                    "OpenAI повернув порожню відповідь; "
                    "використано резервний режим."
                ),
            )

        try:
            parsed = json.loads(
                output_text
            )

        except json.JSONDecodeError:
            app.logger.exception(
                "Не вдалося декодувати структуровану "
                "відповідь OpenAI як JSON."
            )

            return build_open_search_fallback_learning_path(
                context=context,
                reason=(
                    "Не вдалося обробити структуровану "
                    "відповідь OpenAI."
                ),
            )

        normalized_result = normalize_generated_learning_path(
            parsed
        )

        if not normalized_result:
            app.logger.warning(
                "OpenAI повернув некоректну структуру "
                "навчальної траєкторії."
            )

            return build_open_search_fallback_learning_path(
                context=context,
                reason=(
                    "Структура відповіді OpenAI не пройшла "
                    "локальну перевірку."
                ),
            )

        web_sources = extract_openai_web_source_urls(
            response
        )

        if not web_sources:
            app.logger.warning(
                "OpenAI web search не повернув жодного "
                "джерела для навчальної траєкторії."
            )

            return build_open_search_fallback_learning_path(
                context=context,
                reason=(
                    "Web search не повернув перевірених джерел; "
                    "використано резервний каталог."
                ),
            )

        normalized_result[
            "web_sources"
        ] = web_sources

        return normalized_result

    except Exception:
        app.logger.exception(
            "Помилка під час генерації навчальної "
            "траєкторії через OpenAI."
        )

        return build_open_search_fallback_learning_path(
            context=context,
            reason=(
                "Зовнішній ШІ-сервіс тимчасово недоступний; "
                "використано резервний режим."
            ),
        )


# ============================================================
# Кеш навчальних траєкторій
# ============================================================

def get_learning_context_fingerprint(
    context,
) -> str:
    """
    Формує відбиток поточного навчального стану студента.

    Відбиток змінюється після нових спроб, зміни основної
    помилки або її частоти, тому застаріла траєкторія
    не використовується лише через незмінний topic_key.
    """
    safe_context = build_openai_learning_context(
        context
    )

    raw = json.dumps(
        safe_context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        default=str,
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


def make_live_learning_cache_key(
    username,
    lab_id,
    error_type,
    topic_key,
    context,
    mode,
) -> str:
    """
    Формує cache key з урахуванням навчального стану,
    режиму генерації та моделі OpenAI.
    """
    base_key = make_learning_cache_key(
        username=username,
        lab_id=lab_id,
        error_type=error_type,
        topic_key=topic_key,
    )

    context_fingerprint = get_learning_context_fingerprint(
        context
    )

    model_key = (
        str(
            OPENAI_MODEL or ""
        ).strip()
        if mode == "openai"
        else "direct"
    )

    raw = "|".join([
        base_key,
        context_fingerprint,
        str(
            mode or ""
        ),
        model_key,
    ])

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


def get_cached_learning_path(
    username,
    lab_id,
    cache_key,
):
    """
    Повертає останню коректну кешовану навчальну траєкторію.
    """
    conn = get_db()

    try:
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
                cache_key,
            ),
        ).fetchone()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час читання кешу "
            "навчальної траєкторії."
        )

        return None

    finally:
        conn.close()

    if not row:
        return None

    try:
        cached_result = json.loads(
            row["result_json"]
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        app.logger.warning(
            "У кеші навчальної траєкторії виявлено "
            "некоректний JSON для запису %s.",
            get_row_value(
                row,
                "id",
                "?",
            ),
        )

        return None

    if not isinstance(
        cached_result,
        dict,
    ):
        app.logger.warning(
            "Кешована навчальна траєкторія має "
            "некоректний тип даних."
        )

        return None

    return cached_result


def build_cacheable_learning_path_result(
    result,
) -> dict:
    """
    Готує результат до кешування.

    Поточний діагностичний context не дублюється в result_json,
    оскільки він формується заново під час кожного запиту.
    """
    if not isinstance(
        result,
        dict,
    ):
        return {}

    excluded_fields = {
        "context",
        "from_cache",
    }

    return {
        key: value
        for key, value in result.items()
        if key not in excluded_fields
    }


def save_cached_learning_path(
    username,
    lab_id,
    cache_key,
    result,
) -> bool:
    """
    Зберігає навчальну траєкторію в локальному кеші.

    Помилка кешування не повинна переривати основний
    користувацький сценарій, оскільки результат уже сформовано.
    """
    cacheable_result = build_cacheable_learning_path_result(
        result
    )

    try:
        result_json = json.dumps(
            cacheable_result,
            ensure_ascii=False,
        )

    except (
        TypeError,
        ValueError,
    ):
        app.logger.exception(
            "Не вдалося серіалізувати навчальну "
            "траєкторію для кешування."
        )

        return False

    conn = get_db()

    try:
        # Кеш не є журналом аудиту, тому старі записи
        # з тим самим ключем можна безпечно замінити.
        conn.execute(
            """
            DELETE FROM learning_path_cache
            WHERE username = ?
              AND lab_id = ?
              AND cache_key = ?
            """,
            (
                username,
                lab_id or 0,
                cache_key,
            ),
        )

        conn.execute(
            """
            INSERT INTO learning_path_cache (
                username,
                lab_id,
                cache_key,
                result_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                lab_id or 0,
                cache_key,
                result_json,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        conn.commit()

        return True

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час збереження "
            "кешу навчальної траєкторії."
        )

        return False

    finally:
        conn.close()


# ============================================================
# Побудова навчальної траєкторії
# ============================================================

def merge_learning_resources(
    primary,
    secondary,
    limit=LEARNING_PATH_MAX_WEB_RESOURCES_PER_GROUP,
) -> list[dict]:
    """
    Об'єднує два списки ресурсів без дублювання URL.
    """
    combined = []

    if isinstance(
        primary,
        list,
    ):
        combined.extend(
            primary
        )

    if isinstance(
        secondary,
        list,
    ):
        combined.extend(
            secondary
        )

    return normalize_learning_resource_list(
        combined,
        limit=limit,
    )


def normalize_learning_path_mode(
    mode,
) -> str:
    """
    Нормалізує режим побудови навчальної траєкторії.
    """
    normalized_mode = str(
        mode or ""
    ).strip().lower()

    if normalized_mode in LEARNING_PATH_ALLOWED_MODES:
        return normalized_mode

    app.logger.warning(
        "Невідоме значення LEARNING_PATH_MODE=%r. "
        "Використано резервний режим direct.",
        mode,
    )

    return "direct"


def build_live_learning_path(
    username,
    current_lab_id=None,
    refresh=False,
) -> dict:
    """
    Формує персоналізовану навчальну траєкторію.

    Алгоритм використовує актуальний діагностичний контекст,
    кешування, OpenAI web search у режимі openai або локальний
    каталог ресурсів у режимі direct. YouTube Data API
    використовується як додаткове джерело відеоматеріалів.
    """
    normalized_username = str(
        username or ""
    ).strip()

    context = get_recent_student_error_context(
        username=normalized_username,
        current_lab_id=current_lab_id,
    )

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    error_type = str(
        main_error.get(
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    topic_key = str(
        context.get(
            "topic_key",
            "Verilog FPGA",
        )
        or "Verilog FPGA"
    ).strip()

    mode = normalize_learning_path_mode(
        LEARNING_PATH_MODE
    )

    cache_key = make_live_learning_cache_key(
        username=normalized_username,
        lab_id=current_lab_id or 0,
        error_type=error_type,
        topic_key=topic_key,
        context=context,
        mode=mode,
    )

    if not refresh:
        cached = get_cached_learning_path(
            username=normalized_username,
            lab_id=current_lab_id or 0,
            cache_key=cache_key,
        )

        if cached:
            cached["from_cache"] = True
            cached["context"] = context

            return cached

    if mode == "openai":
        result = generate_live_learning_path_with_openai(
            context
        )

    else:
        result = build_open_search_fallback_learning_path(
            context=context,
            reason=(
                "Налаштовано режим direct; "
                "використано локальний каталог "
                "відкритих навчальних ресурсів."
            ),
        )

    if not isinstance(
        result,
        dict,
    ):
        app.logger.error(
            "Модуль навчальної траєкторії повернув "
            "некоректний тип результату."
        )

        result = build_open_search_fallback_learning_path(
            context=context,
            reason=(
                "Основний генератор повернув некоректний результат."
            ),
        )

    youtube_query = (
        f"{topic_key} tutorial Verilog FPGA"
    )

    youtube_videos = search_youtube_videos(
        query=youtube_query,
        max_results=3,
    )

    # Динамічні результати YouTube доповнюють, а не замінюють
    # основні ресурси. Дублікати URL видаляються.
    if youtube_videos:
        prepared_youtube_videos = []

        for video in youtube_videos:
            if not isinstance(
                video,
                dict,
            ):
                continue

            prepared_video = dict(
                video
            )

            prepared_video.setdefault(
                "why_useful",
                (
                    "Додатковий відеоматеріал, підібраний "
                    "за поточною навчальною темою."
                ),
            )

            prepared_youtube_videos.append(
                prepared_video
            )

        result["videos"] = merge_learning_resources(
            prepared_youtube_videos,
            result.get(
                "videos",
                [],
            ),
        )

    result["from_cache"] = False
    result["context"] = context
    result["generated_at"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Тимчасовий fallback через помилку OpenAI не кешується,
    # щоб після відновлення сервісу наступний запит міг знову
    # побудувати повноцінну web-search траєкторію.
    should_cache = not (
        mode == "openai"
        and result.get(
            "status"
        )
        != "OK"
    )

    if should_cache:
        save_cached_learning_path(
            username=normalized_username,
            lab_id=current_lab_id or 0,
            cache_key=cache_key,
            result=result,
        )

    return result


# ============================================================
# Тренажер: визначення теми та навчальних джерел
# ============================================================

TRAINER_SOURCE_TIMEOUT_SECONDS = 8
TRAINER_SOURCE_MAX_REDIRECTS = 3
TRAINER_SOURCE_MAX_RESPONSE_BYTES = 256 * 1024

TRAINER_SOURCE_USER_AGENT = (
    "FPGA-Learning-System/1.0 "
    "(educational resource metadata fetcher)"
)

TRAINER_ALLOWED_SOURCE_HOSTS = frozenset({
    "hdlbits.01xz.net",
    "nandland.com",
    "www.nandland.com",
    "projectf.io",
    "www.projectf.io",
})


TRAINER_ERROR_TOPIC_MAP = {
    "CONTROL_SIGNAL_ERROR": "mux",

    "MODULE_NAME_MISMATCH": "module_name",
    "PORT_MISMATCH": "ports",

    "RESET_CLOCK_ERROR": "reset_clock",

    "BLOCKING_IN_SEQ": "sequential_assignment",
    "BLKSEQ": "sequential_assignment",
    "BLOCKING_ASSIGNMENT_ERROR": "sequential_assignment",

    "FSM_STATE_ERROR": "fsm",
    "FSM_TRANSITION_ERROR": "fsm",
}


TRAINER_SOURCE_CATALOG = {
    "mux": [
        {
            "title": "HDLBits: Combinational Logic",
            "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
        {
            "title": "Project F: Verilog Library",
            "url": "https://projectf.io/verilog-lib/",
        },
    ],

    "adder": [
        {
            "title": "HDLBits: Combinational Logic",
            "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
        {
            "title": "Project F: Verilog Library",
            "url": "https://projectf.io/verilog-lib/",
        },
    ],

    "module_name": [
        {
            "title": "HDLBits: Getting Started",
            "url": "https://hdlbits.01xz.net/wiki/Step_one",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],

    "ports": [
        {
            "title": "HDLBits: Getting Started",
            "url": "https://hdlbits.01xz.net/wiki/Step_one",
        },
        {
            "title": "Nandland: Verilog Tutorials",
            "url": (
                "https://nandland.com/category/"
                "verilog-tutorials-and-examples/verilog-tutorials/"
            ),
        },
    ],

    "case_default": [
        {
            "title": "HDLBits: Always blocks",
            "url": "https://hdlbits.01xz.net/wiki/Alwaysblock1",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],

    "reset_clock": [
        {
            "title": "HDLBits: Always blocks clocked",
            "url": "https://hdlbits.01xz.net/wiki/Alwaysff",
        },
        {
            "title": "HDLBits: D flip-flop",
            "url": "https://hdlbits.01xz.net/wiki/Dff",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],

    "sequential_assignment": [
        {
            "title": "HDLBits: Sequential Logic",
            "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],

    "fsm": [
        {
            "title": "HDLBits: Finite State Machines",
            "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],

    "verilog_basics": [
        {
            "title": "HDLBits: Problem Sets",
            "url": "https://hdlbits.01xz.net/wiki/Problem_sets",
        },
        {
            "title": "Nandland: Learn Verilog",
            "url": "https://nandland.com/learn-verilog/",
        },
    ],
}


def get_trainer_topic_by_error(
    error_type,
    lab_topic="",
    lab_title="",
) -> str:
    """
    Визначає тему тренувального завдання за класифікованою
    помилкою та тематикою поточної лабораторної роботи.

    Тип помилки має вищий пріоритет, але для загальних
    функціональних помилок враховується конкретна тема схеми.
    """
    normalized_error_type = str(
        error_type or ""
    ).strip().upper()

    normalized_lab_topic = detect_normalized_lab_topic(
        lab_topic,
        lab_title,
    )

    direct_topic = TRAINER_ERROR_TOPIC_MAP.get(
        normalized_error_type
    )

    if direct_topic:
        return direct_topic

    if normalized_error_type in {
        "INCOMPLETE_CONDITION",
        "CASE_WITHOUT_DEFAULT",
    }:
        if normalized_lab_topic == "fsm":
            return "fsm"

        return "case_default"

    # Функціональні помилки інтерпретуються в контексті
    # конкретної цифрової схеми, а не автоматично як помилка mux.
    if normalized_error_type in {
        "WRONG_COMBINATIONAL_LOGIC",
        "BOUNDARY_TEST_FAILED",
        "FUNCTIONAL_ERROR",
        "HIDDEN_TEST_FAILED",
    }:
        if normalized_lab_topic == "mux":
            return "mux"

        if normalized_lab_topic == "adder":
            return "adder"

        if normalized_lab_topic in {
            "counter",
            "register",
        }:
            return "reset_clock"

        if normalized_lab_topic == "fsm":
            return "fsm"

    if normalized_lab_topic == "mux":
        return "mux"

    if normalized_lab_topic == "adder":
        return "adder"

    if normalized_lab_topic in {
        "counter",
        "register",
    }:
        return "reset_clock"

    if normalized_lab_topic == "fsm":
        return "fsm"

    return "verilog_basics"


def get_trainer_source_catalog(
    topic_slug,
) -> list[dict]:
    """
    Повертає статичний перелік відкритих навчальних джерел
    для вибраної теми тренажера.
    """
    normalized_topic = str(
        topic_slug or ""
    ).strip().lower()

    if normalized_topic not in TRAINER_SOURCE_CATALOG:
        normalized_topic = "verilog_basics"

    return [
        dict(resource)
        for resource in TRAINER_SOURCE_CATALOG[
            normalized_topic
        ]
    ]


def is_allowed_trainer_source_url(
    url,
) -> bool:
    """
    Перевіряє, чи належить URL до дозволених навчальних джерел.

    Для серверного отримання metadata дозволено лише HTTPS
    та домени з контрольованого каталогу тренажера.
    """
    normalized_url = str(
        url or ""
    ).strip()

    if not normalized_url:
        return False

    try:
        parsed = urlparse(
            normalized_url
        )
    except ValueError:
        return False

    hostname = str(
        parsed.hostname or ""
    ).strip().lower()

    if parsed.scheme.lower() != "https":
        return False

    if not hostname:
        return False

    if hostname not in TRAINER_ALLOWED_SOURCE_HOSTS:
        return False

    # URL із вбудованими credentials не потрібні навчальному модулю
    # і не повинні використовуватися для серверних HTTP-запитів.
    if parsed.username or parsed.password:
        return False

    return True


def build_empty_web_source_metadata(
    url,
) -> dict:
    """Формує стандартний результат невдалого отримання metadata."""
    return {
        "url": str(
            url or ""
        ).strip(),
        "title": "",
        "description": "",
        "ok": False,
    }


def read_limited_html_response(
    response,
    max_bytes=TRAINER_SOURCE_MAX_RESPONSE_BYTES,
) -> str | None:
    """
    Зчитує HTML-відповідь із жорстким обмеженням розміру.

    Обмеження не дозволяє зовнішньому ресурсу змусити сервер
    завантажувати у пам'ять довільно великий документ.
    """
    try:
        content_length = int(
            response.headers.get(
                "Content-Length",
                0,
            )
            or 0
        )
    except (TypeError, ValueError, OverflowError):
        content_length = 0

    if (
        content_length > 0
        and content_length > max_bytes
    ):
        return None

    chunks = []
    received_bytes = 0

    for chunk in response.iter_content(
        chunk_size=8192,
    ):
        if not chunk:
            continue

        received_bytes += len(
            chunk
        )

        if received_bytes > max_bytes:
            return None

        chunks.append(
            chunk
        )

    raw_content = b"".join(
        chunks
    )

    encoding = (
        response.encoding
        or "utf-8"
    )

    try:
        return raw_content.decode(
            encoding,
            errors="replace",
        )
    except LookupError:
        return raw_content.decode(
            "utf-8",
            errors="replace",
        )


def fetch_web_source_metadata(
    url,
) -> dict:
    """
    Отримує обмежений набір metadata для навчального веб-ресурсу.

    Кожен URL і redirect перевіряється за allowlist доменів.
    Завантажується лише HTML і не більше визначеного обсягу даних.
    Такий підхід зменшує ризик SSRF та неконтрольованого
    споживання пам'яті під час роботи з зовнішніми ресурсами.
    """
    original_url = str(
        url or ""
    ).strip()

    if not is_allowed_trainer_source_url(
        original_url
    ):
        app.logger.warning(
            "Відхилено недозволений URL навчального ресурсу."
        )

        return build_empty_web_source_metadata(
            original_url
        )

    current_url = original_url

    try:
        for redirect_number in range(
            TRAINER_SOURCE_MAX_REDIRECTS + 1
        ):
            if not is_allowed_trainer_source_url(
                current_url
            ):
                app.logger.warning(
                    "Відхилено redirect навчального ресурсу "
                    "на недозволений домен."
                )

                return build_empty_web_source_metadata(
                    original_url
                )

            with requests.get(
                current_url,
                timeout=TRAINER_SOURCE_TIMEOUT_SECONDS,
                headers={
                    "User-Agent": TRAINER_SOURCE_USER_AGENT,
                    "Accept": (
                        "text/html,"
                        "application/xhtml+xml;q=0.9"
                    ),
                },
                allow_redirects=False,
                stream=True,
            ) as response:

                if response.status_code in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    if (
                        redirect_number
                        >= TRAINER_SOURCE_MAX_REDIRECTS
                    ):
                        app.logger.warning(
                            "Перевищено допустиму кількість "
                            "redirect під час отримання metadata."
                        )

                        return build_empty_web_source_metadata(
                            original_url
                        )

                    location = str(
                        response.headers.get(
                            "Location",
                            "",
                        )
                        or ""
                    ).strip()

                    if not location:
                        return build_empty_web_source_metadata(
                            original_url
                        )

                    redirected_url = urljoin(
                        current_url,
                        location,
                    )

                    if not is_allowed_trainer_source_url(
                        redirected_url
                    ):
                        app.logger.warning(
                            "Навчальний ресурс виконав redirect "
                            "на недозволений URL."
                        )

                        return build_empty_web_source_metadata(
                            original_url
                        )

                    current_url = redirected_url
                    continue

                if response.status_code != 200:
                    app.logger.info(
                        "Навчальний ресурс повернув HTTP %s.",
                        response.status_code,
                    )

                    return build_empty_web_source_metadata(
                        original_url
                    )

                content_type = str(
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                    or ""
                ).lower()

                if (
                    content_type
                    and "text/html" not in content_type
                    and "application/xhtml+xml"
                    not in content_type
                ):
                    app.logger.info(
                        "Навчальний ресурс повернув "
                        "непідтримуваний Content-Type."
                    )

                    return build_empty_web_source_metadata(
                        original_url
                    )

                html_text = read_limited_html_response(
                    response
                )

                if html_text is None:
                    app.logger.warning(
                        "HTML навчального ресурсу перевищує "
                        "допустимий розмір."
                    )

                    return build_empty_web_source_metadata(
                        original_url
                    )

                soup = BeautifulSoup(
                    html_text,
                    "html.parser",
                )

                title = ""

                if (
                    soup.title
                    and soup.title.string
                ):
                    title = str(
                        soup.title.string
                    ).strip()

                description = ""

                meta_description = soup.find(
                    "meta",
                    attrs={
                        "name": re.compile(
                            r"^description$",
                            re.IGNORECASE,
                        )
                    },
                )

                if (
                    meta_description
                    and meta_description.get(
                        "content"
                    )
                ):
                    description = str(
                        meta_description.get(
                            "content"
                        )
                    ).strip()

                # Зберігається лише короткий metadata-фрагмент,
                # а не повний текст зовнішнього навчального матеріалу.
                title = re.sub(
                    r"\s+",
                    " ",
                    title,
                )[:200]

                description = re.sub(
                    r"\s+",
                    " ",
                    description,
                )[:500]

                return {
                    "url": original_url,
                    "title": title,
                    "description": description,
                    "ok": True,
                }

        return build_empty_web_source_metadata(
            original_url
        )

    except requests.RequestException:
        app.logger.exception(
            "Мережева помилка під час отримання metadata "
            "навчального ресурсу."
        )

        return build_empty_web_source_metadata(
            original_url
        )

    except (ValueError, TypeError):
        app.logger.exception(
            "Не вдалося обробити metadata навчального ресурсу."
        )

        return build_empty_web_source_metadata(
            original_url
        )
    

# ============================================================
# Тренажер: контекст студента та шаблонні завдання
# ============================================================

TRAINER_CONTEXT_ATTEMPT_LIMIT = 30
TRAINER_CONTEXT_RECENT_ATTEMPT_LIMIT = 10
TRAINER_CONTEXT_REPEATED_ERROR_LIMIT = 5

TRAINER_IGNORED_ERROR_TYPES = frozenset({
    "",
    "NO_ERROR",
    "SYSTEM_ERROR",
})

TRAINER_TOPIC_COMPETENCY_MAP = {
    "mux": "combinational_logic",
    "adder": "combinational_logic",
    "module_name": "hdl_syntax_structure",
    "ports": "hdl_syntax_structure",
    "case_default": "combinational_logic",
    "reset_clock": "reset_clock",
    "sequential_assignment": "sequential_logic",
    "fsm": "fsm",
    "verilog_basics": "hdl_syntax_structure",
}


def collect_trainer_web_context(
    topic_slug,
    limit=3,
) -> list[dict]:
    """
    Збирає короткі metadata дозволених навчальних джерел
    для поточної теми тренажера.

    Отримується лише обмежений metadata-контекст; повний текст
    зовнішніх сторінок до тренажера не копіюється.
    """
    try:
        normalized_limit = int(
            limit
        )
    except (TypeError, ValueError, OverflowError):
        normalized_limit = 3

    normalized_limit = max(
        0,
        min(
            normalized_limit,
            10,
        ),
    )

    if normalized_limit == 0:
        return []

    sources = get_trainer_source_catalog(
        topic_slug
    )

    collected = []

    for source in sources[
        :normalized_limit
    ]:
        if not isinstance(
            source,
            dict,
        ):
            continue

        source_url = str(
            source.get(
                "url",
                "",
            )
            or ""
        ).strip()

        source_title = str(
            source.get(
                "title",
                "",
            )
            or ""
        ).strip()

        if not source_url:
            continue

        metadata = fetch_web_source_metadata(
            source_url
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        collected.append({
            "source_title": source_title,
            "source_url": source_url,
            "page_title": str(
                metadata.get(
                    "title",
                    "",
                )
                or source_title
            ).strip(),
            "page_description": str(
                metadata.get(
                    "description",
                    "",
                )
                or ""
            ).strip(),
            "ok": bool(
                metadata.get(
                    "ok",
                    False,
                )
            ),
        })

    return collected


def get_student_trainer_context(
    username,
) -> dict:
    """
    Формує локальний навчальний контекст для HDL-тренажера.

    До профілю повторюваних помилок не включаються SYSTEM_ERROR
    та успішні результати. Python та інші типи лабораторних робіт
    не змішуються з тренажером Verilog/FPGA.
    """
    normalized_username = str(
        username or ""
    ).strip()

    if not normalized_username:
        return {
            "username": "",
            "main_error": None,
            "repeated_errors": [],
            "topic_slug": "verilog_basics",
            "recent_attempts": [],
        }

    conn = get_db()

    try:
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

            JOIN labs
                ON labs.id = submissions.lab_id

            WHERE submissions.username = ?

              AND submissions.status <> 'SYSTEM_ERROR'

              AND COALESCE(
                    NULLIF(labs.checker_type, ''),
                    'hdl_testbench'
                  ) = 'hdl_testbench'

            ORDER BY
                submissions.created_at DESC,
                submissions.id DESC

            LIMIT ?
            """,
            (
                normalized_username,
                TRAINER_CONTEXT_ATTEMPT_LIMIT,
            ),
        ).fetchall()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час формування "
            "контексту HDL-тренажера для студента."
        )

        return {
            "username": normalized_username,
            "main_error": None,
            "repeated_errors": [],
            "topic_slug": "verilog_basics",
            "recent_attempts": [],
        }

    finally:
        conn.close()

    attempts = [
        dict(row)
        for row in rows
    ]

    error_counter = {}

    # Найновіші відправлення розташовані першими, тому поле
    # latest_submission_id використовується для детермінованого
    # вибору між помилками з однаковою частотою.
    for row in attempts:
        error_type = str(
            row.get(
                "error_type",
                "",
            )
            or ""
        ).strip().upper()

        if error_type in TRAINER_IGNORED_ERROR_TYPES:
            continue

        if error_type not in error_counter:
            error_counter[error_type] = {
                "error_type": error_type,
                "error_title": str(
                    row.get(
                        "error_title",
                        "",
                    )
                    or error_type
                ).strip(),
                "count": 0,
                "lab_title": str(
                    row.get(
                        "lab_title",
                        "",
                    )
                    or ""
                ).strip(),
                "lab_topic": str(
                    row.get(
                        "lab_topic",
                        "",
                    )
                    or ""
                ).strip(),
                "recommendation": str(
                    row.get(
                        "recommendation",
                        "",
                    )
                    or ""
                ).strip(),
                "latest_submission_id": int(
                    row.get(
                        "id",
                        0,
                    )
                    or 0
                ),
            }

        error_counter[
            error_type
        ]["count"] += 1

    repeated_errors = sorted(
        error_counter.values(),
        key=lambda item: (
            -item["count"],
            -item["latest_submission_id"],
            item["error_type"],
        ),
    )

    if repeated_errors:
        main_error = repeated_errors[0]

        topic_slug = get_trainer_topic_by_error(
            error_type=main_error[
                "error_type"
            ],
            lab_topic=main_error[
                "lab_topic"
            ],
            lab_title=main_error[
                "lab_title"
            ],
        )
    else:
        main_error = None
        topic_slug = "verilog_basics"

    return {
        # username залишається лише для локальної логіки тренажера.
        # Цей словник не слід безпосередньо передавати зовнішньому LLM.
        "username": normalized_username,
        "main_error": main_error,
        "repeated_errors": repeated_errors[
            :TRAINER_CONTEXT_REPEATED_ERROR_LIMIT
        ],
        "topic_slug": topic_slug,
        "recent_attempts": attempts[
            :TRAINER_CONTEXT_RECENT_ATTEMPT_LIMIT
        ],
    }


def get_trainer_competency_id(
    topic_slug,
) -> str:
    """
    Повертає ідентифікатор компетентності,
    пов'язаної з темою тренувального завдання.
    """
    normalized_topic = str(
        topic_slug or ""
    ).strip().lower()

    return TRAINER_TOPIC_COMPETENCY_MAP.get(
        normalized_topic,
        "hdl_syntax_structure",
    )


def get_preferred_trainer_source(
    web_context,
) -> dict:
    """
    Вибирає доступне навчальне джерело для супроводу завдання.

    Перевага надається ресурсу, metadata якого було успішно
    отримано. Якщо перевірка недоступності не дала результату,
    використовується перший ресурс із контрольованого каталогу.
    """
    if not isinstance(
        web_context,
        list,
    ):
        return {
            "source_title": "",
            "source_url": "",
            "ok": False,
        }

    for source in web_context:
        if (
            isinstance(source, dict)
            and source.get("ok")
        ):
            return source

    for source in web_context:
        if isinstance(
            source,
            dict,
        ):
            return source

    return {
        "source_title": "",
        "source_url": "",
        "ok": False,
    }


def generate_template_trainer_tasks(
    context,
    web_context,
    count=5,
    seed=None,
) -> list[dict]:
    """
    Формує шаблонні тренувальні завдання за визначеною темою.

    Завдання є детермінованими навчальними шаблонами, а зовнішній
    ресурс використовується лише як додатковий матеріал для повторення,
    а не як джерело автоматично скопійованого змісту.

    Параметр seed дає змогу відтворити однакову вибірку завдань
    під час експериментального дослідження.
    """
    if not isinstance(
        context,
        dict,
    ):
        context = {}

    topic_slug = str(
        context.get(
            "topic_slug",
            "verilog_basics",
        )
        or "verilog_basics"
    ).strip().lower()

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    error_type = str(
        main_error.get(
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    try:
        normalized_count = int(
            count
        )
    except (TypeError, ValueError, OverflowError):
        normalized_count = 5

    normalized_count = max(
        0,
        min(
            normalized_count,
            20,
        ),
    )

    if normalized_count == 0:
        return []

    source = get_preferred_trainer_source(
        web_context
    )

    tasks = []

    if topic_slug == "mux":
        tasks.extend([
            {
                "title": "Вибір виходу при sel = 0",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Нехай мультиплексор 2 до 1 описано виразом "
                    "y = sel ? d1 : d0. Який сигнал буде передано "
                    "на вихід при sel = 0?"
                ),
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": [
                    "d0",
                    "d1",
                    "sel",
                    "0",
                ],
                "correct_answer": "d0",
                "explanation": (
                    "Коли sel = 0, тернарний оператор обирає "
                    "значення після двокрапки, тобто d0."
                ),
            },
            {
                "title": "Вибір виходу при sel = 1",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Нехай мультиплексор 2 до 1 описано виразом "
                    "y = sel ? d1 : d0. Який сигнал буде передано "
                    "на вихід при sel = 1?"
                ),
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": [
                    "d0",
                    "d1",
                    "sel",
                    "x",
                ],
                "correct_answer": "d1",
                "explanation": (
                    "Коли sel = 1, тернарний оператор обирає "
                    "значення перед двокрапкою, тобто d1."
                ),
            },
            {
                "title": "Визначення значення y",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Якого значення набуде y, якщо d0 = 1, "
                    "d1 = 0 та sel = 0?"
                ),
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": [
                    "0",
                    "1",
                    "x",
                    "z",
                ],
                "correct_answer": "1",
                "explanation": (
                    "При sel = 0 вибирається d0. Оскільки d0 = 1, "
                    "вихід y також дорівнює 1."
                ),
            },
            {
                "title": "Визначення значення y при sel = 1",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Якого значення набуде y, якщо d0 = 1, "
                    "d1 = 0 та sel = 1?"
                ),
                "code_snippet": "assign y = sel ? d1 : d0;",
                "options": [
                    "0",
                    "1",
                    "d0",
                    "sel",
                ],
                "correct_answer": "0",
                "explanation": (
                    "При sel = 1 вибирається d1. Оскільки d1 = 0, "
                    "вихід y дорівнює 0."
                ),
            },
            {
                "title": "Коректний опис мультиплексора",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Який вираз правильно описує мультиплексор 2 до 1, "
                    "якщо при sel = 0 потрібно вибирати d0, "
                    "а при sel = 1 — d1?"
                ),
                "code_snippet": "",
                "options": [
                    "assign y = sel ? d1 : d0;",
                    "assign y = sel ? d0 : d1;",
                    "assign y = d0 & d1;",
                    "assign y = sel;",
                ],
                "correct_answer": "assign y = sel ? d1 : d0;",
                "explanation": (
                    "У тернарному операторі значення перед двокрапкою "
                    "вибирається при істинній умові, а після неї — "
                    "при хибній."
                ),
            },
            {
                "title": "Пошук логічної помилки",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "За умовою при sel = 0 має вибиратися d0, "
                    "а при sel = 1 — d1. Яка помилка є у виразі?"
                ),
                "code_snippet": "assign y = sel ? d0 : d1;",
                "options": [
                    "Переплутано d0 і d1",
                    "Відсутній endmodule",
                    "Оператор assign заборонено",
                    "sel має бути output",
                ],
                "correct_answer": "Переплутано d0 і d1",
                "explanation": (
                    "У наведеному виразі значення входів для sel = 0 "
                    "і sel = 1 поміняні місцями."
                ),
            },
            {
                "title": "Роль керувального сигналу",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Який сигнал керує вибором входу "
                    "в мультиплексорі 2 до 1?"
                ),
                "code_snippet": (
                    "module mux2to1("
                    "input wire d0, input wire d1, "
                    "input wire sel, output wire y);"
                ),
                "options": [
                    "d0",
                    "d1",
                    "sel",
                    "y",
                ],
                "correct_answer": "sel",
                "explanation": (
                    "Сигнал sel визначає, який інформаційний "
                    "вхід передається на y."
                ),
            },
        ])

    elif topic_slug == "adder":
        tasks.extend([
            {
                "title": "Визначення суми",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Для однорозрядного напівсуматора a = 1 та b = 0. "
                    "Якого значення набуде вихід sum?"
                ),
                "code_snippet": "assign sum = a ^ b;",
                "options": [
                    "0",
                    "1",
                    "x",
                    "z",
                ],
                "correct_answer": "1",
                "explanation": (
                    "Операція XOR дорівнює 1, коли значення "
                    "двох входів відрізняються."
                ),
            },
            {
                "title": "Визначення перенесення",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Для однорозрядного напівсуматора a = 1 та b = 1. "
                    "Якого значення набуде carry?"
                ),
                "code_snippet": "assign carry = a & b;",
                "options": [
                    "0",
                    "1",
                    "x",
                    "a",
                ],
                "correct_answer": "1",
                "explanation": (
                    "Перенесення формується, коли обидва "
                    "вхідні біти дорівнюють 1."
                ),
            },
            {
                "title": "Операція для виходу sum",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Яку логічну операцію використовують для sum "
                    "у простому однорозрядному напівсуматорі?"
                ),
                "code_snippet": "",
                "options": [
                    "^",
                    "&",
                    "|",
                    "~",
                ],
                "correct_answer": "^",
                "explanation": (
                    "Для біта суми напівсуматора використовується XOR."
                ),
            },
        ])

    elif topic_slug == "module_name":
        tasks.extend([
            {
                "title": "Відповідність імені модуля",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Testbench створює екземпляр модуля alu_unit. "
                    "Який заголовок має відповідати цьому інтерфейсу?"
                ),
                "code_snippet": (
                    "alu_unit uut (...);\n\n"
                    "module ??? (...);"
                ),
                "options": [
                    "module alu_unit",
                    "module uut",
                    "module testbench",
                    "module design",
                ],
                "correct_answer": "module alu_unit",
                "explanation": (
                    "Ім'я описаного модуля має відповідати імені типу, "
                    "який створює testbench."
                ),
            }
        ])

    elif topic_slug == "ports":
        tasks.extend([
            {
                "title": "Напрямок вихідного порту",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Модуль отримує сигнали a і b та формує результат y. "
                    "Який напрямок повинен мати порт y?"
                ),
                "code_snippet": (
                    "module logic_unit("
                    "input wire a, input wire b, ??? wire y);"
                ),
                "options": [
                    "output",
                    "input",
                    "parameter",
                    "localparam",
                ],
                "correct_answer": "output",
                "explanation": (
                    "Сигнал y формується модулем, тому він є виходом."
                ),
            }
        ])

    elif topic_slug == "case_default":
        tasks.extend([
            {
                "title": "Завершення case-конструкції",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Яку конструкцію доцільно передбачити в case, "
                    "якщо потрібно явно визначити поведінку "
                    "для інших значень селектора?"
                ),
                "code_snippet": (
                    "case (sel)\n"
                    "    1'b0: y = d0;\n"
                    "    1'b1: y = d1;\n"
                    "    ???\n"
                    "endcase"
                ),
                "options": [
                    "default: y = 1'b0;",
                    "initial y = 0;",
                    "#10 y = d0;",
                    "assign sel = y;",
                ],
                "correct_answer": "default: y = 1'b0;",
                "explanation": (
                    "Гілка default дозволяє явно визначити поведінку "
                    "для значень, не охоплених іншими гілками. "
                    "Конкретне присвоєне значення має відповідати "
                    "специфікації схеми."
                ),
            }
        ])

    elif topic_slug == "reset_clock":
        tasks.extend([
            {
                "title": "Асинхронний reset",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Який список чутливості відповідає регістру "
                    "з активним високим асинхронним reset?"
                ),
                "code_snippet": "",
                "options": [
                    "always @(posedge clk or posedge reset)",
                    "always @(*)",
                    "always @(reset)",
                    "always @(posedge q)",
                ],
                "correct_answer": (
                    "always @(posedge clk or posedge reset)"
                ),
                "explanation": (
                    "Для активного високого асинхронного reset "
                    "подія reset входить до списку чутливості "
                    "разом із фронтом clock."
                ),
            },
            {
                "title": "Присвоєння в тактовому always-блоці",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Який оператор присвоєння зазвичай застосовують "
                    "для регістрів усередині always @(posedge clk)?"
                ),
                "code_snippet": (
                    "always @(posedge clk) begin\n"
                    "    q <= d;\n"
                    "end"
                ),
                "options": [
                    "<=",
                    "=",
                    "assign",
                    "==",
                ],
                "correct_answer": "<=",
                "explanation": (
                    "У тактовій послідовнісній логіці зазвичай "
                    "використовують неблокувальні присвоєння <=."
                ),
            },
        ])

    elif topic_slug == "sequential_assignment":
        tasks.extend([
            {
                "title": "Неблокувальне присвоєння",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Який варіант краще відповідає опису регістра, "
                    "що оновлюється за фронтом clock?"
                ),
                "code_snippet": "always @(posedge clk) begin\n    q ??? d;\nend",
                "options": [
                    "<=",
                    "=",
                    "==",
                    ":=",
                ],
                "correct_answer": "<=",
                "explanation": (
                    "Неблокувальні присвоєння моделюють одночасне "
                    "оновлення регістрів у послідовнісній логіці."
                ),
            },
            {
                "title": "Blocking та nonblocking",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Яке твердження найточніше описує типовий "
                    "стиль HDL-коду?"
                ),
                "code_snippet": "",
                "options": [
                    (
                        "Для тактових регістрів зазвичай використовують "
                        "<=, а для комбінаційних процедурних обчислень — ="
                    ),
                    "У всіх always-блоках потрібно використовувати лише =",
                    "Оператор <= використовується тільки в testbench",
                    "Між = і <= у Verilog немає різниці",
                ],
                "correct_answer": (
                    "Для тактових регістрів зазвичай використовують "
                    "<=, а для комбінаційних процедурних обчислень — ="
                ),
                "explanation": (
                    "Blocking і nonblocking присвоєння мають різну "
                    "семантику планування та використовуються "
                    "для різних типів HDL-логіки."
                ),
            },
        ])

    elif topic_slug == "fsm":
        tasks.extend([
            {
                "title": "Призначення next_state",
                "task_type": "single_choice",
                "difficulty": "medium",
                "prompt": (
                    "Яку роль зазвичай виконує сигнал next_state "
                    "у структурованому описі FSM?"
                ),
                "code_snippet": "",
                "options": [
                    "Містить обчислене наступне значення стану",
                    "Замінює сигнал clock",
                    "Замінює reset",
                    "Зберігає результат testbench",
                ],
                "correct_answer": (
                    "Містить обчислене наступне значення стану"
                ),
                "explanation": (
                    "Комбінаційна логіка FSM визначає next_state, "
                    "а регістр стану переносить його до current state "
                    "за активним фронтом clock."
                ),
            }
        ])

    else:
        tasks.extend([
            {
                "title": "Завершення Verilog-модуля",
                "task_type": "single_choice",
                "difficulty": "basic",
                "prompt": (
                    "Яке ключове слово завершує опис Verilog-модуля?"
                ),
                "code_snippet": (
                    "module example(input wire a, output wire y);\n"
                    "assign y = a;\n"
                    "???"
                ),
                "options": [
                    "endmodule",
                    "end",
                    "finish",
                    "stop",
                ],
                "correct_answer": "endmodule",
                "explanation": (
                    "Опис Verilog-модуля починається словом module "
                    "і завершується endmodule."
                ),
            }
        ])

    competency_id = get_trainer_competency_id(
        topic_slug
    )

    # У звичайному режимі порядок завдань змінюється.
    # Під час експерименту seed дозволяє отримати відтворювану вибірку.
    rng = (
        random.Random(seed)
        if seed is not None
        else random
    )

    rng.shuffle(
        tasks
    )

    prepared = []

    for task in tasks[
        :normalized_count
    ]:
        prepared.append({
            "topic_slug": topic_slug,
            "competency": competency_id,
            "error_type": error_type,
            "title": task["title"],
            "task_type": task["task_type"],
            "difficulty": task["difficulty"],
            "prompt": task["prompt"],
            "code_snippet": task.get(
                "code_snippet",
                "",
            ),
            "options": list(
                task.get(
                    "options",
                    [],
                )
            ),
            "correct_answer": task.get(
                "correct_answer",
                "",
            ),
            "explanation": task.get(
                "explanation",
                "",
            ),

            # Джерело використовується як матеріал для повторення,
            # а не як твердження, що шаблон завдання скопійовано
            # з конкретної зовнішньої сторінки.
            "source_title": str(
                source.get(
                    "source_title",
                    "",
                )
                or ""
            ),
            "source_url": str(
                source.get(
                    "source_url",
                    "",
                )
                or ""
            ),
            "source_available": bool(
                source.get(
                    "ok",
                    False,
                )
            ),
            "source_mode": "template",

            # Поля зберігаються для сумісності з єдиною моделлю
            # шаблонних та ШІ-згенерованих тренувальних завдань.
            "ai_prompt": "",
            "ai_raw_output": "",
        })

    return prepared


# ============================================================
# Тренажер: локальна ШІ-генерація та збереження завдань
# ============================================================

OLLAMA_TRAINER_TIMEOUT_SECONDS = 60

TRAINER_ALLOWED_AI_MODES = frozenset({
    "local",
    "template",
})

TRAINER_ALLOWED_TASK_TYPES = frozenset({
    "single_choice",
})

TRAINER_ALLOWED_DIFFICULTIES = frozenset({
    "basic",
    "medium",
    "advanced",
})

TRAINER_MAX_GENERATED_TASKS = 20
TRAINER_MAX_OPTIONS = 6

TRAINER_TASK_TITLE_MAX_LENGTH = 160
TRAINER_TASK_PROMPT_MAX_LENGTH = 1000
TRAINER_TASK_CODE_MAX_LENGTH = 1500
TRAINER_TASK_EXPLANATION_MAX_LENGTH = 1000
TRAINER_TASK_OPTION_MAX_LENGTH = 300

# Повні prompt/output локальної моделі за замовчуванням не зберігаються,
# оскільки вони можуть дублювати діагностичний контекст студента.
TRAINER_STORE_AI_DEBUG_DATA = False
TRAINER_AI_DEBUG_TEXT_MAX_LENGTH = 12_000


TRAINER_AI_TASK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tasks": {
            "type": "array",
            "maxItems": TRAINER_MAX_GENERATED_TASKS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": [
                            "single_choice",
                        ],
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": [
                            "basic",
                            "medium",
                            "advanced",
                        ],
                    },
                    "prompt": {
                        "type": "string",
                    },
                    "code_snippet": {
                        "type": "string",
                    },
                    "options": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": TRAINER_MAX_OPTIONS,
                        "items": {
                            "type": "string",
                        },
                    },
                    "correct_answer": {
                        "type": "string",
                    },
                    "explanation": {
                        "type": "string",
                    },
                },
                "required": [
                    "title",
                    "task_type",
                    "difficulty",
                    "prompt",
                    "code_snippet",
                    "options",
                    "correct_answer",
                    "explanation",
                ],
            },
        }
    },
    "required": [
        "tasks",
    ],
}


def normalize_trainer_task_count(
    count,
    default=5,
) -> int:
    """Нормалізує бажану кількість тренувальних завдань."""
    try:
        normalized_count = int(
            count
        )
    except (TypeError, ValueError, OverflowError):
        normalized_count = default

    return max(
        0,
        min(
            normalized_count,
            TRAINER_MAX_GENERATED_TASKS,
        ),
    )


def build_ollama_trainer_context(
    context,
) -> dict:
    """
    Формує мінімізований контекст для локальної мовної моделі.

    До prompt не включаються username, HDL-код, hidden testbench,
    raw output перевірки або інші дані, що не потрібні
    для генерації короткого тренувального завдання.
    """
    if not isinstance(
        context,
        dict,
    ):
        context = {}

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    repeated_errors = context.get(
        "repeated_errors",
        [],
    )

    if not isinstance(
        repeated_errors,
        list,
    ):
        repeated_errors = []

    recent_attempts = context.get(
        "recent_attempts",
        [],
    )

    if not isinstance(
        recent_attempts,
        list,
    ):
        recent_attempts = []

    return {
        "topic_slug": str(
            context.get(
                "topic_slug",
                "verilog_basics",
            )
            or "verilog_basics"
        ).strip(),
        "main_error": {
            "error_type": str(
                main_error.get(
                    "error_type",
                    "",
                )
                or ""
            ).strip(),
            "error_title": str(
                main_error.get(
                    "error_title",
                    "",
                )
                or ""
            ).strip(),
            "count": main_error.get(
                "count",
                0,
            ),
            "lab_title": str(
                main_error.get(
                    "lab_title",
                    "",
                )
                or ""
            ).strip(),
            "lab_topic": str(
                main_error.get(
                    "lab_topic",
                    "",
                )
                or ""
            ).strip(),
            "recommendation": str(
                main_error.get(
                    "recommendation",
                    "",
                )
                or ""
            ).strip(),
        },
        "repeated_errors": [
            {
                "error_type": str(
                    item.get(
                        "error_type",
                        "",
                    )
                    or ""
                ).strip(),
                "error_title": str(
                    item.get(
                        "error_title",
                        "",
                    )
                    or ""
                ).strip(),
                "count": item.get(
                    "count",
                    0,
                ),
            }
            for item in repeated_errors[:5]
            if isinstance(
                item,
                dict,
            )
        ],
        "recent_attempts": [
            {
                "status": str(
                    item.get(
                        "status",
                        "",
                    )
                    or ""
                ).strip(),
                "score": item.get(
                    "score"
                ),
                "attempt_number": item.get(
                    "attempt_number"
                ),
                "error_type": str(
                    item.get(
                        "error_type",
                        "",
                    )
                    or ""
                ).strip(),
                "error_title": str(
                    item.get(
                        "error_title",
                        "",
                    )
                    or ""
                ).strip(),
                "lab_title": str(
                    item.get(
                        "lab_title",
                        "",
                    )
                    or ""
                ).strip(),
            }
            for item in recent_attempts[:10]
            if isinstance(
                item,
                dict,
            )
        ],
    }


def build_ollama_trainer_web_context(
    web_context,
) -> list[dict]:
    """
    Формує обмежений набір metadata навчальних джерел
    для локальної мовної моделі.
    """
    if not isinstance(
        web_context,
        list,
    ):
        return []

    prepared = []

    for source in web_context[:3]:
        if not isinstance(
            source,
            dict,
        ):
            continue

        prepared.append({
            "source_title": str(
                source.get(
                    "source_title",
                    "",
                )
                or ""
            ).strip()[:200],
            "source_url": str(
                source.get(
                    "source_url",
                    "",
                )
                or ""
            ).strip()[:1000],
            "page_title": str(
                source.get(
                    "page_title",
                    "",
                )
                or ""
            ).strip()[:200],
            "page_description": str(
                source.get(
                    "page_description",
                    "",
                )
                or ""
            ).strip()[:500],
            "available": bool(
                source.get(
                    "ok",
                    False,
                )
            ),
        })

    return prepared


def build_ollama_trainer_prompt(
    context,
    web_context,
    count,
) -> dict:
    """Формує структурований prompt для генерації завдань."""
    return {
        "role": (
            "Генератор коротких тренувальних завдань "
            "з FPGA-проєктування та Verilog HDL"
        ),
        "language": "uk",
        "student_context": build_ollama_trainer_context(
            context
        ),
        "web_sources": build_ollama_trainer_web_context(
            web_context
        ),
        "requested_task_count": count,
        "task": (
            "Сформуй оригінальні короткі тренувальні завдання "
            "з Verilog/FPGA відповідно до проблемної теми студента. "
            "Не копіюй завдання або текст із зовнішніх джерел дослівно. "
            "Використовуй metadata джерел лише для визначення тематики "
            "та напряму повторення. Кожне завдання повинно мати "
            "одну однозначно правильну відповідь і бути придатним "
            "для автоматичної перевірки."
        ),
        "requirements": [
            (
                "Не розкривай готове рішення поточної "
                "лабораторної роботи."
            ),
            (
                "Не намагайся відновити hidden testbench "
                "або приховані тестові дані."
            ),
            (
                "Не створюй тверджень про зміст зовнішнього "
                "джерела, якщо цього немає в наданому metadata."
            ),
            (
                "У single_choice правильна відповідь повинна "
                "точно входити до списку options."
            ),
            (
                "Варіанти відповіді мають бути різними "
                "та не повинні створювати кілька правильних відповідей."
            ),
            (
                "Пояснення має навчати принципу, "
                "а не просто повторювати правильну відповідь."
            ),
        ],
        "allowed_task_types": [
            "single_choice",
        ],
    }


def prepare_trainer_ai_debug_text(
    value,
) -> str:
    """
    Готує службовий текст ШІ для збереження в БД.

    За замовчуванням debug-вміст не зберігається.
    """
    if not TRAINER_STORE_AI_DEBUG_DATA:
        return ""

    return str(
        value or ""
    )[:TRAINER_AI_DEBUG_TEXT_MAX_LENGTH]


def generate_trainer_tasks_with_ollama(
    context,
    web_context,
    count=5,
) -> list[dict]:
    """
    Генерує персоналізовані тренувальні завдання
    через локальний Ollama API.

    JSON Schema використовується як первинне обмеження формату,
    після чого результат додатково перевіряється локальним
    нормалізатором перед використанням або збереженням.
    """
    normalized_count = normalize_trainer_task_count(
        count
    )

    if normalized_count == 0:
        return []

    if not OLLAMA_URL or not OLLAMA_MODEL:
        app.logger.warning(
            "Ollama для тренажера не налаштовано."
        )
        return []

    prompt = build_ollama_trainer_prompt(
        context=context,
        web_context=web_context,
        count=normalized_count,
    )

    prompt_json = json.dumps(
        prompt,
        ensure_ascii=False,
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt_json,
                "stream": False,

                # Ollama підтримує JSON Schema безпосередньо
                # в полі format, що зменшує кількість
                # структурно некоректних відповідей моделі.
                "format": TRAINER_AI_TASK_SCHEMA,
            },
            timeout=OLLAMA_TRAINER_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            app.logger.warning(
                "Ollama повернув HTTP %s під час "
                "генерації завдань тренажера.",
                response.status_code,
            )

            return []

        try:
            data = response.json()
        except ValueError:
            app.logger.warning(
                "Ollama повернув некоректну JSON-відповідь "
                "на рівні API."
            )

            return []

        raw_output = str(
            data.get(
                "response",
                "",
            )
            or ""
        ).strip()

        if not raw_output:
            app.logger.warning(
                "Ollama повернув порожній результат "
                "генерації завдань тренажера."
            )

            return []

        try:
            parsed = json.loads(
                raw_output
            )
        except json.JSONDecodeError:
            app.logger.warning(
                "Структурована відповідь Ollama "
                "не декодується як JSON."
            )

            return []

        if not isinstance(
            parsed,
            dict,
        ):
            app.logger.warning(
                "Ollama повернув некоректний кореневий "
                "тип структури завдань."
            )

            return []

        tasks = parsed.get(
            "tasks",
            [],
        )

        return normalize_ai_trainer_tasks(
            tasks=tasks,
            context=context,
            web_context=web_context,
            source_mode="local_ai",
            ai_prompt=prompt_json,
            ai_raw_output=raw_output,
            max_tasks=normalized_count,
        )

    except requests.RequestException:
        app.logger.exception(
            "Мережева помилка під час звернення "
            "до локального Ollama API."
        )

        return []

    except (TypeError, ValueError):
        app.logger.exception(
            "Помилка обробки результату локальної "
            "ШІ-генерації завдань."
        )

        return []


def normalize_trainer_option_text(
    value,
) -> str:
    """Нормалізує один варіант відповіді тренувального завдання."""
    return str(
        value or ""
    ).strip()[:TRAINER_TASK_OPTION_MAX_LENGTH]


def normalize_ai_trainer_tasks(
    tasks,
    context,
    web_context,
    source_mode,
    ai_prompt="",
    ai_raw_output="",
    max_tasks=5,
) -> list[dict]:
    """
    Перевіряє та нормалізує недовірений результат мовної моделі.

    Навіть за використання Structured Outputs семантичні правила
    перевіряються локально: допустимий тип завдання, кількість
    варіантів, наявність правильної відповіді та довжина полів.
    """
    if not isinstance(
        tasks,
        list,
    ):
        return []

    if not isinstance(
        context,
        dict,
    ):
        context = {}

    normalized_max_tasks = normalize_trainer_task_count(
        max_tasks
    )

    if normalized_max_tasks == 0:
        return []

    topic_slug = str(
        context.get(
            "topic_slug",
            "verilog_basics",
        )
        or "verilog_basics"
    ).strip().lower()

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    error_type = str(
        main_error.get(
            "error_type",
            "",
        )
        or ""
    ).strip().upper()

    competency_id = get_trainer_competency_id(
        topic_slug
    )

    source = get_preferred_trainer_source(
        web_context
    )

    normalized_source_mode = str(
        source_mode or ""
    ).strip().lower()

    if normalized_source_mode not in {
        "local_ai",
        "openai_ai",
    }:
        normalized_source_mode = "local_ai"

    prepared = []

    for task in tasks:
        if not isinstance(
            task,
            dict,
        ):
            continue

        task_type = str(
            task.get(
                "task_type",
                "single_choice",
            )
            or "single_choice"
        ).strip().lower()

        if task_type not in TRAINER_ALLOWED_TASK_TYPES:
            continue

        title = str(
            task.get(
                "title",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_TITLE_MAX_LENGTH]

        prompt = str(
            task.get(
                "prompt",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_PROMPT_MAX_LENGTH]

        code_snippet = str(
            task.get(
                "code_snippet",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_CODE_MAX_LENGTH]

        explanation = str(
            task.get(
                "explanation",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_EXPLANATION_MAX_LENGTH]

        difficulty = str(
            task.get(
                "difficulty",
                "basic",
            )
            or "basic"
        ).strip().lower()

        if difficulty not in TRAINER_ALLOWED_DIFFICULTIES:
            difficulty = "basic"

        if not title or not prompt:
            continue

        raw_options = task.get(
            "options",
            [],
        )

        if not isinstance(
            raw_options,
            list,
        ):
            continue

        correct_answer = normalize_trainer_option_text(
            task.get(
                "correct_answer",
                ""
            )
        )

        if not correct_answer:
            continue

        # Варіанти нормалізуються та дедуплікуються до перевірки
        # правильної відповіді, щоб локальна модель не могла
        # створити дві однакові альтернативи.
        unique_options = []
        seen_options = set()

        for option in raw_options:
            normalized_option = normalize_trainer_option_text(
                option
            )

            if not normalized_option:
                continue

            option_key = normalized_option.casefold()

            if option_key in seen_options:
                continue

            seen_options.add(
                option_key
            )

            unique_options.append(
                normalized_option
            )

        matching_options = [
            option
            for option in unique_options
            if option == correct_answer
        ]

        if len(
            matching_options
        ) != 1:
            continue

        if len(
            unique_options
        ) < 2:
            continue

        # Якщо модель повернула більше дозволеної кількості варіантів,
        # правильна відповідь гарантовано зберігається після обрізання.
        if len(
            unique_options
        ) > TRAINER_MAX_OPTIONS:
            if (
                correct_answer
                in unique_options[
                    :TRAINER_MAX_OPTIONS
                ]
            ):
                unique_options = unique_options[
                    :TRAINER_MAX_OPTIONS
                ]

            else:
                unique_options = (
                    unique_options[
                        :TRAINER_MAX_OPTIONS - 1
                    ]
                    + [
                        correct_answer
                    ]
                )

        if correct_answer not in unique_options:
            continue

        prepared.append({
            "topic_slug": topic_slug,
            "competency": competency_id,
            "error_type": error_type,
            "title": title,
            "task_type": task_type,
            "difficulty": difficulty,
            "prompt": prompt,
            "code_snippet": code_snippet,
            "options": unique_options,
            "correct_answer": correct_answer,
            "explanation": explanation,

            # Навчальне джерело є матеріалом для повторення,
            # а не джерелом дослівно скопійованого завдання.
            "source_title": str(
                source.get(
                    "source_title",
                    "",
                )
                or ""
            ).strip(),
            "source_url": str(
                source.get(
                    "source_url",
                    "",
                )
                or ""
            ).strip(),
            "source_available": bool(
                source.get(
                    "ok",
                    False,
                )
            ),
            "source_mode": normalized_source_mode,

            # Повний prompt та raw output за замовчуванням
            # не дублюються у студентській БД.
            "ai_prompt": prepare_trainer_ai_debug_text(
                ai_prompt
            ),
            "ai_raw_output": prepare_trainer_ai_debug_text(
                ai_raw_output
            ),
        })

        if (
            len(prepared)
            >= normalized_max_tasks
        ):
            break

    return prepared


def merge_trainer_task_sets(
    primary_tasks,
    fallback_tasks,
    count,
) -> list[dict]:
    """
    Об'єднує ШІ-згенеровані та шаблонні завдання
    без простого дублювання однакових prompt.
    """
    normalized_count = normalize_trainer_task_count(
        count
    )

    if normalized_count == 0:
        return []

    combined = []
    seen = set()

    for task_group in (
        primary_tasks,
        fallback_tasks,
    ):
        if not isinstance(
            task_group,
            list,
        ):
            continue

        for task in task_group:
            if not isinstance(
                task,
                dict,
            ):
                continue

            identity = (
                str(
                    task.get(
                        "title",
                        "",
                    )
                    or ""
                ).strip().casefold(),
                str(
                    task.get(
                        "prompt",
                        "",
                    )
                    or ""
                ).strip().casefold(),
            )

            if not any(
                identity
            ):
                continue

            if identity in seen:
                continue

            seen.add(
                identity
            )

            combined.append(
                task
            )

            if (
                len(combined)
                >= normalized_count
            ):
                return combined

    return combined


def normalize_trainer_ai_mode(
    mode,
) -> str:
    """Нормалізує режим генерації завдань тренажера."""
    normalized_mode = str(
        mode or ""
    ).strip().lower()

    if normalized_mode in TRAINER_ALLOWED_AI_MODES:
        return normalized_mode

    app.logger.warning(
        "Невідоме значення TRAINER_AI_MODE=%r. "
        "Використано шаблонний режим.",
        mode,
    )

    return "template"


def generate_personal_trainer_tasks(
    username,
    count=5,
) -> list[dict]:
    """
    Формує персоналізований набір тренувальних завдань.

    У режимі local спочатку використовується Ollama.
    Якщо модель повернула недостатню кількість коректних завдань,
    набір доповнюється детермінованими шаблонними завданнями.
    """
    normalized_count = normalize_trainer_task_count(
        count
    )

    if normalized_count == 0:
        return []

    context = get_student_trainer_context(
        username
    )

    topic_slug = str(
        context.get(
            "topic_slug",
            "verilog_basics",
        )
        or "verilog_basics"
    ).strip().lower()

    web_context = collect_trainer_web_context(
        topic_slug,
        limit=3,
    )

    mode = normalize_trainer_ai_mode(
        TRAINER_AI_MODE
    )

    generated_tasks = []

    if mode == "local":
        generated_tasks = generate_trainer_tasks_with_ollama(
            context=context,
            web_context=web_context,
            count=normalized_count,
        )

    if (
        mode == "template"
        or len(
            generated_tasks
        ) < normalized_count
    ):
        template_tasks = generate_template_trainer_tasks(
            context=context,
            web_context=web_context,
            count=normalized_count,
        )

        generated_tasks = merge_trainer_task_sets(
            primary_tasks=generated_tasks,
            fallback_tasks=template_tasks,
            count=normalized_count,
        )

    return generated_tasks


def normalize_trainer_task_for_storage(
    task,
) -> dict | None:
    """
    Виконує фінальну валідацію тренувального завдання
    безпосередньо перед записом до SQLite.
    """
    if not isinstance(
        task,
        dict,
    ):
        return None

    task_type = str(
        task.get(
            "task_type",
            "single_choice",
        )
        or "single_choice"
    ).strip().lower()

    if task_type not in TRAINER_ALLOWED_TASK_TYPES:
        return None

    difficulty = str(
        task.get(
            "difficulty",
            "basic",
        )
        or "basic"
    ).strip().lower()

    if difficulty not in TRAINER_ALLOWED_DIFFICULTIES:
        difficulty = "basic"

    title = str(
        task.get(
            "title",
            "",
        )
        or ""
    ).strip()[:TRAINER_TASK_TITLE_MAX_LENGTH]

    prompt = str(
        task.get(
            "prompt",
            "",
        )
        or ""
    ).strip()[:TRAINER_TASK_PROMPT_MAX_LENGTH]

    if not title or not prompt:
        return None

    raw_options = task.get(
        "options",
        [],
    )

    if not isinstance(
        raw_options,
        list,
    ):
        return None

    options = []

    for option in raw_options[
        :TRAINER_MAX_OPTIONS
    ]:
        normalized_option = normalize_trainer_option_text(
            option
        )

        if (
            normalized_option
            and normalized_option not in options
        ):
            options.append(
                normalized_option
            )

    correct_answer = normalize_trainer_option_text(
        task.get(
            "correct_answer",
            "",
        )
    )

    if (
        len(options) < 2
        or correct_answer not in options
    ):
        return None

    source_mode = str(
        task.get(
            "source_mode",
            "template",
        )
        or "template"
    ).strip().lower()

    if source_mode not in {
        "template",
        "local_ai",
        "openai_ai",
    }:
        source_mode = "template"

    return {
        "source_mode": source_mode,
        "topic_slug": str(
            task.get(
                "topic_slug",
                "verilog_basics",
            )
            or "verilog_basics"
        ).strip(),
        "competency": str(
            task.get(
                "competency",
                "",
            )
            or ""
        ).strip(),
        "error_type": str(
            task.get(
                "error_type",
                "",
            )
            or ""
        ).strip().upper(),
        "title": title,
        "task_type": task_type,
        "difficulty": difficulty,
        "prompt": prompt,
        "code_snippet": str(
            task.get(
                "code_snippet",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_CODE_MAX_LENGTH],
        "options": options,
        "correct_answer": correct_answer,
        "explanation": str(
            task.get(
                "explanation",
                "",
            )
            or ""
        ).strip()[:TRAINER_TASK_EXPLANATION_MAX_LENGTH],
        "source_title": str(
            task.get(
                "source_title",
                "",
            )
            or ""
        ).strip()[:300],
        "source_url": str(
            task.get(
                "source_url",
                "",
            )
            or ""
        ).strip()[:1000],
        "ai_prompt": prepare_trainer_ai_debug_text(
            task.get(
                "ai_prompt",
                "",
            )
        ),
        "ai_raw_output": prepare_trainer_ai_debug_text(
            task.get(
                "ai_raw_output",
                "",
            )
        ),
    }


def save_trainer_tasks(
    username,
    tasks,
) -> list[int]:
    """
    Зберігає валідовані тренувальні завдання студента в SQLite.

    Усі завдання одного набору записуються в межах однієї
    транзакції. У разі помилки виконується rollback,
    щоб не залишати частково сформований набір.
    """
    normalized_username = str(
        username or ""
    ).strip()

    if (
        not normalized_username
        or not isinstance(
            tasks,
            list,
        )
    ):
        return []

    prepared_tasks = []

    for task in tasks:
        prepared_task = normalize_trainer_task_for_storage(
            task
        )

        if prepared_task:
            prepared_tasks.append(
                prepared_task
            )

    if not prepared_tasks:
        return []

    conn = get_db()

    saved_ids = []

    try:
        for task in prepared_tasks:
            options_json = json.dumps(
                task["options"],
                ensure_ascii=False,
            )

            correct_answer_json = json.dumps(
                {
                    "answer": task[
                        "correct_answer"
                    ]
                },
                ensure_ascii=False,
            )

            cursor = conn.execute(
                """
                INSERT INTO trainer_tasks (
                    username,
                    source_mode,
                    topic_slug,
                    competency,
                    error_type,
                    title,
                    task_type,
                    difficulty,
                    prompt,
                    code_snippet,
                    options_json,
                    correct_answer_json,
                    explanation,
                    source_title,
                    source_url,
                    ai_prompt,
                    ai_raw_output,
                    status,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    normalized_username,
                    task["source_mode"],
                    task["topic_slug"],
                    task["competency"],
                    task["error_type"],
                    task["title"],
                    task["task_type"],
                    task["difficulty"],
                    task["prompt"],
                    task["code_snippet"],
                    options_json,
                    correct_answer_json,
                    task["explanation"],
                    task["source_title"],
                    task["source_url"],
                    task["ai_prompt"],
                    task["ai_raw_output"],
                    "active",
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                ),
            )

            saved_ids.append(
                cursor.lastrowid
            )

        conn.commit()

        return saved_ids

    except (
        sqlite3.Error,
        TypeError,
        ValueError,
    ):
        conn.rollback()

        app.logger.exception(
            "Не вдалося зберегти набір "
            "тренувальних завдань."
        )

        return []

    finally:
        conn.close()


# ============================================================
# Тренажер: формування персонального набору завдань
# ============================================================

def generate_personal_trainer_tasks(
    username,
    count=5,
    context=None,
) -> list[dict]:
    """
    Формує персоналізований набір тренувальних завдань.

    Якщо готовий навчальний контекст уже передано викликаючим кодом,
    він повторно не завантажується з бази даних.
    """
    normalized_count = normalize_trainer_task_count(
        count
    )

    if normalized_count == 0:
        return []

    normalized_username = str(
        username or ""
    ).strip()

    if not isinstance(
        context,
        dict,
    ):
        context = get_student_trainer_context(
            normalized_username
        )

    topic_slug = str(
        context.get(
            "topic_slug",
            "verilog_basics",
        )
        or "verilog_basics"
    ).strip().lower()

    web_context = collect_trainer_web_context(
        topic_slug,
        limit=3,
    )

    mode = normalize_trainer_ai_mode(
        TRAINER_AI_MODE
    )

    generated_tasks = []

    if mode == "local":
        generated_tasks = generate_trainer_tasks_with_ollama(
            context=context,
            web_context=web_context,
            count=normalized_count,
        )

    if (
        mode == "template"
        or len(generated_tasks) < normalized_count
    ):
        template_tasks = generate_template_trainer_tasks(
            context=context,
            web_context=web_context,
            count=normalized_count,
        )

        generated_tasks = merge_trainer_task_sets(
            primary_tasks=generated_tasks,
            fallback_tasks=template_tasks,
            count=normalized_count,
        )

    return generated_tasks


# ============================================================
# Тренажер: створення сесії
# ============================================================

class ActiveTrainerSessionExists(Exception):
    """Сигналізує, що студент уже має активну сесію тренажера."""

    def __init__(
        self,
        session_id,
    ):
        self.session_id = session_id

        super().__init__(
            f"Active trainer session: {session_id}"
        )


def determine_trainer_session_source_mode(
    tasks,
) -> str:
    """
    Визначає походження набору тренувальних завдань.

    Якщо набір містить як ШІ-згенеровані, так і шаблонні
    завдання, сесія позначається як mixed.
    """
    modes = {
        str(
            task.get(
                "source_mode",
                "template",
            )
            or "template"
        ).strip().lower()
        for task in tasks
        if isinstance(
            task,
            dict,
        )
    }

    modes.discard(
        ""
    )

    if not modes:
        return "template"

    if len(modes) == 1:
        return next(
            iter(modes)
        )

    return "mixed"


def insert_trainer_task_record(
    conn,
    username,
    task,
    created_at,
):
    """
    Зберігає одне попередньо валідоване завдання тренажера.

    Повертає id нового запису або None, якщо завдання
    не проходить фінальну перевірку.
    """
    prepared_task = normalize_trainer_task_for_storage(
        task
    )

    if not prepared_task:
        return None

    options_json = json.dumps(
        prepared_task["options"],
        ensure_ascii=False,
    )

    correct_answer_json = json.dumps(
        {
            "answer": prepared_task[
                "correct_answer"
            ]
        },
        ensure_ascii=False,
    )

    cursor = conn.execute(
        """
        INSERT INTO trainer_tasks (
            username,
            source_mode,
            topic_slug,
            competency,
            error_type,
            title,
            task_type,
            difficulty,
            prompt,
            code_snippet,
            options_json,
            correct_answer_json,
            explanation,
            source_title,
            source_url,
            ai_prompt,
            ai_raw_output,
            status,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            username,
            prepared_task["source_mode"],
            prepared_task["topic_slug"],
            prepared_task["competency"],
            prepared_task["error_type"],
            prepared_task["title"],
            prepared_task["task_type"],
            prepared_task["difficulty"],
            prepared_task["prompt"],
            prepared_task["code_snippet"],
            options_json,
            correct_answer_json,
            prepared_task["explanation"],
            prepared_task["source_title"],
            prepared_task["source_url"],
            prepared_task["ai_prompt"],
            prepared_task["ai_raw_output"],
            "active",
            created_at,
        ),
    )

    return cursor.lastrowid


def create_trainer_session(
    username,
    tasks,
    context,
):
    """
    Створює персональну сесію тренажера та пов'язаний набір завдань.

    Сесія, завдання та зв'язки між ними створюються в межах
    однієї транзакції. Перед створенням повторно перевіряється
    відсутність іншої активної сесії користувача.
    """
    normalized_username = str(
        username or ""
    ).strip()

    if (
        not normalized_username
        or not isinstance(
            tasks,
            list,
        )
        or not tasks
    ):
        return None

    if not isinstance(
        context,
        dict,
    ):
        context = {}

    # Фінальна валідація виконується ще до відкриття транзакції.
    prepared_tasks = []

    for task in tasks:
        prepared_task = normalize_trainer_task_for_storage(
            task
        )

        if prepared_task:
            prepared_tasks.append(
                prepared_task
            )

    if not prepared_tasks:
        return None

    main_error = context.get(
        "main_error"
    )

    if not isinstance(
        main_error,
        dict,
    ):
        main_error = {}

    topic_slug = str(
        context.get(
            "topic_slug",
            prepared_tasks[0].get(
                "topic_slug",
                "verilog_basics",
            ),
        )
        or "verilog_basics"
    ).strip().lower()

    competency = get_trainer_competency_id(
        topic_slug
    )

    error_type = str(
        main_error.get(
            "error_type",
            prepared_tasks[0].get(
                "error_type",
                "",
            ),
        )
        or ""
    ).strip().upper()

    error_title = str(
        main_error.get(
            "error_title",
            "",
        )
        or ""
    ).strip()

    if error_title:
        title = (
            f"Тренувальний тест: {error_title}"
        )
    else:
        title = (
            "Тренувальний тест з Verilog/FPGA"
        )

    source_mode = determine_trainer_session_source_mode(
        prepared_tasks
    )

    created_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_db()

    try:
        # BEGIN IMMEDIATE серіалізує створення активних сесій
        # у SQLite та зменшує ризик двох паралельних POST-запитів,
        # що одночасно створять два активні тести одному студенту.
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        active_session = conn.execute(
            """
            SELECT id
            FROM trainer_sessions
            WHERE username = ?
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (normalized_username,),
        ).fetchone()

        if active_session:
            existing_session_id = int(
                active_session["id"]
            )

            conn.rollback()

            raise ActiveTrainerSessionExists(
                existing_session_id
            )

        cursor = conn.execute(
            """
            INSERT INTO trainer_sessions (
                username,
                topic_slug,
                competency,
                error_type,
                error_title,
                title,
                source_mode,
                status,
                total_questions,
                correct_count,
                score,
                passed,
                created_at,
                submitted_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                normalized_username,
                topic_slug,
                competency,
                error_type,
                error_title,
                title,
                source_mode,
                "active",
                len(prepared_tasks),
                0,
                0,
                0,
                created_at,
                "",
            ),
        )

        trainer_session_id = cursor.lastrowid

        for order_number, task in enumerate(
            prepared_tasks,
            start=1,
        ):
            task_id = insert_trainer_task_record(
                conn=conn,
                username=normalized_username,
                task=task,
                created_at=created_at,
            )

            if task_id is None:
                raise ValueError(
                    "Trainer task failed final validation."
                )

            conn.execute(
                """
                INSERT INTO trainer_session_questions (
                    session_id,
                    task_id,
                    order_number
                )
                VALUES (?, ?, ?)
                """,
                (
                    trainer_session_id,
                    task_id,
                    order_number,
                ),
            )

        conn.commit()

        return trainer_session_id

    except ActiveTrainerSessionExists:
        raise

    except (
        sqlite3.Error,
        TypeError,
        ValueError,
    ):
        conn.rollback()

        app.logger.exception(
            "Не вдалося створити сесію тренажера "
            "для користувача %s.",
            normalized_username,
        )

        return None

    finally:
        conn.close()


def get_active_trainer_session_id(
    username,
):
    """Повертає id поточної активної сесії тренажера студента."""
    normalized_username = str(
        username or ""
    ).strip()

    if not normalized_username:
        return None

    conn = get_db()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM trainer_sessions
            WHERE username = ?
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (normalized_username,),
        ).fetchone()

        if not row:
            return None

        return int(
            row["id"]
        )

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час пошуку "
            "активної сесії тренажера."
        )

        return None

    finally:
        conn.close()


# ============================================================
# Тренажер: генерація нового тесту
# ============================================================

@app.route(
    "/student/trainer/generate",
    methods=["POST"],
)
@login_required
def student_trainer_generate():
    """
    Генерує нову персональну сесію тренажера для студента.

    Одночасно студент може мати лише одну активну
    незавершену сесію.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user[
        "username"
    ]

    active_session_id = get_active_trainer_session_id(
        username
    )

    if active_session_id is not None:
        flash(
            "У вас уже є незавершений тренувальний тест. "
            "Спочатку завершіть його."
        )

        return redirect(
            url_for(
                "student_trainer_session",
                session_id=active_session_id,
            )
        )

    # Один і той самий контекст використовується і для генерації
    # завдань, і для створення сесії, щоб уникнути розбіжностей
    # між темою тесту та фактично згенерованими питаннями.
    context = get_student_trainer_context(
        username
    )

    tasks = generate_personal_trainer_tasks(
        username=username,
        count=7,
        context=context,
    )

    if not tasks:
        flash(
            "Не вдалося сформувати тренувальний тест."
        )

        return redirect(
            url_for("student_trainer")
        )

    try:
        trainer_session_id = create_trainer_session(
            username=username,
            tasks=tasks,
            context=context,
        )

    except ActiveTrainerSessionExists as error:
        flash(
            "У вас уже є незавершений тренувальний тест. "
            "Спочатку завершіть його."
        )

        return redirect(
            url_for(
                "student_trainer_session",
                session_id=error.session_id,
            )
        )

    if trainer_session_id is None:
        flash(
            "Не вдалося створити тренувальний тест "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("student_trainer")
        )

    flash(
        "Тренувальний тест сформовано."
    )

    return redirect(
        url_for(
            "student_trainer_session",
            session_id=trainer_session_id,
        )
    )


# ============================================================
# Тренажер: перегляд сесії студентом
# ============================================================

def parse_trainer_options_json(
    options_json,
    task_id=None,
) -> list[str]:
    """
    Безпечно декодує варіанти відповіді з SQLite.

    Некоректні legacy-дані не повинні призводити
    до HTTP 500 під час відкриття тренувального тесту.
    """
    try:
        options = json.loads(
            options_json or "[]"
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        app.logger.warning(
            "Некоректний options_json у завданні тренажера %s.",
            task_id,
        )

        return []

    if not isinstance(
        options,
        list,
    ):
        app.logger.warning(
            "options_json завдання тренажера %s "
            "не містить JSON-масив.",
            task_id,
        )

        return []

    prepared_options = []

    for option in options[
        :TRAINER_MAX_OPTIONS
    ]:
        normalized_option = normalize_trainer_option_text(
            option
        )

        if normalized_option:
            prepared_options.append(
                normalized_option
            )

    return prepared_options


@app.route(
    "/student/trainer/session/<int:session_id>"
)
@login_required
def student_trainer_session(session_id):
    """
    Відображає тренувальну сесію, що належить поточному студенту.

    До student-facing контексту навмисно не передаються
    correct_answer_json, explanation, ai_prompt або ai_raw_output.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user[
        "username"
    ]

    conn = get_db()

    try:
        trainer_session = conn.execute(
            """
            SELECT
                id,
                username,
                topic_slug,
                competency,
                error_type,
                error_title,
                title,
                source_mode,
                status,
                total_questions,
                correct_count,
                score,
                passed,
                created_at,
                submitted_at
            FROM trainer_sessions
            WHERE id = ?
              AND username = ?
            """,
            (
                session_id,
                username,
            ),
        ).fetchone()

        if not trainer_session:
            abort(404)

        # Вибираються лише поля, безпечні для показу студенту.
        # correct_answer_json, explanation та службові ШІ-поля
        # залишаються на сервері й не передаються до Jinja-шаблону.
        questions = conn.execute(
            """
            SELECT
                trainer_tasks.id,
                trainer_tasks.source_mode,
                trainer_tasks.topic_slug,
                trainer_tasks.competency,
                trainer_tasks.error_type,
                trainer_tasks.title,
                trainer_tasks.task_type,
                trainer_tasks.difficulty,
                trainer_tasks.prompt,
                trainer_tasks.code_snippet,
                trainer_tasks.options_json,
                trainer_tasks.source_title,
                trainer_tasks.source_url,
                trainer_tasks.status,

                trainer_session_questions.order_number

            FROM trainer_session_questions

            JOIN trainer_tasks
                ON trainer_tasks.id =
                   trainer_session_questions.task_id

            WHERE trainer_session_questions.session_id = ?

            ORDER BY
                trainer_session_questions.order_number ASC,
                trainer_tasks.id ASC
            """,
            (session_id,),
        ).fetchall()

        # trainer_session_answers містить correct_answer,
        # тому SELECT * у student-facing route не використовується.
        answers = conn.execute(
            """
            SELECT
                id,
                task_id,
                selected_option,
                is_correct,
                feedback,
                created_at
            FROM trainer_session_answers
            WHERE session_id = ?
              AND username = ?
            """,
            (
                session_id,
                username,
            ),
        ).fetchall()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "сесії тренажера %s для користувача %s.",
            session_id,
            username,
        )

        flash(
            "Не вдалося завантажити тренувальний тест "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("student_trainer")
        )

    finally:
        conn.close()

    answers_map = {
        answer["task_id"]: answer
        for answer in answers
    }

    prepared_questions = []

    for question in questions:
        task_id = question[
            "id"
        ]

        options = parse_trainer_options_json(
            question["options_json"],
            task_id=task_id,
        )

        prepared_questions.append({
            "task": question,
            "options": options,
            "answer": answers_map.get(
                task_id
            ),
        })

    return render_template(
        "student/trainer_session.html",
        trainer_session=trainer_session,
        questions=prepared_questions,
    )


# ============================================================
# Тренажер: перевірка відповідей студента
# ============================================================

TRAINER_PASS_SCORE = 70


def parse_trainer_correct_answer_json(
    correct_answer_json,
    task_id=None,
) -> str:
    """
    Безпечно отримує еталонну відповідь із серверного JSON.

    Функція використовується лише на серверному боці.
    correct_answer_json не повинен передаватися до student-facing
    Jinja-шаблонів до завершення перевірки.
    """
    try:
        correct_data = json.loads(
            correct_answer_json or "{}"
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        app.logger.warning(
            "Некоректний correct_answer_json "
            "у завданні тренажера %s.",
            task_id,
        )

        return ""

    if not isinstance(
        correct_data,
        dict,
    ):
        return ""

    return str(
        correct_data.get(
            "answer",
            "",
        )
        or ""
    ).strip()


def get_trainer_session_for_task(
    conn,
    username,
    task_id,
):
    """
    Перевіряє, чи пов'язане завдання з тренувальною сесією студента.

    Завдання, що належить сесії, повинно виконуватися лише
    через інтерфейс цієї сесії, щоб студент не міг отримати
    правильну відповідь через окремий standalone-route.
    """
    return conn.execute(
        """
        SELECT
            trainer_sessions.id,
            trainer_sessions.status
        FROM trainer_session_questions

        JOIN trainer_sessions
            ON trainer_sessions.id =
               trainer_session_questions.session_id

        WHERE trainer_session_questions.task_id = ?
          AND trainer_sessions.username = ?

        ORDER BY trainer_sessions.id DESC
        LIMIT 1
        """,
        (
            task_id,
            username,
        ),
    ).fetchone()


def build_trainer_answer_feedback(
    is_correct,
    correct_answer,
    explanation,
) -> str:
    """Формує україномовний зворотний зв'язок після перевірки."""
    normalized_explanation = str(
        explanation or ""
    ).strip()

    if is_correct:
        feedback = "Правильно."

    else:
        feedback = (
            f"Неправильно. Правильна відповідь: "
            f"{correct_answer}."
        )

    if normalized_explanation:
        feedback = (
            f"{feedback} "
            f"{normalized_explanation}"
        )

    return feedback


# ============================================================
# Тренажер: окреме тренувальне завдання
# ============================================================

@app.route(
    "/student/trainer/task/<int:task_id>"
)
@login_required
def student_trainer_task(task_id):
    """
    Відображає окреме тренувальне завдання студента.

    Еталонна відповідь, пояснення та службові ШІ-дані
    навмисно не вибираються з БД для student-facing сторінки.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user["username"]

    conn = get_db()

    try:
        # Вибираються лише поля, безпечні для передачі
        # до студентського Jinja-шаблону.
        task = conn.execute(
            """
            SELECT
                id,
                username,
                source_mode,
                topic_slug,
                competency,
                error_type,
                title,
                task_type,
                difficulty,
                prompt,
                code_snippet,
                options_json,
                source_title,
                source_url,
                status,
                created_at
            FROM trainer_tasks
            WHERE id = ?
              AND username = ?
            """,
            (
                task_id,
                username,
            ),
        ).fetchone()

        if not task:
            abort(404)

        session_link = get_trainer_session_for_task(
            conn=conn,
            username=username,
            task_id=task_id,
        )

        if session_link:
            # Завдання, що входить до тесту, не можна виконувати
            # через standalone-route, оскільки окремий submit
            # розкриває правильну відповідь одразу після спроби.
            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_link["id"],
                )
            )

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "завдання тренажера %s.",
            task_id,
        )

        flash(
            "Не вдалося завантажити завдання "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("student_trainer")
        )

    finally:
        conn.close()

    if task["status"] != "active":
        flash(
            "Це тренувальне завдання більше недоступне."
        )

        return redirect(
            url_for("student_trainer")
        )

    options = parse_trainer_options_json(
        task["options_json"],
        task_id=task_id,
    )

    if len(options) < 2:
        app.logger.warning(
            "Завдання тренажера %s не містить "
            "коректного набору варіантів відповіді.",
            task_id,
        )

        flash(
            "Завдання має некоректну конфігурацію."
        )

        return redirect(
            url_for("student_trainer")
        )

    return render_template(
        "student/trainer_task.html",
        task=task,
        options=options,
    )


@app.route(
    "/student/trainer/task/<int:task_id>/submit",
    methods=["POST"],
)
@login_required
def student_trainer_task_submit(task_id):
    """
    Перевіряє відповідь на окреме тренувальне завдання.

    Відповідь студента перевіряється виключно на сервері.
    Завдання, що входить до trainer session, через цей route
    не перевіряється.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user["username"]

    selected_option = str(
        request.form.get(
            "selected_option",
            "",
        )
        or ""
    ).strip()

    conn = get_db()

    try:
        task = conn.execute(
            """
            SELECT
                id,
                username,
                task_type,
                options_json,
                correct_answer_json,
                explanation,
                status
            FROM trainer_tasks
            WHERE id = ?
              AND username = ?
            """,
            (
                task_id,
                username,
            ),
        ).fetchone()

        if not task:
            abort(404)

        session_link = get_trainer_session_for_task(
            conn=conn,
            username=username,
            task_id=task_id,
        )

        if session_link:
            flash(
                "Це завдання входить до тренувального тесту. "
                "Надайте відповідь на сторінці тесту."
            )

            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_link["id"],
                )
            )

        if task["status"] != "active":
            flash(
                "Це тренувальне завдання більше недоступне."
            )

            return redirect(
                url_for("student_trainer")
            )

        options = parse_trainer_options_json(
            task["options_json"],
            task_id=task_id,
        )

        if (
            not selected_option
            or selected_option not in options
        ):
            flash(
                "Оберіть один із запропонованих "
                "варіантів відповіді."
            )

            return redirect(
                url_for(
                    "student_trainer_task",
                    task_id=task_id,
                )
            )

        correct_answer = parse_trainer_correct_answer_json(
            task["correct_answer_json"],
            task_id=task_id,
        )

        if (
            not correct_answer
            or correct_answer not in options
        ):
            app.logger.error(
                "Завдання тренажера %s містить "
                "некоректну еталонну відповідь.",
                task_id,
            )

            flash(
                "Не вдалося перевірити завдання "
                "через внутрішню помилку системи."
            )

            return redirect(
                url_for("student_trainer")
            )

        is_correct = int(
            selected_option == correct_answer
        )

        score = (
            100
            if is_correct
            else 0
        )

        feedback = build_trainer_answer_feedback(
            is_correct=bool(is_correct),
            correct_answer=correct_answer,
            explanation=task["explanation"],
        )

        conn.execute(
            """
            INSERT INTO trainer_attempts (
                username,
                task_id,
                answer_text,
                selected_option,
                is_correct,
                score,
                feedback,
                created_at
            )
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
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        conn.commit()

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час перевірки "
            "завдання тренажера %s.",
            task_id,
        )

        flash(
            "Не вдалося зберегти відповідь "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "student_trainer_task",
                task_id=task_id,
            )
        )

    finally:
        conn.close()

    flash(
        feedback
    )

    return redirect(
        url_for(
            "student_trainer_task",
            task_id=task_id,
        )
    )


# ============================================================
# Тренажер: завершення сесійного тесту
# ============================================================

@app.route(
    "/student/trainer/session/<int:session_id>/submit",
    methods=["POST"],
)
@login_required
def student_trainer_session_submit(session_id):
    """
    Перевіряє всі відповіді активної тренувальної сесії.

    Перевірка, збереження відповідей і завершення сесії
    виконуються в одній SQLite-транзакції. Правильні відповіді
    визначаються лише сервером.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user["username"]

    conn = get_db()

    try:
        # Блокування запису запобігає паралельному завершенню
        # тієї самої сесії двома POST-запитами.
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        trainer_session = conn.execute(
            """
            SELECT
                id,
                username,
                status,
                total_questions
            FROM trainer_sessions
            WHERE id = ?
              AND username = ?
            """,
            (
                session_id,
                username,
            ),
        ).fetchone()

        if not trainer_session:
            conn.rollback()
            abort(404)

        if trainer_session["status"] == "completed":
            conn.rollback()

            flash(
                "Цей тренувальний тест уже завершено. "
                "Змінити відповіді неможливо."
            )

            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_id,
                )
            )

        if trainer_session["status"] != "active":
            conn.rollback()

            flash(
                "Цей тренувальний тест більше не є активним."
            )

            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_id,
                )
            )

        # Це server-side query: правильна відповідь і пояснення
        # потрібні для перевірки, але вони не передаються клієнту.
        questions = conn.execute(
            """
            SELECT
                trainer_tasks.id,
                trainer_tasks.task_type,
                trainer_tasks.options_json,
                trainer_tasks.correct_answer_json,
                trainer_tasks.explanation,

                trainer_session_questions.order_number

            FROM trainer_session_questions

            JOIN trainer_tasks
                ON trainer_tasks.id =
                   trainer_session_questions.task_id

            WHERE trainer_session_questions.session_id = ?
              AND trainer_tasks.username = ?

            ORDER BY
                trainer_session_questions.order_number ASC,
                trainer_tasks.id ASC
            """,
            (
                session_id,
                username,
            ),
        ).fetchall()

        total_questions = len(
            questions
        )

        if total_questions == 0:
            conn.rollback()

            app.logger.error(
                "Сесія тренажера %s не містить завдань.",
                session_id,
            )

            flash(
                "Тренувальний тест має некоректну конфігурацію."
            )

            return redirect(
                url_for("student_trainer")
            )

        checked_answers = []
        unanswered_tasks = []

        for question in questions:
            task_id = int(
                question["id"]
            )

            options = parse_trainer_options_json(
                question["options_json"],
                task_id=task_id,
            )

            correct_answer = parse_trainer_correct_answer_json(
                question["correct_answer_json"],
                task_id=task_id,
            )

            # Некоректна серверна конфігурація не повинна
            # автоматично перетворюватися на неправильну
            # відповідь студента.
            if (
                len(options) < 2
                or not correct_answer
                or correct_answer not in options
            ):
                conn.rollback()

                app.logger.error(
                    "Некоректна конфігурація завдання %s "
                    "у сесії тренажера %s.",
                    task_id,
                    session_id,
                )

                flash(
                    "Не вдалося перевірити тест "
                    "через внутрішню помилку системи."
                )

                return redirect(
                    url_for(
                        "student_trainer_session",
                        session_id=session_id,
                    )
                )

            selected_option = str(
                request.form.get(
                    f"answer_{task_id}",
                    "",
                )
                or ""
            ).strip()

            if (
                not selected_option
                or selected_option not in options
            ):
                unanswered_tasks.append(
                    task_id
                )

                continue

            is_correct = int(
                selected_option == correct_answer
            )

            feedback = build_trainer_answer_feedback(
                is_correct=bool(is_correct),
                correct_answer=correct_answer,
                explanation=question["explanation"],
            )

            checked_answers.append({
                "task_id": task_id,
                "selected_option": selected_option,
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "feedback": feedback,
            })

        # Відсутня або підмінена відповідь не зараховується
        # автоматично як помилка: студенту пропонується завершити тест.
        if unanswered_tasks:
            conn.rollback()

            flash(
                "Надайте відповідь на кожне питання "
                "перед завершенням тесту."
            )

            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_id,
                )
            )

        correct_count = sum(
            answer["is_correct"]
            for answer in checked_answers
        )

        score = round(
            correct_count
            * 100
            / total_questions
        )

        passed = int(
            score >= TRAINER_PASS_SCORE
        )

        submitted_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        for answer in checked_answers:
            # На відміну від INSERT OR REPLACE, UPSERT не видаляє
            # існуючий рядок перед вставкою, а оновлює його.
            conn.execute(
                """
                INSERT INTO trainer_session_answers (
                    session_id,
                    task_id,
                    username,
                    selected_option,
                    is_correct,
                    correct_answer,
                    feedback,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(session_id, task_id)
                DO UPDATE SET
                    username = excluded.username,
                    selected_option = excluded.selected_option,
                    is_correct = excluded.is_correct,
                    correct_answer = excluded.correct_answer,
                    feedback = excluded.feedback,
                    created_at = excluded.created_at
                """,
                (
                    session_id,
                    answer["task_id"],
                    username,
                    answer["selected_option"],
                    answer["is_correct"],
                    answer["correct_answer"],
                    answer["feedback"],
                    submitted_at,
                ),
            )

        cursor = conn.execute(
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
              AND status = 'active'
            """,
            (
                total_questions,
                correct_count,
                score,
                passed,
                submitted_at,
                session_id,
                username,
            ),
        )

        if cursor.rowcount != 1:
            conn.rollback()

            app.logger.warning(
                "Не вдалося атомарно завершити "
                "сесію тренажера %s.",
                session_id,
            )

            flash(
                "Стан тренувального тесту вже змінився. "
                "Оновіть сторінку."
            )

            return redirect(
                url_for(
                    "student_trainer_session",
                    session_id=session_id,
                )
            )

        conn.commit()

    except sqlite3.Error:
        conn.rollback()

        app.logger.exception(
            "Помилка SQLite під час завершення "
            "сесії тренажера %s.",
            session_id,
        )

        flash(
            "Не вдалося завершити тренувальний тест "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "student_trainer_session",
                session_id=session_id,
            )
        )

    finally:
        conn.close()

    if passed:
        flash(
            f"Тест завершено. Результат: {score}/100. "
            "Тест успішно пройдено."
        )
    else:
        flash(
            f"Тест завершено. Результат: {score}/100. "
            "Рекомендується пройти додаткове тренування."
        )

    return redirect(
        url_for(
            "student_trainer_session",
            session_id=session_id,
        )
    )


# =========================
# 12. Student routes
# =========================

GRADEBOOK_NON_COUNTABLE_STATUS = "SYSTEM_ERROR"


def normalize_gradebook_score(
    value,
):
    """
    Нормалізує бал для відображення в електронній заліковій книжці.

    Повертає None за відсутності коректного числового значення
    та обмежує допустимий діапазон значеннями 0–100.
    """
    if value is None:
        return None

    try:
        numeric_score = float(
            value
        )
    except (TypeError, ValueError, OverflowError):
        return None

    if (
        numeric_score != numeric_score
        or numeric_score in {
            float("inf"),
            float("-inf"),
        }
    ):
        return None

    numeric_score = max(
        0.0,
        min(
            100.0,
            numeric_score,
        ),
    )

    if numeric_score.is_integer():
        return int(
            numeric_score
        )

    return round(
        numeric_score,
        2,
    )


def get_current_student():
    """
    Повертає актуальні дані поточного студента з БД.

    Роль і статус користувача перевіряються через
    get_current_session_user(), а не лише за session cookie.
    """
    current_user = get_current_session_user()

    if not current_user:
        return None

    if current_user["role"] != "student":
        return None

    return current_user


# ============================================================
# Електронна залікова книжка
# ============================================================

@app.route("/student/gradebook")
@login_required
def student_gradebook():
    """
    Відображає електронну залікову книжку поточного студента.

    SYSTEM_ERROR не враховується як навчальна спроба та не впливає
    на автоматичний найкращий бал. Ручна оцінка викладача має
    пріоритет над автоматичним результатом.
    """
    current_student = get_current_student()

    if not current_student:
        flash(
            "Залікова книжка доступна лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_student["username"]

    conn = get_db()

    try:
        student = conn.execute(
            """
            SELECT
                username,
                full_name,
                email,
                student_group,
                role,
                status
            FROM users
            WHERE username = ?
              AND role = 'student'
              AND status = 'active'
            """,
            (username,),
        ).fetchone()

        if not student:
            flash(
                "Не вдалося знайти дані студента."
            )

            return redirect(
                url_for("index")
            )

        student_group = str(
            student["student_group"]
            or ""
        ).strip()

        # До залікової книжки включаються:
        # 1) дисципліни, призначені навчальній групі;
        # 2) дисципліни, за якими вже були відправлення;
        # 3) дисципліни з ручними оцінками;
        # 4) дисципліни з підсумковою оцінкою.
        disciplines = conn.execute(
            """
            SELECT discipline
            FROM (
                SELECT DISTINCT
                    teacher_subject_groups.discipline AS discipline
                FROM teacher_subject_groups
                WHERE teacher_subject_groups.student_group = ?

                UNION

                SELECT DISTINCT
                    labs.discipline AS discipline
                FROM labs
                JOIN submissions
                    ON submissions.lab_id = labs.id
                WHERE submissions.username = ?

                UNION

                SELECT DISTINCT
                    labs.discipline AS discipline
                FROM labs
                JOIN grade_overrides
                    ON grade_overrides.lab_id = labs.id
                WHERE grade_overrides.username = ?

                UNION

                SELECT DISTINCT
                    subject_final_grades.discipline AS discipline
                FROM subject_final_grades
                WHERE subject_final_grades.username = ?
            )
            WHERE discipline IS NOT NULL
              AND TRIM(discipline) <> ''
            ORDER BY discipline ASC
            """,
            (
                student_group,
                username,
                username,
                username,
            ),
        ).fetchall()

        discipline_names = [
            str(
                item["discipline"]
                or ""
            ).strip()
            for item in disciplines
            if str(
                item["discipline"]
                or ""
            ).strip()
        ]

        # Викладачі завантажуються одним запитом для всіх дисциплін.
        teacher_rows = conn.execute(
            """
            SELECT DISTINCT
                teacher_subject_groups.discipline,
                teacher_subject_groups.teacher_username,
                COALESCE(
                    NULLIF(
                        TRIM(users.full_name),
                        ''
                    ),
                    teacher_subject_groups.teacher_username
                ) AS full_name
            FROM teacher_subject_groups
            LEFT JOIN users
                ON users.username =
                   teacher_subject_groups.teacher_username
            WHERE teacher_subject_groups.student_group = ?
            ORDER BY
                teacher_subject_groups.discipline ASC,
                full_name ASC
            """,
            (student_group,),
        ).fetchall()

        teachers_by_discipline = {}

        for row in teacher_rows:
            discipline = str(
                row["discipline"]
                or ""
            ).strip()

            if not discipline:
                continue

            teachers_by_discipline.setdefault(
                discipline,
                [],
            ).append(
                row
            )

        # Усі лабораторні роботи потрібних дисциплін
        # завантажуються одним SQL-запитом.
        labs_by_discipline = {}

        if discipline_names:
            placeholders = ", ".join(
                "?"
                for _ in discipline_names
            )

            lab_rows = conn.execute(
                f"""
                SELECT *
                FROM labs
                WHERE discipline IN ({placeholders})
                ORDER BY
                    discipline ASC,
                    created_at ASC,
                    id ASC
                """,
                discipline_names,
            ).fetchall()

            for lab in lab_rows:
                discipline = str(
                    lab["discipline"]
                    or ""
                ).strip()

                labs_by_discipline.setdefault(
                    discipline,
                    [],
                ).append(
                    lab
                )

        # Академічні агрегати формуються одним запитом.
        # SYSTEM_ERROR залишається в історії відправлень,
        # але не зменшує оцінку та не витрачає навчальну спробу.
        auto_rows = conn.execute(
            """
            SELECT
                lab_id,

                MAX(
                    CASE
                        WHEN status <> ?
                        THEN score
                    END
                ) AS best_score,

                COUNT(
                    CASE
                        WHEN status <> ?
                        THEN 1
                    END
                ) AS attempts_count,

                MAX(
                    CASE
                        WHEN status = 'PASSED'
                        THEN 1
                        ELSE 0
                    END
                ) AS has_passed

            FROM submissions
            WHERE username = ?
            GROUP BY lab_id
            """,
            (
                GRADEBOOK_NON_COUNTABLE_STATUS,
                GRADEBOOK_NON_COUNTABLE_STATUS,
                username,
            ),
        ).fetchall()

        auto_results_by_lab = {
            int(row["lab_id"]): row
            for row in auto_rows
        }

        override_rows = conn.execute(
            """
            SELECT *
            FROM grade_overrides
            WHERE username = ?
            ORDER BY id ASC
            """,
            (username,),
        ).fetchall()

        # Якщо legacy-БД містить декілька override для однієї
        # лабораторної роботи, використовується найновіший запис.
        overrides_by_lab = {}

        for row in override_rows:
            overrides_by_lab[
                int(row["lab_id"])
            ] = row

        final_grade_rows = conn.execute(
            """
            SELECT *
            FROM subject_final_grades
            WHERE username = ?
            ORDER BY id ASC
            """,
            (username,),
        ).fetchall()

        # Аналогічно для legacy-дублікатів використовується
        # останній запис відповідної дисципліни.
        final_grades_by_discipline = {}

        for row in final_grade_rows:
            discipline = str(
                row["discipline"]
                or ""
            ).strip()

            if discipline:
                final_grades_by_discipline[
                    discipline
                ] = row

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час формування "
            "залікової книжки студента %s.",
            username,
        )

        flash(
            "Не вдалося завантажити залікову книжку "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("index")
        )

    finally:
        conn.close()

    gradebook_rows = []

    for discipline in discipline_names:
        labs = labs_by_discipline.get(
            discipline,
            [],
        )

        lab_results = []

        total_score = 0.0

        # graded_count використовується як знаменник
        # для середнього бала.
        graded_count = 0

        # completed_count має окрему семантику:
        # лабораторна успішно завершена або має ручну оцінку.
        completed_count = 0

        for lab in labs:
            lab_id = int(
                lab["id"]
            )

            auto_result = auto_results_by_lab.get(
                lab_id
            )

            override = overrides_by_lab.get(
                lab_id
            )

            if auto_result:
                auto_score = normalize_gradebook_score(
                    auto_result["best_score"]
                )

                attempts_count = int(
                    auto_result["attempts_count"]
                    or 0
                )

                has_passed = bool(
                    auto_result["has_passed"]
                )

            else:
                auto_score = None
                attempts_count = 0
                has_passed = False

            if override:
                display_score = normalize_gradebook_score(
                    override["score"]
                )

                source = "manual"

            else:
                display_score = auto_score
                source = (
                    "auto"
                    if auto_score is not None
                    else "none"
                )

            has_grade = (
                display_score is not None
            )

            # Ручна оцінка вважається викладацьким завершеним
            # результатом. Для автоматичного режиму завершення
            # підтверджується статусом PASSED.
            is_completed = bool(
                (
                    override
                    and display_score is not None
                )
                or has_passed
            )

            if has_grade:
                total_score += float(
                    display_score
                )

                graded_count += 1

            if is_completed:
                completed_count += 1

            lab_results.append({
                "lab": lab,
                "display_score": display_score,
                "auto_score": auto_score,
                "source": source,
                "attempts_count": attempts_count,
                "has_passed": has_passed,
                "has_grade": has_grade,
                "is_completed": is_completed,
                "manual_override": override,
            })

        average_score = (
            round(
                total_score
                / graded_count,
                1,
            )
            if graded_count > 0
            else None
        )

        gradebook_rows.append({
            "discipline": discipline,
            "teachers": teachers_by_discipline.get(
                discipline,
                [],
            ),
            "labs": lab_results,
            "average_score": average_score,

            # Зберігається окреме розрізнення:
            # оцінені роботи та фактично завершені роботи.
            "graded_count": graded_count,
            "completed_count": completed_count,
            "total_labs": len(
                labs
            ),
            "final_grade": (
                final_grades_by_discipline.get(
                    discipline
                )
            ),
        })

    return render_template(
        "student/gradebook.html",
        student=student,
        gradebook_rows=gradebook_rows,
    )


# ============================================================
# Карта компетентностей
# ============================================================

@app.route("/student/competencies")
@login_required
def student_competencies():
    """
    Відображає персональну карту HDL-компетентностей студента.
    """
    current_student = get_current_student()

    if not current_student:
        flash(
            "Карта компетентностей доступна лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_student["username"]

    conn = get_db()

    try:
        student = conn.execute(
            """
            SELECT
                username,
                full_name,
                email,
                student_group,
                role,
                status
            FROM users
            WHERE username = ?
              AND role = 'student'
              AND status = 'active'
            """,
            (username,),
        ).fetchone()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "даних студента %s для карти компетентностей.",
            username,
        )

        flash(
            "Не вдалося завантажити карту компетентностей "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("index")
        )

    finally:
        conn.close()

    if not student:
        flash(
            "Студента не знайдено."
        )

        return redirect(
            url_for("index")
        )

    try:
        competency_map = calculate_student_competency_map(
            username
        )

    except sqlite3.Error:
        app.logger.exception(
            "Не вдалося розрахувати карту "
            "компетентностей студента %s.",
            username,
        )

        flash(
            "Не вдалося розрахувати карту компетентностей "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("index")
        )

    return render_template(
        "student/competencies.html",
        student=student,
        competency_map=competency_map,
    )


# ============================================================
# Персоналізована навчальна траєкторія
# ============================================================

def parse_optional_positive_int(
    value,
):
    """Перетворює необов'язковий параметр на додатний int."""
    normalized_value = str(
        value or ""
    ).strip()

    if not normalized_value:
        return None

    try:
        parsed_value = int(
            normalized_value
        )
    except (TypeError, ValueError, OverflowError):
        return None

    if parsed_value <= 0:
        return None

    return parsed_value


def validate_learning_path_lab_id(
    lab_id,
):
    """
    Перевіряє існування HDL-лабораторної роботи,
    яку передано як контекст навчальної траєкторії.
    """
    if lab_id is None:
        return None

    conn = get_db()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM labs
            WHERE id = ?
              AND COALESCE(
                    NULLIF(checker_type, ''),
                    'hdl_testbench'
                  ) = 'hdl_testbench'
            """,
            (lab_id,),
        ).fetchone()

        if not row:
            return None

        return int(
            row["id"]
        )

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час перевірки "
            "лабораторної роботи %s для навчальної траєкторії.",
            lab_id,
        )

        return None

    finally:
        conn.close()


@app.route("/student/learning-path-live")
@login_required
def student_learning_path_live():
    """
    Відображає персоналізовану навчальну траєкторію студента.

    GET не виконує примусове оновлення вже кешованої траєкторії.
    Для явного refresh використовується окремий POST-route.
    """
    current_student = get_current_student()

    if not current_student:
        flash(
            "Навчальна ШІ-траєкторія доступна лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_student["username"]

    requested_lab_id = parse_optional_positive_int(
        request.args.get(
            "lab_id",
            "",
        )
    )

    current_lab_id = validate_learning_path_lab_id(
        requested_lab_id
    )

    if (
        requested_lab_id is not None
        and current_lab_id is None
    ):
        flash(
            "Вибрану HDL-лабораторну роботу не знайдено."
        )

    try:
        learning_path = build_live_learning_path(
            username=username,
            current_lab_id=current_lab_id,
            refresh=False,
        )

    except Exception:
        # build_live_learning_path уже має власні fallback-механізми
        # для зовнішніх сервісів. Цей рівень захищає сам route
        # від неочікуваної помилки прикладної логіки.
        app.logger.exception(
            "Не вдалося сформувати навчальну "
            "траєкторію студента %s.",
            username,
        )

        flash(
            "Не вдалося сформувати навчальну траєкторію "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("index")
        )

    return render_template(
        "student/learning_path_live.html",
        learning_path=learning_path,
        current_lab_id=current_lab_id,
    )


@app.route(
    "/student/learning-path-live/refresh",
    methods=["POST"],
)
@login_required
def student_learning_path_live_refresh():
    """
    Примусово перебудовує персоналізовану навчальну траєкторію.

    Операція виконується через POST, оскільки вона може запускати
    зовнішній web search / ШІ-запит і змінювати локальний кеш.
    """
    current_student = get_current_student()

    if not current_student:
        flash(
            "Навчальна ШІ-траєкторія доступна лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_student["username"]

    requested_lab_id = parse_optional_positive_int(
        request.form.get(
            "lab_id",
            "",
        )
    )

    current_lab_id = validate_learning_path_lab_id(
        requested_lab_id
    )

    if (
        requested_lab_id is not None
        and current_lab_id is None
    ):
        flash(
            "Вибрану HDL-лабораторну роботу не знайдено."
        )

        return redirect(
            url_for(
                "student_learning_path_live"
            )
        )

    try:
        learning_path = build_live_learning_path(
            username=username,
            current_lab_id=current_lab_id,
            refresh=True,
        )

    except Exception:
        app.logger.exception(
            "Не вдалося примусово оновити навчальну "
            "траєкторію студента %s.",
            username,
        )

        flash(
            "Не вдалося оновити навчальну траєкторію "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "student_learning_path_live",
                lab_id=(
                    current_lab_id
                    if current_lab_id is not None
                    else None
                ),
            )
        )

    return render_template(
        "student/learning_path_live.html",
        learning_path=learning_path,
        current_lab_id=current_lab_id,
    )


# ============================================================
# 12. Маршрути студента
# ============================================================

DEFAULT_SOLUTION_FILE_SIZE_LIMIT = 256 * 1024

SUBMISSION_INFRASTRUCTURE_ERROR_STATUSES = frozenset({
    "SYSTEM_ERROR",
})


def get_solution_file_size_limit() -> int:
    """
    Повертає максимальний допустимий розмір файлу рішення.

    MAX_SOLUTION_FILE_SIZE задає ліміт саме для файлу рішення,
    тоді як Flask MAX_CONTENT_LENGTH обмежує весь HTTP-запит.
    """
    value = app.config.get(
        "MAX_SOLUTION_FILE_SIZE",
        DEFAULT_SOLUTION_FILE_SIZE_LIMIT,
    )

    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        value = DEFAULT_SOLUTION_FILE_SIZE_LIMIT

    return max(
        1024,
        value,
    )


def read_uploaded_solution_file(
    file,
):
    """
    Безпечно читає текстовий файл рішення з обмеженням розміру.

    Повертає кортеж:
        (normalized_code, error_message)

    Якщо файл коректний, error_message дорівнює None.
    """
    if not file:
        return None, "Файл не вибрано."

    filename = str(
        file.filename or ""
    ).strip()

    if not filename:
        return None, "Файл не вибрано."

    max_file_size = get_solution_file_size_limit()

    try:
        file.stream.seek(0)

        raw_data = file.stream.read(
            max_file_size + 1
        )

    except (OSError, ValueError):
        app.logger.exception(
            "Не вдалося прочитати завантажений файл рішення."
        )

        return None, (
            "Не вдалося прочитати завантажений файл."
        )

    if len(raw_data) > max_file_size:
        max_size_kb = round(
            max_file_size / 1024
        )

        return None, (
            "Файл надто великий. "
            f"Максимальний розмір файлу — {max_size_kb} КБ."
        )

    uploaded_code = raw_data.decode(
        "utf-8",
        errors="replace",
    )

    uploaded_code = (
        uploaded_code
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    if not uploaded_code.endswith("\n"):
        uploaded_code += "\n"

    return uploaded_code, None


def build_default_lint_result(
    status="UNAVAILABLE",
) -> dict:
    """Формує початковий результат lint-перевірки."""
    return {
        "lint_status": status,
        "lint_score": 0,
        "lint_issues_count": 0,
        "lint_output": "",
        "lint_recommendation": "",
        "lint_issues": [],
    }


def build_default_synthesis_result(
    status="UNAVAILABLE",
) -> dict:
    """Формує початковий результат перевірки синтезу."""
    return {
        "synth_status": status,
        "synth_score": 0,
        "synth_cells_count": 0,
        "synth_wires_count": 0,
        "synth_wire_bits_count": 0,
        "synth_warnings_count": 0,
        "synth_output": "",
        "synth_recommendation": "",
        "synth_stats": {},
    }


def build_system_error_check_result() -> dict:
    """
    Формує безпечний результат у разі неочікуваної
    внутрішньої помилки основного checker.
    """
    return {
        "status": "SYSTEM_ERROR",
        "output": (
            "Внутрішня помилка системи перевірки. "
            "Спроба не повинна впливати на академічний результат."
        ),
        "score": 0,
        "passed_tests": 0,
        "total_tests": 0,

        "public_status": "SYSTEM_ERROR",
        "public_score": 0,
        "public_passed_tests": 0,
        "public_total_tests": 0,
        "public_output": (
            "Внутрішня помилка системи перевірки."
        ),

        "hidden_status": "",
        "hidden_score": 0,
        "hidden_passed_tests": 0,
        "hidden_total_tests": 0,
        "hidden_output": "",

        "waveform_created": False,
    }


def build_ungraded_system_result(
    status,
) -> dict:
    """
    Формує технічний результат для інфраструктурної помилки.

    SYSTEM_ERROR зберігається в історії, але не є академічною
    оцінкою студента та не повинен враховуватися в ліміті спроб.
    """
    return {
        "final_score": 0,
        "final_status": "Системна помилка",
        "ects_grade": "",
        "national_grade": "",
        "grading_breakdown": {
            "graded": False,
            "reason": str(
                status or "SYSTEM_ERROR"
            ),
        },
    }


def is_hdl_lab(
    lab,
) -> bool:
    """Перевіряє, чи використовує лабораторна HDL-checker."""
    checker_type = str(
        lab["checker_type"]
        if lab
        else ""
    ).strip().lower()

    return (
        checker_type
        or "hdl_testbench"
    ) == "hdl_testbench"


def build_submission_diagnostics(
    *,
    status,
    output,
    public_output,
    public_passed_tests,
    public_total_tests,
    hidden_status,
    hidden_passed_tests,
    hidden_total_tests,
    lab,
    student_code,
) -> dict:
    """
    Формує студентську діагностику без розкриття
    вмісту hidden testbench або конкретних hidden-векторів.
    """
    hidden_functional_failure = (
        str(
            hidden_status or ""
        ).strip().upper()
        in {
            "FAILED",
            "PARTIAL",
        }
        and hidden_total_tests > 0
        and hidden_passed_tests < hidden_total_tests
        and public_total_tests > 0
        and public_passed_tests == public_total_tests
    )

    if hidden_functional_failure:
        return {
            "error_type": "HIDDEN_TEST_FAILED",
            "error_title": (
                "Рішення не пройшло додаткові перевірки"
            ),
            "error_details": (
                "Рішення успішно пройшло відкриті тести, "
                "але не виконує всі додаткові перевірки. "
                "Це може свідчити про помилку на граничних "
                "або неочевидних комбінаціях вхідних сигналів."
            ),
            "recommendation": (
                "Перевірте повну таблицю істинності, "
                "граничні комбінації сигналів та випадки, "
                "які не представлені серед відкритих прикладів."
            ),
            "error_confidence": 85,
        }

    return classify_solution_error(
        status=status,
        output=public_output or output,
        lab=lab,
        code=student_code,
    )


def build_unique_artifact_name(
    preferred_filename,
    attempt_index,
) -> str:
    """
    Формує альтернативне ім'я артефакту у разі колізії.

    Це важливо, оскільки SYSTEM_ERROR не витрачає академічну
    спробу, тому наступне рішення може мати той самий
    attempt_number.
    """
    stem, extension = os.path.splitext(
        preferred_filename
    )

    return (
        f"{stem}_{attempt_index}_"
        f"{secrets.token_hex(4)}"
        f"{extension}"
    )


def write_unique_text_artifact(
    base_dir,
    preferred_filename,
    content,
):
    """
    Атомарно створює текстовий артефакт без перезапису
    вже існуючого файлу.

    Повертає:
        (actual_filename, absolute_path)
    """
    for attempt_index in range(20):
        if attempt_index == 0:
            candidate_filename = preferred_filename
        else:
            candidate_filename = build_unique_artifact_name(
                preferred_filename,
                attempt_index,
            )

        candidate_path = resolve_safe_storage_path(
            base_dir,
            candidate_filename,
        )

        if not candidate_path:
            raise ValueError(
                "Unsafe submission storage path."
            )

        try:
            with open(
                candidate_path,
                "x",
                encoding="utf-8",
            ) as output_file:
                output_file.write(
                    content
                )

            return (
                candidate_filename,
                candidate_path,
            )

        except FileExistsError:
            continue

    raise RuntimeError(
        "Unable to allocate unique submission filename."
    )


def copy_unique_binary_artifact(
    source_path,
    base_dir,
    preferred_filename,
):
    """
    Копіює бінарний артефакт до постійного сховища
    без перезапису існуючого файлу.
    """
    for attempt_index in range(20):
        if attempt_index == 0:
            candidate_filename = preferred_filename
        else:
            candidate_filename = build_unique_artifact_name(
                preferred_filename,
                attempt_index,
            )

        candidate_path = resolve_safe_storage_path(
            base_dir,
            candidate_filename,
        )

        if not candidate_path:
            raise ValueError(
                "Unsafe waveform storage path."
            )

        try:
            with open(
                source_path,
                "rb",
            ) as source_file:
                with open(
                    candidate_path,
                    "xb",
                ) as target_file:
                    while True:
                        chunk = source_file.read(
                            64 * 1024
                        )

                        if not chunk:
                            break

                        target_file.write(
                            chunk
                        )

            return (
                candidate_filename,
                candidate_path,
            )

        except FileExistsError:
            continue

        except Exception:
            try:
                os.remove(
                    candidate_path
                )
            except FileNotFoundError:
                pass

            raise

    raise RuntimeError(
        "Unable to allocate unique waveform filename."
    )


def remove_artifact_quietly(
    path,
):
    """Видаляє локальний артефакт без маскування основної помилки."""
    if not path:
        return

    try:
        os.remove(
            path
        )
    except FileNotFoundError:
        pass
    except OSError:
        app.logger.exception(
            "Не вдалося видалити тимчасовий артефакт %s.",
            path,
        )


# ============================================================
# Тренажер студента
# ============================================================

@app.route("/student/trainer")
@login_required
def student_trainer():
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Тренажер доступний лише студентам."
        )

        return redirect(
            url_for("index")
        )

    username = current_user[
        "username"
    ]

    conn = get_db()

    try:
        sessions = conn.execute(
            """
            SELECT
                id,
                username,
                topic_slug,
                competency,
                error_type,
                error_title,
                title,
                source_mode,
                status,
                total_questions,
                correct_count,
                score,
                passed,
                created_at,
                submitted_at
            FROM trainer_sessions
            WHERE username = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (username,),
        ).fetchall()

        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total_sessions,
                COALESCE(
                    SUM(
                        CASE
                            WHEN passed = 1
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS passed_sessions,
                ROUND(
                    AVG(score),
                    1
                ) AS avg_score
            FROM trainer_sessions
            WHERE username = ?
              AND status = 'completed'
            """,
            (username,),
        ).fetchone()

        active_session = conn.execute(
            """
            SELECT
                id,
                username,
                topic_slug,
                competency,
                error_type,
                error_title,
                title,
                source_mode,
                status,
                total_questions,
                correct_count,
                score,
                passed,
                created_at,
                submitted_at
            FROM trainer_sessions
            WHERE username = ?
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (username,),
        ).fetchone()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "сторінки тренажера студента %s.",
            username,
        )

        flash(
            "Не вдалося завантажити тренажер "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for("index")
        )

    finally:
        conn.close()

    context = get_student_trainer_context(
        username
    )

    return render_template(
        "student/trainer.html",
        sessions=sessions,
        stats=stats,
        active_session=active_session,
        context=context,
    )


# ============================================================
# Історія відправлень лабораторної роботи
# ============================================================

@app.route("/lab/<int:lab_id>/history")
@login_required
def student_lab_history(lab_id):
    """
    Відображає історію відправлень поточного студента
    для конкретної лабораторної роботи.

    Hidden output та інші приховані тестові дані
    не передаються до student-facing Jinja-шаблону.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Історія спроб доступна лише студентам."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=lab_id,
            )
        )

    username = current_user[
        "username"
    ]

    conn = get_db()

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        if not lab:
            abort(404)

        # Для HDL студенту передається лише public output.
        # hidden_status, hidden_score, hidden_output та кількість
        # hidden tests навмисно не вибираються.
        submissions = conn.execute(
            """
            SELECT
                submissions.id,
                submissions.lab_id,
                submissions.username,
                submissions.filename,
                submissions.waveform_filename,

                submissions.status,
                submissions.score,

                CASE
                    WHEN COALESCE(
                        NULLIF(labs.checker_type, ''),
                        'hdl_testbench'
                    ) = 'hdl_testbench'
                    THEN submissions.public_passed_tests
                    ELSE submissions.passed_tests
                END AS passed_tests,

                CASE
                    WHEN COALESCE(
                        NULLIF(labs.checker_type, ''),
                        'hdl_testbench'
                    ) = 'hdl_testbench'
                    THEN submissions.public_total_tests
                    ELSE submissions.total_tests
                END AS total_tests,

                submissions.lint_status,
                submissions.lint_score,
                submissions.lint_issues_count,
                submissions.lint_output,
                submissions.lint_recommendation,
                submissions.lint_issues_json,

                submissions.synth_status,
                submissions.synth_score,
                submissions.synth_cells_count,
                submissions.synth_wires_count,
                submissions.synth_wire_bits_count,
                submissions.synth_warnings_count,
                submissions.synth_output,
                submissions.synth_recommendation,
                submissions.synth_stats_json,

                submissions.public_status,
                submissions.public_score,
                submissions.public_passed_tests,
                submissions.public_total_tests,
                submissions.public_output,

                submissions.error_type,
                submissions.error_title,
                submissions.error_details,
                submissions.recommendation,
                submissions.error_confidence,

                CASE
                    WHEN COALESCE(
                        NULLIF(labs.checker_type, ''),
                        'hdl_testbench'
                    ) = 'hdl_testbench'
                    THEN submissions.public_output
                    ELSE submissions.output
                END AS output,

                submissions.created_at,
                submissions.attempt_number,
                submissions.file_deleted,
                submissions.file_hidden_for_student,

                submissions.testbench_score,
                submissions.questions_score,
                submissions.final_score,
                submissions.final_status,
                submissions.ects_grade,
                submissions.national_grade,
                submissions.grading_breakdown

            FROM submissions

            JOIN labs
                ON labs.id = submissions.lab_id

            WHERE submissions.lab_id = ?
              AND submissions.username = ?

            ORDER BY
                submissions.id DESC
            """,
            (
                lab_id,
                username,
            ),
        ).fetchall()

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час завантаження "
            "історії лабораторної роботи %s "
            "для студента %s.",
            lab_id,
            username,
        )

        flash(
            "Не вдалося завантажити історію спроб "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=lab_id,
            )
        )

    finally:
        conn.close()

    return render_template(
        "student/history.html",
        lab=lab,
        submissions=submissions,
    )


# ============================================================
# Відправлення рішення лабораторної роботи
# ============================================================

@app.route(
    "/submit/<int:lab_id>",
    methods=["POST"],
)
@login_required
def submit_solution(lab_id):
    """
    Приймає рішення студента, виконує автоматизовану перевірку
    та атомарно зберігає результат у SQLite.

    Тривалі операції Icarus Verilog/VVP, Verilator і Yosys
    виконуються без відкритої write-транзакції SQLite.
    """
    current_user = get_current_session_user()

    if not current_user:
        return redirect(
            url_for("login")
        )

    if current_user["role"] != "student":
        flash(
            "Надсилати рішення можуть лише студенти."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=lab_id,
            )
        )

    username = current_user[
        "username"
    ]

    file = request.files.get(
        "solution"
    )

    # --------------------------------------------------------
    # 1. Короткий етап читання БД та первинної валідації.
    # --------------------------------------------------------

    conn = get_db()

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        if not lab:
            flash(
                "Лабораторну роботу не знайдено."
            )

            return redirect(
                url_for("index")
            )

        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
              AND role = 'student'
              AND status = 'active'
            """,
            (username,),
        ).fetchone()

        if not student:
            flash(
                "Не вдалося знайти активний "
                "обліковий запис студента."
            )

            return redirect(
                url_for("index")
            )

        if not file or not str(
            file.filename or ""
        ).strip():
            flash(
                "Файл не вибрано."
            )

            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=lab_id,
                )
            )

        if not is_allowed_solution_file(
            file.filename,
            lab,
        ):
            allowed_extensions = ", ".join(
                get_allowed_extensions_for_lab(
                    lab
                )
            )

            flash(
                "Для цієї лабораторної роботи "
                "дозволено завантажувати лише файли: "
                f"{allowed_extensions}"
            )

            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=lab_id,
                )
            )

        attempts_info = get_attempts_info(
            conn=conn,
            lab=lab,
            username=username,
        )

        if attempts_info[
            "is_limit_reached"
        ]:
            flash(
                "Ви використали доступну кількість спроб. "
                "Для отримання додаткової спроби "
                "зверніться до викладача."
            )

            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=lab_id,
                )
            )

    except sqlite3.Error:
        app.logger.exception(
            "Помилка SQLite під час підготовки "
            "відправлення студента %s для лабораторної %s.",
            username,
            lab_id,
        )

        flash(
            "Не вдалося підготувати відправлення "
            "через внутрішню помилку системи."
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=lab_id,
            )
        )

    finally:
        conn.close()

    uploaded_code, file_error = read_uploaded_solution_file(
        file
    )

    if file_error:
        flash(
            file_error
        )

        return redirect(
            url_for(
                "lab_detail",
                lab_id=lab_id,
            )
        )

    original_extension = os.path.splitext(
        str(
            file.filename or ""
        )
    )[1]

    if not original_extension:
        original_extension = ".txt"

    is_hdl = is_hdl_lab(
        lab
    )

    # --------------------------------------------------------
    # 2. Перевірка рішення без відкритої транзакції SQLite.
    # --------------------------------------------------------

    with tempfile.TemporaryDirectory(
        prefix="student_submission_"
    ) as temporary_directory:

        temporary_solution_path = os.path.join(
            temporary_directory,
            f"solution{original_extension}",
        )

        temporary_waveform_path = os.path.join(
            temporary_directory,
            "waveform.vcd",
        )

        with open(
            temporary_solution_path,
            "w",
            encoding="utf-8",
        ) as temporary_solution:
            temporary_solution.write(
                uploaded_code
            )

        try:
            check_result = run_solution_check(
                temporary_solution_path,
                lab,
                waveform_save_path=temporary_waveform_path,
            )

            if not isinstance(
                check_result,
                dict,
            ):
                raise TypeError(
                    "Checker returned invalid result type."
                )

        except Exception:
            app.logger.exception(
                "Неочікувана помилка основного checker "
                "для лабораторної %s, студент %s.",
                lab_id,
                username,
            )

            check_result = build_system_error_check_result()

        status = str(
            check_result.get(
                "status",
                "SYSTEM_ERROR",
            )
            or "SYSTEM_ERROR"
        ).strip().upper()

        output = str(
            check_result.get(
                "output",
                "",
            )
            or ""
        )

        raw_score = check_result.get(
            "score",
            0,
        )

        passed_tests = int(
            check_result.get(
                "passed_tests",
                0,
            )
            or 0
        )

        total_tests = int(
            check_result.get(
                "total_tests",
                0,
            )
            or 0
        )

        public_status = str(
            check_result.get(
                "public_status",
                status,
            )
            or status
        )

        public_score = clamp_score(
            check_result.get(
                "public_score",
                0,
            )
        )

        public_passed_tests = int(
            check_result.get(
                "public_passed_tests",
                0,
            )
            or 0
        )

        public_total_tests = int(
            check_result.get(
                "public_total_tests",
                0,
            )
            or 0
        )

        public_output = str(
            check_result.get(
                "public_output",
                "",
            )
            or ""
        )

        hidden_status = str(
            check_result.get(
                "hidden_status",
                "",
            )
            or ""
        )

        hidden_score = clamp_score(
            check_result.get(
                "hidden_score",
                0,
            )
        )

        hidden_passed_tests = int(
            check_result.get(
                "hidden_passed_tests",
                0,
            )
            or 0
        )

        hidden_total_tests = int(
            check_result.get(
                "hidden_total_tests",
                0,
            )
            or 0
        )

        hidden_output = str(
            check_result.get(
                "hidden_output",
                "",
            )
            or ""
        )

        waveform_created = bool(
            check_result.get(
                "waveform_created",
                False,
            )
            and os.path.isfile(
                temporary_waveform_path
            )
        )

        testbench_score = clamp_score(
            raw_score
        )

        # ----------------------------------------------------
        # Lint та synthesis запускаються лише для HDL.
        # Після SYSTEM_ERROR додаткові інструменти не запускаються,
        # оскільки результат уже є інфраструктурно недостовірним.
        # ----------------------------------------------------

        if (
            is_hdl
            and status not in SUBMISSION_INFRASTRUCTURE_ERROR_STATUSES
        ):
            try:
                lint_result = run_hdl_lint_check(
                    temporary_solution_path
                )
            except Exception:
                app.logger.exception(
                    "Неочікувана помилка Verilator "
                    "для лабораторної %s.",
                    lab_id,
                )

                lint_result = build_default_lint_result(
                    "UNAVAILABLE"
                )

            try:
                synth_result = run_hdl_synthesis_check(
                    temporary_solution_path,
                    lab,
                )
            except Exception:
                app.logger.exception(
                    "Неочікувана помилка Yosys "
                    "для лабораторної %s.",
                    lab_id,
                )

                synth_result = (
                    build_default_synthesis_result(
                        "UNAVAILABLE"
                    )
                )

        elif is_hdl:
            lint_result = build_default_lint_result(
                "NOT_RUN"
            )

            synth_result = (
                build_default_synthesis_result(
                    "NOT_RUN"
                )
            )

        else:
            lint_result = build_default_lint_result(
                "UNAVAILABLE"
            )

            synth_result = (
                build_default_synthesis_result(
                    "UNAVAILABLE"
                )
            )

        lint_status = str(
            lint_result.get(
                "lint_status",
                "UNAVAILABLE",
            )
            or "UNAVAILABLE"
        )

        lint_score = clamp_score(
            lint_result.get(
                "lint_score",
                0,
            )
        )

        lint_issues_count = int(
            lint_result.get(
                "lint_issues_count",
                0,
            )
            or 0
        )

        lint_output = str(
            lint_result.get(
                "lint_output",
                "",
            )
            or ""
        )

        lint_recommendation = str(
            lint_result.get(
                "lint_recommendation",
                "",
            )
            or ""
        )

        lint_issues_json = json.dumps(
            lint_result.get(
                "lint_issues",
                [],
            ),
            ensure_ascii=False,
        )

        synth_status = str(
            synth_result.get(
                "synth_status",
                "UNAVAILABLE",
            )
            or "UNAVAILABLE"
        )

        synth_score = clamp_score(
            synth_result.get(
                "synth_score",
                0,
            )
        )

        has_questions = bool(
            lab["allow_extra_questions"]
        )

        # SYSTEM_ERROR зберігається для аудиту, але академічна
        # оцінка на його основі не формується.
        if status in SUBMISSION_INFRASTRUCTURE_ERROR_STATUSES:
            final_grade = build_ungraded_system_result(
                status
            )

        else:
            final_grade = build_lab_final_grade(
                testbench_score=testbench_score,
                lint_score=lint_score,
                synth_score=synth_score,
                questions_score=0,
                has_questions=has_questions,
                lint_status=lint_status,
                synth_status=synth_status,
            )

        diagnostics = build_submission_diagnostics(
            status=status,
            output=output,
            public_output=public_output,
            public_passed_tests=public_passed_tests,
            public_total_tests=public_total_tests,
            hidden_status=hidden_status,
            hidden_passed_tests=hidden_passed_tests,
            hidden_total_tests=hidden_total_tests,
            lab=lab,
            student_code=uploaded_code,
        )

        # ----------------------------------------------------
        # 3. Коротка атомарна транзакція збереження результату.
        # ----------------------------------------------------

        conn = get_db()

        saved_path = None
        waveform_saved_path = None
        saved_filename = ""
        waveform_filename = ""

        try:
            conn.execute(
                "BEGIN IMMEDIATE"
            )

            # Після тривалої перевірки повторно читаємо лабораторну
            # та ліміт спроб: за цей час інший request міг уже
            # створити нову submission.
            current_lab = conn.execute(
                """
                SELECT *
                FROM labs
                WHERE id = ?
                """,
                (lab_id,),
            ).fetchone()

            if not current_lab:
                conn.rollback()

                flash(
                    "Лабораторну роботу більше не знайдено."
                )

                return redirect(
                    url_for("index")
                )

            current_attempts_info = get_attempts_info(
                conn=conn,
                lab=current_lab,
                username=username,
            )

            if current_attempts_info[
                "is_limit_reached"
            ]:
                conn.rollback()

                flash(
                    "Поки виконувалася перевірка, "
                    "ліміт доступних спроб було вичерпано. "
                    "Результат не збережено."
                )

                return redirect(
                    url_for(
                        "lab_detail",
                        lab_id=lab_id,
                    )
                )

            attempt_number = (
                current_attempts_info[
                    "used_attempts"
                ]
                + 1
            )

            preferred_filename = build_submission_filename(
                lab=current_lab,
                student=student,
                attempt_number=attempt_number,
                original_filename=file.filename,
            )

            (
                saved_filename,
                saved_path,
            ) = write_unique_text_artifact(
                UPLOAD_DIR,
                preferred_filename,
                uploaded_code,
            )

            if waveform_created:
                preferred_waveform_filename = (
                    build_waveform_filename(
                        saved_filename
                    )
                )

                (
                    waveform_filename,
                    waveform_saved_path,
                ) = copy_unique_binary_artifact(
                    temporary_waveform_path,
                    WAVEFORM_DIR,
                    preferred_waveform_filename,
                )

            previous_submission = conn.execute(
                """
                SELECT id
                FROM submissions
                WHERE lab_id = ?
                  AND username = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    lab_id,
                    username,
                ),
            ).fetchone()

            submission_values = (
                lab_id,
                username,
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
                synth_result.get(
                    "synth_cells_count",
                    0,
                ),
                synth_result.get(
                    "synth_wires_count",
                    0,
                ),
                synth_result.get(
                    "synth_wire_bits_count",
                    0,
                ),
                synth_result.get(
                    "synth_warnings_count",
                    0,
                ),
                synth_result.get(
                    "synth_output",
                    "",
                ),
                synth_result.get(
                    "synth_recommendation",
                    "",
                ),
                json.dumps(
                    synth_result.get(
                        "synth_stats",
                        {},
                    ),
                    ensure_ascii=False,
                ),

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
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                attempt_number,
                0,
                0,

                testbench_score,
                0,
                final_grade["final_score"],
                final_grade["final_status"],
                final_grade["ects_grade"],
                final_grade["national_grade"],
                json.dumps(
                    final_grade[
                        "grading_breakdown"
                    ],
                    ensure_ascii=False,
                ),
            )

            submission_placeholders = ", ".join(
                ["?"] * len(
                    submission_values
                )
            )

            cursor = conn.execute(
                f"""
                INSERT INTO submissions (
                    lab_id,
                    username,
                    filename,
                    waveform_filename,

                    status,
                    score,
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
                    synth_cells_count,
                    synth_wires_count,
                    synth_wire_bits_count,
                    synth_warnings_count,
                    synth_output,
                    synth_recommendation,
                    synth_stats_json,

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

                    error_type,
                    error_title,
                    error_details,
                    recommendation,
                    error_confidence,

                    output,
                    created_at,
                    attempt_number,
                    file_deleted,
                    file_hidden_for_student,

                    testbench_score,
                    questions_score,
                    final_score,
                    final_status,
                    ects_grade,
                    national_grade,
                    grading_breakdown
                )
                VALUES ({submission_placeholders})
                """,
                submission_values,
            )

            new_submission_id = cursor.lastrowid

            # Попередній файл приховується лише після того,
            # як новий результат успішно підготовлено до INSERT.
            if previous_submission:
                conn.execute(
                    """
                    UPDATE submissions
                    SET file_hidden_for_student = 1
                    WHERE id = ?
                      AND id <> ?
                    """,
                    (
                        previous_submission["id"],
                        new_submission_id,
                    ),
                )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            remove_artifact_quietly(
                waveform_saved_path
            )

            remove_artifact_quietly(
                saved_path
            )

            app.logger.exception(
                "Помилка SQLite під час збереження "
                "submission студента %s для лабораторної %s.",
                username,
                lab_id,
            )

            flash(
                "Рішення було перевірено, але результат "
                "не вдалося зберегти через внутрішню "
                "помилку системи."
            )

            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=lab_id,
                )
            )

        except (
            OSError,
            ValueError,
            RuntimeError,
            TypeError,
        ):
            conn.rollback()

            remove_artifact_quietly(
                waveform_saved_path
            )

            remove_artifact_quietly(
                saved_path
            )

            app.logger.exception(
                "Не вдалося зберегти файлові артефакти "
                "submission студента %s для лабораторної %s.",
                username,
                lab_id,
            )

            flash(
                "Рішення було перевірено, але файлові "
                "артефакти не вдалося безпечно зберегти."
            )

            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=lab_id,
                )
            )

        finally:
            conn.close()

    if status == "SYSTEM_ERROR":
        flash(
            "Рішення отримано, але під час перевірки сталася "
            "системна помилка. Ця спроба не повинна впливати "
            "на академічний результат."
        )
    else:
        flash(
            "Рішення надіслано та перевірено."
        )

    return redirect(
        url_for(
            "lab_detail",
            lab_id=lab_id,
        )
    )


@app.route("/submit-code/<int:lab_id>", methods=["POST"])
@login_required
def submit_code_from_editor(lab_id):
    """
    Приймає HDL-код із вбудованого редактора, виконує перевірку розв'язання
    та зберігає результати спроби студента.

    Для Verilog-завдань послідовно виконуються основна testbench-перевірка,
    lint-аналіз і синтез. Результати відкритих і прихованих тестів,
    діагностика, оцінки та дозволені артефакти зберігаються в базі даних.
    """
    if session.get("role") != "student":
        flash("Надсилати розв'язання може лише студент.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    conn = get_db()

    try:
        lab = conn.execute(
            "SELECT * FROM labs WHERE id = ?",
            (lab_id,),
        ).fetchone()

        if lab is None:
            flash("Лабораторну роботу не знайдено.")
            return redirect(url_for("index"))

        checker_type = lab["checker_type"] or "hdl_testbench"

        if checker_type != "hdl_testbench":
            flash("HDL-редактор доступний лише для Verilog-завдань.")
            return redirect(url_for("lab_detail", lab_id=lab_id))

        code_text = request.form.get("code_text", "")

        if len(code_text.encode("utf-8")) > MAX_EDITOR_CODE_LENGTH:
            flash(
                "Код завеликий. Максимальний розмір коду "
                "в редакторі — 100 КБ."
            )
            return redirect(url_for("lab_detail", lab_id=lab_id))

        if not code_text.strip():
            flash("Код розв'язання не може бути порожнім.")
            return redirect(url_for("lab_detail", lab_id=lab_id))

        # Нормалізація завершень рядків забезпечує однакове представлення
        # HDL-коду незалежно від операційної системи клієнта.
        code_text = code_text.replace("\r\n", "\n").replace("\r", "\n")

        if not code_text.endswith("\n"):
            code_text += "\n"

        attempts_info = get_attempts_info(
            conn=conn,
            lab=lab,
            username=session["username"],
        )

        if attempts_info["is_limit_reached"]:
            flash(
                "Ви вичерпали кількість спроб. "
                "Для отримання додаткової спроби зверніться до викладача."
            )
            return redirect(url_for("lab_detail", lab_id=lab_id))

        previous_submission = conn.execute(
            """
            SELECT *
            FROM submissions
            WHERE lab_id = ? AND username = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (lab_id, session["username"]),
        ).fetchone()

        if previous_submission:
            # Попередній файл приховується від студента після створення
            # нової спроби, але запис залишається в системі для історії
            # перевірок і подальшої аналітики.
            conn.execute(
                """
                UPDATE submissions
                SET file_hidden_for_student = 1
                WHERE id = ?
                """,
                (previous_submission["id"],),
            )

        attempt_number = attempts_info["used_attempts"] + 1

        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (session["username"],),
        ).fetchone()

        if student is None:
            app.logger.warning(
                "Не знайдено запис користувача '%s' під час надсилання "
                "лабораторної роботи %s.",
                session["username"],
                lab_id,
            )
            flash("Не вдалося знайти обліковий запис студента.")
            return redirect(url_for("lab_detail", lab_id=lab_id))

        saved_filename = build_submission_filename(
            lab=lab,
            student=student,
            attempt_number=attempt_number,
            original_filename="editor_solution.v",
        )

        saved_path = os.path.join(UPLOAD_DIR, saved_filename)

        with open(saved_path, "w", encoding="utf-8") as file:
            file.write(code_text)

        waveform_filename = build_waveform_filename(saved_filename)
        waveform_save_path = os.path.join(
            WAVEFORM_DIR,
            waveform_filename,
        )

        # Основна HDL-перевірка виконує testbench-сценарій і формує
        # результат функціонального тестування. Якщо симуляція створила
        # VCD-артефакт, він зберігається окремо для подальшого перегляду.
        check_result = run_solution_check(
            saved_path,
            lab,
            waveform_save_path=waveform_save_path,
        )

        if not check_result.get("waveform_created"):
            waveform_filename = ""

            if os.path.exists(waveform_save_path):
                os.remove(waveform_save_path)

        # Після функціональної перевірки окремо виконується статичний
        # lint-аналіз HDL-коду. Його результат використовується як одна
        # зі складових підсумкового оцінювання.
        lint_result = run_hdl_lint_check(saved_path)

        # Синтез перевіряє придатність HDL-опису до апаратної реалізації
        # та формує структурну статистику, яка зберігається разом зі спробою.
        synth_result = run_hdl_synthesis_check(saved_path, lab)

        status = check_result["status"]
        output = check_result["output"]
        score = check_result["score"]
        passed_tests = check_result["passed_tests"]
        total_tests = check_result["total_tests"]

        public_status = check_result.get("public_status", status)
        public_score = check_result.get("public_score", 0)
        public_passed_tests = check_result.get(
            "public_passed_tests",
            0,
        )
        public_total_tests = check_result.get(
            "public_total_tests",
            0,
        )
        public_output = check_result.get("public_output", "")

        hidden_status = check_result.get("hidden_status", "")
        hidden_score = check_result.get("hidden_score", 0)
        hidden_passed_tests = check_result.get(
            "hidden_passed_tests",
            0,
        )
        hidden_total_tests = check_result.get(
            "hidden_total_tests",
            0,
        )
        hidden_output = check_result.get("hidden_output", "")

        lint_status = lint_result.get("lint_status", "")
        lint_score = lint_result.get("lint_score", 0)
        lint_issues_count = lint_result.get(
            "lint_issues_count",
            0,
        )
        lint_output = lint_result.get("lint_output", "")
        lint_recommendation = lint_result.get(
            "lint_recommendation",
            "",
        )
        lint_issues_json = json.dumps(
            lint_result.get("lint_issues", []),
            ensure_ascii=False,
        )

        testbench_score = clamp_score(score)

        lint_score = clamp_score(lint_score)
        lint_status = lint_status or "OK"

        synth_score = clamp_score(
            synth_result.get("synth_score", 0)
        )
        synth_status = synth_result.get(
            "synth_status",
            "OK",
        )

        has_questions = bool(lab["allow_extra_questions"])

        # Підсумкова оцінка формується централізовано з результатів
        # функціонального тестування, lint-аналізу та синтезу.
        # Додаткові запитання на цьому етапі ще мають нульову оцінку.
        final_grade = build_lab_final_grade(
            testbench_score=testbench_score,
            lint_score=lint_score,
            synth_score=synth_score,
            questions_score=0,
            has_questions=has_questions,
            lint_status=lint_status,
            synth_status=synth_status,
        )

        if (
            hidden_total_tests > 0
            and hidden_passed_tests < hidden_total_tests
            and public_total_tests > 0
            and public_passed_tests == public_total_tests
        ):
            # Студенту повідомляється лише загальна причина невдачі.
            # Вміст прихованих тестів не використовується для формування
            # рекомендації, що запобігає розкриттю контрольних сценаріїв.
            diagnostics = {
                "error_type": "HIDDEN_TEST_FAILED",
                "error_title": "Не пройдено приховані тести",
                "error_details": (
                    "Розв'язання пройшло відкриті тести, але не пройшло "
                    "частину прихованих перевірок. Це означає, що код "
                    "працює для відомих прикладів, але містить помилки "
                    "для додаткових або граничних випадків."
                ),
                "recommendation": (
                    "Перевірте повну таблицю істинності, граничні "
                    "комбінації вхідних сигналів і випадки, які не були "
                    "явно представлені у відкритих тестах."
                ),
                "error_confidence": 85,
            }
        else:
            # Для автоматичної класифікації використовується лише
            # дозволений для студента результат перевірки. Прихований
            # діагностичний вивід сюди навмисно не передається.
            diagnostics = classify_solution_error(
                status=status,
                output=public_output or output,
                lab=lab,
                code=code_text,
            )

        # Порядок значень повинен точно відповідати порядку стовпців
        # у INSERT-запиті, оскільки тут одночасно зберігаються результати
        # testbench, lint, synthesis, діагностики та підсумкового оцінювання.
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
            json.dumps(
                synth_result.get("synth_stats", {}),
                ensure_ascii=False,
            ),

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
            json.dumps(
                final_grade["grading_breakdown"],
                ensure_ascii=False,
            ),
        )

        submission_placeholders = ", ".join(
            ["?"] * len(submission_values)
        )

        conn.execute(
            f"""
            INSERT INTO submissions
            (
                lab_id,
                username,
                filename,
                waveform_filename,
                status,
                score,
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
                synth_cells_count,
                synth_wires_count,
                synth_wire_bits_count,
                synth_warnings_count,
                synth_output,
                synth_recommendation,
                synth_stats_json,
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
                error_type,
                error_title,
                error_details,
                recommendation,
                error_confidence,
                output,
                created_at,
                attempt_number,
                file_deleted,
                file_hidden_for_student,
                testbench_score,
                questions_score,
                final_score,
                final_status,
                ects_grade,
                national_grade,
                grading_breakdown
            )
            VALUES ({submission_placeholders})
            """,
            submission_values,
        )

        conn.commit()

    finally:
        # З'єднання закривається для всіх сценаріїв завершення маршруту,
        # включно з ранніми return та необробленими винятками.
        conn.close()

    flash("Код із HDL-редактора надіслано та перевірено.")
    return redirect(url_for("lab_detail", lab_id=lab_id))


@app.route("/retry/<int:submission_id>", methods=["POST"])
@login_required
def retry_submission(submission_id):
    """
    Перевіряє можливість повторного надсилання розв'язання студентом.

    Маршрут не створює нову спробу безпосередньо, а перевіряє доступний
    ліміт спроб і повертає студента до форми надсилання лабораторної роботи.
    """
    if session.get("role") != "student":
        flash("Повторне надсилання доступне лише студенту.")
        return redirect(url_for("index"))

    submission = get_submission_for_current_user(submission_id)

    conn = get_db()

    try:
        lab = conn.execute(
            "SELECT * FROM labs WHERE id = ?",
            (submission["lab_id"],),
        ).fetchone()

        if lab is None:
            flash("Лабораторну роботу не знайдено.")
            return redirect(url_for("index"))

        # Для перевірки ліміту використовується спільна функція проєкту.
        # Це забезпечує однаковий облік основних і додаткових спроб
        # у всіх сценаріях надсилання HDL-розв'язань.
        attempts_info = get_attempts_info(
            conn=conn,
            lab=lab,
            username=session["username"],
        )

        if attempts_info["is_limit_reached"]:
            flash(
                "Ліміт спроб для цієї лабораторної роботи вичерпано. "
                "Для отримання додаткової спроби зверніться до викладача."
            )
            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=submission["lab_id"],
                )
            )

    finally:
        conn.close()

    flash("Завантажте новий файл розв'язання у формі надсилання вище.")
    return redirect(
        url_for(
            "lab_detail",
            lab_id=submission["lab_id"],
        )
    )


@app.route("/ai-help/<int:submission_id>")
@login_required
def ai_help(submission_id):
    """
    Формує адаптивну підказку ШІ-помічника для розв'язання студента.

    Підказка створюється на основі результатів автоматичної перевірки,
    HDL-коду та визначеного рівня деталізації. Для вже успішно пройдених
    функціональних тестів додаткова підказка не формується.
    """
    if session.get("role") != "student":
        flash("Підказки ШІ доступні лише студентам.")
        return redirect(url_for("index"))

    submission = get_submission_for_current_user(submission_id)

    if submission["status"] == "PASSED":
        flash("Розв'язання вже пройшло всі тести. Підказка ШІ не потрібна.")
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    code = read_submission_code(submission["filename"])

    # Адаптивний план узагальнює результат перевірки та визначає
    # тему, проблемні тести, рівень підказки й навчальні рекомендації.
    adaptive_plan = build_adaptive_learning_plan(
        submission,
        code,
    )

    requested_level = request.args.get("level", type=int)

    if requested_level in {1, 2, 3}:
        adaptive_plan["hint_level"] = requested_level

        adaptive_plan["hint_text"] = generate_adaptive_hint(
            submission=submission,
            topic=adaptive_plan["topic"],
            failed_tests=adaptive_plan["failed_tests"],
            hint_level=requested_level,
        )

    return render_template(
        "student/ai_help.html",
        submission=submission,
        hint=adaptive_plan["hint_text"],
        level=adaptive_plan["hint_level"],
        code=code,
        adaptive_plan=adaptive_plan,
    )


@app.route(
    "/improve-score/<int:submission_id>",
    methods=["GET", "POST"],
)
@login_required
def improve_score(submission_id):
    """
    Реалізує одноразове покращення підсумкової оцінки за допомогою
    додаткових запитань, сформованих адаптивною навчальною підсистемою.

    Після перевірки відповідей повторно обчислюється підсумкова оцінка
    з урахуванням testbench, lint, synthesis і компонента додаткових
    запитань. Результат зберігається разом з історією спроби.
    """
    if session.get("role") != "student":
        flash("Покращення оцінки доступне лише студентам.")
        return redirect(url_for("index"))

    submission = get_submission_for_current_user(submission_id)

    # Статус PASSED характеризує результат функціональних тестів,
    # але не обов'язково означає максимальну підсумкову оцінку.
    # Тому можливість покращення визначається саме за final_score.
    if submission["final_score"] is not None:
        current_score = int(submission["final_score"])
    else:
        current_score = int(submission["score"] or 0)

    if current_score >= 100:
        flash("Це розв'язання вже має максимальний підсумковий бал.")
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    conn = get_db()

    try:
        lab = conn.execute(
            "SELECT * FROM labs WHERE id = ?",
            (submission["lab_id"],),
        ).fetchone()

        if lab is None:
            flash("Лабораторну роботу не знайдено.")
            return redirect(url_for("index"))

        if not lab["allow_extra_questions"]:
            flash(
                "Для цієї лабораторної роботи покращення оцінки "
                "за допомогою додаткових запитань вимкнено."
            )
            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=submission["lab_id"],
                )
            )

        used_extra_attempts = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM extra_task_attempts
            WHERE submission_id = ?
            """,
            (submission_id,),
        ).fetchone()["count"]

        if used_extra_attempts > 0:
            flash(
                "Ви вже використали можливість покращити оцінку "
                "для цієї спроби."
            )
            return redirect(
                url_for(
                    "lab_detail",
                    lab_id=submission["lab_id"],
                )
            )

    finally:
        conn.close()

    code = read_submission_code(submission["filename"])

    # Додаткові запитання формуються на основі проблем, виявлених
    # під час автоматичної перевірки конкретного HDL-розв'язання.
    adaptive_plan = build_adaptive_learning_plan(
        submission,
        code,
    )

    tasks = adaptive_plan.get("questions", [])

    # Поточна модель оцінювання передбачає рівно три запитання.
    # Невідповідність кількості розглядається як помилка формування
    # адаптивного завдання, а не як помилка студента.
    if not isinstance(tasks, (list, tuple)) or len(tasks) != 3:
        app.logger.error(
            "Для submission_id=%s сформовано некоректну кількість "
            "додаткових запитань: %s.",
            submission_id,
            len(tasks) if isinstance(tasks, (list, tuple)) else "invalid",
        )

        flash(
            "Не вдалося коректно сформувати додаткові запитання. "
            "Спробуйте повторити операцію пізніше."
        )
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    check_result = None

    student_answers = {
        "answer_1": "",
        "answer_2": "",
        "answer_3": "",
    }

    if request.method == "POST":
        student_answers = {
            "answer_1": request.form.get("answer_1", ""),
            "answer_2": request.form.get("answer_2", ""),
            "answer_3": request.form.get("answer_3", ""),
        }

        correct_count, bonus, feedback = evaluate_extra_task_answers(
            submission,
            student_answers,
        )

        questions_score = round(correct_count * 100 / 3)

        score_before = current_score

        # Нуль є коректним результатом testbench, тому fallback
        # застосовується лише для NULL, а не для будь-якого false-значення.
        if submission["testbench_score"] is not None:
            testbench_score = int(submission["testbench_score"])
        else:
            testbench_score = int(submission["score"] or 0)

        lint_score = int(submission["lint_score"] or 0)
        synth_score = int(submission["synth_score"] or 0)

        lint_status = submission["lint_status"] or "OK"
        synth_status = submission["synth_status"] or "OK"

        # Після відповідей студента підсумкова оцінка перераховується
        # тією самою централізованою функцією, що використовується
        # під час первинної автоматичної перевірки.
        final_grade = build_lab_final_grade(
            testbench_score=testbench_score,
            lint_score=lint_score,
            synth_score=synth_score,
            questions_score=questions_score,
            has_questions=True,
            lint_status=lint_status,
            synth_status=synth_status,
        )

        score_after = final_grade["final_score"]

        updated_output = (
            (submission["output"] or "")
            + "\n\n---\n"
            + "Додаткові запитання враховано як компонент "
            + "підсумкової оцінки.\n"
            + f"Правильних відповідей: {correct_count} із 3.\n"
            + (
                "Оцінка за додаткові запитання: "
                f"{questions_score} / 100.\n"
            )
            + f"Підсумковий бал за формулою: {score_after} / 100.\n"
            + f"ECTS: {final_grade['ects_grade']}.\n"
            + (
                "Національна оцінка: "
                f"{final_grade['national_grade']}.\n"
            )
        )

        conn = get_db()

        try:
            # Запис відповідей і оновлення результату виконуються
            # в межах однієї транзакції, щоб уникнути ситуації,
            # коли збережено лише одну частину операції.
            conn.execute(
                """
                INSERT INTO extra_task_attempts
                (
                    submission_id,
                    username,
                    answer_1,
                    answer_2,
                    answer_3,
                    correct_count,
                    total_count,
                    bonus,
                    score_before,
                    score_after,
                    feedback,
                    created_at
                )
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
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
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
                    json.dumps(
                        final_grade["grading_breakdown"],
                        ensure_ascii=False,
                    ),
                    updated_output,
                    submission_id,
                    session["username"],
                ),
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

        if correct_count >= 2:
            flash(
                "Відповіді прийнято. Додаткові запитання враховано "
                "в підсумковій оцінці."
            )
        else:
            flash(
                "Відповіді збережено, але оцінка за додаткові "
                "запитання є низькою."
            )

        check_result = {
            "correct_count": correct_count,
            "bonus": bonus,
            "questions_score": questions_score,
            "score_before": score_before,
            "score_after": score_after,
            "feedback": feedback,
        }

    return render_template(
        "student/improve_score.html",
        submission=submission,
        tasks=tasks,
        check_result=check_result,
        student_answers=student_answers,
        adaptive_plan=adaptive_plan,
    )


# =========================
# 15. Маршрути часових діаграм
# =========================


def _resolve_waveform_path(waveform_filename):
    """
    Формує безпечний абсолютний шлях до VCD-файлу.

    Шлях вважається допустимим лише тоді, коли після нормалізації
    він залишається всередині каталогу WAVEFORM_DIR. Це додатково
    захищає файлові артефакти від некоректних або модифікованих
    значень waveform_filename.
    """
    if not waveform_filename:
        return None

    waveform_directory = os.path.realpath(WAVEFORM_DIR)
    waveform_path = os.path.realpath(
        os.path.join(waveform_directory, waveform_filename)
    )

    try:
        common_path = os.path.commonpath(
            [waveform_directory, waveform_path]
        )
    except ValueError:
        return None

    if common_path != waveform_directory:
        return None

    return waveform_path


@app.route("/waveform-view/<int:submission_id>")
@login_required
def view_waveform(submission_id):
    """
    Відображає сторінку перегляду часової діаграми для спроби студента.

    Доступ до VCD-артефакту надається лише після перевірки належності
    відповідної спроби поточному користувачу.
    """
    submission = get_waveform_submission_for_current_user(submission_id)

    if not submission["waveform_filename"]:
        flash("Для цієї спроби часова діаграма недоступна.")
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    waveform_path = _resolve_waveform_path(
        submission["waveform_filename"]
    )

    if waveform_path is None:
        app.logger.warning(
            "Виявлено некоректний шлях до VCD-файлу "
            "для submission_id=%s.",
            submission_id,
        )
        flash("Файл часової діаграми недоступний.")
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    if not os.path.isfile(waveform_path):
        flash("Файл часової діаграми відсутній на сервері.")
        return redirect(
            url_for(
                "lab_detail",
                lab_id=submission["lab_id"],
            )
        )

    return render_template(
        "student/waveform_viewer.html",
        submission=submission,
    )


@app.route("/waveform-data/<int:submission_id>")
@login_required
def waveform_data(submission_id):
    """
    Повертає структуровані дані VCD-файлу у форматі JSON.

    VCD розбирається серверною частиною, після чого клієнт отримує
    часову шкалу, перелік сигналів та їх зміни без прямого доступу
    до файлової системи сервера.
    """
    submission = get_waveform_submission_for_current_user(submission_id)

    if not submission["waveform_filename"]:
        return jsonify(
            {
                "timescale": "",
                "max_time": 0,
                "signals": [],
                "error": (
                    "Для цієї спроби часова діаграма недоступна."
                ),
            }
        )

    waveform_path = _resolve_waveform_path(
        submission["waveform_filename"]
    )

    if waveform_path is None:
        app.logger.warning(
            "Виявлено некоректний шлях до VCD-файлу "
            "для submission_id=%s.",
            submission_id,
        )

        return jsonify(
            {
                "timescale": "",
                "max_time": 0,
                "signals": [],
                "error": "VCD-файл недоступний.",
            }
        )

    if not os.path.isfile(waveform_path):
        return jsonify(
            {
                "timescale": "",
                "max_time": 0,
                "signals": [],
                "error": "VCD-файл не знайдено на сервері.",
            }
        )

    try:
        # VCD є результатом HDL-моделювання та містить зміни значень
        # сигналів у часі. Парсер перетворює цей артефакт на структуру,
        # придатну для відображення у вебінтерфейсі.
        parsed = parse_vcd_file(waveform_path)

    except Exception:
        # Деталі помилки залишаються лише в серверному журналі,
        # щоб не розкривати користувачу внутрішню структуру файлової
        # системи або реалізацію VCD-парсера.
        app.logger.exception(
            "Помилка обробки VCD-файлу для submission_id=%s.",
            submission_id,
        )

        return jsonify(
            {
                "timescale": "",
                "max_time": 0,
                "signals": [],
                "error": (
                    "Не вдалося обробити файл часової діаграми."
                ),
            }
        )

    return jsonify(parsed)

# =========================
# 16. Маршрути керування оцінками
# =========================


def _get_safe_grade_redirect(default_endpoint="teacher_journal"):
    """
    Повертає безпечну адресу для перенаправлення після зміни оцінки.

    Значення HTTP Referer використовується лише тоді, коли воно належить
    поточному застосунку. Це запобігає перенаправленню користувача
    на зовнішній ресурс через модифікований заголовок запиту.
    """
    fallback_url = url_for(default_endpoint)
    referrer = request.referrer

    if not referrer:
        return fallback_url

    referrer_url = urlparse(referrer)
    host_url = urlparse(request.host_url)

    if (
        referrer_url.scheme in {"http", "https"}
        and referrer_url.netloc == host_url.netloc
    ):
        return referrer

    return fallback_url


def _upsert_grade_override(
    conn,
    username,
    lab_id,
    score,
    comment,
    edited_by,
    edited_at,
):
    """
    Створює або оновлює ручну оцінку для лабораторної роботи.

    Ручна оцінка зберігається окремо від результату автоматичної
    HDL-перевірки, що дозволяє не змінювати первинні результати
    testbench, lint і synthesis.
    """
    existing = conn.execute(
        """
        SELECT id
        FROM grade_overrides
        WHERE username = ?
          AND lab_id = ?
        """,
        (username, lab_id),
    ).fetchone()

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
                edited_by,
                edited_at,
                username,
                lab_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO grade_overrides
            (
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
                edited_by,
                edited_at,
            ),
        )


@app.route(
    "/grades/lab/<int:lab_id>/<username>/update",
    methods=["POST"],
)
@login_required
def update_lab_grade(lab_id, username):
    """
    Створює, змінює або видаляє ручну оцінку за лабораторну роботу.

    Викладач може редагувати лише ті оцінки, до яких він має доступ
    відповідно до призначених груп, дисциплін і лабораторних робіт.
    Адміністратор використовує ту саму перевірку авторизації з урахуванням
    розширених повноважень своєї ролі.
    """
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in {"admin", "teacher"}:
        flash(
            "Редагувати оцінки може лише викладач або адміністратор."
        )
        return redirect(url_for("index"))

    score_raw = request.form.get("score", "").strip()
    comment = request.form.get("comment", "").strip()

    redirect_url = _get_safe_grade_redirect()

    conn = get_db()

    try:
        # Перевірка виконується не лише за роллю, а й за конкретною
        # парою «студент — лабораторна робота». Це обмежує викладача
        # межами призначених йому навчальних об'єктів.
        if not can_edit_lab_grade(
            conn,
            current_username,
            current_role,
            username,
            lab_id,
        ):
            flash("У вас немає прав для редагування цієї оцінки.")
            return redirect(redirect_url)

        if score_raw == "":
            # Видалення ручного перевизначення не видаляє автоматичний
            # результат. Після цього журнал знову використовує оцінку,
            # сформовану автоматизованою системою перевірки.
            conn.execute(
                """
                DELETE FROM grade_overrides
                WHERE username = ?
                  AND lab_id = ?
                """,
                (username, lab_id),
            )

            conn.commit()

            flash(
                "Ручну оцінку видалено. У журналі знову "
                "відображатиметься автоматичний результат."
            )
            return redirect(redirect_url)

        try:
            score = int(score_raw)
        except ValueError:
            flash("Оцінка має бути цілим числом від 0 до 100.")
            return redirect(redirect_url)

        if not 0 <= score <= 100:
            flash("Оцінка має бути в діапазоні від 0 до 100.")
            return redirect(redirect_url)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _upsert_grade_override(
            conn=conn,
            username=username,
            lab_id=lab_id,
            score=score,
            comment=comment,
            edited_by=current_username,
            edited_at=now,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("Оцінку оновлено.")
    return redirect(redirect_url)


@app.route(
    "/teacher/journal/update-group",
    methods=["POST"],
)
@login_required
def update_group_journal():
    """
    Зберігає групові зміни ручних оцінок у журналі викладача.

    Кожен запис перевіряється окремо, оскільки наявність ролі викладача
    сама по собі не надає права змінювати оцінки всіх студентів системи.
    Некоректні або недоступні записи пропускаються та не впливають
    на дозволені зміни.
    """
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in {"teacher", "admin"}:
        flash("Недостатньо прав для редагування журналу.")
        return redirect(url_for("index"))

    redirect_url = _get_safe_grade_redirect()

    updated_count = 0
    deleted_count = 0
    invalid_count = 0
    denied_count = 0

    conn = get_db()

    try:
        for key, value in request.form.items():
            if not key.startswith("score__"):
                continue

            try:
                _, username, lab_id_raw = key.split("__", 2)
                lab_id = int(lab_id_raw)
            except (ValueError, TypeError):
                invalid_count += 1
                continue

            score_text = value.strip()

            comment_key = (
                f"comment__{username}__{lab_id_raw}"
            )
            comment = request.form.get(
                comment_key,
                "",
            ).strip()

            # Поля форми вважаються недовіреними даними. Навіть якщо
            # інтерфейс показує викладачу лише дозволені лабораторні роботи,
            # сервер повторно перевіряє право редагування кожного запису.
            if not can_edit_lab_grade(
                conn,
                current_username,
                current_role,
                username,
                lab_id,
            ):
                denied_count += 1
                continue

            if score_text == "" and comment == "":
                cursor = conn.execute(
                    """
                    DELETE FROM grade_overrides
                    WHERE username = ?
                      AND lab_id = ?
                    """,
                    (username, lab_id),
                )

                if cursor.rowcount > 0:
                    deleted_count += 1

                continue

            # Поточна модель ручного перевизначення передбачає
            # обов'язковий числовий бал. Коментар без оцінки
            # самостійним записом grade_overrides не є.
            if score_text == "":
                invalid_count += 1
                continue

            try:
                score = int(score_text)
            except ValueError:
                invalid_count += 1
                continue

            if not 0 <= score <= 100:
                invalid_count += 1
                continue

            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            _upsert_grade_override(
                conn=conn,
                username=username,
                lab_id=lab_id,
                score=score,
                comment=comment,
                edited_by=current_username,
                edited_at=now,
            )

            updated_count += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    if denied_count > 0:
        app.logger.warning(
            "Користувач '%s' не мав права редагувати %s запис(ів) "
            "під час групового оновлення журналу.",
            current_username,
            denied_count,
        )

    if invalid_count > 0 or denied_count > 0:
        flash(
            "Зміни журналу оброблено. "
            f"Оновлено: {updated_count}, "
            f"видалено: {deleted_count}, "
            f"пропущено некоректних: {invalid_count}, "
            f"пропущено через відсутність прав: {denied_count}."
        )
    else:
        flash("Зміни в журналі збережено.")

    return redirect(redirect_url)


# =========================
# 17. Адміністративні маршрути
# =========================


def _get_safe_referrer_redirect(default_endpoint):
    """
    Повертає безпечну адресу для перенаправлення в межах застосунку.

    HTTP Referer використовується лише тоді, коли він належить
    поточному хосту. В інших випадках використовується заданий
    внутрішній маршрут.
    """
    fallback_url = url_for(default_endpoint)
    referrer = request.referrer

    if not referrer:
        return fallback_url

    referrer_url = urlparse(referrer)
    host_url = urlparse(request.host_url)

    if (
        referrer_url.scheme in {"http", "https"}
        and referrer_url.netloc == host_url.netloc
    ):
        return referrer

    return fallback_url


@app.route("/admin")
@admin_required
def admin_panel():
    """
    Відображає адміністративну панель зі статистикою користувачів
    і переліком облікових записів, які очікують підтвердження.
    """
    conn = get_db()

    try:
        stats = conn.execute(
            """
            SELECT
                COUNT(
                    CASE WHEN status = 'pending' THEN 1 END
                ) AS pending_users,
                COUNT(
                    CASE WHEN role = 'student' THEN 1 END
                ) AS students,
                COUNT(
                    CASE WHEN role = 'teacher' THEN 1 END
                ) AS teachers,
                COUNT(
                    CASE WHEN role = 'admin' THEN 1 END
                ) AS admins
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

    finally:
        conn.close()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        pending_users=pending_users,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    """
    Відображає перелік користувачів із ролями та поточними
    станами облікових записів.
    """
    conn = get_db()

    try:
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

    finally:
        conn.close()

    return render_template(
        "admin/users.html",
        users=users,
    )


@app.route("/admin/groups", methods=["GET", "POST"])
@admin_required
def admin_groups():
    """
    Забезпечує перегляд і створення навчальних груп
    в адміністративній частині системи.
    """
    conn = get_db()

    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get(
                "description",
                "",
            ).strip()

            if not name:
                flash("Назва групи не може бути порожньою.")
                return redirect(url_for("admin_groups"))

            try:
                conn.execute(
                    """
                    INSERT INTO study_groups
                    (
                        name,
                        description,
                        created_at,
                        created_by
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        description,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        session["username"],
                    ),
                )

                conn.commit()

                app.logger.info(
                    "Адміністратор '%s' створив навчальну групу '%s'.",
                    session["username"],
                    name,
                )

                flash("Групу додано.")

            except sqlite3.IntegrityError:
                conn.rollback()
                flash("Група з такою назвою вже існує.")

            return redirect(url_for("admin_groups"))

        groups = conn.execute(
            """
            SELECT *
            FROM study_groups
            ORDER BY name ASC
            """
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "admin/groups.html",
        groups=groups,
    )


@app.route("/admin/disciplines", methods=["GET", "POST"])
@admin_required
def admin_disciplines():
    """
    Забезпечує перегляд і створення навчальних дисциплін
    в адміністративній частині системи.
    """
    conn = get_db()

    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get(
                "description",
                "",
            ).strip()

            if not name:
                flash("Назва дисципліни не може бути порожньою.")
                return redirect(url_for("admin_disciplines"))

            try:
                conn.execute(
                    """
                    INSERT INTO disciplines
                    (
                        name,
                        description,
                        created_at,
                        created_by
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        description,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        session["username"],
                    ),
                )

                conn.commit()

                app.logger.info(
                    "Адміністратор '%s' створив дисципліну '%s'.",
                    session["username"],
                    name,
                )

                flash("Дисципліну додано.")

            except sqlite3.IntegrityError:
                conn.rollback()
                flash("Дисципліна з такою назвою вже існує.")

            return redirect(url_for("admin_disciplines"))

        disciplines = conn.execute(
            """
            SELECT *
            FROM disciplines
            ORDER BY name ASC
            """
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "admin/disciplines.html",
        disciplines=disciplines,
    )


@app.route(
    "/admin/users/<int:user_id>/approve",
    methods=["POST"],
)
@admin_required
def admin_approve_user(user_id):
    """
    Активує обліковий запис користувача від імені адміністратора.
    """
    redirect_url = _get_safe_referrer_redirect("admin_users")
    conn = get_db()

    try:
        user = conn.execute(
            """
            SELECT id, username, status, role
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if user is None:
            flash("Користувача не знайдено.")
            return redirect(redirect_url)

        conn.execute(
            """
            UPDATE users
            SET status = 'active',
                approved_by = ?
            WHERE id = ?
            """,
            (
                session["username"],
                user_id,
            ),
        )

        conn.commit()

        app.logger.info(
            "Адміністратор '%s' активував користувача '%s' "
            "(user_id=%s).",
            session["username"],
            user["username"],
            user_id,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("Користувача активовано.")
    return redirect(redirect_url)


@app.route(
    "/admin/users/<int:user_id>/block",
    methods=["POST"],
)
@admin_required
def admin_block_user(user_id):
    """
    Блокує обліковий запис користувача.

    Облікові записи адміністраторів не блокуються через цей маршрут,
    що запобігає випадковому блокуванню адміністративного доступу.
    """
    redirect_url = _get_safe_referrer_redirect("admin_users")
    conn = get_db()

    try:
        user = conn.execute(
            """
            SELECT id, username, role, status
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if user is None:
            flash("Користувача не знайдено.")
            return redirect(redirect_url)

        if user["role"] == "admin":
            flash("Адміністратора не можна заблокувати.")
            return redirect(redirect_url)

        if user["status"] == "blocked":
            flash("Користувача вже заблоковано.")
            return redirect(redirect_url)

        conn.execute(
            """
            UPDATE users
            SET status = 'blocked'
            WHERE id = ?
            """,
            (user_id,),
        )

        conn.commit()

        app.logger.info(
            "Адміністратор '%s' заблокував користувача '%s' "
            "(user_id=%s).",
            session["username"],
            user["username"],
            user_id,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("Користувача заблоковано.")
    return redirect(redirect_url)


@app.route(
    "/admin/teacher-access",
    methods=["GET", "POST"],
)
@admin_required
def admin_teacher_access():
    """
    Керує призначенням викладачів до навчальних дисциплін і груп.

    Сервер перевіряє існування всіх пов'язаних сутностей перед
    створенням призначення, оскільки значення HTML-форми не можуть
    вважатися достовірними лише на підставі перевірки інтерфейсу.
    """
    conn = get_db()

    try:
        if request.method == "POST":
            teacher_username = request.form.get(
                "teacher_username",
                "",
            ).strip()

            discipline_name = request.form.get(
                "discipline",
                "",
            ).strip()

            student_group_name = request.form.get(
                "student_group",
                "",
            ).strip()

            if (
                not teacher_username
                or not discipline_name
                or not student_group_name
            ):
                flash(
                    "Необхідно вибрати викладача, дисципліну та групу."
                )
                return redirect(url_for("admin_teacher_access"))

            # Значення форми повторно перевіряються на сервері.
            # Це запобігає створенню призначень для неіснуючих
            # або неактивних користувачів і навчальних об'єктів.
            teacher = conn.execute(
                """
                SELECT username
                FROM users
                WHERE username = ?
                  AND role = 'teacher'
                  AND status = 'active'
                """,
                (teacher_username,),
            ).fetchone()

            if teacher is None:
                flash(
                    "Вибраного активного викладача не знайдено."
                )
                return redirect(url_for("admin_teacher_access"))

            discipline = conn.execute(
                """
                SELECT name
                FROM disciplines
                WHERE name = ?
                """,
                (discipline_name,),
            ).fetchone()

            if discipline is None:
                flash("Вибрану дисципліну не знайдено.")
                return redirect(url_for("admin_teacher_access"))

            student_group = conn.execute(
                """
                SELECT name
                FROM study_groups
                WHERE name = ?
                """,
                (student_group_name,),
            ).fetchone()

            if student_group is None:
                flash("Вибрану навчальну групу не знайдено.")
                return redirect(url_for("admin_teacher_access"))

            try:
                conn.execute(
                    """
                    INSERT INTO teacher_subject_groups
                    (
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
                        discipline_name,
                        student_group_name,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        session["username"],
                    ),
                )

                conn.commit()

                app.logger.info(
                    "Адміністратор '%s' надав викладачу '%s' "
                    "доступ до дисципліни '%s' та групи '%s'.",
                    session["username"],
                    teacher_username,
                    discipline_name,
                    student_group_name,
                )

                flash("Доступ викладачу додано.")

            except sqlite3.IntegrityError:
                conn.rollback()
                flash("Таке призначення вже існує.")

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
            LEFT JOIN users
                ON users.username =
                   teacher_subject_groups.teacher_username
            ORDER BY
                teacher_subject_groups.discipline ASC,
                teacher_subject_groups.student_group ASC,
                users.full_name ASC
            """
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "admin/teacher_access.html",
        teachers=teachers,
        disciplines=disciplines,
        groups=groups,
        access_rows=access_rows,
    )

# =========================
# 18. Маршрути викладача
# =========================


@app.route("/teacher")
@teacher_required
def teacher_panel():
    """
    Відображає зведену статистику за навчальними об'єктами,
    доступними поточному викладачу.

    До статистики включаються лабораторні роботи, створені викладачем,
    а також результати студентів із груп і дисциплін, призначених йому
    адміністратором.
    """
    current_username = session.get("username")
    conn = get_db()

    try:
        # Статистика обмежується тією самою моделлю доступу, що й
        # детальна аналітика: власні лабораторні роботи викладача
        # та призначені йому комбінації дисциплін і навчальних груп.
        stats = conn.execute(
            """
            WITH accessible_submissions AS (
                SELECT
                    submissions.*
                FROM submissions
                JOIN labs
                    ON submissions.lab_id = labs.id
                LEFT JOIN users
                    ON users.username = submissions.username
                WHERE labs.created_by = ?
                   OR EXISTS (
                        SELECT 1
                        FROM teacher_subject_groups tsg
                        WHERE tsg.teacher_username = ?
                          AND tsg.discipline = labs.discipline
                          AND tsg.student_group = users.student_group
                   )
            ),
            accessible_labs AS (
                SELECT DISTINCT
                    labs.id
                FROM labs
                WHERE labs.created_by = ?
                   OR EXISTS (
                        SELECT 1
                        FROM teacher_subject_groups tsg
                        WHERE tsg.teacher_username = ?
                          AND tsg.discipline = labs.discipline
                   )
            ),
            accessible_students AS (
                SELECT DISTINCT
                    users.username
                FROM users
                WHERE users.role = 'student'
                  AND (
                        EXISTS (
                            SELECT 1
                            FROM teacher_subject_groups tsg
                            WHERE tsg.teacher_username = ?
                              AND tsg.student_group = users.student_group
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM submissions
                            JOIN labs
                                ON submissions.lab_id = labs.id
                            WHERE submissions.username = users.username
                              AND labs.created_by = ?
                        )
                  )
            )
            SELECT
                (
                    SELECT COUNT(*)
                    FROM accessible_students
                ) AS total_students,

                (
                    SELECT COUNT(*)
                    FROM accessible_labs
                ) AS total_labs,

                COUNT(id) AS total_submissions,

                COUNT(
                    CASE WHEN status = 'PASSED' THEN 1 END
                ) AS passed,

                COUNT(
                    CASE WHEN status = 'PARTIAL' THEN 1 END
                ) AS partial,

                COUNT(
                    CASE WHEN status = 'FAILED' THEN 1 END
                ) AS failed,

                COUNT(
                    CASE WHEN status = 'COMPILE_ERROR' THEN 1 END
                ) AS compile_errors,

                ROUND(AVG(score), 1) AS average_score,

                ROUND(
                    100.0
                    * COUNT(
                        CASE WHEN status = 'PASSED' THEN 1 END
                    )
                    / NULLIF(COUNT(id), 0),
                    1
                ) AS success_percent
            FROM accessible_submissions
            """,
            (
                current_username,
                current_username,
                current_username,
                current_username,
                current_username,
                current_username,
            ),
        ).fetchone()

        # Аналіз типів помилок також обмежується лише тими спробами,
        # які поточний викладач має право переглядати.
        error_summary = conn.execute(
            """
            SELECT
                submissions.error_type,
                submissions.error_title,
                COUNT(*) AS count
            FROM submissions
            JOIN labs
                ON submissions.lab_id = labs.id
            LEFT JOIN users
                ON users.username = submissions.username
            WHERE submissions.error_type IS NOT NULL
              AND submissions.error_type != ''
              AND submissions.error_type != 'NO_ERROR'
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
            GROUP BY
                submissions.error_type,
                submissions.error_title
            ORDER BY count DESC
            """,
            (
                current_username,
                current_username,
            ),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "teacher/dashboard.html",
        stats=stats,
        error_summary=error_summary,
    )


@app.route("/teacher/analytics")
@login_required
def teacher_analytics():
    """
    Формує аналітичні дані за спробами студентів із підтримкою
    фільтрації за дисципліною, лабораторною роботою, групою та датою.

    Адміністратор має доступ до всіх даних, тоді як для викладача
    вибірка обмежується його власними лабораторними роботами та
    призначеними поєднаннями дисциплін і навчальних груп.
    """
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in {"teacher", "admin"}:
        flash(
            "Аналітика доступна лише викладачу або адміністратору."
        )
        return redirect(url_for("index"))

    is_admin = current_role == "admin"

    selected_discipline = request.args.get(
        "discipline",
        "",
    ).strip()

    selected_lab_id_raw = request.args.get(
        "lab_id",
        "",
    ).strip()

    selected_group = request.args.get(
        "group",
        "",
    ).strip()

    date_from = request.args.get(
        "date_from",
        "",
    ).strip()

    date_to = request.args.get(
        "date_to",
        "",
    ).strip()

    selected_lab_id = None

    if selected_lab_id_raw:
        try:
            selected_lab_id = int(selected_lab_id_raw)
        except ValueError:
            flash("Некоректний ідентифікатор лабораторної роботи.")
            return redirect(url_for("teacher_analytics"))

        if selected_lab_id <= 0:
            flash("Некоректний ідентифікатор лабораторної роботи.")
            return redirect(url_for("teacher_analytics"))

    # Дати перевіряються на сервері, оскільки значення query-параметрів
    # не можна вважати коректними лише через використання HTML date input.
    try:
        if date_from:
            datetime.strptime(date_from, "%Y-%m-%d")

        if date_to:
            datetime.strptime(date_to, "%Y-%m-%d")

    except ValueError:
        flash("Дата має бути в форматі РРРР-ММ-ДД.")
        return redirect(url_for("teacher_analytics"))

    if date_from and date_to and date_from > date_to:
        flash(
            "Початкова дата не може бути пізнішою за кінцеву."
        )
        return redirect(url_for("teacher_analytics"))

    conn = get_db()

    try:
        # -------------------------------------------------
        # 1. Списки для фільтрів
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
                SELECT
                    id,
                    title,
                    discipline
                FROM labs
                ORDER BY discipline ASC, title ASC
                """
            ).fetchall()

        else:
            disciplines = conn.execute(
                """
                SELECT DISTINCT
                    labs.discipline
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
                    current_username,
                ),
            ).fetchall()

            groups = conn.execute(
                """
                SELECT DISTINCT
                    users.student_group
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
                            JOIN labs
                                ON submissions.lab_id = labs.id
                            WHERE submissions.username = users.username
                              AND labs.created_by = ?
                        )
                  )
                ORDER BY users.student_group ASC
                """,
                (
                    current_username,
                    current_username,
                ),
            ).fetchall()

            labs_for_filter = conn.execute(
                """
                SELECT DISTINCT
                    labs.id,
                    labs.title,
                    labs.discipline
                FROM labs
                LEFT JOIN teacher_subject_groups tsg
                    ON tsg.discipline = labs.discipline
                   AND tsg.teacher_username = ?
                WHERE labs.created_by = ?
                   OR tsg.teacher_username = ?
                ORDER BY
                    labs.discipline ASC,
                    labs.title ASC
                """,
                (
                    current_username,
                    current_username,
                    current_username,
                ),
            ).fetchall()

        # -------------------------------------------------
        # 2. Основний запит спроб
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
            JOIN labs
                ON submissions.lab_id = labs.id
            LEFT JOIN users
                ON users.username = submissions.username
            WHERE 1 = 1
        """

        params = []

        if not is_admin:
            # Перевірка доступу виконується безпосередньо в SQL,
            # тому довільна зміна параметрів фільтра в URL не дозволяє
            # викладачу отримати результати недоступних студентів.
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

            params.extend(
                [
                    current_username,
                    current_username,
                ]
            )

        if selected_discipline:
            sql += """
                AND labs.discipline = ?
            """
            params.append(selected_discipline)

        if selected_lab_id is not None:
            sql += """
                AND labs.id = ?
            """
            params.append(selected_lab_id)

        if selected_group:
            sql += """
                AND users.student_group = ?
            """
            params.append(selected_group)

        if date_from:
            sql += """
                AND submissions.created_at >= ?
            """
            params.append(f"{date_from} 00:00:00")

        if date_to:
            sql += """
                AND submissions.created_at <= ?
            """
            params.append(f"{date_to} 23:59:59")

        sql += """
            ORDER BY
                submissions.created_at ASC,
                submissions.id ASC
        """

        rows = conn.execute(
            sql,
            params,
        ).fetchall()

    finally:
        conn.close()

    attempts = [dict(row) for row in rows]

    # -------------------------------------------------
    # 3. Групування за студентом і лабораторною роботою
    # -------------------------------------------------

    student_lab_map = {}

    for attempt in attempts:
        key = (
            attempt["username"],
            attempt["lab_id"],
        )

        if key not in student_lab_map:
            student_lab_map[key] = {
                "username": attempt["username"],
                "full_name": (
                    attempt["full_name"]
                    or attempt["username"]
                ),
                "student_group": (
                    attempt["student_group"]
                    or "—"
                ),
                "lab_id": attempt["lab_id"],
                "lab_title": attempt["lab_title"],
                "discipline": (
                    attempt["discipline"]
                    or "—"
                ),
                "topic": normalize_lab_topic_for_analytics(
                    attempt["lab_topic"],
                    attempt["lab_title"],
                ),
                "attempts": [],
            }

        student_lab_map[key]["attempts"].append(attempt)

    student_lab_results = []

    for item in student_lab_map.values():
        item_attempts = item["attempts"]

        # Основним критерієм порядку є номер спроби.
        # Дата створення та id використовуються як додаткові критерії,
        # щоб порядок залишався детермінованим навіть за наявності
        # неконсистентних або однакових номерів спроб.
        item_attempts.sort(
            key=lambda row: (
                int(row["attempt_number"] or 1),
                row["created_at"] or "",
                int(row["id"]),
            )
        )

        best_score = max(
            int(row["score"] or 0)
            for row in item_attempts
        )

        attempts_count = len(item_attempts)

        # Лабораторна робота вважається успішно виконаною,
        # якщо хоча б одна зі спроб завершилася статусом PASSED.
        is_passed = any(
            row["status"] == "PASSED"
            for row in item_attempts
        )

        first_attempt = item_attempts[0]
        first_try_passed = (
            first_attempt["status"] == "PASSED"
        )

        last_attempt = item_attempts[-1]

        student_lab_results.append(
            {
                "username": item["username"],
                "full_name": item["full_name"],
                "student_group": item["student_group"],
                "lab_id": item["lab_id"],
                "lab_title": item["lab_title"],
                "discipline": item["discipline"],
                "topic": item["topic"],
                "topic_display": get_topic_display_name(
                    item["topic"]
                ),
                "best_score": best_score,
                "attempts_count": attempts_count,
                "is_passed": is_passed,
                "first_try_passed": first_try_passed,
                "last_status": last_attempt["status"],
                "last_created_at": last_attempt["created_at"],
            }
        )

    # -------------------------------------------------
    # 4. Загальні показники
    # -------------------------------------------------

    total_students = len(
        {
            row["username"]
            for row in attempts
        }
    )

    total_submissions = len(attempts)
    total_student_lab_pairs = len(student_lab_results)

    if student_lab_results:
        results_count = len(student_lab_results)

        # Для загальної успішності використовується найкращий результат
        # кожного студента за кожною лабораторною роботою. Таким чином
        # велика кількість невдалих повторних спроб одного студента
        # не спотворює середній підсумковий результат.
        average_score = round(
            sum(
                item["best_score"]
                for item in student_lab_results
            )
            / results_count,
            1,
        )

        average_attempts = round(
            sum(
                item["attempts_count"]
                for item in student_lab_results
            )
            / results_count,
            2,
        )

        success_count = sum(
            1
            for item in student_lab_results
            if item["is_passed"]
        )

        first_try_count = sum(
            1
            for item in student_lab_results
            if item["first_try_passed"]
        )

        success_percent = round(
            success_count * 100 / results_count,
            1,
        )

        first_try_percent = round(
            first_try_count * 100 / results_count,
            1,
        )

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
        "first_try_percent": first_try_percent,
    }

    # -------------------------------------------------
    # 5. Аналітика за лабораторними роботами
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
                "errors_count": 0,
            }

        lab_item = lab_map[lab_id]

        lab_item["students_count"] += 1
        lab_item["best_scores"].append(
            result["best_score"]
        )
        lab_item["attempts_counts"].append(
            result["attempts_count"]
        )

        if result["is_passed"]:
            lab_item["passed_count"] += 1

        if result["first_try_passed"]:
            lab_item["first_try_count"] += 1

    # Кількість помилок розраховується за всіма спробами.
    # Показник відображає інтенсивність виникнення проблем під час
    # виконання лабораторної роботи, а не лише кількість студентів,
    # які хоча б один раз припустилися помилки.
    for attempt in attempts:
        error_type = attempt["error_type"] or ""

        if not error_type or error_type == "NO_ERROR":
            continue

        lab_id = attempt["lab_id"]

        if lab_id in lab_map:
            lab_map[lab_id]["errors_count"] += 1

    lab_analytics = []

    for lab_item in lab_map.values():
        students_count = lab_item["students_count"]

        if students_count > 0:
            avg_score = round(
                sum(lab_item["best_scores"])
                / students_count,
                1,
            )

            avg_attempts = round(
                sum(lab_item["attempts_counts"])
                / students_count,
                2,
            )

            success_percent_lab = round(
                lab_item["passed_count"]
                * 100
                / students_count,
                1,
            )

            first_try_percent_lab = round(
                lab_item["first_try_count"]
                * 100
                / students_count,
                1,
            )

        else:
            avg_score = 0
            avg_attempts = 0
            success_percent_lab = 0
            first_try_percent_lab = 0

        # Евристичний індекс поєднує рівень отриманих балів,
        # середню кількість спроб і загальну кількість помилок.
        # Формула має бути узгоджена з методикою експериментального
        # дослідження, оскільки errors_count залежить від обсягу вибірки.
        difficulty_index = round(
            (100 - avg_score)
            + avg_attempts * 10
            + lab_item["errors_count"] * 2,
            1,
        )

        lab_analytics.append(
            {
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
                "difficulty_index": difficulty_index,
            }
        )

    lab_analytics.sort(
        key=lambda item: item["difficulty_index"],
        reverse=True,
    )

    hardest_lab = (
        lab_analytics[0]
        if lab_analytics
        else None
    )

    # -------------------------------------------------
    # 6. Аналіз помилок за типами та темами
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
            attempt["lab_title"],
        )

        error_key = (
            error_type,
            error_title,
        )

        if error_key not in error_map:
            error_map[error_key] = {
                "error_type": error_type,
                "error_title": (
                    error_title
                    or error_type
                ),
                "count": 0,
            }

        error_map[error_key]["count"] += 1

        topic_key = (
            topic,
            error_type,
            error_title,
        )

        if topic_key not in topic_error_map:
            topic_error_map[topic_key] = {
                "topic": topic,
                "topic_display": get_topic_display_name(
                    topic
                ),
                "error_type": error_type,
                "error_title": (
                    error_title
                    or error_type
                ),
                "count": 0,
            }

        topic_error_map[topic_key]["count"] += 1

    common_errors = sorted(
        error_map.values(),
        key=lambda item: item["count"],
        reverse=True,
    )[:10]

    topic_error_rows = sorted(
        topic_error_map.values(),
        key=lambda item: item["count"],
        reverse=True,
    )[:15]


    # -------------------------------------------------
    # 7. Динаміка результатів за датами
    # -------------------------------------------------

    dynamics_map = {}

    for attempt in attempts:
        created_at = attempt["created_at"] or ""

        try:
            attempt_date = datetime.strptime(
                created_at,
                "%Y-%m-%d %H:%M:%S",
            ).date()

        except ValueError:
            # Некоректний timestamp свідчить про проблему цілісності
            # збережених даних, тому така спроба не включається
            # до часової аналітики.
            app.logger.warning(
                "Некоректна дата спроби submission_id=%s: %r.",
                attempt["id"],
                created_at,
            )
            continue

        day = attempt_date.isoformat()

        if day not in dynamics_map:
            dynamics_map[day] = {
                "date": day,
                "scores": [],
                "submissions_count": 0,
                "passed_count": 0,
            }

        dynamics_map[day]["scores"].append(
            int(attempt["score"] or 0)
        )
        dynamics_map[day]["submissions_count"] += 1

        if attempt["status"] == "PASSED":
            dynamics_map[day]["passed_count"] += 1

    dynamics_rows = []

    for item in dynamics_map.values():
        submissions_count = item["submissions_count"]

        if item["scores"]:
            avg_day_score = round(
                sum(item["scores"])
                / len(item["scores"]),
                1,
            )
        else:
            avg_day_score = 0

        if submissions_count > 0:
            day_success_percent = round(
                item["passed_count"]
                * 100
                / submissions_count,
                1,
            )
        else:
            day_success_percent = 0

        dynamics_rows.append(
            {
                "date": item["date"],
                "avg_score": avg_day_score,
                "submissions_count": submissions_count,
                "success_percent": day_success_percent,
            }
        )

    # Формат YYYY-MM-DD дозволяє коректно використовувати
    # лексикографічне сортування для хронологічного порядку.
    dynamics_rows.sort(
        key=lambda item: item["date"]
    )

    # -------------------------------------------------
    # 8. Формування сторінки аналітики
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
        date_to=date_to,
    )


@app.route("/teacher/journal")
@login_required
def teacher_journal():
    """
    Відображає журнал успішності студентів за лабораторними роботами.

    Адміністратор має доступ до всього журналу. Для викладача доступ
    обмежується власними лабораторними роботами та призначеними
    дисциплінами і навчальними групами. Для кожної комбінації
    «студент — лабораторна робота» додатково перевіряється право
    перегляду та редагування оцінки.
    """
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in {"teacher", "admin"}:
        flash(
            "Журнал оцінок доступний лише викладачу "
            "або адміністратору."
        )
        return redirect(url_for("index"))

    is_admin = current_role == "admin"

    selected_discipline = request.args.get(
        "discipline",
        "",
    ).strip()

    selected_lab_id_raw = request.args.get(
        "lab_id",
        "",
    ).strip()

    selected_group = request.args.get(
        "group",
        "",
    ).strip()

    selected_lab_id = None

    if selected_lab_id_raw:
        try:
            selected_lab_id = int(selected_lab_id_raw)
        except ValueError:
            flash(
                "Некоректний ідентифікатор лабораторної роботи."
            )
            return redirect(url_for("teacher_journal"))

        if selected_lab_id <= 0:
            flash(
                "Некоректний ідентифікатор лабораторної роботи."
            )
            return redirect(url_for("teacher_journal"))

    conn = get_db()

    try:
        # -----------------------------
        # 1. Дисципліни для фільтра
        # -----------------------------

        if is_admin:
            disciplines = conn.execute(
                """
                SELECT DISTINCT
                    name AS discipline
                FROM disciplines
                WHERE name IS NOT NULL
                  AND name != ''
                ORDER BY name ASC
                """
            ).fetchall()

            # Fallback підтримує старі дані, якщо окремий довідник
            # дисциплін ще не був заповнений.
            if not disciplines:
                disciplines = conn.execute(
                    """
                    SELECT DISTINCT
                        discipline
                    FROM labs
                    WHERE discipline IS NOT NULL
                      AND discipline != ''
                    ORDER BY discipline ASC
                    """
                ).fetchall()

        else:
            disciplines = conn.execute(
                """
                SELECT DISTINCT
                    labs.discipline
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
                    current_username,
                ),
            ).fetchall()

        # -----------------------------
        # 2. Лабораторні роботи журналу
        # -----------------------------

        if is_admin:
            labs_sql = """
                SELECT DISTINCT
                    labs.*
                FROM labs
                WHERE 1 = 1
            """

            labs_params = []

        else:
            labs_sql = """
                SELECT DISTINCT
                    labs.*
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
                current_username,
            ]

        if selected_discipline:
            labs_sql += """
                AND labs.discipline = ?
            """
            labs_params.append(selected_discipline)

        if selected_lab_id is not None:
            labs_sql += """
                AND labs.id = ?
            """
            labs_params.append(selected_lab_id)

        labs_sql += """
            ORDER BY
                labs.created_at ASC,
                labs.id ASC
        """

        labs = conn.execute(
            labs_sql,
            labs_params,
        ).fetchall()

        # -----------------------------
        # 3. Лабораторні роботи для фільтра
        # -----------------------------

        if is_admin:
            labs_for_filter = conn.execute(
                """
                SELECT DISTINCT
                    labs.id,
                    labs.title,
                    labs.discipline
                FROM labs
                ORDER BY
                    labs.discipline ASC,
                    labs.title ASC
                """
            ).fetchall()

        else:
            labs_for_filter = conn.execute(
                """
                SELECT DISTINCT
                    labs.id,
                    labs.title,
                    labs.discipline
                FROM labs
                LEFT JOIN teacher_subject_groups tsg
                    ON tsg.discipline = labs.discipline
                   AND tsg.teacher_username = ?
                WHERE labs.created_by = ?
                   OR tsg.teacher_username = ?
                ORDER BY
                    labs.discipline ASC,
                    labs.title ASC
                """,
                (
                    current_username,
                    current_username,
                    current_username,
                ),
            ).fetchall()

        # -----------------------------
        # 4. Навчальні групи для фільтра
        # -----------------------------

        if is_admin:
            groups = conn.execute(
                """
                SELECT DISTINCT
                    name AS student_group
                FROM study_groups
                WHERE name IS NOT NULL
                  AND name != ''
                ORDER BY name ASC
                """
            ).fetchall()

            # Fallback використовується для сумісності зі старими
            # записами, якщо довідник груп ще не заповнений.
            if not groups:
                groups = conn.execute(
                    """
                    SELECT DISTINCT
                        student_group
                    FROM users
                    WHERE role = 'student'
                      AND student_group IS NOT NULL
                      AND student_group != ''
                    ORDER BY student_group ASC
                    """
                ).fetchall()

        else:
            groups = conn.execute(
                """
                SELECT DISTINCT
                    users.student_group
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
                            JOIN labs
                                ON submissions.lab_id = labs.id
                            WHERE submissions.username = users.username
                              AND labs.created_by = ?
                        )
                  )
                ORDER BY users.student_group ASC
                """,
                (
                    current_username,
                    current_username,
                ),
            ).fetchall()

        # -----------------------------
        # 5. Студенти журналу
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
                            JOIN labs
                                ON submissions.lab_id = labs.id
                            WHERE submissions.username = users.username
                              AND labs.created_by = ?
                        )
                  )
            """

            students_params = [
                current_username,
                current_username,
            ]

        if selected_group:
            students_sql += """
                AND student_group = ?
            """
            students_params.append(selected_group)

        students_sql += """
            ORDER BY
                student_group ASC,
                full_name ASC
        """

        students = conn.execute(
            students_sql,
            students_params,
        ).fetchall()

        # -----------------------------
        # 6. Формування журналу за групами
        # -----------------------------

        journal_by_groups = {}

        for student in students:
            group_name = (
                student["student_group"]
                or "Без групи"
            )

            if group_name not in journal_by_groups:
                journal_by_groups[group_name] = []

            cells = []
            total_score = 0
            completed_count = 0

            for lab in labs:
                # Окремо перевіряється доступ до конкретної комбінації
                # «студент — лабораторна робота». Це необхідно, оскільки
                # списки студентів і лабораторних формуються незалежно
                # та самі по собі не гарантують право доступу до кожної
                # можливої комбінації.
                if (
                    not is_admin
                    and not can_edit_lab_grade(
                        conn,
                        current_username,
                        current_role,
                        student["username"],
                        lab["id"],
                    )
                ):
                    # Порожня службова комірка зберігає структуру таблиці,
                    # але не розкриває викладачу недоступні результати.
                    cells.append(
                        {
                            "lab_id": lab["id"],
                            "is_accessible": False,
                            "display_score": None,
                            "auto_score": None,
                            "manual_score": None,
                            "grade_source": "",
                            "manual_comment": "",
                            "edited_by": "",
                            "edited_at": "",
                            "attempts_count": 0,
                            "last_status": "",
                            "last_created_at": "",
                            "used_attempts": 0,
                            "base_limit": 0,
                            "extra_attempts": 0,
                            "total_limit": 0,
                            "attempts_left": 0,
                            "is_limit_reached": False,
                        }
                    )
                    continue

                # Для автоматичної оцінки використовується найкращий
                # підсумковий результат. Поле score залишається fallback
                # для старих записів, у яких final_score ще відсутній.
                result = conn.execute(
                    """
                    SELECT
                        MAX(
                            COALESCE(
                                submissions.final_score,
                                submissions.score
                            )
                        ) AS best_score,

                        (
                            SELECT s2.status
                            FROM submissions s2
                            WHERE s2.username = ?
                              AND s2.lab_id = ?
                            ORDER BY
                                s2.id DESC
                            LIMIT 1
                        ) AS last_status,

                        (
                            SELECT s2.created_at
                            FROM submissions s2
                            WHERE s2.username = ?
                              AND s2.lab_id = ?
                            ORDER BY
                                s2.id DESC
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
                        lab["id"],
                    ),
                ).fetchone()

                override = conn.execute(
                    """
                    SELECT
                        score,
                        comment,
                        edited_by,
                        edited_at
                    FROM grade_overrides
                    WHERE username = ?
                      AND lab_id = ?
                    """,
                    (
                        student["username"],
                        lab["id"],
                    ),
                ).fetchone()

                auto_score = (
                    result["best_score"]
                    if result
                    and result["best_score"] is not None
                    else None
                )

                last_status = (
                    result["last_status"]
                    if result
                    else ""
                )

                last_created_at = (
                    result["last_created_at"]
                    if result
                    else ""
                )

                manual_score = (
                    override["score"]
                    if override
                    else None
                )

                manual_comment = (
                    override["comment"]
                    if override
                    else ""
                )

                edited_by = (
                    override["edited_by"]
                    if override
                    else ""
                )

                edited_at = (
                    override["edited_at"]
                    if override
                    else ""
                )

                # Ручне перевизначення має пріоритет лише для
                # відображуваної академічної оцінки. Первинний
                # автоматичний результат при цьому не змінюється.
                if manual_score is not None:
                    display_score = manual_score
                    grade_source = "manual"
                else:
                    display_score = auto_score
                    grade_source = "auto"

                if display_score is not None:
                    total_score += int(display_score)
                    completed_count += 1

                # Інформація про спроби обчислюється тією самою
                # централізованою функцією, що використовується
                # під час надсилання нового HDL-розв'язання.
                attempts_info = get_attempts_info(
                    conn=conn,
                    lab=lab,
                    username=student["username"],
                )

                cells.append(
                    {
                        "lab_id": lab["id"],
                        "is_accessible": True,
                        "display_score": display_score,
                        "auto_score": auto_score,
                        "manual_score": manual_score,
                        "grade_source": grade_source,
                        "manual_comment": manual_comment,
                        "edited_by": edited_by,
                        "edited_at": edited_at,

                        "attempts_count": (
                            attempts_info["used_attempts"]
                        ),
                        "last_status": last_status,
                        "last_created_at": last_created_at,

                        "used_attempts": (
                            attempts_info["used_attempts"]
                        ),
                        "base_limit": (
                            attempts_info["base_limit"]
                        ),
                        "extra_attempts": (
                            attempts_info["extra_attempts"]
                        ),
                        "total_limit": (
                            attempts_info["total_limit"]
                        ),
                        "attempts_left": (
                            attempts_info["attempts_left"]
                        ),
                        "is_limit_reached": (
                            attempts_info["is_limit_reached"]
                        ),
                    }
                )

            average_score = (
                round(
                    total_score / completed_count,
                    1,
                )
                if completed_count > 0
                else None
            )

            journal_by_groups[group_name].append(
                {
                    "student": student,
                    "cells": cells,
                    "average_score": average_score,
                    "completed_count": completed_count,
                }
            )

        # -----------------------------
        # 7. Зведені показники журналу
        # -----------------------------

        journal_summary = {}

        for group_name, rows in journal_by_groups.items():
            total_score = 0
            scored_cells_count = 0
            passed_cells_count = 0
            exhausted_students = set()
            manual_overrides_count = 0

            for row in rows:
                student_username = row["student"]["username"]

                for cell in row["cells"]:
                    if not cell.get("is_accessible", True):
                        continue

                    display_score = cell.get("display_score")

                    if display_score is not None:
                        score_value = int(display_score)

                        total_score += score_value
                        scored_cells_count += 1

                        if score_value >= JOURNAL_PASSING_SCORE:
                            passed_cells_count += 1

                    # Студент враховується як такий, що вичерпав спроби
                    # з незадовільним результатом, лише якщо для комірки
                    # вже існує оцінка нижче прохідного порога.
                    if (
                        cell.get("is_limit_reached")
                        and display_score is not None
                        and int(display_score)
                        < JOURNAL_PASSING_SCORE
                    ):
                        exhausted_students.add(
                            student_username
                        )

                    if cell.get("manual_score") is not None:
                        manual_overrides_count += 1

            average_score = (
                round(
                    total_score / scored_cells_count,
                    1,
                )
                if scored_cells_count > 0
                else 0
            )

            journal_summary[group_name] = {
                "average_score": average_score,
                "passed_count": passed_cells_count,
                "exhausted_students_count": len(
                    exhausted_students
                ),
                "manual_overrides_count": (
                    manual_overrides_count
                ),
            }

    finally:
        conn.close()

    return render_template(
        "teacher/journal.html",
        groups=groups,
        disciplines=disciplines,
        labs=labs,
        labs_for_filter=labs_for_filter,
        journal_by_groups=journal_by_groups,
        journal_summary=journal_summary,
        selected_discipline=selected_discipline,
        selected_lab_id=selected_lab_id,
        selected_group=selected_group,
    )


@app.route("/teacher/attempts/grant", methods=["POST"])
@teacher_required
def teacher_grant_extra_attempt():
    """
    Надає студенту одну додаткову спробу для вибраної
    лабораторної роботи.

    Перед створенням запису перевіряються існування студента,
    лабораторної роботи та право поточного користувача працювати
    з відповідною парою «студент — лабораторна робота».
    """
    current_role = session.get("role")
    current_username = session.get("username")

    if current_role not in {"teacher", "admin"}:
        flash(
            "Надавати додаткові спроби може лише викладач "
            "або адміністратор."
        )
        return redirect(url_for("index"))

    lab_id = (
        request.form.get("lab_id", type=int)
        or request.args.get("lab_id", type=int)
    )

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

    if lab_id is None or lab_id <= 0 or not username:
        flash(
            "Не вдалося визначити лабораторну роботу або студента."
        )
        return redirect(url_for("teacher_journal"))

    if not reason:
        reason = "Додаткову спробу надано викладачем."

    conn = get_db()

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
              AND role = 'student'
            """,
            (username,),
        ).fetchone()

        if lab is None or student is None:
            flash(
                "Лабораторну роботу або студента не знайдено."
            )
            return redirect(url_for("teacher_journal"))

        # Перевірка ролі сама по собі не гарантує права на зміну
        # навчальних даних конкретного студента. Тому додатково
        # перевіряється доступ до відповідної лабораторної роботи.
        if not can_edit_lab_grade(
            conn,
            current_username,
            current_role,
            username,
            lab_id,
        ):
            flash(
                "У вас немає прав для надання додаткової спроби "
                "цьому студенту."
            )
            return redirect(url_for("teacher_journal"))

        conn.execute(
            """
            INSERT INTO attempt_overrides
            (
                lab_id,
                username,
                extra_attempts,
                reason,
                granted_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lab_id,
                username,
                1,
                reason,
                current_username,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()

        # Надання додаткової спроби змінює умови оцінювання студента,
        # тому операція фіксується в серверному журналі аудиту.
        app.logger.info(
            "Користувач '%s' надав студенту '%s' одну додаткову "
            "спробу для lab_id=%s.",
            current_username,
            username,
            lab_id,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(
        f"Студенту {username} додано одну додаткову спробу."
    )
    return redirect(url_for("teacher_journal"))


@app.route("/teacher/labs")
@teacher_required
def teacher_labs():
    """
    Відображає доступні викладачу лабораторні роботи та статистику
    студентських відправок.

    Для лабораторних робіт, доступ до яких отримано через призначення
    дисципліни, статистика враховує лише студентів із призначених
    викладачу навчальних груп.
    """
    current_username = session.get("username")
    conn = get_db()

    try:
        # Перелік доступних лабораторних і перелік доступних відправок
        # формуються окремо. Це запобігає включенню до агрегованої
        # статистики результатів студентів із чужих навчальних груп.
        labs = conn.execute(
            """
            WITH accessible_submissions AS (
                SELECT
                    submissions.*
                FROM submissions
                JOIN labs AS submission_labs
                    ON submission_labs.id = submissions.lab_id
                LEFT JOIN users
                    ON users.username = submissions.username
                WHERE submission_labs.created_by = ?
                   OR EXISTS (
                        SELECT 1
                        FROM teacher_subject_groups tsg
                        WHERE tsg.teacher_username = ?
                          AND tsg.discipline =
                              submission_labs.discipline
                          AND tsg.student_group =
                              users.student_group
                   )
            )
            SELECT
                labs.*,
                COUNT(
                    accessible_submissions.id
                ) AS submissions_count,
                ROUND(
                    AVG(
                        COALESCE(
                            accessible_submissions.final_score,
                            accessible_submissions.score
                        )
                    ),
                    1
                ) AS average_score,
                COUNT(
                    CASE
                        WHEN accessible_submissions.status = 'PASSED'
                        THEN 1
                    END
                ) AS passed_count
            FROM labs
            LEFT JOIN accessible_submissions
                ON accessible_submissions.lab_id = labs.id
            WHERE labs.created_by = ?
               OR EXISTS (
                    SELECT 1
                    FROM teacher_subject_groups tsg
                    WHERE tsg.teacher_username = ?
                      AND tsg.discipline = labs.discipline
               )
            GROUP BY labs.id
            ORDER BY
                labs.discipline ASC,
                labs.id DESC
            """,
            (
                current_username,
                current_username,
                current_username,
                current_username,
            ),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "teacher/labs.html",
        labs=labs,
    )

@app.route("/teacher/submissions-history")
@teacher_required
def teacher_submissions_history():
    """
    Відображає історію відправок студентів із пошуком, фільтрацією
    та сортуванням результатів.

    Спроби групуються за парою «студент — лабораторна робота».
    Для кожної групи визначаються найкращий результат і спроба,
    яка використовується для стислого представлення в інтерфейсі.
    """
    current_username = session.get("username")

    search_query = request.args.get(
        "q",
        "",
    ).strip()

    selected_discipline = request.args.get(
        "discipline",
        "",
    ).strip()

    selected_lab_id_raw = request.args.get(
        "lab_id",
        "",
    ).strip()

    selected_group = request.args.get(
        "group",
        "",
    ).strip()

    selected_status = request.args.get(
        "status",
        "",
    ).strip()

    selected_error_type = request.args.get(
        "error_type",
        "",
    ).strip()

    date_from = request.args.get(
        "date_from",
        "",
    ).strip()

    date_to = request.args.get(
        "date_to",
        "",
    ).strip()

    sort = request.args.get(
        "sort",
        "submitted_at",
    ).strip()

    direction = request.args.get(
        "direction",
        "desc",
    ).strip().lower()

    allowed_sort_fields = {
        "submitted_at",
        "student",
        "group",
        "lab",
        "best_score",
        "status",
        "attempt",
    }

    if direction not in {"asc", "desc"}:
        direction = "desc"

    if sort not in allowed_sort_fields:
        sort = "submitted_at"

    selected_lab_id = None

    if selected_lab_id_raw:
        try:
            selected_lab_id = int(selected_lab_id_raw)
        except ValueError:
            flash(
                "Некоректний ідентифікатор лабораторної роботи."
            )
            return redirect(
                url_for("teacher_submissions_history")
            )

        if selected_lab_id <= 0:
            flash(
                "Некоректний ідентифікатор лабораторної роботи."
            )
            return redirect(
                url_for("teacher_submissions_history")
            )

    # Дати перевіряються на сервері, оскільки query-параметри
    # не можна вважати коректними лише на підставі HTML-форми.
    try:
        if date_from:
            datetime.strptime(
                date_from,
                "%Y-%m-%d",
            )

        if date_to:
            datetime.strptime(
                date_to,
                "%Y-%m-%d",
            )

    except ValueError:
        flash("Дата має бути у форматі РРРР-ММ-ДД.")
        return redirect(
            url_for("teacher_submissions_history")
        )

    if date_from and date_to and date_from > date_to:
        flash(
            "Початкова дата не може бути пізнішою за кінцеву."
        )
        return redirect(
            url_for("teacher_submissions_history")
        )

    conn = get_db()

    try:
        # Функція має повертати лише статичне серверне SQL-умовлення
        # доступу. Усі користувацькі значення передаються окремими
        # параметрами SQLite.
        access_condition = get_teacher_access_condition()

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
            JOIN labs
                ON submissions.lab_id = labs.id
            LEFT JOIN users
                ON submissions.username = users.username
            WHERE {access_condition}
        """

        params = [
            current_username,
            current_username,
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

            params.extend(
                [
                    search_value,
                    search_value,
                    search_value,
                    search_value,
                ]
            )

        if selected_discipline:
            sql += """
                AND labs.discipline = ?
            """
            params.append(selected_discipline)

        if selected_lab_id is not None:
            sql += """
                AND labs.id = ?
            """
            params.append(selected_lab_id)

        if selected_group:
            sql += """
                AND users.student_group = ?
            """
            params.append(selected_group)

        if selected_status:
            sql += """
                AND submissions.status = ?
            """
            params.append(selected_status)

        if selected_error_type:
            sql += """
                AND submissions.error_type = ?
            """
            params.append(selected_error_type)

        if date_from:
            sql += """
                AND submissions.created_at >= ?
            """
            params.append(f"{date_from} 00:00:00")

        if date_to:
            sql += """
                AND submissions.created_at <= ?
            """
            params.append(f"{date_to} 23:59:59")

        # Первинне сортування забезпечує стабільний порядок спроб
        # усередині кожної пари «студент — лабораторна робота».
        sql += """
            ORDER BY
                submissions.username ASC,
                submissions.lab_id ASC,
                submissions.attempt_number DESC,
                submissions.created_at DESC,
                submissions.id DESC
        """

        attempt_rows = conn.execute(
            sql,
            params,
        ).fetchall()

        disciplines = conn.execute(
            """
            SELECT DISTINCT
                labs.discipline
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
                current_username,
            ),
        ).fetchall()

        labs_query = """
            SELECT DISTINCT
                labs.id,
                labs.title,
                labs.discipline
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
            current_username,
        ]

        if selected_discipline:
            labs_query += """
                AND labs.discipline = ?
            """
            labs_params.append(selected_discipline)

        labs_query += """
            ORDER BY
                labs.discipline ASC,
                labs.title ASC
        """

        labs = conn.execute(
            labs_query,
            labs_params,
        ).fetchall()

        groups = conn.execute(
            """
            SELECT DISTINCT
                users.student_group
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
                        JOIN labs
                            ON submissions.lab_id = labs.id
                        WHERE submissions.username = users.username
                          AND labs.created_by = ?
                    )
              )
            ORDER BY users.student_group ASC
            """,
            (
                current_username,
                current_username,
            ),
        ).fetchall()

    finally:
        conn.close()

    # Спроби об'єднуються в одну логічну групу для кожної
    # пари «студент — лабораторна робота».
    grouped = {}

    for row in attempt_rows:
        attempt = dict(row)

        key = (
            attempt["username"],
            attempt["lab_id"],
        )

        if key not in grouped:
            grouped[key] = {
                "username": attempt["username"],
                "full_name": (
                    attempt["full_name"]
                    or attempt["username"]
                ),
                "student_group": (
                    attempt["student_group"]
                    or "—"
                ),
                "lab_id": attempt["lab_id"],
                "lab_title": attempt["lab_title"],
                "lab_created_at": attempt["lab_created_at"],
                "discipline": (
                    attempt["discipline"]
                    or "—"
                ),
                "programming_language": (
                    attempt["programming_language"]
                    or "—"
                ),
                "checker_type": (
                    attempt["checker_type"]
                    or "—"
                ),
                "attempts": [],
            }

        grouped[key]["attempts"].append(attempt)

    def get_effective_score(attempt):
        """
        Повертає актуальний підсумковий бал спроби.

        final_score використовується як основне значення,
        а score — як fallback для старих записів.
        """
        final_score = attempt.get("final_score")

        if final_score is not None:
            return int(final_score)

        return int(attempt.get("score") or 0)

    submission_groups = []

    for group in grouped.values():
        attempts = group["attempts"]

        attempts.sort(
            key=lambda item: (
                int(item["attempt_number"] or 1),
                item["created_at"] or "",
                int(item["id"]),
            ),
            reverse=True,
        )

        best_score = max(
            get_effective_score(item)
            for item in attempts
        )

        successful_attempts = [
            item
            for item in attempts
            if item["status"] == "PASSED"
        ]

        # Якщо існує хоча б одна успішна спроба, для стислого
        # представлення вибирається найкраща серед успішних.
        # Інакше використовується найкраща з усіх наявних.
        candidate_attempts = (
            successful_attempts
            if successful_attempts
            else attempts
        )

        display_attempt = max(
            candidate_attempts,
            key=lambda item: (
                get_effective_score(item),
                int(item["attempt_number"] or 1),
                int(item["id"]),
            ),
        )

        display_label = (
            "Успішна спроба"
            if successful_attempts
            else "Найкраща спроба"
        )

        group["attempts_count"] = len(attempts)
        group["best_score"] = best_score
        group["display_attempt"] = display_attempt
        group["display_label"] = display_label

        submission_groups.append(group)

    def sort_value(group):
        """
        Формує значення для сортування згрупованих результатів.

        Сортування виконується після групування, оскільки частина
        критеріїв належить до агрегованої групи спроб, а не до
        окремого запису submissions.
        """
        display_attempt = group["display_attempt"]

        if sort == "student":
            return group["full_name"].casefold()

        if sort == "group":
            return group["student_group"].casefold()

        if sort == "lab":
            return group["lab_title"].casefold()

        if sort == "best_score":
            return int(group["best_score"] or 0)

        if sort == "status":
            return display_attempt["status"] or ""

        if sort == "attempt":
            return int(
                display_attempt["attempt_number"] or 1
            )

        return display_attempt["created_at"] or ""

    submission_groups.sort(
        key=sort_value,
        reverse=direction == "desc",
    )

    return render_template(
        "teacher/submissions_history.html",
        submission_groups=submission_groups,
        labs=labs,
        groups=groups,
        disciplines=disciplines,
        search_query=search_query,
        selected_discipline=selected_discipline,

        # У шаблон передається початкове строкове значення,
        # щоб не змінювати існуючу логіку вибору <option>.
        selected_lab_id=selected_lab_id_raw,

        selected_group=selected_group,
        selected_status=selected_status,
        selected_error_type=selected_error_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        direction=direction,
    )


def _get_manageable_student_groups(
    conn,
    current_username,
    current_role,
):
    """
    Повертає навчальні групи, у межах яких поточний користувач
    має право керувати обліковими записами студентів.

    Адміністратор отримує повний перелік груп, а викладач —
    лише групи, явно призначені йому адміністратором.
    """
    if current_role == "admin":
        return conn.execute(
            """
            SELECT DISTINCT
                name AS student_group
            FROM study_groups
            WHERE name IS NOT NULL
              AND name != ''
            ORDER BY name ASC
            """
        ).fetchall()

    return conn.execute(
        """
        SELECT DISTINCT
            student_group
        FROM teacher_subject_groups
        WHERE teacher_username = ?
          AND student_group IS NOT NULL
          AND student_group != ''
        ORDER BY student_group ASC
        """,
        (current_username,),
    ).fetchall()


def _can_manage_student_group(
    conn,
    current_username,
    current_role,
    student_group,
):
    """
    Перевіряє право користувача керувати студентами вибраної групи.

    Для операцій з обліковими записами використовується явне
    призначення групи, оскільки право перегляду лабораторної роботи
    не повинно автоматично надавати право змінювати персональні
    або автентифікаційні дані студента.
    """
    if current_role == "admin":
        return True

    access = conn.execute(
        """
        SELECT 1
        FROM teacher_subject_groups
        WHERE teacher_username = ?
          AND student_group = ?
        LIMIT 1
        """,
        (
            current_username,
            student_group,
        ),
    ).fetchone()

    return access is not None


@app.route("/teacher/students", methods=["GET", "POST"])
@teacher_required
def manage_students():
    """
    Забезпечує перегляд і створення облікових записів студентів,
    доступних поточному викладачу.

    Викладач працює лише зі студентами призначених йому навчальних
    груп. Адміністратор, якщо це дозволено декоратором teacher_required,
    може працювати з усіма групами.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    conn = get_db()

    try:
        if request.method == "POST":
            username = request.form.get(
                "username",
                "",
            ).strip()

            password = request.form.get(
                "password",
                "",
            )

            full_name = request.form.get(
                "full_name",
                "",
            ).strip()

            student_group = request.form.get(
                "student_group",
                "",
            ).strip()

            if (
                not username
                or not password
                or not full_name
                or not student_group
            ):
                flash("Необхідно заповнити всі поля.")
                return redirect(url_for("manage_students"))

            group_exists = conn.execute(
                """
                SELECT 1
                FROM study_groups
                WHERE name = ?
                LIMIT 1
                """,
                (student_group,),
            ).fetchone()

            if group_exists is None:
                flash("Вибрану навчальну групу не знайдено.")
                return redirect(url_for("manage_students"))

            # HTML-форма не є джерелом авторизації: викладач не може
            # створити студента в групі, яка йому не призначена.
            if not _can_manage_student_group(
                conn,
                current_username,
                current_role,
                student_group,
            ):
                flash(
                    "У вас немає прав для додавання студентів "
                    "до цієї навчальної групи."
                )
                return redirect(url_for("manage_students"))

            existing_user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE username = ?
                LIMIT 1
                """,
                (username,),
            ).fetchone()

            if existing_user is not None:
                flash(
                    "Користувач із таким логіном уже існує."
                )
                return redirect(url_for("manage_students"))

            password_ok, password_error = (
                validate_password_strength(
                    password,
                    username,
                )
            )

            if not password_ok:
                flash(password_error)
                return redirect(url_for("manage_students"))

            password_hash = hash_password(password)

            try:
                conn.execute(
                    """
                    INSERT INTO users
                    (
                        username,
                        password,
                        role,
                        full_name,
                        student_group
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        password_hash,
                        "student",
                        full_name,
                        student_group,
                    ),
                )

                conn.commit()

            except sqlite3.IntegrityError:
                conn.rollback()

                flash(
                    "Не вдалося створити студента через "
                    "конфлікт даних."
                )
                return redirect(url_for("manage_students"))

            app.logger.info(
                "Користувач '%s' створив обліковий запис "
                "студента '%s' у групі '%s'.",
                current_username,
                username,
                student_group,
            )

            flash("Студента успішно додано.")
            return redirect(url_for("manage_students"))

        search_query = request.args.get(
            "q",
            "",
        ).strip()

        selected_group = request.args.get(
            "group",
            "",
        ).strip()

        groups = _get_manageable_student_groups(
            conn,
            current_username,
            current_role,
        )

        if (
            selected_group
            and not _can_manage_student_group(
                conn,
                current_username,
                current_role,
                selected_group,
            )
        ):
            flash(
                "У вас немає доступу до вибраної навчальної групи."
            )
            return redirect(url_for("manage_students"))

        sql = """
            SELECT
                users.id,
                users.username,
                users.role,
                users.full_name,
                users.student_group,
                COUNT(submissions.id) AS attempts_count,
                ROUND(
                    AVG(
                        COALESCE(
                            submissions.final_score,
                            submissions.score
                        )
                    ),
                    1
                ) AS average_score,
                MAX(
                    COALESCE(
                        submissions.final_score,
                        submissions.score
                    )
                ) AS best_score
            FROM users
            LEFT JOIN submissions
                ON submissions.username = users.username
            WHERE users.role = 'student'
        """

        params = []

        if current_role != "admin":
            sql += """
                AND users.student_group IN (
                    SELECT student_group
                    FROM teacher_subject_groups
                    WHERE teacher_username = ?
                )
            """
            params.append(current_username)

        if search_query:
            sql += """
                AND (
                    users.full_name LIKE ?
                    OR users.username LIKE ?
                )
            """

            search_value = f"%{search_query}%"

            params.extend(
                [
                    search_value,
                    search_value,
                ]
            )

        if selected_group:
            sql += """
                AND users.student_group = ?
            """
            params.append(selected_group)

        sql += """
            GROUP BY
                users.id,
                users.username,
                users.role,
                users.full_name,
                users.student_group
            ORDER BY
                users.student_group ASC,
                users.full_name ASC
        """

        students = conn.execute(
            sql,
            params,
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "teacher/students.html",
        students=students,
        groups=groups,
        search_query=search_query,
        selected_group=selected_group,
    )


@app.route(
    "/teacher/edit-student/<int:user_id>",
    methods=["GET", "POST"],
)
@teacher_required
def edit_student(user_id):
    """
    Забезпечує редагування даних студента в межах області доступу
    поточного викладача.

    Зміна логіна виконується разом з оновленням пов'язаних академічних
    записів в одній транзакції, щоб уникнути часткового оновлення даних.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    conn = get_db()

    try:
        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
              AND role = 'student'
            """,
            (user_id,),
        ).fetchone()

        if student is None:
            flash("Студента не знайдено.")
            return redirect(url_for("manage_students"))

        # Перевіряється право саме на керування обліковим записом,
        # а не лише на перегляд результатів лабораторних робіт.
        if not _can_manage_student_group(
            conn,
            current_username,
            current_role,
            student["student_group"],
        ):
            flash(
                "У вас немає прав для редагування "
                "цього облікового запису студента."
            )
            return redirect(url_for("manage_students"))

        if request.method == "POST":
            username = request.form.get(
                "username",
                "",
            ).strip()

            # Пароль навмисно не обробляється через strip(),
            # оскільки пробіли можуть бути допустимими його символами.
            new_password = request.form.get(
                "password",
                "",
            )

            full_name = request.form.get(
                "full_name",
                "",
            ).strip()

            student_group = request.form.get(
                "student_group",
                "",
            ).strip()

            if (
                not username
                or not full_name
                or not student_group
            ):
                flash(
                    "Необхідно заповнити логін, повне ім'я та групу."
                )
                return redirect(
                    url_for(
                        "edit_student",
                        user_id=user_id,
                    )
                )

            group_exists = conn.execute(
                """
                SELECT 1
                FROM study_groups
                WHERE name = ?
                LIMIT 1
                """,
                (student_group,),
            ).fetchone()

            if group_exists is None:
                flash("Вибрану навчальну групу не знайдено.")
                return redirect(
                    url_for(
                        "edit_student",
                        user_id=user_id,
                    )
                )

            # Викладач не може використати редагування облікового
            # запису для перенесення студента до недоступної групи.
            if not _can_manage_student_group(
                conn,
                current_username,
                current_role,
                student_group,
            ):
                flash(
                    "У вас немає прав для переміщення студента "
                    "до цієї навчальної групи."
                )
                return redirect(
                    url_for(
                        "edit_student",
                        user_id=user_id,
                    )
                )

            existing_user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE username = ?
                  AND id != ?
                LIMIT 1
                """,
                (
                    username,
                    user_id,
                ),
            ).fetchone()

            if existing_user is not None:
                flash(
                    "Користувач із таким логіном уже існує."
                )
                return redirect(
                    url_for(
                        "edit_student",
                        user_id=user_id,
                    )
                )

            password_hash = None

            if new_password:
                password_ok, password_error = (
                    validate_password_strength(
                        new_password,
                        username,
                    )
                )

                if not password_ok:
                    flash(password_error)
                    return redirect(
                        url_for(
                            "edit_student",
                            user_id=user_id,
                        )
                    )

                password_hash = hash_password(new_password)

            old_username = student["username"]

            try:
                if password_hash is not None:
                    conn.execute(
                        """
                        UPDATE users
                        SET username = ?,
                            password = ?,
                            full_name = ?,
                            student_group = ?
                        WHERE id = ?
                          AND role = 'student'
                        """,
                        (
                            username,
                            password_hash,
                            full_name,
                            student_group,
                            user_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE users
                        SET username = ?,
                            full_name = ?,
                            student_group = ?
                        WHERE id = ?
                          AND role = 'student'
                        """,
                        (
                            username,
                            full_name,
                            student_group,
                            user_id,
                        ),
                    )

                if old_username != username:
                    # Ім'я користувача використовується як зв'язувальний
                    # ключ у кількох таблицях. Усі пов'язані записи
                    # оновлюються в межах однієї транзакції.
                    related_username_tables = (
                        "submissions",
                        "extra_task_attempts",
                        "grade_overrides",
                        "subject_final_grades",
                        "attempt_overrides",
                    )

                    for table_name in related_username_tables:
                        conn.execute(
                            f"""
                            UPDATE {table_name}
                            SET username = ?
                            WHERE username = ?
                            """,
                            (
                                username,
                                old_username,
                            ),
                        )

                conn.commit()

            except sqlite3.IntegrityError:
                conn.rollback()

                app.logger.exception(
                    "Помилка цілісності даних під час редагування "
                    "студента user_id=%s.",
                    user_id,
                )

                flash(
                    "Не вдалося оновити дані студента через "
                    "конфлікт пов'язаних записів."
                )
                return redirect(
                    url_for(
                        "edit_student",
                        user_id=user_id,
                    )
                )

            app.logger.info(
                "Користувач '%s' оновив дані студента "
                "user_id=%s: '%s' -> '%s', група '%s'.",
                current_username,
                user_id,
                old_username,
                username,
                student_group,
            )

            flash("Дані студента оновлено.")
            return redirect(url_for("manage_students"))

        groups = _get_manageable_student_groups(
            conn,
            current_username,
            current_role,
        )

    finally:
        conn.close()

    return render_template(
        "teacher/edit_student.html",
        student=student,
        groups=groups,
    )


def _remove_managed_artifact(base_directory, filename, artifact_type):
    """
    Безпечно видаляє файловий артефакт з керованого каталогу.

    Після нормалізації шлях повинен залишатися всередині заданого
    каталогу. Помилка видалення окремого файла журналюється, але
    не порушує вже завершену транзакцію видалення академічних даних.
    """
    if not filename:
        return

    base_path = os.path.realpath(base_directory)
    artifact_path = os.path.realpath(
        os.path.join(base_path, filename)
    )

    try:
        common_path = os.path.commonpath(
            [base_path, artifact_path]
        )
    except ValueError:
        common_path = ""

    if common_path != base_path:
        app.logger.warning(
            "Відхилено некоректний шлях до артефакту типу '%s': %r.",
            artifact_type,
            filename,
        )
        return

    if not os.path.isfile(artifact_path):
        return

    try:
        os.remove(artifact_path)
    except OSError:
        app.logger.exception(
            "Не вдалося видалити артефакт типу '%s': %s.",
            artifact_type,
            artifact_path,
        )


def _delete_student_related_data(conn, usernames):
    """
    Видаляє академічні записи студентів і повертає перелік
    файлових артефактів, які необхідно видалити після commit.

    Пов'язані записи видаляються до submissions, щоб не залишати
    сирітські дані та не порушувати можливі зовнішні ключі SQLite.
    """
    if not usernames:
        return [], []

    username_placeholders = ", ".join(
        ["?"] * len(usernames)
    )

    submission_rows = conn.execute(
        f"""
        SELECT
            id,
            filename,
            waveform_filename
        FROM submissions
        WHERE username IN ({username_placeholders})
        """,
        usernames,
    ).fetchall()

    submission_ids = [
        row["id"]
        for row in submission_rows
    ]

    solution_files = [
        row["filename"]
        for row in submission_rows
        if row["filename"]
    ]

    waveform_files = [
        row["waveform_filename"]
        for row in submission_rows
        if row["waveform_filename"]
    ]

    if submission_ids:
        submission_placeholders = ", ".join(
            ["?"] * len(submission_ids)
        )

        conn.execute(
            f"""
            DELETE FROM extra_task_attempts
            WHERE submission_id IN ({submission_placeholders})
            """,
            submission_ids,
        )

    # Додаткове видалення за username захищає від старих або
    # неконсистентних записів, які могли втратити зв'язок із submission.
    conn.execute(
        f"""
        DELETE FROM extra_task_attempts
        WHERE username IN ({username_placeholders})
        """,
        usernames,
    )

    for table_name in (
        "grade_overrides",
        "subject_final_grades",
        "attempt_overrides",
    ):
        conn.execute(
            f"""
            DELETE FROM {table_name}
            WHERE username IN ({username_placeholders})
            """,
            usernames,
        )

    conn.execute(
        f"""
        DELETE FROM submissions
        WHERE username IN ({username_placeholders})
        """,
        usernames,
    )

    return solution_files, waveform_files


@app.route(
    "/teacher/delete-student/<int:user_id>",
    methods=["POST"],
)
@teacher_required
def delete_student(user_id):
    """
    Видаляє обліковий запис студента разом із пов'язаними
    академічними записами та файловими артефактами.

    Викладач може видаляти лише студентів тих навчальних груп,
    які явно призначені йому адміністратором.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    conn = get_db()

    solution_files = []
    waveform_files = []

    try:
        student = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
              AND role = 'student'
            """,
            (user_id,),
        ).fetchone()

        if student is None:
            flash("Студента не знайдено.")
            return redirect(url_for("manage_students"))

        if not _can_manage_student_group(
            conn,
            current_username,
            current_role,
            student["student_group"],
        ):
            flash(
                "У вас немає прав для видалення цього студента."
            )
            return redirect(url_for("manage_students"))

        username = student["username"]

        # Академічні дані видаляються в межах однієї транзакції.
        # Файлові артефакти обробляються лише після успішного commit.
        solution_files, waveform_files = (
            _delete_student_related_data(
                conn,
                [username],
            )
        )

        conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
              AND role = 'student'
            """,
            (user_id,),
        )

        conn.commit()

        app.logger.info(
            "Користувач '%s' видалив студента '%s' "
            "(user_id=%s) та пов'язані академічні записи.",
            current_username,
            username,
            user_id,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    for filename in solution_files:
        _remove_managed_artifact(
            UPLOAD_DIR,
            filename,
            "HDL-рішення",
        )

    for filename in waveform_files:
        _remove_managed_artifact(
            WAVEFORM_DIR,
            filename,
            "VCD",
        )

    flash(
        "Студента, його спроби та пов'язані дані видалено."
    )
    return redirect(url_for("manage_students"))


@app.route("/teacher/delete-group", methods=["POST"])
@teacher_required
def delete_group_students():
    """
    Видаляє облікові записи всіх студентів вибраної навчальної
    групи разом із пов'язаними академічними даними та артефактами.

    Сам запис навчальної групи в study_groups не видаляється.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    student_group = request.form.get(
        "student_group",
        "",
    ).strip()

    if not student_group:
        flash("Необхідно вибрати групу для видалення студентів.")
        return redirect(url_for("manage_students"))

    conn = get_db()

    solution_files = []
    waveform_files = []
    deleted_students_count = 0

    try:
        if not _can_manage_student_group(
            conn,
            current_username,
            current_role,
            student_group,
        ):
            flash(
                "У вас немає прав для керування "
                "вибраною навчальною групою."
            )
            return redirect(url_for("manage_students"))

        students = conn.execute(
            """
            SELECT
                id,
                username
            FROM users
            WHERE role = 'student'
              AND student_group = ?
            """,
            (student_group,),
        ).fetchall()

        if not students:
            flash("У вибраній групі немає студентів.")
            return redirect(url_for("manage_students"))

        usernames = [
            student["username"]
            for student in students
        ]

        deleted_students_count = len(usernames)

        solution_files, waveform_files = (
            _delete_student_related_data(
                conn,
                usernames,
            )
        )

        username_placeholders = ", ".join(
            ["?"] * len(usernames)
        )

        conn.execute(
            f"""
            DELETE FROM users
            WHERE role = 'student'
              AND username IN ({username_placeholders})
            """,
            usernames,
        )

        conn.commit()

        app.logger.info(
            "Користувач '%s' видалив %s студентів групи '%s' "
            "разом із пов'язаними академічними записами.",
            current_username,
            deleted_students_count,
            student_group,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    for filename in solution_files:
        _remove_managed_artifact(
            UPLOAD_DIR,
            filename,
            "HDL-рішення",
        )

    for filename in waveform_files:
        _remove_managed_artifact(
            WAVEFORM_DIR,
            filename,
            "VCD",
        )

    flash(
        f"Студентів групи {student_group} видалено разом "
        "зі спробами та пов'язаними файлами."
    )
    return redirect(url_for("manage_students"))


@app.route("/teacher/labs/new", methods=["GET", "POST"])
@teacher_required
def add_lab():
    """
    Створює нову лабораторну роботу з параметрами HDL-перевірки,
    оцінювання та адаптивної навчальної підтримки.

    Перед збереженням сервер перевіряє коректність основних параметрів
    і право викладача створювати лабораторну роботу для вибраної
    навчальної дисципліни.
    """
    if request.method == "GET":
        return render_template(
            "teacher/add_lab.html"
        )

    current_username = session.get("username")
    current_role = session.get("role")

    title = request.form.get(
        "title",
        "",
    ).strip()

    description = request.form.get(
        "description",
        "",
    ).strip()

    public_testbench = request.form.get(
        "public_testbench",
        "",
    ).strip()

    hidden_testbench = request.form.get(
        "hidden_testbench",
        "",
    ).strip()

    show_hidden_details = (
        1
        if request.form.get("show_hidden_details") == "on"
        else 0
    )

    # Поле testbench зберігається для сумісності з попередньою
    # структурою даних і містить відкритий testbench.
    testbench = public_testbench

    discipline = request.form.get(
        "discipline",
        "FPGA-проєктування",
    ).strip()

    programming_language = request.form.get(
        "programming_language",
        "Verilog",
    ).strip()

    checker_type = request.form.get(
        "checker_type",
        "hdl_testbench",
    ).strip()

    topic = request.form.get(
        "topic",
        "",
    ).strip()

    difficulty = request.form.get(
        "difficulty",
        "basic",
    ).strip()

    concepts = request.form.get(
        "concepts",
        "",
    ).strip()

    grading_policy = request.form.get(
        "grading_policy",
        "",
    ).strip()

    starter_code = request.form.get(
        "starter_code",
        "",
    ).strip()

    max_attempts_raw = request.form.get(
        "max_attempts",
        "3",
    ).strip()

    allow_extra_questions = (
        1
        if request.form.get("allow_extra_questions") == "on"
        else 0
    )

    if not title or not description or not public_testbench:
        flash(
            "Необхідно заповнити назву, опис і відкритий testbench."
        )
        return redirect(url_for("add_lab"))

    if not discipline:
        flash("Необхідно вибрати навчальну дисципліну.")
        return redirect(url_for("add_lab"))

    if not programming_language or not checker_type:
        flash(
            "Необхідно визначити мову програмування "
            "та тип перевірки."
        )
        return redirect(url_for("add_lab"))

    try:
        max_attempts = int(max_attempts_raw)
    except ValueError:
        flash(
            "Максимальна кількість спроб має бути цілим числом."
        )
        return redirect(url_for("add_lab"))

    if max_attempts < 1:
        flash(
            "Максимальна кількість спроб має бути не меншою за 1."
        )
        return redirect(url_for("add_lab"))

    conn = get_db()

    try:
        discipline_row = conn.execute(
            """
            SELECT name
            FROM disciplines
            WHERE name = ?
            """,
            (discipline,),
        ).fetchone()

        if discipline_row is None:
            flash("Вибрану навчальну дисципліну не знайдено.")
            return redirect(url_for("add_lab"))

        # Викладач може створювати лабораторні роботи лише в межах
        # дисциплін, до яких йому явно надано доступ адміністратором.
        if current_role != "admin":
            discipline_access = conn.execute(
                """
                SELECT 1
                FROM teacher_subject_groups
                WHERE teacher_username = ?
                  AND discipline = ?
                LIMIT 1
                """,
                (
                    current_username,
                    discipline,
                ),
            ).fetchone()

            if discipline_access is None:
                flash(
                    "У вас немає прав для створення лабораторної "
                    "роботи з цієї дисципліни."
                )
                return redirect(url_for("add_lab"))

        cursor = conn.execute(
            """
            INSERT INTO labs
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
                current_username,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        lab_id = cursor.lastrowid

        conn.commit()

        app.logger.info(
            "Користувач '%s' створив лабораторну роботу "
            "lab_id=%s, дисципліна='%s', checker_type='%s'.",
            current_username,
            lab_id,
            discipline,
            checker_type,
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("Лабораторну роботу успішно додано.")
    return redirect(url_for("teacher_panel"))


def _can_manage_lab(current_username, current_role, lab):
    """
    Перевіряє право користувача змінювати структуру лабораторної роботи.

    Адміністратор може керувати всіма лабораторними роботами.
    Викладач може редагувати та видаляти лише лабораторні роботи,
    створені ним особисто.
    """
    if current_role == "admin":
        return True

    return (
        current_role == "teacher"
        and lab["created_by"] == current_username
    )


def _normalize_multiline_text(value):
    """
    Нормалізує завершення рядків у багаторядковому тексті.

    Для HDL-коду та testbench не використовується strip(), оскільки
    такі поля доцільно зберігати максимально близько до введеного
    користувачем представлення.
    """
    return (
        (value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _delete_lab_file_artifacts(submissions, lab_id):
    """
    Видаляє HDL-рішення та VCD-артефакти після успішного видалення
    відповідних записів із бази даних.

    Файлова система не входить до транзакції SQLite, тому фізичне
    видалення виконується лише після commit. Помилка окремого файла
    журналюється та не перериває очищення інших артефактів.
    """
    for submission in submissions:
        try:
            if submission["filename"]:
                delete_uploaded_file(
                    submission["filename"]
                )
        except Exception:
            app.logger.exception(
                "Не вдалося видалити файл HDL-рішення '%s' "
                "для lab_id=%s.",
                submission["filename"],
                lab_id,
            )

        try:
            if submission["waveform_filename"]:
                delete_waveform_file(
                    submission["waveform_filename"]
                )
        except Exception:
            app.logger.exception(
                "Не вдалося видалити VCD-файл '%s' "
                "для lab_id=%s.",
                submission["waveform_filename"],
                lab_id,
            )


@app.route(
    "/teacher/edit-lab/<int:lab_id>",
    methods=["GET", "POST"],
)
@teacher_required
def edit_lab(lab_id):
    """
    Забезпечує редагування параметрів існуючої лабораторної роботи.

    Викладач може змінювати лише створені ним лабораторні роботи.
    Перед оновленням перевіряються дисципліна, основні параметри
    HDL-перевірки та допустимість кількості спроб.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    conn = get_db()

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        if lab is None:
            flash("Лабораторну роботу не знайдено.")
            return redirect(url_for("teacher_panel"))

        if not _can_manage_lab(
            current_username,
            current_role,
            lab,
        ):
            flash(
                "У вас немає прав для редагування "
                "цієї лабораторної роботи."
            )
            return redirect(url_for("teacher_panel"))

        if request.method == "POST":
            title = request.form.get(
                "title",
                "",
            ).strip()

            description = request.form.get(
                "description",
                "",
            ).strip()

            public_testbench = _normalize_multiline_text(
                request.form.get(
                    "public_testbench",
                    "",
                )
            )

            hidden_testbench = _normalize_multiline_text(
                request.form.get(
                    "hidden_testbench",
                    "",
                )
            )

            starter_code = _normalize_multiline_text(
                request.form.get(
                    "starter_code",
                    "",
                )
            )

            show_hidden_details = (
                1
                if request.form.get("show_hidden_details") == "on"
                else 0
            )

            # Поле testbench зберігається для сумісності з попередньою
            # схемою даних та дублює відкритий testbench.
            testbench = public_testbench

            discipline = request.form.get(
                "discipline",
                "FPGA-проєктування",
            ).strip()

            programming_language = request.form.get(
                "programming_language",
                "Verilog",
            ).strip()

            checker_type = request.form.get(
                "checker_type",
                "hdl_testbench",
            ).strip()

            topic = request.form.get(
                "topic",
                "",
            ).strip()

            difficulty = request.form.get(
                "difficulty",
                "basic",
            ).strip()

            concepts = request.form.get(
                "concepts",
                "",
            ).strip()

            grading_policy = request.form.get(
                "grading_policy",
                "",
            ).strip()

            max_attempts_raw = request.form.get(
                "max_attempts",
                "3",
            ).strip()

            allow_extra_questions = (
                1
                if request.form.get("allow_extra_questions") == "on"
                else 0
            )

            if (
                not title
                or not description
                or not public_testbench.strip()
            ):
                flash(
                    "Назва, опис і відкритий testbench "
                    "є обов'язковими для заповнення."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            if not discipline:
                flash(
                    "Необхідно вибрати навчальну дисципліну."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            if not programming_language or not checker_type:
                flash(
                    "Необхідно визначити мову програмування "
                    "та тип перевірки."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            try:
                max_attempts = int(max_attempts_raw)
            except ValueError:
                flash(
                    "Максимальна кількість спроб має бути "
                    "цілим числом."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            if max_attempts < 1:
                flash(
                    "Максимальна кількість спроб має бути "
                    "не меншою за 1."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            discipline_row = conn.execute(
                """
                SELECT name
                FROM disciplines
                WHERE name = ?
                """,
                (discipline,),
            ).fetchone()

            if discipline_row is None:
                flash(
                    "Вибрану навчальну дисципліну не знайдено."
                )
                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab_id,
                    )
                )

            # Викладач не може перенести лабораторну роботу
            # до дисципліни, яка йому не призначена.
            if current_role != "admin":
                discipline_access = conn.execute(
                    """
                    SELECT 1
                    FROM teacher_subject_groups
                    WHERE teacher_username = ?
                      AND discipline = ?
                    LIMIT 1
                    """,
                    (
                        current_username,
                        discipline,
                    ),
                ).fetchone()

                if discipline_access is None:
                    flash(
                        "У вас немає прав для використання "
                        "вибраної дисципліни."
                    )
                    return redirect(
                        url_for(
                            "edit_lab",
                            lab_id=lab_id,
                        )
                    )

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
                    lab_id,
                ),
            )

            conn.commit()

            app.logger.info(
                "Користувач '%s' оновив лабораторну роботу "
                "lab_id=%s, дисципліна='%s', checker_type='%s'.",
                current_username,
                lab_id,
                discipline,
                checker_type,
            )

            flash("Лабораторну роботу оновлено.")
            return redirect(url_for("teacher_panel"))

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return render_template(
        "teacher/edit_lab.html",
        lab=lab,
    )


@app.route(
    "/teacher/delete-lab/<int:lab_id>",
    methods=["POST"],
)
@teacher_required
def delete_lab(lab_id):
    """
    Видаляє лабораторну роботу разом із пов'язаними спробами,
    додатковими завданнями, ручними оцінками та файловими артефактами.

    Записи SQLite видаляються в межах однієї транзакції. HDL- і
    VCD-файли фізично видаляються лише після успішного commit,
    щоб помилка бази даних не призвела до втрати файлів при
    збереженні посилань на них у submissions.
    """
    current_username = session.get("username")
    current_role = session.get("role")

    conn = get_db()
    submissions = []

    try:
        lab = conn.execute(
            """
            SELECT *
            FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        ).fetchone()

        if lab is None:
            flash("Лабораторну роботу не знайдено.")
            return redirect(url_for("teacher_panel"))

        if not _can_manage_lab(
            current_username,
            current_role,
            lab,
        ):
            flash(
                "У вас немає прав для видалення "
                "цієї лабораторної роботи."
            )
            return redirect(url_for("teacher_panel"))

        submissions = conn.execute(
            """
            SELECT
                id,
                filename,
                waveform_filename
            FROM submissions
            WHERE lab_id = ?
            """,
            (lab_id,),
        ).fetchall()

        submission_ids = [
            submission["id"]
            for submission in submissions
        ]

        # Додаткові відповіді належать конкретним спробам,
        # тому видаляються до самих записів submissions.
        if submission_ids:
            placeholders = ", ".join(
                ["?"] * len(submission_ids)
            )

            conn.execute(
                f"""
                DELETE FROM extra_task_attempts
                WHERE submission_id IN ({placeholders})
                """,
                submission_ids,
            )

        conn.execute(
            """
            DELETE FROM grade_overrides
            WHERE lab_id = ?
            """,
            (lab_id,),
        )

        conn.execute(
            """
            DELETE FROM attempt_overrides
            WHERE lab_id = ?
            """,
            (lab_id,),
        )

        conn.execute(
            """
            DELETE FROM submissions
            WHERE lab_id = ?
            """,
            (lab_id,),
        )

        conn.execute(
            """
            DELETE FROM labs
            WHERE id = ?
            """,
            (lab_id,),
        )

        conn.commit()

        app.logger.info(
            "Користувач '%s' видалив лабораторну роботу "
            "lab_id=%s та %s пов'язаних спроб.",
            current_username,
            lab_id,
            len(submissions),
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # SQLite-транзакція вже успішно завершена. Файлова система
    # обробляється окремо, оскільки не підтримує спільний commit
    # із базою даних.
    _delete_lab_file_artifacts(
        submissions,
        lab_id,
    )

    flash(
        "Лабораторну роботу видалено разом зі спробами, "
        "файлами рішень і часовими діаграмами."
    )
    return redirect(url_for("teacher_panel"))


# =========================
# 19. Запуск застосунку
# =========================

if __name__ == "__main__":
    init_db()

    # Вбудований Flask-сервер використовується лише для локального
    # запуску. Режим debug активується явно через змінну середовища.
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )