# -*- coding: utf-8 -*-

import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_from_directory
)

from config import (
    SECRET_KEY, UPLOAD_FOLDER, ALLOWED_EXTENSIONS,
    MAX_CONTENT_LENGTH, ASSETS_DIR, AVATAR_FOLDER,
    ALLOWED_AVATAR_EXTENSIONS
)
from database import get_db_connection, init_db, seed_default_users

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

# تهيئة قاعدة البيانات عند بدء التطبيق (يعمل مع gunicorn على Render)
init_db()
seed_default_users(generate_password_hash)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_avatar_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('يجب تسجيل الدخول أولاً', 'error')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_user_data():
    if 'user_id' not in session:
        return None
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    conn.close()
    return dict(user) if user else None

def get_student_data(user_id):
    conn = get_db_connection()
    student = conn.execute(
        'SELECT s.*, u.name, u.email, u.phone, u.department FROM students s '
        'JOIN users u ON s.user_id = u.id WHERE u.id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return dict(student) if student else None

def get_company_data(user_id):
    conn = get_db_connection()
    company = conn.execute(
        'SELECT c.*, u.name, u.email, u.phone, u.department FROM companies c '
        'JOIN users u ON c.user_id = u.id WHERE u.id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return dict(company) if company else None

def get_supervisor_data(user_id):
    conn = get_db_connection()
    supervisor = conn.execute(
        'SELECT s.*, u.name, u.email, u.department FROM supervisors s '
        'JOIN users u ON s.user_id = u.id WHERE u.id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return dict(supervisor) if supervisor else None

@app.context_processor
def inject_current_user():
    user = get_user_data()
    return dict(current_user=user)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route('/uploads/avatar/<filename>')
def serve_avatar(filename):
    return send_from_directory(app.config['AVATAR_FOLDER'], filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('يرجى إدخال البريد الإلكتروني وكلمة المرور', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        major = request.form.get('major', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        skills = request.form.get('skills', '').strip()
        
        if not all([name, email, password]):
            flash('يرجى تعبئة الحقول الإلزامية', 'error')
            return render_template('register_student.html')
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template('register_student.html')
        
        cv_file = ''
        if 'cv_file' in request.files and request.files['cv_file'].filename:
            file = request.files['cv_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f"{email}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                cv_file = unique_name
        
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, phone, 'student', department)
        )
        user_id = cursor.lastrowid
        conn.execute(
            'INSERT INTO students (user_id, gender, major, age, skills, cv_file) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, gender, major, int(age) if age.isdigit() else None, skills, cv_file)
        )
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_student.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        organization_type = request.form.get('organization_type', '').strip()
        organization_category = request.form.get('organization_category', '').strip()
        
        if not all([name, email, password]):
            flash('يرجى تعبئة الحقول الإلزامية', 'error')
            return render_template('register_company.html')
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template('register_company.html')
        
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, phone, 'company', department)
        )
        user_id = cursor.lastrowid
        conn.execute(
            'INSERT INTO companies (user_id, organization_type, organization_category) VALUES (?, ?, ?)',
            (user_id, organization_type, organization_category)
        )
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_company.html')

@app.route('/register/supervisor', methods=['GET', 'POST'])
def register_supervisor():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip()
        
        if not all([name, email, password]):
            flash('يرجى تعبئة الحقول الإلزامية', 'error')
            return render_template('register_supervisor.html')
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template('register_supervisor.html')
        
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, '', 'supervisor', department)
        )
        user_id = cursor.lastrowid
        conn.execute(
            'INSERT INTO supervisors (user_id, department) VALUES (?, ?)',
            (user_id, department)
        )
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_supervisor.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    role = session.get('role')
    if role == 'student':
        return redirect(url_for('dashboard_student'))
    elif role == 'company':
        return redirect(url_for('dashboard_company'))
    elif role == 'supervisor':
        return redirect(url_for('dashboard_supervisor'))
    return redirect(url_for('index'))

@app.route('/dashboard/student')
@login_required(role='student')
def dashboard_student():
    user_data = get_user_data()
    student_data = get_student_data(session['user_id'])
    
    conn = get_db_connection()
    applications = conn.execute('''
        SELECT a.*, u.name as company_name FROM applications a
        JOIN companies c ON a.company_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE a.student_id = (SELECT id FROM students WHERE user_id = ?)
        ORDER BY a.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    companies = conn.execute('''
        SELECT c.id, u.name, u.department, c.organization_type
        FROM companies c
        JOIN users u ON c.user_id = u.id
    ''').fetchall()
    
    applied_company_ids = [a['company_id'] for a in applications]
    
    conn.close()
    
    return render_template('dashboard_student.html',
        user=user_data, student=student_data,
        applications=[dict(a) for a in applications],
        companies=[dict(c) for c in companies],
        applied_company_ids=applied_company_ids)

@app.route('/dashboard/company')
@login_required(role='company')
def dashboard_company():
    user_data = get_user_data()
    company_data = get_company_data(session['user_id'])
    
    conn = get_db_connection()
    company_id = company_data['id']
    
    applicants = conn.execute('''
        SELECT a.*, s.gender, s.major, s.skills, s.cv_file, u.name, u.email, u.phone
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE a.company_id = ? AND a.status = 'pending'
        ORDER BY a.created_at DESC
    ''', (company_id,)).fetchall()
    
    accepted = conn.execute('''
        SELECT a.*, s.gender, s.major, s.skills, s.cv_file, u.name, u.email, u.phone
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE a.company_id = ? AND a.status = 'accepted'
    ''', (company_id,)).fetchall()
    
    rejected = conn.execute('''
        SELECT a.*, s.gender, s.major, s.skills, s.cv_file, u.name, u.email, u.phone
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE a.company_id = ? AND a.status = 'rejected'
    ''', (company_id,)).fetchall()
    
    male_applicants = [dict(a) for a in applicants if a['gender'] == 'male']
    female_applicants = [dict(a) for a in applicants if a['gender'] == 'female']
    
    conn.close()
    
    return render_template('dashboard_company.html',
        user=user_data, company=company_data,
        male_applicants=male_applicants,
        female_applicants=female_applicants,
        accepted=[dict(a) for a in accepted],
        rejected=[dict(a) for a in rejected])

@app.route('/dashboard/supervisor')
@login_required(role='supervisor')
def dashboard_supervisor():
    user_data = get_user_data()
    supervisor_data = get_supervisor_data(session['user_id'])
    
    conn = get_db_connection()
    companies = conn.execute(
        'SELECT c.*, u.name, u.department FROM companies c JOIN users u ON c.user_id = u.id'
    ).fetchall()
    
    students = conn.execute(
        'SELECT s.*, u.name, u.department FROM students s JOIN users u ON s.user_id = u.id'
    ).fetchall()
    
    applications = conn.execute('''
        SELECT a.*, u1.name as student_name, u2.name as company_name
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN companies c ON a.company_id = c.id
        JOIN users u1 ON s.user_id = u1.id
        JOIN users u2 ON c.user_id = u2.id
    ''').fetchall()
    
    conn.close()
    
    apps_list = [dict(a) for a in applications]
    pending_apps = [a for a in apps_list if a['status'] == 'pending']
    accepted_apps = [a for a in apps_list if a['status'] == 'accepted']
    rejected_apps = [a for a in apps_list if a['status'] == 'rejected']
    
    return render_template('dashboard_supervisor.html',
        user=user_data, supervisor=supervisor_data,
        companies=[dict(c) for c in companies],
        students=[dict(s) for s in students],
        pending_apps=pending_apps,
        accepted_apps=accepted_apps,
        rejected_apps=rejected_apps)

@app.route('/profile')
@login_required()
def profile():
    user_data = get_user_data()
    role = session.get('role')
    extra_data = None
    if role == 'student':
        extra_data = get_student_data(session['user_id'])
    elif role == 'company':
        extra_data = get_company_data(session['user_id'])
    elif role == 'supervisor':
        extra_data = get_supervisor_data(session['user_id'])
    
    return render_template('profile.html', user=user_data, extra=extra_data)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required()
def edit_profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        skills = request.form.get('skills', '').strip()
        
        conn = get_db_connection()
        avatar_file = None
        if 'avatar_file' in request.files and request.files['avatar_file'].filename:
            file = request.files['avatar_file']
            if file and allowed_avatar_file(file.filename):
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                unique_name = f"user_{session['user_id']}.{ext}"
                file.save(os.path.join(app.config['AVATAR_FOLDER'], unique_name))
                avatar_file = unique_name
        
        if avatar_file:
            conn.execute(
                'UPDATE users SET name = ?, phone = ?, department = ?, avatar_file = ? WHERE id = ?',
                (name, phone, department, avatar_file, session['user_id'])
            )
        else:
            conn.execute(
                'UPDATE users SET name = ?, phone = ?, department = ? WHERE id = ?',
                (name, phone, department, session['user_id'])
            )
        
        if session.get('role') == 'student':
            if 'cv_file' in request.files and request.files['cv_file'].filename:
                file = request.files['cv_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    user = conn.execute('SELECT email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
                    unique_name = f"{user['email']}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                    conn.execute(
                        'UPDATE students SET skills = ?, cv_file = ? WHERE user_id = ?',
                        (skills, unique_name, session['user_id'])
                    )
            else:
                conn.execute(
                    'UPDATE students SET skills = ? WHERE user_id = ?',
                    (skills, session['user_id'])
                )
        
        conn.commit()
        conn.close()
        
        flash('تم تحديث البيانات بنجاح', 'success')
        return redirect(url_for('profile'))
    
    user_data = get_user_data()
    extra_data = None
    if session.get('role') == 'student':
        extra_data = get_student_data(session['user_id'])
    elif session.get('role') == 'company':
        extra_data = get_company_data(session['user_id'])
    elif session.get('role') == 'supervisor':
        extra_data = get_supervisor_data(session['user_id'])
    
    return render_template('edit_profile.html', user=user_data, extra=extra_data)

@app.route('/application/submit', methods=['POST'])
@login_required(role='student')
def submit_application():
    company_id = request.form.get('company_id', type=int)
    if not company_id:
        flash('خطأ في البيانات', 'error')
        return redirect(url_for('dashboard_student'))
    
    conn = get_db_connection()
    student = conn.execute(
        'SELECT id FROM students WHERE user_id = ?', (session['user_id'],)
    ).fetchone()
    
    if not student:
        conn.close()
        flash('خطأ في البيانات', 'error')
        return redirect(url_for('dashboard_student'))
    
    existing = conn.execute(
        'SELECT id FROM applications WHERE student_id = ? AND company_id = ?',
        (student['id'], company_id)
    ).fetchone()
    
    if existing:
        conn.close()
        flash('تم تقديم الطلب مسبقاً لهذه الجهة', 'error')
        return redirect(url_for('dashboard_student'))
    
    conn.execute(
        'INSERT INTO applications (student_id, company_id, status) VALUES (?, ?, ?)',
        (student['id'], company_id, 'pending')
    )
    conn.commit()
    conn.close()
    
    flash('تم إرسال الطلب بنجاح', 'success')
    return redirect(url_for('dashboard_student'))

@app.route('/application/<int:app_id>/accept', methods=['POST'])
@login_required(role='company')
def accept_application(app_id):
    conn = get_db_connection()
    company = conn.execute(
        'SELECT c.id FROM companies c WHERE c.user_id = ?', (session['user_id'],)
    ).fetchone()
    
    if company:
        conn.execute(
            'UPDATE applications SET status = ? WHERE id = ? AND company_id = ?',
            ('accepted', app_id, company['id'])
        )
        conn.commit()
        flash('تم قبول الطلب', 'success')
    conn.close()
    return redirect(url_for('dashboard_company'))

@app.route('/application/<int:app_id>/reject', methods=['POST'])
@login_required(role='company')
def reject_application(app_id):
    conn = get_db_connection()
    company = conn.execute(
        'SELECT c.id FROM companies c WHERE c.user_id = ?', (session['user_id'],)
    ).fetchone()
    
    if company:
        conn.execute(
            'UPDATE applications SET status = ? WHERE id = ? AND company_id = ?',
            ('rejected', app_id, company['id'])
        )
        conn.commit()
        flash('تم رفض الطلب', 'info')
    conn.close()
    return redirect(url_for('dashboard_company'))

@app.route('/uploads/cv/<filename>')
@login_required()
def download_cv(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    init_db()
    seed_default_users(generate_password_hash)
    app.run(host='127.0.0.1', port=5000, debug=True)
