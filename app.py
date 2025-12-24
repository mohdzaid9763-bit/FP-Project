from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import click
import os
from pathlib import Path
import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"  # needed for flash messages

# MySQL configuration - CHANGE these values to match your MySQL setup
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Parth",  # your MySQL password
    "database": "school_erp",
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


@app.before_request
def require_login():
    # Allow unauthenticated access to public pages (landing/home/teams/contact), login, signup, static files and db-check
    allowed_endpoints = ("index", "home", "teams", "contact", "login", "signup", "static", "about", "db_check")
    if request.endpoint in allowed_endpoints or request.endpoint is None:
        return
    if "user_id" not in session:
        return redirect(url_for("login"))


def requires_role(*roles):
    """Decorator to restrict access to endpoints by user role(s).

    Usage: @requires_role('teacher', 'admin')
    If the role is not in the allowed list, the user is redirected to the index
    with a flash message.
    """
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get('role')
            if role not in roles:
                flash('Permission denied', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)

        return wrapped

    return decorator


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST": 
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "teacher")
        if role not in ("teacher", "student"):
            role = "teacher"

        # Hash the password before storing it
        hashed = generate_password_hash(password)

        try:
            conn = get_db_connection()
        except mysql.connector.Error:
            flash("Database connection error. Please check your database configuration.", "danger")
            return render_template("signup.html")

        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, hashed, role),
            )
            conn.commit()
            flash("Signup successful. Please login.", "success")
            return redirect(url_for("login"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Signup DB error", exc_info=e)
            flash("Username already exists or database error. Check server logs.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST": 
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "student")
        if role not in ("student", "teacher"):
            role = "student"

        try:
            conn = get_db_connection()
        except mysql.connector.Error as e:
            app.logger.error("Login DB connection failed", exc_info=e)
            flash("Database connection error. Please check your database configuration.", "danger")
            return render_template("login.html")

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s AND role = %s",
                (username, role),
            )
            user = cursor.fetchone()
        except mysql.connector.Error as e:
            app.logger.error("Login DB query error", exc_info=e)
            flash("Database query error. Please try again later. (see server logs)", "danger")
            user = None
        finally:
            cursor.close()
            conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user.get("role")
            flash("Logged in successfully", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username, role, or password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.context_processor
def inject_recent_notices():
    """Provide a few recent notices to all templates for the header dropdown."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, title, created_at FROM notices ORDER BY created_at DESC, id DESC LIMIT 5"
        )
        recent_notices = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception:
        recent_notices = []

    return dict(recent_notices=recent_notices, current_year=datetime.datetime.now().year)


@app.cli.command("create-default-users")
def create_default_users():
    """Create default teacher (admin) and student users."""
    try:
        conn = get_db_connection()
    except mysql.connector.Error as e:
        click.echo(f"Database connection failed: {e}")
        return

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO users (username, password, role) VALUES (%s, %s, %s)",
            ("admin", generate_password_hash("admin123"), "teacher"),
        )
        cursor.execute(
            "INSERT IGNORE INTO users (username, password, role) VALUES (%s, %s, %s)",
            ("student1", generate_password_hash("student123"), "student"),
        )
        conn.commit()
        click.echo("Default users created: admin/admin123, student1/student123")
    except mysql.connector.Error as e:
        click.echo(f"DB error: {e}")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@app.route('/db-check')
def db_check():
    """Quick endpoint to check DB connectivity."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        return 'OK', 200
    except Exception as e:
        app.logger.error('DB check failed', exc_info=e)
        return f'DB error: {e}', 500


@app.route('/health')
def health():
    """Return JSON health information for server and database."""
    data = {'server': 'ok'}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        data['db'] = 'ok'
    except Exception as e:
        app.logger.error('Health DB check failed', exc_info=e)
        data['db'] = f'error: {str(e)}'
    return jsonify(data)


def ensure_users_role_column():
    """Ensure the `users.role` column exists; add it if missing."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
        if cursor.fetchone() is None:
            app.logger.info("'role' column not found on users table — adding it now")
            # Use IF NOT EXISTS to be safe on compatible MySQL versions
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'teacher'")
            except mysql.connector.Error:
                # Older MySQL versions may not support IF NOT EXISTS — try without it
                cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'teacher'")
            conn.commit()
            app.logger.info("Added 'role' column to users table")
        cursor.close()
        conn.close()
    except Exception as e:
        app.logger.error("Schema migration error", exc_info=e)


def test_db_connection():
    """Return (ok: bool, message: str) after trying to connect using DB_CONFIG."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        return True, 'OK'
    except Exception as e:
        return False, str(e)


def init_db_from_schema(schema_path: str = None):
    """Initialize the database by executing the SQL in schema.sql.

    This connects to the MySQL server (without selecting a database) and executes
    each statement in the schema file. Returns (ok: bool, message: str).
    """
    schema_file = schema_path or os.path.join(Path(__file__).parent, 'schema.sql')
    if not os.path.exists(schema_file):
        return False, f"Schema file not found: {schema_file}"

    # Connect to server without specifying database so CREATE DATABASE works
    config_without_db = dict(DB_CONFIG)
    config_without_db.pop('database', None)

    try:
        conn = mysql.connector.connect(**config_without_db)
        cursor = conn.cursor()

        with open(schema_file, 'r', encoding='utf-8') as f:
            sql = f.read()

        # Split statements by ';' and execute non-empty lines (simple splitter)
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for stmt in statements:
            try:
                cursor.execute(stmt)
            except mysql.connector.Error as e:
                app.logger.warning('Failed to execute statement (continuing): %s -- %s', stmt[:80], e)
        conn.commit()
        cursor.close()
        conn.close()
        return True, 'Schema executed (some harmless warnings may have occurred)'
    except Exception as e:
        return False, str(e)


@app.cli.command('init-db')
def init_db_command():
    """Initialize the database by applying schema.sql."""
    ok, msg = init_db_from_schema()
    if ok:
        click.echo('Schema applied successfully.')
    else:
        click.echo(f'Failed to apply schema: {msg}')



# Run migrations at startup (best-effort)
try:
    ensure_users_role_column()
except Exception as e:
    app.logger.error("Failed running migrations at startup", exc_info=e)


@app.route("/")
def index():
    # Public landing page for unauthenticated visitors
    if "user_id" not in session:
        return render_template("landing.html")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teachers")
    total_teachers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM classes")
    total_classes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notices")
    total_notices = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        total_students=total_students,
        total_teachers=total_teachers,
        total_classes=total_classes,
        total_attendance=total_attendance,
        total_notices=total_notices,
    )


@app.route('/home')
def home_page():
    """Public home page route (linked from landing cards)."""
    return render_template('home.html')


@app.route('/teams')
def teams():
    return render_template('teams.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


# ---------------- Students CRUD ----------------
@app.route("/students")
def students_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students ORDER BY id DESC")
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("students_list.html", students=students)


@app.route("/students/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_student():
    if request.method == "POST":
        name = request.form.get("name")
        student_class = request.form.get("student_class")
        age = request.form.get("age")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (name, student_class, age) VALUES (%s, %s, %s)",
                (name, student_class, age),
            )
            conn.commit()
            flash("Student added successfully", "success")
            return redirect(url_for("students_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add student DB error", exc_info=e)
            flash("Failed to add student. See server logs.", "danger")
            # fall through to re-render form with previous values
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        # keep the entered values in the form so the user can correct them
        return render_template("student_form.html", action="Add", student={"name": name, "student_class": student_class, "age": age})

    return render_template("student_form.html", action="Add", student=None)


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        conn.close()
        flash("Student not found", "danger")
        return redirect(url_for("students_list"))

    if request.method == "POST":
        name = request.form.get("name")
        student_class = request.form.get("student_class")
        age = request.form.get("age")

        try:
            cursor.execute(
                "UPDATE students SET name=%s, student_class=%s, age=%s WHERE id=%s",
                (name, student_class, age, student_id),
            )
            conn.commit()
            flash("Student updated successfully", "success")
            return redirect(url_for("students_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update student DB error", exc_info=e)
            flash("Failed to update student. See server logs.", "danger")
            # fall through to re-render form with previous values
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("student_form.html", action="Edit", student={"id": student_id, "name": name, "student_class": student_class, "age": age})

    cursor.close()
    conn.close()
    return render_template("student_form.html", action="Edit", student=student)


@app.route("/students/delete/<int:student_id>")
@requires_role('teacher', 'admin')
def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        conn.commit()
        flash("Student deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete student DB error", exc_info=e)
        flash("Failed to delete student. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("students_list"))


# ---------------- Teachers CRUD ----------------
@app.route("/teachers")
def teachers_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM teachers ORDER BY id DESC")
    teachers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("teachers_list.html", teachers=teachers)


@app.route("/teachers/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_teacher():
    if request.method == "POST":
        name = request.form.get("name")
        subject = request.form.get("subject")
        phone = request.form.get("phone")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO teachers (name, subject, phone) VALUES (%s, %s, %s)",
                (name, subject, phone),
            )
            conn.commit()
            flash("Teacher added successfully", "success")
            return redirect(url_for("teachers_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add teacher DB error", exc_info=e)
            flash("Failed to add teacher. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("teacher_form.html", action="Add", teacher={"name": name, "subject": subject, "phone": phone})

    return render_template("teacher_form.html", action="Add", teacher=None)


@app.route("/teachers/edit/<int:teacher_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_teacher(teacher_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
    teacher = cursor.fetchone()

    if not teacher:
        cursor.close()
        conn.close()
        flash("Teacher not found", "danger")
        return redirect(url_for("teachers_list"))

    if request.method == "POST":
        name = request.form.get("name")
        subject = request.form.get("subject")
        phone = request.form.get("phone")

        try:
            cursor.execute(
                "UPDATE teachers SET name=%s, subject=%s, phone=%s WHERE id=%s",
                (name, subject, phone, teacher_id),
            )
            conn.commit()
            flash("Teacher updated successfully", "success")
            return redirect(url_for("teachers_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update teacher DB error", exc_info=e)
            flash("Failed to update teacher. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("teacher_form.html", action="Edit", teacher={"id": teacher_id, "name": name, "subject": subject, "phone": phone})

    cursor.close()
    conn.close()
    return render_template("teacher_form.html", action="Edit", teacher=teacher)


@app.route("/teachers/delete/<int:teacher_id>")
@requires_role('teacher', 'admin')
def delete_teacher(teacher_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM teachers WHERE id = %s", (teacher_id,))
        conn.commit()
        flash("Teacher deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete teacher DB error", exc_info=e)
        flash("Failed to delete teacher. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("teachers_list"))


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------- Attendance CRUD ----------------
@app.route("/attendance")
def attendance_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT a.id,
               a.date,
               a.status,
               s.name AS student_name,
               c.name AS class_name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN classes c ON a.class_id = c.id
        ORDER BY a.date DESC, a.id DESC
        """
    )
    attendance_records = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("attendance_list.html", attendance_records=attendance_records)


@app.route('/attendance/chart-data')
def attendance_chart_data():
    """Return monthly attendance percentages as JSON for charting."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE_FORMAT(date, '%Y-%m') as period,
                   SUM(LOWER(status)='present') as present_count,
                   COUNT(*) as total_count
            FROM attendance
            GROUP BY period
            ORDER BY period
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        labels = [r[0] for r in rows]
        percents = [round((r[1] / r[2]) * 100, 2) if r[2] and r[2] > 0 else 0 for r in rows]
        return jsonify({"labels": labels, "percent": percents}), 200
    except Exception as e:
        app.logger.error('Attendance chart data error', exc_info=e)
        return jsonify({"error": str(e)}), 500


def _load_students_and_classes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM students ORDER BY name")
    students = cursor.fetchall()
    cursor.execute("SELECT id, name FROM classes ORDER BY name")
    classes = cursor.fetchall()
    cursor.close()
    conn.close()
    return students, classes


@app.route("/attendance/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_attendance():
    students, classes = _load_students_and_classes()

    if request.method == "POST":
        student_id = request.form.get("student_id")
        class_id = request.form.get("class_id")
        date = request.form.get("date")
        status = request.form.get("status")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO attendance (student_id, class_id, date, status) VALUES (%s, %s, %s, %s)",
                (student_id, class_id, date, status),
            )
            conn.commit()
            flash("Attendance record added", "success")
            return redirect(url_for("attendance_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add attendance DB error", exc_info=e)
            flash("Failed to add attendance record. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template(
            "attendance_form.html",
            action="Add",
            record=None,
            students=students,
            classes=classes,
        )

    return render_template(
        "attendance_form.html",
        action="Add",
        record=None,
        students=students,
        classes=classes,
    )


@app.route("/attendance/edit/<int:attendance_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_attendance(attendance_id):
    students, classes = _load_students_and_classes()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance WHERE id = %s", (attendance_id,))
    record = cursor.fetchone()

    if not record:
        cursor.close()
        conn.close()
        flash("Attendance record not found", "danger")
        return redirect(url_for("attendance_list"))

    if request.method == "POST":
        student_id = request.form.get("student_id")
        class_id = request.form.get("class_id")
        date = request.form.get("date")
        status = request.form.get("status")

        try:
            cursor.execute(
                "UPDATE attendance SET student_id=%s, class_id=%s, date=%s, status=%s WHERE id=%s",
                (student_id, class_id, date, status, attendance_id),
            )
            conn.commit()
            flash("Attendance record updated", "success")
            return redirect(url_for("attendance_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update attendance DB error", exc_info=e)
            flash("Failed to update attendance record. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template(
            "attendance_form.html",
            action="Edit",
            record={"id": attendance_id, "student_id": student_id, "class_id": class_id, "date": date, "status": status},
            students=students,
            classes=classes,
        )

    cursor.close()
    conn.close()
    return render_template(
        "attendance_form.html",
        action="Edit",
        record=record,
        students=students,
        classes=classes,
    )


@app.route("/attendance/delete/<int:attendance_id>")
@requires_role('teacher', 'admin')
def delete_attendance(attendance_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM attendance WHERE id = %s", (attendance_id,))
        conn.commit()
        flash("Attendance record deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete attendance DB error", exc_info=e)
        flash("Failed to delete attendance record. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("attendance_list"))


# ---------------- Notices CRUD ----------------
@app.route("/notices")
def notices_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT n.id,
               n.title,
               n.message,
               n.created_at,
               c.name AS class_name
        FROM notices n
        LEFT JOIN classes c ON n.class_id = c.id
        ORDER BY n.created_at DESC, n.id DESC
        """
    )
    notices = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("notices_list.html", notices=notices)


def _load_classes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM classes ORDER BY name")
    classes = cursor.fetchall()
    cursor.close()
    conn.close()
    return classes


@app.route("/notices/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_notice():
    classes = _load_classes()

    if request.method == "POST":
        class_id = request.form.get("class_id") or None
        title = request.form.get("title")
        created_at = request.form.get("created_at")
        message = request.form.get("message")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO notices (class_id, title, message, created_at) VALUES (%s, %s, %s, %s)",
                (class_id, title, message, created_at),
            )
            conn.commit()
            flash("Notice added", "success")
            return redirect(url_for("notices_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add notice DB error", exc_info=e)
            flash("Failed to add notice. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("notice_form.html", action="Add", notice={"class_id": class_id, "title": title, "created_at": created_at, "message": message}, classes=classes)

    return render_template("notice_form.html", action="Add", notice=None, classes=classes)


@app.route("/notices/edit/<int:notice_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_notice(notice_id):
    classes = _load_classes()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notices WHERE id = %s", (notice_id,))
    notice = cursor.fetchone()

    if not notice:
        cursor.close()
        conn.close()
        flash("Notice not found", "danger")
        return redirect(url_for("notices_list"))

    if request.method == "POST":
        class_id = request.form.get("class_id") or None
        title = request.form.get("title")
        created_at = request.form.get("created_at")
        message = request.form.get("message")

        try:
            cursor.execute(
                "UPDATE notices SET class_id=%s, title=%s, message=%s, created_at=%s WHERE id=%s",
                (class_id, title, message, created_at, notice_id),
            )
            conn.commit()
            flash("Notice updated", "success")
            return redirect(url_for("notices_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update notice DB error", exc_info=e)
            flash("Failed to update notice. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("notice_form.html", action="Edit", notice={"id": notice_id, "class_id": class_id, "title": title, "created_at": created_at, "message": message}, classes=classes)

    cursor.close()
    conn.close()
    return render_template("notice_form.html", action="Edit", notice=notice, classes=classes)


@app.route("/notices/delete/<int:notice_id>")
@requires_role('teacher', 'admin')
def delete_notice(notice_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notices WHERE id = %s", (notice_id,))
        conn.commit()
        flash("Notice deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete notice DB error", exc_info=e)
        flash("Failed to delete notice. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("notices_list"))


# ---------------- Classes CRUD ----------------
@app.route("/classes")
def classes_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM classes ORDER BY id DESC")
    classes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("classes_list.html", classes=classes)


@app.route("/classes/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_class():
    if request.method == "POST":
        name = request.form.get("name")
        room = request.form.get("room")
        class_teacher = request.form.get("class_teacher")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO classes (name, room, class_teacher) VALUES (%s, %s, %s)",
                (name, room, class_teacher),
            )
            conn.commit()
            flash("Class added successfully", "success")
            return redirect(url_for("classes_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add class DB error", exc_info=e)
            flash("Failed to add class. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("class_form.html", action="Add", class_data={"name": name, "room": room, "class_teacher": class_teacher})

    return render_template("class_form.html", action="Add", class_data=None)


@app.route("/classes/edit/<int:class_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_class(class_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM classes WHERE id = %s", (class_id,))
    class_data = cursor.fetchone()

    if not class_data:
        cursor.close()
        conn.close()
        flash("Class not found", "danger")
        return redirect(url_for("classes_list"))

    if request.method == "POST":
        name = request.form.get("name")
        room = request.form.get("room")
        class_teacher = request.form.get("class_teacher")

        try:
            cursor.execute(
                "UPDATE classes SET name=%s, room=%s, class_teacher=%s WHERE id=%s",
                (name, room, class_teacher, class_id),
            )
            conn.commit()
            flash("Class updated successfully", "success")
            return redirect(url_for("classes_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update class DB error", exc_info=e)
            flash("Failed to update class. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("class_form.html", action="Edit", class_data={"id": class_id, "name": name, "room": room, "class_teacher": class_teacher})

    cursor.close()
    conn.close()
    return render_template("class_form.html", action="Edit", class_data=class_data)


@app.route("/classes/delete/<int:class_id>")
@requires_role('teacher', 'admin')
def delete_class(class_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM classes WHERE id = %s", (class_id,))
        conn.commit()
        flash("Class deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete class DB error", exc_info=e)
        flash("Failed to delete class. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("classes_list"))


# ---------------- Fees CRUD ----------------
@app.route("/fees")
def fees_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fees ORDER BY id DESC")
    fees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("fees_list.html", fees=fees)


@app.route('/fees/chart-data')
def fees_chart_data():
    """Return monthly fees totals as JSON for charting."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE_FORMAT(paid_date, '%Y-%m') as period,
                   SUM(amount) as total_amount
            FROM fees
            WHERE paid_date IS NOT NULL
            GROUP BY period
            ORDER BY period
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        labels = [r[0] for r in rows]
        # Ensure numeric types usable by JSON
        data = [float(r[1]) if r[1] is not None else 0.0 for r in rows]
        return jsonify({"labels": labels, "data": data}), 200
    except Exception as e:
        app.logger.error('Fees chart data error', exc_info=e)
        return jsonify({"error": str(e)}), 500


@app.route("/fees/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_fee():
    if request.method == "POST":
        student_name = request.form.get("student_name")
        amount = request.form.get("amount")
        paid_date = request.form.get("paid_date")
        status = request.form.get("status")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO fees (student_name, amount, paid_date, status) VALUES (%s, %s, %s, %s)",
                (student_name, amount, paid_date, status),
            )
            conn.commit()
            flash("Fee record added", "success")
            return redirect(url_for("fees_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add fee DB error", exc_info=e)
            flash("Failed to add fee record. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("fee_form.html", action="Add", fee={"student_name": student_name, "amount": amount, "paid_date": paid_date, "status": status})

    return render_template("fee_form.html", action="Add", fee=None)


@app.route("/fees/edit/<int:fee_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_fee(fee_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fees WHERE id = %s", (fee_id,))
    fee = cursor.fetchone()

    if not fee:
        cursor.close()
        conn.close()
        flash("Fee record not found", "danger")
        return redirect(url_for("fees_list"))

    if request.method == "POST":
        student_name = request.form.get("student_name")
        amount = request.form.get("amount")
        paid_date = request.form.get("paid_date")
        status = request.form.get("status")

        try:
            cursor.execute(
                "UPDATE fees SET student_name=%s, amount=%s, paid_date=%s, status=%s WHERE id=%s",
                (student_name, amount, paid_date, status, fee_id),
            )
            conn.commit()
            flash("Fee record updated", "success")
            return redirect(url_for("fees_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update fee DB error", exc_info=e)
            flash("Failed to update fee record. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("fee_form.html", action="Edit", fee={"id": fee_id, "student_name": student_name, "amount": amount, "paid_date": paid_date, "status": status})

    cursor.close()
    conn.close()
    return render_template("fee_form.html", action="Edit", fee=fee)


@app.route("/fees/delete/<int:fee_id>")
@requires_role('teacher', 'admin')
def delete_fee(fee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM fees WHERE id = %s", (fee_id,))
        conn.commit()
        flash("Fee record deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete fee DB error", exc_info=e)
        flash("Failed to delete fee record. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("fees_list"))


# ---------------- Exams CRUD ----------------
@app.route("/exams")
def exams_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM exams ORDER BY exam_date DESC, id DESC")
    exams = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("exams_list.html", exams=exams)


@app.route("/exams/add", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def add_exam():
    if request.method == "POST":
        name = request.form.get("name")
        exam_date = request.form.get("exam_date")
        remarks = request.form.get("remarks")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO exams (name, exam_date, remarks) VALUES (%s, %s, %s)",
                (name, exam_date, remarks),
            )
            conn.commit()
            flash("Exam added", "success")
            return redirect(url_for("exams_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Add exam DB error", exc_info=e)
            flash("Failed to add exam. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("exam_form.html", action="Add", exam={"name": name, "exam_date": exam_date, "remarks": remarks})

    return render_template("exam_form.html", action="Add", exam=None)


@app.route("/exams/edit/<int:exam_id>", methods=["GET", "POST"])
@requires_role('teacher', 'admin')
def edit_exam(exam_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
    exam = cursor.fetchone()

    if not exam:
        cursor.close()
        conn.close()
        flash("Exam not found", "danger")
        return redirect(url_for("exams_list"))

    if request.method == "POST":
        name = request.form.get("name")
        exam_date = request.form.get("exam_date")
        remarks = request.form.get("remarks")

        try:
            cursor.execute(
                "UPDATE exams SET name=%s, exam_date=%s, remarks=%s WHERE id=%s",
                (name, exam_date, remarks, exam_id),
            )
            conn.commit()
            flash("Exam updated", "success")
            return redirect(url_for("exams_list"))
        except mysql.connector.Error as e:
            conn.rollback()
            app.logger.error("Update exam DB error", exc_info=e)
            flash("Failed to update exam. See server logs.", "danger")
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

        return render_template("exam_form.html", action="Edit", exam={"id": exam_id, "name": name, "exam_date": exam_date, "remarks": remarks})

    cursor.close()
    conn.close()
    return render_template("exam_form.html", action="Edit", exam=exam)


@app.route("/exams/delete/<int:exam_id>")
@requires_role('teacher', 'admin')
def delete_exam(exam_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
        conn.commit()
        flash("Exam deleted", "info")
    except mysql.connector.Error as e:
        conn.rollback()
        app.logger.error("Delete exam DB error", exc_info=e)
        flash("Failed to delete exam. See server logs.", "danger")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
    return redirect(url_for("exams_list"))


if __name__ == "__main__":
    # Bind to 0.0.0.0 so localhost and other hosts can reach the dev server if needed.
    # If you only need local access, 127.0.0.1 is fine.
    host = '0.0.0.0'
    port = 5000
    print(f"Starting School ERP on http://{host}:{port}/ (debug={app.debug})")
    try:
        app.run(host=host, port=port, debug=True)
    except Exception as e:
        app.logger.error("Failed to start Flask server", exc_info=e)
        print("Failed to start server:", e)
