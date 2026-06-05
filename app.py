import os
import sqlite3
import subprocess
import tempfile
import shutil
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
            testbench TEXT NOT NULL
        )
    """)

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
        submissions = conn.execute(
            """
            SELECT 
                submissions.*,
                users.full_name,
                users.student_group
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
            SELECT * FROM submissions
            WHERE lab_id = ? AND username = ?
            ORDER BY id DESC
            """,
            (lab_id, session["username"])
        ).fetchall()

        student_results = []

    conn.close()

    return render_template(
        "lab_detail.html",
        lab=lab,
        submissions=submissions,
        student_results=student_results
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

    saved_filename = f"{session['username']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)
    file.save(saved_path)

    status, output, score, passed_tests, total_tests = run_hdl_check(saved_path, lab["testbench"])

    conn.execute(
        """
        INSERT INTO submissions
        (lab_id, username, filename, status, score, passed_tests, total_tests, output, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("lab_detail", lab_id=lab_id))

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

    if session.get("role") != "teacher" and submission["username"] != session["username"]:
        abort(403)

    return send_from_directory(
        UPLOAD_DIR,
        submission["filename"],
        as_attachment=True
    )


@app.route("/teacher")
@teacher_required
def teacher_panel():
    conn = get_db()

    labs = conn.execute(
        "SELECT * FROM labs ORDER BY id DESC"
    ).fetchall()

    submissions = conn.execute("""
        SELECT 
            submissions.*,
            labs.title AS lab_title,
            users.full_name,
            users.student_group
        FROM submissions
        JOIN labs ON submissions.lab_id = labs.id
        LEFT JOIN users ON submissions.username = users.username
        ORDER BY submissions.id DESC
        LIMIT 20
    """).fetchall()

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
        submissions=submissions,
        stats=stats,
        student_lab_summary=student_lab_summary
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

    if not title or not description or not testbench:
        flash("Нужно заполнить все поля.")
        return redirect(url_for("teacher_panel"))

    conn = get_db()
    conn.execute(
        "INSERT INTO labs (title, description, testbench) VALUES (?, ?, ?)",
        (title, description, testbench)
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

        if not title or not description or not testbench:
            conn.close()
            flash("Нужно заполнить все поля.")
            return redirect(url_for("edit_lab", lab_id=lab_id))

        conn.execute(
            """
            UPDATE labs
            SET title = ?, description = ?, testbench = ?
            WHERE id = ?
            """,
            (title, description, testbench, lab_id)
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
