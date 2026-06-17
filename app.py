from flask import Flask, render_template, request, redirect, session, make_response, send_from_directory, send_file
from flask_mysqldb import MySQL
from PIL import Image
from werkzeug.utils import secure_filename
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
import os
import math
import random

app = Flask(__name__)

# Secret Key
app.secret_key = 'supersecretkey'

# Upload Folder
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# MySQL Configuration
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))

mysql = MySQL(app)

# =========================================
# Home Page
# =========================================
@app.route('/')
def home():
    return render_template('index.html')


# =========================================
# Login
# =========================================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if username == 'admin' and password == '1234':

            session['logged_in'] = True

            return redirect('/dashboard')

    return render_template('login.html')

@app.route('/create_table')
def create_table():
    cursor = mysql.connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        email VARCHAR(255),
        course VARCHAR(255),
        filename VARCHAR(255),
        original_size BIGINT,
        compressed_size BIGINT,
        storage_type VARCHAR(100)
    )
    """)

    mysql.connection.commit()
    cursor.close()

    return "Students table created successfully!"


# =========================================
# Dashboard
# =========================================
@app.route('/dashboard')
def dashboard():

    if 'logged_in' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    # Total Students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Total Original Size
    cursor.execute("SELECT SUM(original_size) FROM students")
    original_size = cursor.fetchone()[0]

    if original_size is None:
        original_size = 0

    # Total Compressed Size
    cursor.execute("SELECT SUM(compressed_size) FROM students")
    compressed_size = cursor.fetchone()[0]

    if compressed_size is None:
        compressed_size = 0

    # Storage Saved
    saved = original_size - compressed_size

    # Saved Percentage
    if original_size > 0:

        saved_percentage = round(
            (saved / original_size) * 100,
            2
        )

    else:

        saved_percentage = 0

    # AI Prediction
    future_students = 1000

    if total_students > 0:

        average_storage = compressed_size / total_students

        predicted_storage = math.ceil(
            (average_storage * future_students) / 1024
        )

    else:

        predicted_storage = 0

    cursor.close()

    return render_template(
        'dashboard.html',
        total_students=total_students,
        original_size=original_size,
        compressed_size=compressed_size,
        saved_percentage=saved_percentage,
        predicted_storage=predicted_storage
    )


# =========================================
# Add Student
# =========================================
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():

    if 'logged_in' not in session:
        return redirect('/login')

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        course = request.form['course']

        file = request.files['file']

        # Allowed file types
        allowed_extensions = ['png', 'jpg', 'jpeg', 'pdf', 'docx']

        # File extension
        file_extension = file.filename.split('.')[-1].lower()

        # Validate file type
        if file_extension not in allowed_extensions:

            return '''
            <h2 style="color:red;">
                Only JPG, JPEG, PNG, PDF, and DOCX files are allowed!
            </h2>

            <a href="/add_student">
                Go Back
            </a>
            '''

        # Secure filename
        filename = secure_filename(file.filename)

        # Save original file
        filepath = os.path.join(
            app.config['UPLOAD_FOLDER'],
            filename
        )

        file.save(filepath)

        # Original Size
        original_size = os.path.getsize(filepath)

        compressed_size = original_size

        # =========================================
        # IMAGE COMPRESSION
        # =========================================
        if file_extension in ['jpg', 'jpeg', 'png']:

            compressed_filename = 'compressed_' + filename

            compressed_path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                compressed_filename
            )

            image = Image.open(filepath)

            image.save(
                compressed_path,
                optimize=True,
                quality=30
            )

            compressed_size = os.path.getsize(compressed_path)

        # =========================================
        # PDF / DOCX
        # =========================================
        else:

            compressed_filename = filename

         # Random Storage Type
        storage_type = random.choice([
            'Local Storage',
            'Cloud Storage'
        ])

        # Save to database
        cursor = mysql.connection.cursor()

        cursor.execute("""
            INSERT INTO students
            (name, email, course, filename,
             original_size, compressed_size,storage_type)

            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            email,
            course,
            filename,
            str(original_size),
            str(compressed_size),
            storage_type
        ))

        mysql.connection.commit()

        cursor.close()

        return redirect('/view_students')

    return render_template('add_student.html')


# =========================================
# View Students + Search
# =========================================
@app.route('/view_students')
def view_students():

    if 'logged_in' not in session:
        return redirect('/login')

    search = request.args.get('search')

    cursor = mysql.connection.cursor()

    if search:

        query = """
        SELECT * FROM students
        WHERE name LIKE %s
        OR email LIKE %s
        OR course LIKE %s
        """

        value = "%" + search + "%"

        cursor.execute(
            query,
            (value, value, value)
        )

    else:

        cursor.execute("SELECT * FROM students")

    students = cursor.fetchall()

    cursor.close()

    return render_template(
        'view_students.html',
        students=students
    )


# =========================================
# Edit Student
# =========================================
@app.route('/edit_student/<int:id>', methods=['GET', 'POST'])
def edit_student(id):

    if 'logged_in' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    # Update Student
    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        course = request.form['course']

        cursor.execute("""
            UPDATE students
            SET name=%s,
                email=%s,
                course=%s
            WHERE id=%s
        """, (
            name,
            email,
            course,
            id
        ))

        mysql.connection.commit()

        cursor.close()

        return redirect('/view_students')

    # Get Student Data
    cursor.execute(
        "SELECT * FROM students WHERE id=%s",
        [id]
    )

    student = cursor.fetchone()

    cursor.close()

    return render_template(
        'edit_student.html',
        student=student
    )


# =========================================
# Delete Student
# =========================================
@app.route('/delete_student/<int:id>')
def delete_student(id):

    if 'logged_in' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    cursor.execute(
        "DELETE FROM students WHERE id=%s",
        [id]
    )

    mysql.connection.commit()

    cursor.close()

    return redirect('/view_students')


# =========================================
# Export PDF
# =========================================
@app.route('/export_pdf')
def export_pdf():

    if 'logged_in' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    cursor.execute("SELECT * FROM students")

    students = cursor.fetchall()

    cursor.close()

    # PDF File
    pdf_file = "student_report.pdf"

    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter
    )

    elements = []

    # Table Data
    data = [
        ['ID', 'Name', 'Email', 'Course']
    ]

    for student in students:

        data.append([
            student[0],
            student[1],
            student[2],
            student[3]
        ])

    # Table
    table = Table(data)

    # Style
    style = TableStyle([

        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),

        ('GRID', (0,0), (-1,-1), 1, colors.black),

        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),

        ('BOTTOMPADDING', (0,0), (-1,0), 10),

        ('BACKGROUND', (0,1), (-1,-1), colors.beige)

    ])

    table.setStyle(style)

    elements.append(table)

    doc.build(elements)

    # Download Response
    response = make_response(
        open(pdf_file, 'rb').read()
    )

    response.headers['Content-Type'] = 'application/pdf'

    response.headers['Content-Disposition'] = \
        'attachment; filename=student_report.pdf'

    return response


# =========================================
# Logout
# =========================================
@app.route('/logout')
def logout():

    session.pop('logged_in', None)

    return redirect('/login')


# Preview File
@app.route('/preview/<filename>')
def preview_file(filename):

    if 'logged_in' not in session:
        return redirect('/login')

    filepath = os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename
    )

    extension = filename.split('.')[-1].lower()

    # PDF Preview
    if extension == 'pdf':

        return send_file(
            filepath,
            mimetype='application/pdf'
        )

    # Image Preview
    elif extension in ['jpg', 'jpeg', 'png']:

        return send_file(filepath)

    # DOCX
    else:

        return '''
        <h2>
            DOCX Preview Not Supported Yet
        </h2>

        <a href="/view_students">
            Back
        </a>
        '''

# Download File
@app.route('/download/<filename>')
def download_file(filename):

    if 'logged_in' not in session:
        return redirect('/login')

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )


# =========================================
# Run App
# =========================================
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)