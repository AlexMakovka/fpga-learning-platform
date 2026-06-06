import os
import sqlite3
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from functools import wraps

from flask import Flask, request, redirect, url_for, session, render_template, flash, send_from_directory, abort
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "change_this_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            student_group TEXT DEFAULT ''
        )
    """)

    user_columns = cur.execute("PRAGMA table_info(users)").fetchall()
    user_column_names = [column["name"] for column in user_columns]

    if "full_name" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")

    if "student_group" not in user_column_names:
        cur.execute("ALTER TABLE users ADD COLUMN student_group TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            testbench TEXT NOT NULL,
            max_attempts INTEGER DEFAULT 3,
            allow_extra_questions INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    lab_columns = cur.execute("PRAGMA table_info(labs)").fetchall()
    lab_column_names = [column["name"] for column in lab_columns]

    if "max_attempts" not in lab_column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN max_attempts INTEGER DEFAULT 3")

    if "allow_extra_questions" not in lab_column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN allow_extra_questions INTEGER DEFAULT 1")

    if "created_at" not in lab_column_names:
        cur.execute("ALTER TABLE labs ADD COLUMN created_at TEXT DEFAULT ''")
        cur.execute(
            "UPDATE labs SET created_at = ? WHERE created_at = '' OR created_at IS NULL",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )


    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
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
            FOREIGN KEY (lab_id) REFERENCES labs(id)
        )
    """)

    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]

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

    if "attempt_number" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN attempt_number INTEGER DEFAULT 1")

    if "file_deleted" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN file_deleted INTEGER DEFAULT 0")


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

    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]

    if "score" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN score INTEGER DEFAULT 0")

    if "passed_tests" not in column_names:
        cur.execute("ALTER TABLE submissions ADD COLUMN passed_tests INTEGER DEFAULT 0")

    if "total_tests" not in column_names:
         cur.execute("ALTER TABLE submissions ADD COLUMN total_tests INTEGER DEFAULT 0")

    

    cur.execute("SELECT COUNT(*) AS count FROM users")
    if cur.fetchone()["count"] == 0:
        cur.execute(
            """
            INSERT INTO users (username, password, role, full_name, student_group)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("student1", "student123", "student", "Иван Иванов", "Группа 101")
        )

        cur.execute(
                """
                INSERT INTO users (username, password, role, full_name, student_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("teacher", "teacher123", "teacher", "Преподаватель", "")
        )


    cur.execute("SELECT COUNT(*) AS count FROM labs")
    if False and cur.fetchone()["count"] == 0:
        default_testbench = """
module tb;
    reg a;
    reg b;
    wire sum;
    wire carry;

    half_adder dut (
        .a(a),
        .b(b),
        .sum(sum),
        .carry(carry)
    );

    initial begin
        a = 0; b = 0; #1;
        if (sum !== 0 || carry !== 0) begin
            $display("FAIL: input 00");
            $finish;
        end

        a = 0; b = 1; #1;
        if (sum !== 1 || carry !== 0) begin
            $display("FAIL: input 01");
            $finish;
        end

        a = 1; b = 0; #1;
        if (sum !== 1 || carry !== 0) begin
            $display("FAIL: input 10");
            $finish;
        end

        a = 1; b = 1; #1;
        if (sum !== 0 || carry !== 1) begin
            $display("FAIL: input 11");
            $finish;
        end

        $display("ALL_TESTS_PASSED");
        $finish;
    end
endmodule
        """

        cur.execute(
            "INSERT INTO labs (title, description, testbench) VALUES (?, ?, ?)",
            (
                "Лабораторная работа 1. Полусумматор",
                "Создайте Verilog-модуль half_adder с входами a, b и выходами sum, carry.",
                default_testbench
            )
        )

    conn.commit()
    conn.close()






def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


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


def format_hdl_report(raw_output):
    """
    Преобразует технический вывод testbench в понятный отчет.
    Также считает количество пройденных тестов и баллы.

    Testbench должен выводить строки формата:
    CASE|номер|входы|ожидалось|получено|PASS/FAIL
    """

    lines = raw_output.splitlines()
    test_cases = []

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

    if not test_cases:
        return raw_output, 0, 0, 0

    passed_count = sum(1 for test in test_cases if test["result"] == "PASS")
    total_count = len(test_cases)

    if total_count > 0:
        score = round((passed_count / total_count) * 100)
    else:
        score = 0

    report_lines = []

    report_lines.append(f"Результат: {score} / 100 баллов")
    report_lines.append(f"Пройдено тестов: {passed_count} из {total_count}")
    report_lines.append("")

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

    if passed_count == total_count:
        report_lines.append("Итоговый статус: все тесты успешно пройдены.")
    elif passed_count > 0:
        report_lines.append("Итоговый статус: часть тестов пройдена, решение требует доработки.")
    else:
        report_lines.append("Итоговый статус: тесты не пройдены.")

    return "\n".join(report_lines), score, passed_count, total_count


def run_hdl_check(user_code_path, testbench_text):
    """
    Автоматическая проверка HDL-кода:
    1. Создаётся временная папка.
    2. Туда копируется решение студента.
    3. Создаётся файл testbench.
    4. Запускается компиляция через iverilog.
    5. Запускается симуляция через vvp.
    6. Возвращается статус, отчет, баллы и количество пройденных тестов.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        solution_path = os.path.join(temp_dir, "solution.v")
        testbench_path = os.path.join(temp_dir, "testbench.v")
        output_path = os.path.join(temp_dir, "simulation.out")

        shutil.copy(user_code_path, solution_path)

        with open(testbench_path, "w", encoding="utf-8") as file:
            file.write(testbench_text)

        compile_command = [
            "iverilog",
            "-o",
            output_path,
            solution_path,
            testbench_path
        ]

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
                0
            )
        except subprocess.TimeoutExpired:
            return (
                "TIMEOUT",
                "Ошибка: компиляция выполнялась слишком долго.",
                0,
                0,
                0
            )

        if compile_result.returncode != 0:
            return (
                "COMPILE_ERROR",
                compile_result.stderr or compile_result.stdout,
                0,
                0,
                0
            )

        run_command = ["vvp", output_path]

        try:
            run_result = subprocess.run(
                run_command,
                capture_output=True,
                text=True,
                timeout=10
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

        if run_result.returncode != 0:
            return (
                "SIMULATION_ERROR",
                full_output,
                0,
                0,
                0
            )

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
                total_tests
            )

        if "ALL_TESTS_PASSED" in full_output:
            return (
                "PASSED",
                full_output,
                100,
                1,
                1
            )

        return (
            "FAILED",
            full_output or "Тесты не пройдены или testbench не вывел результат проверки.",
            0,
            0,
            0
        )
    

def detect_lab_topic_for_diagnostics(lab, code):
    """
    Определяет тему лабораторной работы по названию, описанию, testbench и коду студента.
    Это нужно, чтобы классификатор понимал, какую логику проверять.
    """

    text = (
        str(lab["title"]) + " " +
        str(lab["description"]) + " " +
        str(lab["testbench"]) + " " +
        str(code)
    ).lower()

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


def has_any(text, keywords):
    """
    Проверяет, встречается ли в тексте хотя бы одно ключевое слово.
    """

    text = text.lower()

    for keyword in keywords:
        if keyword.lower() in text:
            return True

    return False


def code_has_incomplete_condition(code):
    """
    Примитивно выявляет риск неполного описания условий в комбинационной логике.
    Например:
    - есть if, но нет else;
    - есть case, но нет default.
    """

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


def get_failed_test_blocks(output):
    """
    Извлекает из отчета проверки блоки ошибочных тестов.
    Работает с русским отчетом:
    Тест 4: ... — ошибка
    Ожидалось: ...
    Получено: ...
    """

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


def classify_hdl_error(status, output, lab, code):
    """
    Классифицирует ошибку HDL-решения.
    
    Возвращает словарь:
    {
        error_type,
        error_title,
        error_details,
        recommendation,
        error_confidence
    }
    """

    output_lower = str(output).lower()
    code_lower = str(code).lower()
    topic = detect_lab_topic_for_diagnostics(lab, code)
    failed_blocks = get_failed_test_blocks(output)
    failed_text = "\n".join(failed_blocks).lower()

    if status == "PASSED":
        return {
            "error_type": "NO_ERROR",
            "error_title": "Ошибок не обнаружено",
            "error_details": "HDL-решение успешно прошло все тесты.",
            "recommendation": "Дополнительные действия не требуются.",
            "error_confidence": 100
        }

    # 1. Несовпадение имени модуля
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

    # 2. Несовпадение портов
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

    # 3. Общая ошибка компиляции
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

    # 4. Ошибка reset/clock для последовательностных схем
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

    # 5. Ошибка управляющего сигнала для мультиплексора
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

    # 6. Неполное описание условий
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

    # 7. Неверная комбинационная логика
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

    # 8. Не пройдены граничные тесты
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

    # 9. Общая ошибка поведения
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


def read_submission_code(filename):
    """
    Читает HDL-код отправленного студентом файла.
    Используется ИИ-помощником для анализа решения.
    """

    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        return ""

    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def get_submission_for_current_user(submission_id):
    """
    Получает попытку студента вместе с названием лабораторной работы.
    Студент может видеть только свои попытки.
    Преподаватель может видеть все попытки.
    """

    conn = get_db()

    submission = conn.execute(
        """
        SELECT 
            submissions.*,
            labs.title AS lab_title,
            labs.description AS lab_description,
            labs.testbench AS lab_testbench,
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


def get_student_attempts_count(username, lab_id):
    conn = get_db()

    result = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM submissions
        WHERE username = ? AND lab_id = ?
        """,
        (username, lab_id)
    ).fetchone()

    conn.close()

    return result["count"] if result else 0


def get_next_attempt_number(username, lab_id):
    return get_student_attempts_count(username, lab_id) + 1


def delete_uploaded_file(filename):
    if not filename:
        return

    file_path = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(file_path):
        os.remove(file_path)


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

def extract_failed_tests(output):
    """
    Извлекает из текстового отчета строки с ошибочными тестами.
    """

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

def extract_failed_tests_for_adaptive_module(output):
    """
    Извлекает ошибочные тесты из отчета проверки.
    Используется адаптивным модулем для понимания конкретной ошибки.
    """

    lines = output.splitlines()
    failed_tests = []

    for index, line in enumerate(lines):
        line_lower = line.lower()

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


def get_student_error_history(username, lab_id):
    """
    Возвращает историю ошибок студента по конкретной лабораторной.
    Нужна для адаптации подсказок: если студент повторяет одну и ту же ошибку,
    система делает подсказку конкретнее.
    """

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


def detect_lab_topic_adaptive(submission, code):
    """
    Определяет тему лабораторной на основе названия, описания, testbench и кода.
    """

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


def define_hint_level(submission, error_history):
    """
    Определяет уровень подсказки.
    Чем больше попыток и повторов ошибки, тем конкретнее подсказка.
    """

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


def build_recommendations_to_repeat(topic, error_type):
    """
    Формирует список тем, которые студенту рекомендуется повторить.
    """

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


def generate_adaptive_hint(submission, topic, failed_tests, hint_level):
    """
    Формирует подсказку с учетом темы, типа ошибки, ошибочных тестов и уровня подсказки.
    """

    error_type = submission["error_type"]

    failed_text = ""

    if failed_tests:
        first_failed = failed_tests[0]
        failed_text = (
            f"\n\nОдин из ошибочных тестов:\n"
            f"{first_failed['test_line']}\n"
            f"{first_failed['expected']}\n"
            f"{first_failed['actual']}"
        )

    if error_type == "MODULE_NAME_MISMATCH":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Проблема связана не с логикой схемы, а с подключением модуля к testbench. "
                "Проверьте, совпадает ли имя вашего module с тем, которое требуется в задании."
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Testbench вызывает конкретное имя модуля. Если в задании требуется mux2to1, "
                "то в коде должно быть написано именно module mux2to1(...)."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Проверьте первую строку вашего Verilog-кода. Она должна иметь вид:\n\n"
            "module имя_из_задания(...);\n\n"
            "Не меняйте имя модуля произвольно, иначе testbench не сможет его проверить."
        )

    if error_type == "PORT_MISMATCH":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Проблема может быть связана с тем, что имена входов и выходов в вашем модуле "
                "не совпадают с теми, которые ожидает testbench."
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Сравните список портов в условии лабораторной работы и в вашем module. "
                "Даже одна лишняя буква в имени порта может привести к ошибке подключения."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Проверьте заголовок модуля. Например, если testbench ожидает d0, d1, sel и y, "
            "то именно эти имена должны быть указаны в списке input/output."
        )

    if error_type == "CONTROL_SIGNAL_ERROR" and topic == "mux":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Ошибка связана с выбором входа. В мультиплексоре управляющий сигнал sel определяет, "
                "какой вход должен попасть на выход y."
                f"{failed_text}"
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, какой вход выбирается при sel = 0 и какой при sel = 1. "
                "Если часть тестов не проходит, возможно, d0 и d1 перепутаны местами."
                f"{failed_text}"
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для мультиплексора 2 к 1 логика выбора должна учитывать оба случая: "
            "sel = 0 и sel = 1. Проверьте условное выражение справа от assign и сопоставьте его "
            "с таблицей истинности."
            f"{failed_text}"
        )

    if error_type == "RESET_CLOCK_ERROR":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Ошибка связана с последовательностной логикой. Для таких схем важно правильно описать "
                "clock, reset и момент изменения значения."
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, что состояние схемы меняется по нужному фронту clock, а reset задает корректное "
                "начальное значение."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Обратите внимание на always-блок. Для последовательностных схем обычно проверяют чувствительность "
            "к clock/reset и порядок условий внутри блока."
        )

    if error_type == "INCOMPLETE_CONDITION":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "В коде может быть не описан один из вариантов входных сигналов."
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Проверьте, есть ли ветка else для if-условий или default для case-конструкций."
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Для комбинационной логики важно, чтобы выход получал значение при всех возможных вариантах входов. "
            "Иначе могут появиться неопределенные значения или защелки."
        )

    if error_type == "WRONG_COMBINATIONAL_LOGIC":
        if hint_level == 1:
            return (
                "ИИ-подсказка 1 уровня:\n\n"
                "Код компилируется, но логика схемы не совпадает с ожидаемой."
                f"{failed_text}"
            )

        if hint_level == 2:
            return (
                "ИИ-подсказка 2 уровня:\n\n"
                "Сравните таблицу истинности задания с выражениями assign или always в вашем коде."
                f"{failed_text}"
            )

        return (
            "ИИ-подсказка 3 уровня:\n\n"
            "Сосредоточьтесь на тех входных комбинациях, где testbench показывает различие между "
            "ожидаемым и полученным значением."
            f"{failed_text}"
        )

    return (
        f"ИИ-подсказка {hint_level} уровня:\n\n"
        "Система обнаружила ошибку в решении. Начните с анализа строк отчета testbench: "
        "сравните ожидаемые и полученные значения."
        f"{failed_text}"
    )


def generate_adaptive_questions(submission, topic, failed_tests, hint_level):
    """
    Формирует индивидуальные дополнительные вопросы.
    Вопросы зависят от темы лабораторной, типа ошибки и уровня подсказки.
    """

    error_type = submission["error_type"]

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


def generate_ai_hint(submission, code, level):
    """
    Генерирует подсказку по HDL-ошибке.
    Важно: функция не дает готовое решение, а объясняет направление исправления.
    level:
    1 — общая подсказка;
    2 — более конкретная;
    3 — пример похожей конструкции без полного ответа.
    """

    status = submission["status"]
    output = submission["output"]
    lab_title = submission["lab_title"].lower()
    code_lower = code.lower()
    failed_tests = extract_failed_tests(output)

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


def get_student_attempts_count(username, lab_id):
    """
    Возвращает количество попыток студента по конкретной лабораторной.
    Используется для индивидуализации дополнительных заданий.
    """

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


def detect_lab_topic(submission, code):
    """
    Определяет тему лабораторной работы по названию, описанию и коду студента.
    """

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


def detect_error_focus(submission, code, topic):
    """
    Определяет, на чем лучше сфокусировать дополнительные вопросы.
    """

    output = str(submission["output"]).lower()
    code_lower = code.lower()

    if submission["status"] == "COMPILE_ERROR":
        if "unknown module" in output or "unable to bind" in output:
            return "module_or_ports"

        if "syntax" in output or "malformed" in output:
            return "syntax"

        return "compile"

    if topic == "mux":
        if "sel=0" in output and "ошибка" in output:
            return "mux_sel_0"

        if "sel=1" in output and "ошибка" in output:
            return "mux_sel_1"

        if "d0" in output and "d1" in output:
            return "mux_logic"

        return "mux_general"

    if topic == "adder":
        if "carry" in output:
            return "adder_carry"

        if "sum" in output:
            return "adder_sum"

        return "adder_general"

    if topic == "counter":
        if "reset" in output or "rst" in output:
            return "counter_reset"

        if "clk" in code_lower or "clock" in code_lower:
            return "counter_clock"

        return "counter_general"

    if topic == "register":
        if "reset" in output or "rst" in output:
            return "register_reset"

        return "register_general"

    if topic == "fsm":
        if "state" in output or "состоя" in output:
            return "fsm_state"

        return "fsm_general"

    return "general_logic"


def build_task(field, title, text, required_groups, min_length=25):
    """
    Формирует одно дополнительное задание.
    required_groups — группы ключевых слов.
    Для принятия ответа нужно, чтобы в ответе встретилось хотя бы одно слово из каждой группы.
    """

    return {
        "field": field,
        "title": title,
        "text": text,
        "required_groups": required_groups,
        "min_length": min_length
    }


def generate_extra_tasks(submission, code):
    """
    Адаптивно формирует дополнительные задания на основе:
    - темы лабораторной;
    - описания задания;
    - результата проверки;
    - HDL-кода студента;
    - количества попыток студента.
    """

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

def normalize_text(text):
    """
    Нормализует текст ответа студента:
    переводит в нижний регистр, убирает лишние пробелы.
    """

    if text is None:
        return ""

    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compact_text(text):
    """
    Убирает пробелы из текста.
    Нужно, чтобы система одинаково понимала sel = 0 и sel=0.
    """

    text = normalize_text(text)
    return text.replace(" ", "")


def is_bad_answer(text):
    """
    Отсекает слишком короткие или явно бессмысленные ответы.
    """

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

def answer_matches_task(answer, task):
    """
    Проверяет один ответ по требованиям конкретного задания.
    """

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


def evaluate_extra_task_answers(submission, answers):
    """
    Проверяет ответы студента на динамически сформированные дополнительные задания.
    """

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


def build_adaptive_learning_plan(submission, code):
    """
    Главный алгоритм адаптивного обучающего модуля.

    Вход:
    - тема лабораторной;
    - описание задания;
    - HDL-код студента;
    - результат testbench;
    - список ошибочных тестов;
    - номер попытки;
    - история ошибок студента.

    Выход:
    - тип ошибки;
    - уровень подсказки;
    - текст подсказки;
    - дополнительные вопросы;
    - рекомендации к повторению;
    - ограниченный бонус.
    """

    topic = detect_lab_topic_adaptive(submission, code)
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
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("index"))

        flash("Неверный логин или пароль.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    conn = get_db()

    labs = conn.execute(
        "SELECT * FROM labs ORDER BY id DESC"
    ).fetchall()

    my_submissions = conn.execute(
        """
        SELECT submissions.*, labs.title AS lab_title
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        WHERE submissions.username = ?
        ORDER BY submissions.id DESC
        LIMIT 5
        """,
        (session["username"],)
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        labs=labs,
        my_submissions=my_submissions
    )

@app.route("/lab/<int:lab_id>")
@login_required
def lab_detail(lab_id):
    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if not lab:
        conn.close()
        return "Лабораторная работа не найдена", 404

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
        "lab_detail.html",
        lab=lab,
        submissions=submissions,
        student_results=student_results,
        attempts_count=attempts_count
    )

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
        "student_history.html",
        lab=lab,
        submissions=submissions
    )

@app.route("/submit/<int:lab_id>", methods=["POST"])
@login_required
def submit_solution(lab_id):
    if session.get("role") != "student":
        flash("Отправлять HDL-решения может только студент.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    file = request.files.get("solution")

    if not file:
        flash("Файл не выбран.")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    filename = secure_filename(file.filename)

    if not filename.endswith(".v"):
        flash("Можно загружать только Verilog-файлы с расширением .v")
        return redirect(url_for("lab_detail", lab_id=lab_id))

    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if not lab:
        conn.close()
        return "Лабораторная работа не найдена", 404

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

    if previous_submission and previous_submission["file_deleted"] == 0:
        delete_uploaded_file(previous_submission["filename"])
        conn.execute(
            """
            UPDATE submissions
            SET file_deleted = 1
            WHERE id = ?
            """,
            (previous_submission["id"],)
        )

    attempt_number = attempts_count + 1

    saved_filename = f"{session['username']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)
    file.save(saved_path)

    status, output, score, passed_tests, total_tests = run_hdl_check(saved_path, lab["testbench"])

    with open(saved_path, "r", encoding="utf-8", errors="replace") as code_file:
        student_code = code_file.read()

    diagnostics = classify_hdl_error(
        status=status,
        output=output,
        lab=lab,
        code=student_code
    )

    conn.execute(
    """
    INSERT INTO submissions
    (lab_id, username, filename, status, score, passed_tests, total_tests,
     error_type, error_title, error_details, recommendation, error_confidence,
     output, created_at, attempt_number, file_deleted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        lab_id,
        session["username"],
        saved_filename,
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
        0
    )
)

    conn.commit()
    conn.close()

    return redirect(url_for("lab_detail", lab_id=lab_id))



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

    mark_submission_file_deleted(submission_id)

    flash("Предыдущий HDL-файл удалён. Теперь можно отправить новую попытку.")
    return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))



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
        flash("Файл этой попытки был удалён после повторной отправки.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if session.get("role") != "teacher" and submission["username"] != session["username"]:
        abort(403)

    return send_from_directory(
        UPLOAD_DIR,
        submission["filename"],
        as_attachment=True
    )

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
        "ai_help.html",
        submission=submission,
        hint=adaptive_plan["hint_text"],
        level=adaptive_plan["hint_level"],
        code=code,
        adaptive_plan=adaptive_plan
    )


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
        "improve_score.html",
        submission=submission,
        tasks=tasks,
        check_result=check_result,
        student_answers=student_answers,
        adaptive_plan=adaptive_plan
    )

@app.route("/teacher")
@teacher_required
def teacher_panel():
    conn = get_db()

    labs = conn.execute(
        "SELECT * FROM labs ORDER BY id DESC"
    ).fetchall()


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

    student_lab_summary = conn.execute("""
        SELECT
            submissions.username,
            COALESCE(users.full_name, submissions.username) AS full_name,
            COALESCE(users.student_group, '') AS student_group,
            labs.title AS lab_title,
            COUNT(submissions.id) AS attempts_count,
            MAX(submissions.score) AS best_score,
            (
                SELECT s2.status
                FROM submissions s2
                WHERE s2.username = submissions.username
                  AND s2.lab_id = submissions.lab_id
                ORDER BY s2.id DESC
                LIMIT 1
            ) AS last_status,
            (
                SELECT s2.created_at
                FROM submissions s2
                WHERE s2.username = submissions.username
                  AND s2.lab_id = submissions.lab_id
                ORDER BY s2.id DESC
                LIMIT 1
            ) AS last_attempt_at,
            (
                SELECT s2.filename
                FROM submissions s2
                WHERE s2.username = submissions.username
                  AND s2.lab_id = submissions.lab_id
                ORDER BY s2.id DESC
                LIMIT 1
            ) AS last_filename
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        LEFT JOIN users ON submissions.username = users.username
        GROUP BY submissions.username, submissions.lab_id
        ORDER BY last_attempt_at DESC
    """).fetchall()

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
        "teacher.html",
        labs=labs,
        stats=stats,
        student_lab_summary=student_lab_summary,
        error_summary=error_summary
    )


@app.route("/teacher/submissions-history")
@teacher_required
def teacher_submissions_history():
    conn = get_db()

    search_query = request.args.get("q", "").strip()
    selected_lab_id = request.args.get("lab_id", "").strip()
    selected_group = request.args.get("group", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_error_type = request.args.get("error_type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    

    sort = request.args.get("sort", "submitted_at")
    direction = request.args.get("direction", "desc")

    allowed_sort_columns = {
        "student": "users.full_name",
        "group": "users.student_group",
        "lab": "labs.title",
        "lab_created": "labs.created_at",
        "submitted_at": "submissions.created_at",
        "score": "submissions.score",
        "best_score": "best_score",
        "status": "submissions.status",
        "attempt": "submissions.attempt_number"
    }

    if sort not in allowed_sort_columns:
        sort = "submitted_at"

    if direction not in ["asc", "desc"]:
        direction = "desc"

    sql = """
        SELECT
            submissions.*,
            labs.title AS lab_title,
            labs.created_at AS lab_created_at,
            users.full_name,
            users.student_group,
            (
                SELECT MAX(s2.score)
                FROM submissions s2
                WHERE s2.username = submissions.username
                  AND s2.lab_id = submissions.lab_id
            ) AS best_score
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        LEFT JOIN users ON submissions.username = users.username
        WHERE 1 = 1
    """

    params = []

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

    sql += f"""
        ORDER BY {allowed_sort_columns[sort]} {direction.upper()}
    """

    submissions = conn.execute(sql, params).fetchall()

    labs = conn.execute(
        """
        SELECT id, title
        FROM labs
        ORDER BY title
        """
    ).fetchall()

    groups = conn.execute(
        """
        SELECT DISTINCT student_group
        FROM users
        WHERE role = 'student' AND student_group != ''
        ORDER BY student_group
        """
    ).fetchall()

    conn.close()

    return render_template(
        "teacher_submissions_history.html",
        submissions=submissions,
        labs=labs,
        groups=groups,
        search_query=search_query,
        selected_lab_id=selected_lab_id,
        selected_group=selected_group,
        selected_status=selected_status,
        selected_error_type=selected_error_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        direction=direction
    )




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
        "students.html",
        students=students,
        groups=groups,
        search_query=search_query,
        selected_group=selected_group
    )

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

    return render_template("edit_student.html", student=student)


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

@app.route("/teacher/add-lab", methods=["POST"])
@teacher_required
def add_lab():
    title = request.form.get("title")
    description = request.form.get("description")
    testbench = request.form.get("testbench")
    max_attempts = request.form.get("max_attempts", "3")
    allow_extra_questions = 1 if request.form.get("allow_extra_questions") == "on" else 0

    if not title or not description or not testbench:
        flash("Нужно заполнить название, описание и testbench.")
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
        INSERT INTO labs
        (title, description, testbench, max_attempts, allow_extra_questions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            testbench,
            max_attempts,
            allow_extra_questions,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    conn.commit()
    conn.close()

    return redirect(url_for("teacher_panel"))



@app.route("/teacher/edit-lab/<int:lab_id>", methods=["GET", "POST"])
@teacher_required
def edit_lab(lab_id):
    conn = get_db()

    lab = conn.execute(
        "SELECT * FROM labs WHERE id = ?",
        (lab_id,)
    ).fetchone()

    if not lab:
        conn.close()
        return "Лабораторная работа не найдена", 404

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        testbench = request.form.get("testbench")
        max_attempts = request.form.get("max_attempts", "3")
        allow_extra_questions = 1 if request.form.get("allow_extra_questions") == "on" else 0

        if not title or not description or not testbench:
            conn.close()
            flash("Нужно заполнить все поля.")
            return redirect(url_for("edit_lab", lab_id=lab_id))

        try:
            max_attempts = int(max_attempts)
        except ValueError:
            max_attempts = 3

        if max_attempts < 1:
            max_attempts = 1

        conn.execute(
            """
            UPDATE labs
            SET title = ?, description = ?, testbench = ?,
                max_attempts = ?, allow_extra_questions = ?
            WHERE id = ?
            """,
            (title, description, testbench, max_attempts, allow_extra_questions, lab_id)
        )

        conn.commit()
        conn.close()

        flash("Лабораторная работа обновлена.")
        return redirect(url_for("teacher_panel"))

    conn.close()

    return render_template("edit_lab.html", lab=lab)





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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
