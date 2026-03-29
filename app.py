# -*- coding: utf-8 -*-

import os
import sqlite3
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
from constants import (
    SAUDI_MINISTRIES,
    FACULTY_DEPARTMENTS,
    COLLEGE_MAJORS,
    COLLEGE_NAME,
)
from database import get_db_connection, init_db, seed_default_users
from ai_matching import match_student_to_companies_ai

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

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
        '''
        SELECT s.*, u.name, u.email, u.phone, u.department,
               sup_u.name AS assigned_supervisor_name
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN supervisors sup ON s.assigned_supervisor_id = sup.id
        LEFT JOIN users sup_u ON sup.user_id = sup_u.id
        WHERE u.id = ?
        ''',
        (user_id,),
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
        '''
        SELECT s.id, s.user_id, u.name, u.email, u.phone, u.department, u.gender
        FROM supervisors s
        JOIN users u ON s.user_id = u.id
        WHERE u.id = ?
        ''',
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(supervisor) if supervisor else None


def _value_in_list(value, allowed):
    v = (value or '').strip()
    return v if v in allowed else None


def _insert_student_row(
    conn,
    user_id,
    gender,
    major,
    age,
    skills,
    cv_file,
    course_name,
    crn,
    section_code,
    assigned_supervisor_id=None,
):
    conn.execute(
        '''
        INSERT INTO students (
            user_id, gender, major, age, skills, cv_file, course_name, crn, section_code, assigned_supervisor_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            gender,
            major,
            age,
            skills or '',
            cv_file or '',
            course_name,
            crn,
            section_code,
            assigned_supervisor_id,
        ),
    )


def get_supervisors_for_dropdown():
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT s.id AS supervisor_id, u.name AS name
        FROM supervisors s
        JOIN users u ON u.id = s.user_id
        WHERE COALESCE(u.account_status, 'active') = 'active'
        ORDER BY u.name
        '''
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_assigned_students_for_supervisor(supervisor_pk):
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT u.name, u.email, u.phone, st.major, st.course_name, st.crn, st.section_code, st.gender
        FROM students st
        JOIN users u ON st.user_id = u.id
        WHERE st.assigned_supervisor_id = ?
        ORDER BY u.name
        '''
        , (supervisor_pk,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_professor_name(student_row):
    """اسم المشرف: إسناد رسمي أولاً، ثم تطابق الشعبة/الرقم المرجعي."""
    if not student_row:
        return None
    if student_row.get('assigned_supervisor_name'):
        return student_row['assigned_supervisor_name']
    if not student_row.get('crn') or not student_row.get('section_code'):
        return None
    conn = get_db_connection()
    row = conn.execute(
        '''
        SELECT u.name FROM supervisor_sections ss
        JOIN supervisors sup ON ss.supervisor_id = sup.id
        JOIN users u ON sup.user_id = u.id
        WHERE ss.crn = ? AND ss.section_code = ?
        LIMIT 1
        ''',
        (student_row['crn'].strip(), student_row['section_code'].strip()),
    ).fetchone()
    conn.close()
    return row['name'] if row else None


def get_supervisor_sections_with_students(supervisor_pk):
    conn = get_db_connection()
    secs = conn.execute(
        'SELECT * FROM supervisor_sections WHERE supervisor_id = ? ORDER BY created_at DESC',
        (supervisor_pk,),
    ).fetchall()
    result = []
    for sec in secs:
        studs = conn.execute(
            '''
            SELECT u.name, u.email, u.phone, s.major, s.course_name, s.crn, s.section_code, s.gender
            FROM students s
            JOIN users u ON s.user_id = u.id
            WHERE TRIM(s.crn) = TRIM(?) AND TRIM(s.section_code) = TRIM(?)
            ORDER BY u.name
            ''',
            (sec['crn'], sec['section_code']),
        ).fetchall()
        d = dict(sec)
        rows = [dict(r) for r in studs]
        d['students'] = rows
        d['students_male'] = [r for r in rows if r.get('gender') == 'male']
        d['students_female'] = [r for r in rows if r.get('gender') == 'female']
        result.append(d)
    conn.close()
    return result

@app.context_processor
def inject_current_user():
    user = get_user_data()
    return dict(current_user=user, college_name=COLLEGE_NAME)


def get_all_training_supervisors_grouped():
    """مشرفو التدريب في الكلية — ذكور وإناث (للعرض في لوحة المشرف)."""
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT u.name, u.email, u.phone, u.department, u.gender
        FROM users u
        INNER JOIN supervisors s ON s.user_id = u.id
        WHERE u.role = 'supervisor'
          AND COALESCE(u.account_status, 'active') = 'active'
        ORDER BY u.name
        '''
    ).fetchall()
    conn.close()
    lst = [dict(r) for r in rows]
    males = [r for r in lst if r.get('gender') == 'male']
    females = [r for r in lst if r.get('gender') == 'female']
    other = [r for r in lst if r.get('gender') not in ('male', 'female')]
    return males, females, other

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
            status = (dict(user).get('account_status') or 'active')
            if status == 'suspended':
                flash('تم تعليق حسابك. تواصل مع إدارة المنصة.', 'error')
                return render_template('login.html')
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
        course_name = request.form.get('course_name', '').strip()
        crn = request.form.get('crn', '').strip()
        section_code = request.form.get('section_code', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        skills = request.form.get('skills', '').strip()
        
        if not all([name, email, password, course_name, crn, section_code]):
            flash('يرجى تعبئة الحقول الإلزامية بما فيها اسم المقرر والرقم المرجعي والشعبة', 'error')
            return render_template(
                'register_student.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        if _value_in_list(department, FACULTY_DEPARTMENTS) is None or _value_in_list(major, FACULTY_DEPARTMENTS) is None:
            flash('يرجى اختيار القسم والتخصص من القائمة المعتمدة', 'error')
            return render_template(
                'register_student.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template(
                'register_student.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        
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
        _insert_student_row(
            conn,
            user_id,
            gender,
            major,
            int(age) if age.isdigit() else None,
            skills,
            cv_file,
            course_name,
            crn,
            section_code,
            None,
        )
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_student.html', faculty_departments=FACULTY_DEPARTMENTS)

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
        ministry = request.form.get('ministry', '').strip() if organization_type == 'government' else ''
        
        if not all([name, email, password]):
            flash('يرجى تعبئة الحقول الإلزامية', 'error')
            return render_template(
                'register_company.html',
                ministries=SAUDI_MINISTRIES,
                college_majors=COLLEGE_MAJORS,
            )
        if _value_in_list(department, COLLEGE_MAJORS) is None:
            flash('يرجى اختيار الجهة (التخصص) من قائمة تخصصات الكلية', 'error')
            return render_template(
                'register_company.html',
                ministries=SAUDI_MINISTRIES,
                college_majors=COLLEGE_MAJORS,
            )
        if organization_type == 'government' and not ministry:
            flash('يرجى اختيار الوزارة التابعة لها', 'error')
            return render_template(
                'register_company.html',
                ministries=SAUDI_MINISTRIES,
                college_majors=COLLEGE_MAJORS,
            )
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template(
                'register_company.html',
                ministries=SAUDI_MINISTRIES,
                college_majors=COLLEGE_MAJORS,
            )
        
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, phone, 'company', department)
        )
        user_id = cursor.lastrowid
        conn.execute(
            'INSERT INTO companies (user_id, organization_type, organization_category, ministry) VALUES (?, ?, ?, ?)',
            (user_id, organization_type, organization_category or name, ministry)
        )
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template(
        'register_company.html',
        ministries=SAUDI_MINISTRIES,
        college_majors=COLLEGE_MAJORS,
    )

@app.route('/register/supervisor', methods=['GET', 'POST'])
def register_supervisor():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip()
        gender = request.form.get('gender', '').strip()
        
        if not all([name, email, password]):
            flash('يرجى تعبئة الحقول الإلزامية', 'error')
            return render_template(
                'register_supervisor.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        if gender not in ('male', 'female'):
            flash('يرجى تحديد الجنس (دكتور / دكتورة) لمشرف التدريب', 'error')
            return render_template(
                'register_supervisor.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        if _value_in_list(department, FACULTY_DEPARTMENTS) is None:
            flash('يرجى اختيار القسم من قائمة الأقسام العلمية', 'error')
            return render_template(
                'register_supervisor.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            flash('البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template(
                'register_supervisor.html',
                faculty_departments=FACULTY_DEPARTMENTS,
            )
        
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, role, department, gender) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, '', 'supervisor', department, gender)
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
    
    return render_template('register_supervisor.html', faculty_departments=FACULTY_DEPARTMENTS)

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
    elif role == 'admin':
        return redirect(url_for('admin_supervisors'))
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
    
    companies_raw = conn.execute('''
        SELECT c.id, u.name, u.department, c.organization_type, c.ministry, c.organization_category
        FROM companies c
        JOIN users u ON c.user_id = u.id
    ''').fetchall()
    
    companies_all = [dict(c) for c in companies_raw]
    suitable_companies = match_student_to_companies_ai(student_data, companies_all)
    applied_company_ids = [a['company_id'] for a in applications]
    
    conn.close()
    
    professor_name = get_student_professor_name(student_data)
    
    return render_template('dashboard_student.html',
        user=user_data, student=student_data,
        applications=[dict(a) for a in applications],
        companies=suitable_companies,
        applied_company_ids=applied_company_ids,
        professor_name=professor_name)

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
    
    stats = {
        'total_applicants': len(applicants) + len(accepted) + len(rejected),
        'pending': len(applicants),
        'accepted': len(accepted),
        'rejected': len(rejected),
        'male_count': len(male_applicants) + sum(1 for a in accepted if a['gender'] == 'male') + sum(1 for a in rejected if a['gender'] == 'male'),
        'female_count': len(female_applicants) + sum(1 for a in accepted if a['gender'] == 'female') + sum(1 for a in rejected if a['gender'] == 'female'),
    }
    
    conn.close()
    
    return render_template('dashboard_company.html',
        user=user_data, company=company_data,
        male_applicants=male_applicants,
        female_applicants=female_applicants,
        accepted=[dict(a) for a in accepted],
        rejected=[dict(a) for a in rejected],
        stats=stats)

@app.route('/dashboard/supervisor')
@login_required(role='supervisor')
def dashboard_supervisor():
    user_data = get_user_data()
    if user_data and (user_data.get('account_status') or 'active') == 'suspended':
        session.clear()
        flash('تم تعليق حسابك. تواصل مع إدارة المنصة.', 'error')
        return redirect(url_for('login'))
    supervisor_data = get_supervisor_data(session['user_id'])
    
    conn = get_db_connection()
    companies = conn.execute(
        'SELECT c.*, u.name, u.department FROM companies c JOIN users u ON c.user_id = u.id'
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
    
    sections_with_students = get_supervisor_sections_with_students(supervisor_data['id'])
    sup_males, sup_females, sup_other = get_all_training_supervisors_grouped()
    assigned_students = get_assigned_students_for_supervisor(supervisor_data['id'])
    
    return render_template('dashboard_supervisor.html',
        user=user_data, supervisor=supervisor_data,
        companies=[dict(c) for c in companies],
        sections_with_students=sections_with_students,
        training_supervisors_male=sup_males,
        training_supervisors_female=sup_females,
        training_supervisors_other=sup_other,
        assigned_students=assigned_students,
        faculty_departments=FACULTY_DEPARTMENTS,
        pending_apps=pending_apps,
        accepted_apps=accepted_apps,
        rejected_apps=rejected_apps)

@app.route('/profile')
@login_required()
def profile():
    user_data = get_user_data()
    role = session.get('role')
    if role == 'admin':
        return render_template('profile_admin.html', user=user_data)
    extra_data = None
    professor_name = None
    supervisor_sections = None
    if role == 'student':
        extra_data = get_student_data(session['user_id'])
        professor_name = get_student_professor_name(extra_data)
    elif role == 'company':
        extra_data = get_company_data(session['user_id'])
    elif role == 'supervisor':
        extra_data = get_supervisor_data(session['user_id'])
        if extra_data:
            supervisor_sections = get_supervisor_sections_with_students(extra_data['id'])
    else:
        extra_data = None
    
    return render_template(
        'profile.html',
        user=user_data,
        extra=extra_data,
        professor_name=professor_name,
        supervisor_sections=supervisor_sections,
    )

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required()
def edit_profile():
    if session.get('role') == 'admin':
        flash('المدير يستخدم لوحة «إدارة المشرفين» لإدارة الحسابات', 'info')
        return redirect(url_for('admin_supervisors'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        skills = request.form.get('skills', '').strip()
        major = request.form.get('major', '').strip()
        course_name = request.form.get('course_name', '').strip()
        crn = request.form.get('crn', '').strip()
        section_code = request.form.get('section_code', '').strip()
        sup_gender = request.form.get('gender', '').strip()
        
        role = session.get('role')
        if role == 'student':
            if _value_in_list(department, FACULTY_DEPARTMENTS) is None or _value_in_list(major, FACULTY_DEPARTMENTS) is None:
                flash('يرجى اختيار القسم والتخصص من القائمة المعتمدة', 'error')
                return redirect(url_for('edit_profile'))
            if not all([course_name, crn, section_code]):
                flash('يرجى إدخال اسم المقرر والرقم المرجعي والشعبة', 'error')
                return redirect(url_for('edit_profile'))
        elif role == 'supervisor':
            if _value_in_list(department, FACULTY_DEPARTMENTS) is None:
                flash('يرجى اختيار القسم من قائمة الأقسام العلمية', 'error')
                return redirect(url_for('edit_profile'))
            if sup_gender not in ('male', 'female'):
                flash('يرجى تحديد الجنس (دكتور / دكتورة)', 'error')
                return redirect(url_for('edit_profile'))
        elif role == 'company':
            if _value_in_list(department, COLLEGE_MAJORS) is None:
                flash('يرجى اختيار الجهة (التخصص) من قائمة تخصصات الكلية', 'error')
                return redirect(url_for('edit_profile'))
        
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
        
        uid = session['user_id']
        if session.get('role') == 'supervisor':
            if avatar_file:
                conn.execute(
                    'UPDATE users SET name = ?, phone = ?, department = ?, avatar_file = ?, gender = ? WHERE id = ?',
                    (name, phone, department, avatar_file, sup_gender, uid),
                )
            else:
                conn.execute(
                    'UPDATE users SET name = ?, phone = ?, department = ?, gender = ? WHERE id = ?',
                    (name, phone, department, sup_gender, uid),
                )
        else:
            if avatar_file:
                conn.execute(
                    'UPDATE users SET name = ?, phone = ?, department = ?, avatar_file = ? WHERE id = ?',
                    (name, phone, department, avatar_file, uid),
                )
            else:
                conn.execute(
                    'UPDATE users SET name = ?, phone = ?, department = ? WHERE id = ?',
                    (name, phone, department, uid),
                )
        
        if session.get('role') == 'student':
            conn.execute(
                'UPDATE students SET skills = ?, major = ?, course_name = ?, crn = ?, section_code = ? WHERE user_id = ?',
                (skills, major, course_name, crn, section_code, session['user_id'])
            )
            if 'cv_file' in request.files and request.files['cv_file'].filename:
                file = request.files['cv_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    user = conn.execute('SELECT email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
                    unique_name = f"{user['email']}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                    conn.execute(
                        'UPDATE students SET cv_file = ? WHERE user_id = ?',
                        (unique_name, session['user_id'])
                    )
        
        if session.get('role') == 'supervisor':
            conn.execute(
                'UPDATE supervisors SET department = ? WHERE user_id = ?',
                (department, session['user_id'])
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
    
    return render_template(
        'edit_profile.html',
        user=user_data,
        extra=extra_data,
        faculty_departments=FACULTY_DEPARTMENTS,
        college_majors=COLLEGE_MAJORS,
    )

@app.route('/application/submit', methods=['POST'])
@login_required(role='student')
def submit_application():
    company_id = request.form.get('company_id', type=int)
    if not company_id:
        flash('خطأ في البيانات', 'error')
        return redirect(url_for('dashboard_student'))
    
    conn = get_db_connection()
    student = conn.execute(
        'SELECT id, cv_file FROM students WHERE user_id = ?', (session['user_id'],)
    ).fetchone()
    
    if not student:
        conn.close()
        flash('خطأ في البيانات', 'error')
        return redirect(url_for('dashboard_student'))
    
    if not student['cv_file']:
        conn.close()
        flash('يجب رفع السيرة الذاتية أولاً من صفحة تعديل البيانات', 'error')
        return redirect(url_for('dashboard_student'))
    
    company = conn.execute(
        'SELECT c.id, u.name, u.department, c.ministry, c.organization_category FROM companies c JOIN users u ON c.user_id = u.id WHERE c.id = ?',
        (company_id,)
    ).fetchone()
    
    if not company:
        conn.close()
        flash('الجهة غير موجودة', 'error')
        return redirect(url_for('dashboard_student'))
    
    student_data = get_student_data(session['user_id'])
    suitable = match_student_to_companies_ai(student_data, [dict(company)])
    if not suitable:
        conn.close()
        flash('هذه الجهة غير مناسبة لتخصصك ومهاراتك', 'error')
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
    
    flash('تم إرسال الطلب والسيرة الذاتية بنجاح للجهة المناسبة', 'success')
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
    conn = get_db_connection()
    if session.get('role') == 'student':
        student = conn.execute(
            'SELECT cv_file FROM students WHERE user_id = ?', (session['user_id'],)
        ).fetchone()
        if student and student['cv_file'] == filename:
            conn.close()
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    elif session.get('role') == 'company':
        company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session['user_id'],)).fetchone()
        if company:
            app_row = conn.execute(
                'SELECT a.id FROM applications a JOIN students s ON a.student_id = s.id WHERE s.cv_file = ? AND a.company_id = ?',
                (filename, company['id'])
            ).fetchone()
            if app_row:
                conn.close()
                return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    conn.close()
    flash('غير مصرح بتحميل هذا الملف', 'error')
    return redirect(url_for('dashboard'))

@app.route('/about')
def about():
    return render_template('about.html')


def _get_supervisor_admin_row(supervisor_pk):
    conn = get_db_connection()
    row = conn.execute(
        '''
        SELECT s.id AS supervisor_id, u.id AS user_id, u.name, u.email, u.phone, u.department, u.gender,
               COALESCE(u.account_status, 'active') AS account_status
        FROM supervisors s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = ?
        ''',
        (supervisor_pk,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


@app.route('/admin')
@login_required(role='admin')
def admin_supervisors():
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT s.id AS supervisor_id, u.id AS user_id, u.name, u.email, u.phone, u.department, u.gender,
               COALESCE(u.account_status, 'active') AS account_status
        FROM supervisors s
        JOIN users u ON u.id = s.user_id
        ORDER BY u.name
        '''
    ).fetchall()
    conn.close()
    return render_template(
        'admin_supervisors.html',
        supervisors=[dict(r) for r in rows],
        faculty_departments=FACULTY_DEPARTMENTS,
    )


@app.route('/admin/supervisors/add', methods=['POST'])
@login_required(role='admin')
def admin_supervisor_add():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', '').strip()
    gender = request.form.get('gender', '').strip()
    if not all([name, email, password, department]) or gender not in ('male', 'female'):
        flash('يرجى تعبئة جميع الحقول الإلزامية بشكل صحيح', 'error')
        return redirect(url_for('admin_supervisors'))
    if _value_in_list(department, FACULTY_DEPARTMENTS) is None:
        flash('القسم غير صالح', 'error')
        return redirect(url_for('admin_supervisors'))
    conn = get_db_connection()
    if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        conn.close()
        flash('البريد الإلكتروني مستخدم مسبقاً', 'error')
        return redirect(url_for('admin_supervisors'))
    ph = generate_password_hash(password)
    cur = conn.execute(
        '''INSERT INTO users (name, email, password, phone, role, department, gender, account_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'active')''',
        (name, email, ph, phone, 'supervisor', department, gender),
    )
    uid = cur.lastrowid
    conn.execute('INSERT INTO supervisors (user_id, department) VALUES (?, ?)', (uid, department))
    conn.commit()
    conn.close()
    flash('تم إضافة المشرف بنجاح', 'success')
    return redirect(url_for('admin_supervisors'))


@app.route('/admin/students', endpoint='admin_students')
@login_required(role='admin')
def admin_students():
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT st.id AS student_id, st.assigned_supervisor_id, u.id AS user_id, u.name, u.email, u.phone, u.department,
               st.major, st.course_name, st.crn, st.section_code, st.gender,
               COALESCE(u.account_status, 'active') AS account_status,
               sup_u.name AS assigned_supervisor_name
        FROM students st
        JOIN users u ON u.id = st.user_id
        LEFT JOIN supervisors sup ON st.assigned_supervisor_id = sup.id
        LEFT JOIN users sup_u ON sup.user_id = sup_u.id
        WHERE u.role = 'student'
        ORDER BY u.name
        '''
    ).fetchall()
    conn.close()
    return render_template(
        'admin_students.html',
        students=[dict(r) for r in rows],
        faculty_departments=FACULTY_DEPARTMENTS,
        supervisors_dd=get_supervisors_for_dropdown(),
    )


@app.route('/admin/students/add', methods=['POST'], endpoint='admin_student_add')
@login_required(role='admin')
def admin_student_add():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', '').strip()
    major = request.form.get('major', '').strip()
    course_name = request.form.get('course_name', '').strip()
    crn = request.form.get('crn', '').strip()
    section_code = request.form.get('section_code', '').strip()
    age = request.form.get('age', '').strip()
    gender = request.form.get('gender', '').strip()
    skills = request.form.get('skills', '').strip()
    assign_raw = request.form.get('assigned_supervisor_id', '').strip()
    assigned_sid = None
    if assign_raw.isdigit():
        assigned_sid = int(assign_raw)
    if not all([name, email, password, course_name, crn, section_code]):
        flash('يرجى تعبئة الاسم والبريد وكلمة المرور والمقرر والرقم المرجعي والشعبة', 'error')
        return redirect(url_for('admin_students'))
    if _value_in_list(department, FACULTY_DEPARTMENTS) is None or _value_in_list(major, FACULTY_DEPARTMENTS) is None:
        flash('يرجى اختيار القسم والتخصص من القائمة المعتمدة', 'error')
        return redirect(url_for('admin_students'))
    conn = get_db_connection()
    if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        conn.close()
        flash('البريد الإلكتروني مستخدم مسبقاً', 'error')
        return redirect(url_for('admin_students'))
    if assigned_sid is not None and not conn.execute(
        'SELECT id FROM supervisors WHERE id = ?', (assigned_sid,)
    ).fetchone():
        assigned_sid = None
    ph = generate_password_hash(password)
    cur = conn.execute(
        '''INSERT INTO users (name, email, password, phone, role, department, account_status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')''',
        (name, email, ph, phone, 'student', department),
    )
    uid = cur.lastrowid
    g = gender if gender in ('male', 'female') else None
    _insert_student_row(
        conn,
        uid,
        g,
        major,
        int(age) if age.isdigit() else None,
        skills,
        '',
        course_name,
        crn,
        section_code,
        assigned_sid,
    )
    conn.commit()
    conn.close()
    flash('تم إضافة الطالب بنجاح', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/students/<int:student_pk>/assign', methods=['POST'], endpoint='admin_student_assign')
@login_required(role='admin')
def admin_student_assign(student_pk):
    sup_raw = request.form.get('supervisor_id', '').strip()
    conn = get_db_connection()
    st = conn.execute('SELECT id FROM students WHERE id = ?', (student_pk,)).fetchone()
    if not st:
        conn.close()
        flash('الطالب غير موجود', 'error')
        return redirect(url_for('admin_students'))
    if sup_raw == '' or sup_raw == '0':
        conn.execute('UPDATE students SET assigned_supervisor_id = NULL WHERE id = ?', (student_pk,))
        conn.commit()
        conn.close()
        flash('تم إلغاء إسناد المشرف', 'success')
        return redirect(url_for('admin_students'))
    if sup_raw.isdigit():
        sid = int(sup_raw)
        if conn.execute('SELECT id FROM supervisors WHERE id = ?', (sid,)).fetchone():
            conn.execute(
                'UPDATE students SET assigned_supervisor_id = ? WHERE id = ?',
                (sid, student_pk),
            )
            conn.commit()
            conn.close()
            flash('تم تحديث إسناد المشرف', 'success')
            return redirect(url_for('admin_students'))
    conn.close()
    flash('مشرف غير صالح', 'error')
    return redirect(url_for('admin_students'))


@app.route('/admin/users', endpoint='admin_users')
@login_required(role='admin')
def admin_users():
    conn = get_db_connection()
    rows = conn.execute(
        '''
        SELECT id, name, email, phone, role, department,
               COALESCE(account_status, 'active') AS account_status
        FROM users
        ORDER BY role, name
        '''
    ).fetchall()
    conn.close()
    return render_template('admin_users.html', users=[dict(r) for r in rows])


@app.route('/supervisor/students/add', methods=['POST'], endpoint='supervisor_add_student')
@login_required(role='supervisor')
def supervisor_add_student():
    user_data = get_user_data()
    if user_data and (user_data.get('account_status') or 'active') == 'suspended':
        session.clear()
        flash('تم تعليق حسابك.', 'error')
        return redirect(url_for('login'))
    sup = get_supervisor_data(session['user_id'])
    if not sup:
        flash('خطأ في بيانات المشرف', 'error')
        return redirect(url_for('dashboard_supervisor'))
    supervisor_pk = sup['id']
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', '').strip()
    major = request.form.get('major', '').strip()
    course_name = request.form.get('course_name', '').strip()
    crn = request.form.get('crn', '').strip()
    section_code = request.form.get('section_code', '').strip()
    age = request.form.get('age', '').strip()
    gender = request.form.get('gender', '').strip()
    skills = request.form.get('skills', '').strip()
    if not all([name, email, password, course_name, crn, section_code]):
        flash('يرجى تعبئة الحقول الإلزامية', 'error')
        return redirect(url_for('dashboard_supervisor'))
    if _value_in_list(department, FACULTY_DEPARTMENTS) is None or _value_in_list(major, FACULTY_DEPARTMENTS) is None:
        flash('يرجى اختيار القسم والتخصص من القائمة', 'error')
        return redirect(url_for('dashboard_supervisor'))
    conn = get_db_connection()
    if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        conn.close()
        flash('البريد مستخدم مسبقاً', 'error')
        return redirect(url_for('dashboard_supervisor'))
    ph = generate_password_hash(password)
    cur = conn.execute(
        '''INSERT INTO users (name, email, password, phone, role, department, account_status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')''',
        (name, email, ph, phone, 'student', department),
    )
    uid = cur.lastrowid
    g = gender if gender in ('male', 'female') else None
    _insert_student_row(
        conn,
        uid,
        g,
        major,
        int(age) if age.isdigit() else None,
        skills,
        '',
        course_name,
        crn,
        section_code,
        supervisor_pk,
    )
    conn.commit()
    conn.close()
    flash('تم إضافة الطالب وربطه بحسابك كمشرف', 'success')
    return redirect(url_for('dashboard_supervisor'))


@app.route('/admin/supervisor/<int:supervisor_pk>')
@login_required(role='admin')
def admin_supervisor_detail(supervisor_pk):
    sup = _get_supervisor_admin_row(supervisor_pk)
    if not sup:
        flash('المشرف غير موجود', 'error')
        return redirect(url_for('admin_supervisors'))
    sections = get_supervisor_sections_with_students(supervisor_pk)
    assigned_students = get_assigned_students_for_supervisor(supervisor_pk)
    return render_template(
        'admin_supervisor_detail.html',
        sup=sup,
        sections_with_students=sections,
        assigned_students=assigned_students,
        faculty_departments=FACULTY_DEPARTMENTS,
    )


@app.route('/admin/supervisor/<int:supervisor_pk>/update', methods=['POST'])
@login_required(role='admin')
def admin_supervisor_update(supervisor_pk):
    row = _get_supervisor_admin_row(supervisor_pk)
    if not row:
        flash('المشرف غير موجود', 'error')
        return redirect(url_for('admin_supervisors'))
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', '').strip()
    gender = request.form.get('gender', '').strip()
    new_password = request.form.get('new_password', '').strip()
    if not all([name, email, department]) or gender not in ('male', 'female'):
        flash('يرجى التحقق من الحقول', 'error')
        return redirect(url_for('admin_supervisor_detail', supervisor_pk=supervisor_pk))
    if _value_in_list(department, FACULTY_DEPARTMENTS) is None:
        flash('القسم غير صالح', 'error')
        return redirect(url_for('admin_supervisor_detail', supervisor_pk=supervisor_pk))
    uid = row['user_id']
    conn = get_db_connection()
    other = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?', (email, uid)).fetchone()
    if other:
        conn.close()
        flash('البريد الإلكتروني مستخدم لحساب آخر', 'error')
        return redirect(url_for('admin_supervisor_detail', supervisor_pk=supervisor_pk))
    conn.execute(
        'UPDATE users SET name = ?, email = ?, phone = ?, department = ?, gender = ? WHERE id = ?',
        (name, email, phone, department, gender, uid),
    )
    conn.execute(
        'UPDATE supervisors SET department = ? WHERE id = ?',
        (department, supervisor_pk),
    )
    if new_password:
        conn.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (generate_password_hash(new_password), uid),
        )
    conn.commit()
    conn.close()
    flash('تم حفظ بيانات المشرف', 'success')
    return redirect(url_for('admin_supervisor_detail', supervisor_pk=supervisor_pk))


@app.route('/admin/supervisor/<int:supervisor_pk>/suspend', methods=['POST'])
@login_required(role='admin')
def admin_supervisor_suspend(supervisor_pk):
    row = _get_supervisor_admin_row(supervisor_pk)
    if not row:
        flash('المشرف غير موجود', 'error')
        return redirect(url_for('admin_supervisors'))
    cur = row['account_status'] or 'active'
    new_status = 'active' if cur == 'suspended' else 'suspended'
    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET account_status = ? WHERE id = ?',
        (new_status, row['user_id']),
    )
    conn.commit()
    conn.close()
    flash('تم تعليق الحساب' if new_status == 'suspended' else 'تم تفعيل الحساب', 'success')
    return redirect(url_for('admin_supervisor_detail', supervisor_pk=supervisor_pk))


@app.route('/admin/supervisor/<int:supervisor_pk>/delete', methods=['POST'])
@login_required(role='admin')
def admin_supervisor_delete(supervisor_pk):
    row = _get_supervisor_admin_row(supervisor_pk)
    if not row:
        flash('المشرف غير موجود', 'error')
        return redirect(url_for('admin_supervisors'))
    conn = get_db_connection()
    conn.execute(
        'UPDATE students SET assigned_supervisor_id = NULL WHERE assigned_supervisor_id = ?',
        (supervisor_pk,),
    )
    conn.execute('DELETE FROM users WHERE id = ?', (row['user_id'],))
    conn.commit()
    conn.close()
    flash('تم حذف المشرف وحسابه نهائياً', 'info')
    return redirect(url_for('admin_supervisors'))


@app.route('/supervisor/section/add', methods=['POST'])
@login_required(role='supervisor')
def add_supervisor_section():
    course_name = request.form.get('course_name', '').strip()
    crn = request.form.get('crn', '').strip()
    section_code = request.form.get('section_code', '').strip()
    if not all([course_name, crn, section_code]):
        flash('يرجى إدخال اسم المقرر والرقم المرجعي ورمز الشعبة', 'error')
        return redirect(url_for('dashboard_supervisor'))
    conn = get_db_connection()
    sup = conn.execute(
        'SELECT id FROM supervisors WHERE user_id = ?', (session['user_id'],)
    ).fetchone()
    if not sup:
        conn.close()
        flash('خطأ في بيانات المشرف', 'error')
        return redirect(url_for('dashboard_supervisor'))
    try:
        conn.execute(
            'INSERT INTO supervisor_sections (supervisor_id, course_name, crn, section_code) VALUES (?, ?, ?, ?)',
            (sup['id'], course_name, crn, section_code),
        )
        conn.commit()
        flash('تمت إضافة الشعبة والرقم المرجعي. ستظهر الطلاب الذين يطابقون نفس الرقم والشعبة.', 'success')
    except sqlite3.IntegrityError:
        conn.rollback()
        flash('هذه الشعبة والرقم المرجعي مسجّلان مسبقاً لحسابك', 'error')
    conn.close()
    return redirect(url_for('dashboard_supervisor'))


@app.route('/supervisor/section/<int:sec_id>/delete', methods=['POST'])
@login_required(role='supervisor')
def delete_supervisor_section(sec_id):
    conn = get_db_connection()
    sup = conn.execute(
        'SELECT id FROM supervisors WHERE user_id = ?', (session['user_id'],)
    ).fetchone()
    if sup:
        conn.execute(
            'DELETE FROM supervisor_sections WHERE id = ? AND supervisor_id = ?',
            (sec_id, sup['id']),
        )
        conn.commit()
        flash('تم حذف السجل', 'info')
    conn.close()
    return redirect(url_for('dashboard_supervisor'))


if __name__ == '__main__':
    init_db()
    seed_default_users(generate_password_hash)
    app.run(host='127.0.0.1', port=5000, debug=True)
