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
        output TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (lab_id) REFERENCES labs(id)
        )
    """)

    columns = cur.execute("PRAGMA table_info(submissions)").fetchall()
    column_names = [column["name"] for column in columns]

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
            labs.description AS lab_description
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

    conn.execute(
        """
        INSERT INTO submissions
        (lab_id, username, filename, status, score, passed_tests, total_tests,
         output, created_at, attempt_number, file_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lab_id,
            session["username"],
            saved_filename,
            status,
            score,
            passed_tests,
            total_tests,
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

    if submission["file_deleted"]:
        flash("Файл этой попытки был удалён после повторной отправки.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    if submission["status"] == "PASSED":
        flash("Решение уже прошло все тесты. Подсказка ИИ не требуется.")
        return redirect(url_for("lab_detail", lab_id=submission["lab_id"]))

    level = request.args.get("level", 1, type=int)

    if level < 1:
        level = 1

    if level > 3:
        level = 3

    code = read_submission_code(submission["filename"])
    hint = generate_ai_hint(submission, code, level)

    return render_template(
        "ai_help.html",
        submission=submission,
        hint=hint,
        level=level,
        code=code
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
    tasks = generate_extra_tasks(submission, code)

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

        if correct_count == 3:
            score_after = min(80, score_before + bonus)
        elif correct_count == 2:
            score_after = min(70, score_before + bonus)
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
        student_answers=student_answers
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

    conn.close()

    return render_template(
        "teacher.html",
        labs=labs,
        stats=stats,
        student_lab_summary=student_lab_summary
    )


@app.route("/teacher/submissions-history")
@teacher_required
def teacher_submissions_history():
    conn = get_db()

    search_query = request.args.get("q", "").strip()
    selected_lab_id = request.args.get("lab_id", "").strip()
    selected_group = request.args.get("group", "").strip()
    selected_status = request.args.get("status", "").strip()
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
