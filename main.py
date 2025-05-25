from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import psycopg2
from psycopg2 import sql, Error
import os
from dotenv import load_dotenv
from datetime import datetime
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


@login_manager.user_loader
def load_user(user_id):
    """Load user from database for Flask-Login session management"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password FROM users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        if user_data:
            return User(id=user_data[0], username=user_data[1], password=user_data[2])
        return None
    except Error as e:
        print(f"Error loading user: {e}")
        return None

# Database connection configuration


def get_db_connection():
    """Establish connection to PostgreSQL database using environment variables"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    return conn

# Initialize database tables (DDL - Data Definition Language)


def initialize_database():
    """Create all required tables if they don't exist"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create users table for authentication
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Original tables for student management
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                date_of_birth DATE,
                major VARCHAR(50),
                enrollment_date DATE DEFAULT CURRENT_DATE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                course_id SERIAL PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                code VARCHAR(20) UNIQUE NOT NULL,
                credits INTEGER NOT NULL,
                instructor VARCHAR(100),
                max_capacity INTEGER DEFAULT 30
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS enrollments (
                enrollment_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
                course_id INTEGER REFERENCES courses(course_id) ON DELETE CASCADE,
                enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                grade VARCHAR(2),
                UNIQUE(student_id, course_id)
            )
        """)

        # Audit log table for triggers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_audit_log (
                log_id SERIAL PRIMARY KEY,
                student_id INTEGER,
                action VARCHAR(10) NOT NULL,
                changed_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                old_data JSONB,
                new_data JSONB
            )
        """)

        # Stored procedure for grade updates
        cur.execute("""
            CREATE OR REPLACE PROCEDURE update_course_grade(
                p_student_id INTEGER,
                p_course_id INTEGER,
                p_grade VARCHAR(2)
            )
            AS $$
            BEGIN
                UPDATE enrollments
                SET grade = p_grade
                WHERE student_id = p_student_id AND course_id = p_course_id;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Student % is not enrolled in course %', p_student_id, p_course_id;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
        """)

        conn.commit()
        cur.close()
        conn.close()
    except Error as e:
        print(f"Error initializing database: {e}")

# Template filters and context processors


@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """Format datetime objects in templates"""
    if value is None:
        return ''
    return value.strftime(format)


@app.context_processor
def inject_now():
    """Inject current datetime into all templates"""
    return {'now': datetime.now()}


# Initialize database when app starts
initialize_database()

# --------------------------
# PUBLIC ROUTES (No login required)
# --------------------------


@app.route('/')
def landing_page():
    """Public landing page"""
    return render_template('landing_page.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password FROM users WHERE username = %s", (username,))
            user_data = cur.fetchone()

            if user_data and check_password_hash(user_data[2], password):
                user = User(
                    id=user_data[0], username=user_data[1], password=user_data[2])
                login_user(user)
                flash('Login successful!', 'success')
                next_page = request.args.get('next') or url_for('home')
                return redirect(next_page)
            else:
                flash('Invalid username or password', 'danger')

        except Error as e:
            flash(f'Login error: {str(e)}', 'danger')
        finally:
            cur.close()
            conn.close()

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(
            password, method='pbkdf2:sha256')

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Check if username exists
            cur.execute(
                "SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))

            # Create new user
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
                (username, hashed_password)
            )
            user_id = cur.fetchone()[0]
            conn.commit()

            # Log in the new user
            user = User(id=user_id, username=username,
                        password=hashed_password)
            login_user(user)

            flash('Registration successful!', 'success')
            return redirect(url_for('home'))

        except Error as e:
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('register'))
        finally:
            cur.close()
            conn.close()

    return render_template('auth/register.html')


# --------------------------
# PROTECTED ROUTES (Login required)
# --------------------------

# Route to handle user logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing_page'))

# Route to display the home page (dashboard) after login


@app.route('/home')
@login_required
def home():
    """Dashboard home page - requires login"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get counts for dashboard
        cur.execute("SELECT COUNT(*) FROM students")
        student_count = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) FROM courses")
        course_count = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) FROM enrollments")
        enrollment_count = cur.fetchone()['count']

        # Get recent activities (last 5)
        cur.execute("""
            SELECT * FROM student_audit_log
            ORDER BY changed_on DESC
            LIMIT 5
        """)
        recent_activities = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('index.html',
                               student_count=student_count,
                               course_count=course_count,
                               enrollment_count=enrollment_count,
                               recent_activities=recent_activities)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('index.html')

# --------------------------
# STUDENT MANAGEMENT ROUTES
# --------------------------

# Route to display all students (uses JOIN query)


@app.route('/students')
@login_required
def list_students():
    """List all students - requires login"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT s.student_id, s.name, s.email, s.date_of_birth, s.major, 
                   COUNT(e.enrollment_id) AS course_count, s.enrollment_date
            FROM students s
            LEFT JOIN enrollments e ON s.student_id = e.student_id
            GROUP BY s.student_id, s.name, s.email, s.date_of_birth, s.major, s.enrollment_date
            ORDER BY s.name
        """)

        students = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('students/list.html', students=students)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('home'))

# Route to add a new student (DML - INSERT)


@app.route('/student/add', methods=['GET', 'POST'])
@login_required
def add_student():
    """Add new student - requires login"""
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            dob = request.form['dob']
            major = request.form['major']

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO students (name, email, date_of_birth, major)
                VALUES (%s, %s, %s, %s)
                RETURNING student_id
            """, (name, email, dob, major))

            student_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            flash('Student added successfully!', 'success')
            return redirect(url_for('view_student', student_id=student_id))
        except Error as e:
            flash(f'Error adding student: {str(e)}', 'danger')

    return render_template('students/add.html')

# Route to view a single student (uses NESTED QUERY)


@app.route('/student/<int:student_id>')
@login_required
def view_student(student_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get student info
        cur.execute("SELECT * FROM students WHERE student_id = %s",
                    (student_id,))
        student = cur.fetchone()

        if not student:
            return "Student not found", 404

        # NESTED QUERY: Get courses the student is NOT enrolled in
        cur.execute("""
            SELECT * FROM courses 
            WHERE course_id NOT IN (
                SELECT course_id FROM enrollments WHERE student_id = %s
            )
        """, (student_id,))
        available_courses = cur.fetchall()

        # JOIN QUERY: Get enrolled courses with grades
        cur.execute("""
            SELECT c.course_id, c.title, c.code, e.grade
            FROM courses c
            JOIN enrollments e ON c.course_id = e.course_id
            WHERE e.student_id = %s
        """, (student_id,))
        enrolled_courses = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('students/view.html',
                               student=student,
                               available_courses=available_courses,
                               enrolled_courses=enrolled_courses)
    except Error as e:
        return str(e), 500

# Route to update student info (DML - UPDATE)


@app.route('/student/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            dob = request.form['dob']
            major = request.form['major']

            conn = get_db_connection()
            cur = conn.cursor()

            # DML: UPDATE operation
            cur.execute("""
                UPDATE students
                SET name = %s, email = %s, date_of_birth = %s, major = %s
                WHERE student_id = %s
            """, (name, email, dob, major, student_id))

            conn.commit()
            cur.close()
            conn.close()

            return redirect(url_for('view_student', student_id=student_id))
        except Error as e:
            return str(e), 500

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE student_id = %s",
                    (student_id,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if not student:
            return "Student not found", 404

        return render_template('students/edit.html', student=student)
    except Error as e:
        return str(e), 500

# Route to delete a student (DML - DELETE)


@app.route('/student/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # DML: DELETE operation
        cur.execute("DELETE FROM students WHERE student_id = %s",
                    (student_id,))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('list_students'))
    except Error as e:
        return str(e), 500

# --------------------------
# COURSE MANAGEMENT ROUTES
# --------------------------

# Route to list all courses (uses USER-DEFINED FUNCTION)


@app.route('/courses')
@login_required
def list_courses():
    """List all courses - requires login"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE OR REPLACE FUNCTION get_student_count(course_id INTEGER)
            RETURNS INTEGER AS $$
            DECLARE
                student_count INTEGER;
            BEGIN
                SELECT COUNT(*) INTO student_count
                FROM enrollments
                WHERE enrollments.course_id = $1;
                
                RETURN student_count;
            END;
            $$ LANGUAGE plpgsql;
        """)

        cur.execute("""
            SELECT c.*, get_student_count(c.course_id) AS student_count
            FROM courses c
            ORDER BY c.title
        """)

        courses = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('courses/list.html', courses=courses)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('home'))

# Route to add a new course (DML - INSERT)


@app.route('/course/add', methods=['GET', 'POST'])
@login_required
def add_course():
    if request.method == 'POST':
        try:
            title = request.form['title']
            code = request.form['code']
            credits = request.form['credits']
            instructor = request.form['instructor']
            capacity = request.form['capacity']

            conn = get_db_connection()
            cur = conn.cursor()

            # DML: INSERT operation
            cur.execute("""
                INSERT INTO courses (title, code, credits, instructor, max_capacity)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING course_id
            """, (title, code, credits, instructor, capacity))

            course_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()

            return redirect(url_for('view_course', course_id=course_id))
        except Error as e:
            return str(e), 500

    return render_template('courses/add.html')

# Route to view a single course (uses STORED PROCEDURE)


@app.route('/course/<int:course_id>')
@login_required
def view_course(course_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First, let's create a STORED PROCEDURE if it doesn't exist
        cur.execute("""
            CREATE OR REPLACE PROCEDURE update_course_grade(
                p_student_id INTEGER,
                p_course_id INTEGER,
                p_grade VARCHAR(2)
            )
            AS $$
            BEGIN
                UPDATE enrollments
                SET grade = p_grade
                WHERE student_id = p_student_id AND course_id = p_course_id;
                
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Student % is not enrolled in course %', p_student_id, p_course_id;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Get course info
        cur.execute("SELECT * FROM courses WHERE course_id = %s", (course_id,))
        course = cur.fetchone()

        if not course:
            return "Course not found", 404

        # JOIN QUERY: Get enrolled students
        cur.execute("""
            SELECT s.student_id, s.name, e.grade
            FROM students s
            JOIN enrollments e ON s.student_id = e.student_id
            WHERE e.course_id = %s
            ORDER BY s.name
        """, (course_id,))
        enrolled_students = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('courses/view.html',
                               course=course,
                               enrolled_students=enrolled_students)
    except Error as e:
        return str(e), 500

# Route to enroll a student in a course (uses CURSOR and HANDLER)


@app.route('/enroll', methods=['POST'])
@login_required
def enroll_student():
    try:
        student_id = request.form['student_id']
        course_id = request.form['course_id']

        conn = get_db_connection()
        cur = conn.cursor()

        # Let's create a procedure with CURSOR and HANDLER for enrollment
        cur.execute("""
            CREATE OR REPLACE PROCEDURE enroll_student(
                p_student_id INTEGER,
                p_course_id INTEGER
            )
            AS $$
            DECLARE
                v_course_capacity INTEGER;
                v_current_enrollment INTEGER;
                v_student_exists BOOLEAN;
                v_course_exists BOOLEAN;
                
                -- CURSOR to check if student is already enrolled
                cur_enrolled CURSOR FOR
                    SELECT 1 FROM enrollments
                    WHERE student_id = p_student_id AND course_id = p_course_id;
            BEGIN
                -- Check if student exists
                SELECT EXISTS(SELECT 1 FROM students WHERE student_id = p_student_id) INTO v_student_exists;
                IF NOT v_student_exists THEN
                    RAISE EXCEPTION 'Student % does not exist', p_student_id;
                END IF;
                
                -- Check if course exists
                SELECT EXISTS(SELECT 1 FROM courses WHERE course_id = p_course_id) INTO v_course_exists;
                IF NOT v_course_exists THEN
                    RAISE EXCEPTION 'Course % does not exist', p_course_id;
                END IF;
                
                -- Check if already enrolled using CURSOR
                OPEN cur_enrolled;
                FETCH cur_enrolled INTO v_student_exists;
                IF FOUND THEN
                    CLOSE cur_enrolled;
                    RAISE EXCEPTION 'Student is already enrolled in this course';
                END IF;
                CLOSE cur_enrolled;
                
                -- Check course capacity
                SELECT max_capacity INTO v_course_capacity FROM courses WHERE course_id = p_course_id;
                SELECT COUNT(*) INTO v_current_enrollment FROM enrollments WHERE course_id = p_course_id;
                
                IF v_current_enrollment >= v_course_capacity THEN
                    RAISE EXCEPTION 'Course has reached maximum capacity';
                END IF;
                
                -- If all checks pass, enroll the student
                INSERT INTO enrollments (student_id, course_id)
                VALUES (p_student_id, p_course_id);
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Call the stored procedure
        cur.execute("CALL enroll_student(%s, %s)", (student_id, course_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('view_student', student_id=student_id))
    except Error as e:
        return str(e), 500

# Route to update a student's grade (uses the STORED PROCEDURE we created earlier)


@app.route('/update_grade', methods=['POST'])
@login_required
def update_grade():
    try:
        student_id = int(request.form['student_id'])
        course_id = int(request.form['course_id'])
        grade = request.form['grade']

        conn = get_db_connection()
        cur = conn.cursor()

        # Explicitly cast grade to VARCHAR in the SQL call
        cur.execute("CALL update_course_grade(%s, %s, %s::VARCHAR)",
                    (student_id, course_id, grade))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('view_course', course_id=course_id))
    except Error as e:
        return str(e), 500

# Route to drop a course (DML - DELETE)


@app.route('/drop_course', methods=['POST'])
@login_required
def drop_course():
    try:
        student_id = request.form['student_id']
        course_id = request.form['course_id']

        conn = get_db_connection()
        cur = conn.cursor()

        # DML: DELETE operation
        cur.execute("""
            DELETE FROM enrollments
            WHERE student_id = %s AND course_id = %s
        """, (student_id, course_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('view_student', student_id=student_id))
    except Error as e:
        return str(e), 500

# Route to edit a course (DML - UPDATE)


@app.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if request.method == 'POST':
        try:
            title = request.form['title']
            code = request.form['code']
            credits = request.form['credits']
            instructor = request.form['instructor']
            capacity = request.form['capacity']

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE courses
                SET title = %s, code = %s, credits = %s, instructor = %s, max_capacity = %s
                WHERE course_id = %s
            """, (title, code, credits, instructor, capacity, course_id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('view_course', course_id=course_id))
        except Error as e:
            return str(e), 500

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM courses WHERE course_id = %s", (course_id,))
        course = cur.fetchone()
        cur.close()
        conn.close()
        if not course:
            return "Course not found", 404
        return render_template('courses/edit.html', course=course)
    except Error as e:
        return str(e), 500

# --------------------------
# REPORTING ROUTES
# --------------------------

# Route to generate a report (uses CURSOR and HANDLER extensively)


@app.route('/reports/student_grades')
@login_required
def student_grades_report():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create or replace the report function with qualified column names
        cur.execute("""
            CREATE OR REPLACE FUNCTION generate_student_grades_report()
            RETURNS TABLE (
                student_id INTEGER,
                student_name VARCHAR(100),
                course_title VARCHAR(100),
                grade VARCHAR(2),
                credits INTEGER,
                grade_points NUMERIC
            ) AS $$
            DECLARE
                grade_rec RECORD;
                cur_students CURSOR FOR
                    SELECT students.student_id, students.name FROM students ORDER BY students.name;
                cur_courses CURSOR(p_student_id INTEGER) FOR
                    SELECT c.title, e.grade, c.credits
                    FROM enrollments e
                    JOIN courses c ON e.course_id = c.course_id
                    WHERE e.student_id = p_student_id;
                
                -- HANDLER variables
                v_grade_points NUMERIC;
                v_total_credits INTEGER := 0;
                v_total_grade_points NUMERIC := 0;
            BEGIN
                FOR student_rec IN cur_students LOOP
                    FOR course_rec IN cur_courses(student_rec.student_id) LOOP
                        -- Calculate grade points (A=4, B=3, etc.)
                        CASE course_rec.grade
                            WHEN 'A' THEN v_grade_points := 4.0;
                            WHEN 'A-' THEN v_grade_points := 3.7;
                            WHEN 'B+' THEN v_grade_points := 3.3;
                            WHEN 'B' THEN v_grade_points := 3.0;
                            WHEN 'B-' THEN v_grade_points := 2.7;
                            WHEN 'C+' THEN v_grade_points := 2.3;
                            WHEN 'C' THEN v_grade_points := 2.0;
                            WHEN 'D' THEN v_grade_points := 1.0;
                            ELSE v_grade_points := 0.0;
                        END CASE;
                        
                        -- Return the row
                        student_id := student_rec.student_id;
                        student_name := student_rec.name;
                        course_title := course_rec.title;
                        grade := course_rec.grade;
                        credits := course_rec.credits;
                        grade_points := v_grade_points * course_rec.credits;
                        
                        -- Accumulate for GPA calculation
                        v_total_credits := v_total_credits + course_rec.credits;
                        v_total_grade_points := v_total_grade_points + (v_grade_points * course_rec.credits);
                        
                        RETURN NEXT;
                    END LOOP;
                END LOOP;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Execute the function to get the report
        cur.execute("SELECT * FROM generate_student_grades_report()")
        report_data = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('reports/grades.html', report_data=report_data)
    except Error as e:
        return str(e), 500

# --------------------------
# TRIGGER IMPLEMENTATION
# --------------------------

# Let's create TRIGGERS to audit student changes


def create_audit_triggers():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE OR REPLACE FUNCTION log_student_changes()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    INSERT INTO student_audit_log(student_id, action, new_data)
                    VALUES (NEW.student_id, 'INSERT', to_jsonb(NEW));
                ELSIF TG_OP = 'UPDATE' THEN
                    INSERT INTO student_audit_log(student_id, action, old_data, new_data)
                    VALUES (NEW.student_id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW));
                ELSIF TG_OP = 'DELETE' THEN
                    INSERT INTO student_audit_log(student_id, action, old_data)
                    VALUES (OLD.student_id, 'DELETE', to_jsonb(OLD));
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
        """)

        cur.execute("""
            DROP TRIGGER IF EXISTS students_audit_trigger ON students;
            CREATE TRIGGER students_audit_trigger
            AFTER INSERT OR UPDATE OR DELETE ON students
            FOR EACH ROW EXECUTE FUNCTION log_student_changes();
        """)

        conn.commit()
        cur.close()
        conn.close()
    except Error as e:
        print(f"Error creating triggers: {e}")


# Call the function to create triggers when the app starts
create_audit_triggers()

# Route to view audit log (shows TRIGGER results)


@app.route('/audit_log')
@login_required
def view_audit_log():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM student_audit_log
            ORDER BY changed_on DESC
            LIMIT 100
        """)

        log_entries = cur.fetchall()
        cur.close()
        conn.close()

        return render_template('audit_log.html', log_entries=log_entries)
    except Error as e:
        return str(e), 500

# --------------------------
# API ENDPOINTS (for AJAX)
# --------------------------


@app.route('/api/courses')
@login_required
def api_courses():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT course_id, title FROM courses ORDER BY title")
        courses = [{'id': row[0], 'title': row[1]} for row in cur.fetchall()]

        cur.close()
        conn.close()

        return jsonify(courses)
    except Error as e:
        return jsonify({'error': str(e)}), 500

# --------------------------
# MAIN EXECUTION
# --------------------------


if __name__ == '__main__':
    app.run(debug=True)
