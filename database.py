# -*- coding: utf-8 -*-

import sqlite3
import os
from config import DATABASE_PATH

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            gender TEXT,
            major TEXT,
            age INTEGER,
            skills TEXT,
            cv_file TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            organization_type TEXT,
            organization_category TEXT,
            ministry TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    try:
        cursor.execute('ALTER TABLE companies ADD COLUMN ministry TEXT')
    except sqlite3.OperationalError:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            department TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN avatar_file TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN gender TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'active'"
        )
    except sqlite3.OperationalError:
        pass
    
    _migrate_schema(cursor)
    conn.commit()
    conn.close()


def _migrate_schema(cursor):
    """ترقية المخطط: مقرر، رقم مرجعي، شعبة، وجدول شُعب المشرفين."""
    for table, col, coltype in [
        ('students', 'course_name', 'TEXT'),
        ('students', 'crn', 'TEXT'),
        ('students', 'section_code', 'TEXT'),
    ]:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {coltype}')
        except sqlite3.OperationalError:
            pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supervisor_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_id INTEGER NOT NULL,
            course_name TEXT NOT NULL,
            crn TEXT NOT NULL,
            section_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id) ON DELETE CASCADE,
            UNIQUE (supervisor_id, crn, section_code)
        )
    ''')
    try:
        cursor.execute('ALTER TABLE students ADD COLUMN assigned_supervisor_id INTEGER')
    except sqlite3.OperationalError:
        pass

def seed_default_users(password_hash_fn):
    conn = get_db_connection()
    cursor = conn.cursor()
    default_password = password_hash_fn('123456')
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('student@tawun.com',)).fetchone():
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('أحمد الطالب', 'student@tawun.com', default_password, '0501234567', 'student', 'صحافة و الاعلام الرقمي')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO students (user_id, gender, major, age, skills, course_name, crn, section_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (user_id, 'male', 'صحافة و الاعلام الرقمي', 22, 'كتابة صحفية، وسائل التواصل', 'مقدمة في الصحافة الرقمية', 'CS101', '01')
        )
    
    company_user = cursor.execute('SELECT id FROM users WHERE email = ?', ('company@tawun.com',)).fetchone()
    if not company_user:
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('شركة/جهة حكومية التدريبية', 'company@tawun.com', default_password, '0507654321', 'company', 'صحافة و الاعلام الرقمي')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO companies (user_id, organization_type, organization_category, ministry) VALUES (?, ?, ?, ?)',
            (user_id, 'government', 'شركة/جهة حكومية', 'وزارة التعليم')
        )
    else:
        cursor.execute(
            'UPDATE users SET name = ? WHERE email = ?',
            ('شركة/جهة حكومية التدريبية', 'company@tawun.com')
        )
        cursor.execute(
            'UPDATE companies SET organization_category = ?, ministry = ? WHERE user_id = ?',
            ('شركة/جهة حكومية', 'وزارة التعليم', company_user['id'])
        )
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('supervisor@tawun.com',)).fetchone():
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department, gender) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('د. محمد المشرف', 'supervisor@tawun.com', default_password, '', 'supervisor', 'صحافة و الاعلام الرقمي', 'male')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO supervisors (user_id, department) VALUES (?, ?)',
            (user_id, 'صحافة و الاعلام الرقمي')
        )
        sup_row = cursor.execute('SELECT id FROM supervisors WHERE user_id = ?', (user_id,)).fetchone()
        if sup_row:
            cursor.execute(
                '''INSERT INTO supervisor_sections (supervisor_id, course_name, crn, section_code)
                   VALUES (?, ?, ?, ?)''',
                (sup_row['id'], 'مقدمة في الصحافة الرقمية', 'CS101', '01')
            )
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('supervisor2@tawun.com',)).fetchone():
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department, gender) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('د. رانية المشرفة', 'supervisor2@tawun.com', default_password, '', 'supervisor', 'علاقات عامة', 'female')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO supervisors (user_id, department) VALUES (?, ?)',
            (user_id, 'علاقات عامة')
        )
    
    seed_default_applicants(cursor, password_hash_fn)
    _ensure_demo_section_links(cursor)
    cursor.execute(
        """UPDATE users SET gender = 'male' WHERE role = 'supervisor' AND email = 'supervisor@tawun.com'
           AND (gender IS NULL OR TRIM(gender) = '')"""
    )
    cursor.execute(
        """UPDATE users SET gender = 'female' WHERE role = 'supervisor' AND email = 'supervisor2@tawun.com'
           AND (gender IS NULL OR TRIM(gender) = '')"""
    )
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('admin@tawun.com',)).fetchone():
        cursor.execute(
            '''INSERT INTO users (name, email, password, phone, role, department, account_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            ('مدير النظام', 'admin@tawun.com', default_password, '', 'admin', 'إدارة', 'active'),
        )
    else:
        cursor.execute(
            "UPDATE users SET account_status = 'active' WHERE email = 'admin@tawun.com' AND (account_status IS NULL OR account_status = '')"
        )
    
    cursor.execute(
        "UPDATE users SET account_status = 'active' WHERE account_status IS NULL OR TRIM(account_status) = ''"
    )
    
    conn.commit()
    conn.close()


def _ensure_demo_section_links(cursor):
    """ربط تجريبي: مشرف افتراضي + شعبة + طالب أحمد بنفس الرقم المرجعي والشعبة."""
    sup_u = cursor.execute(
        'SELECT u.id FROM users u WHERE u.email = ?', ('supervisor@tawun.com',)
    ).fetchone()
    if not sup_u:
        return
    sup = cursor.execute(
        'SELECT id FROM supervisors WHERE user_id = ?', (sup_u['id'],)
    ).fetchone()
    if not sup:
        return
    if not cursor.execute(
        'SELECT id FROM supervisor_sections WHERE supervisor_id = ? AND crn = ? AND section_code = ?',
        (sup['id'], 'CS101', '01'),
    ).fetchone():
        cursor.execute(
            '''INSERT INTO supervisor_sections (supervisor_id, course_name, crn, section_code)
               VALUES (?, ?, ?, ?)''',
            (sup['id'], 'مقدمة في الصحافة الرقمية', 'CS101', '01'),
        )
    stu_u = cursor.execute(
        'SELECT id FROM users WHERE email = ?', ('student@tawun.com',)
    ).fetchone()
    if stu_u:
        cursor.execute(
            '''UPDATE students SET
               course_name = COALESCE(NULLIF(TRIM(course_name), ''), ?),
               crn = COALESCE(NULLIF(TRIM(crn), ''), ?),
               section_code = COALESCE(NULLIF(TRIM(section_code), ''), ?)
               WHERE user_id = ?''',
            ('مقدمة في الصحافة الرقمية', 'CS101', '01', stu_u['id']),
        )


def seed_default_applicants(cursor, password_hash_fn):
    company_user = cursor.execute('SELECT id FROM users WHERE email = ?', ('company@tawun.com',)).fetchone()
    if not company_user:
        return
    company_row = cursor.execute('SELECT id FROM companies WHERE user_id = ?', (company_user['id'],)).fetchone()
    if not company_row:
        return
    company_id = company_row['id']
    
    extra_students = [
        ('سارة أحمد', 'sara@tawun.com', '0501112233', 'female', 'انتاج المرئي و المسموع', 'انتاج المرئي و المسموع', 21, 'مونتاج، تصوير'),
        ('خالد العتيبي', 'khalid@tawun.com', '0502223344', 'male', 'الاتصال التسويقي', 'الاتصال التسويقي', 23, 'حملات، محتوى'),
        ('نورة السعيد', 'noura@tawun.com', '0503334455', 'female', 'علاقات عامة', 'علاقات عامة', 20, 'فعاليات، تواصل'),
        ('عمر الشمري', 'omar@tawun.com', '0504445566', 'male', 'صحافة و الاعلام الرقمي', 'صحافة و الاعلام الرقمي', 22, 'صحافة، تحرير'),
        ('فاطمة القحطاني', 'fatima@tawun.com', '0505556677', 'female', 'انتاج المرئي و المسموع', 'انتاج المرئي و المسموع', 21, 'إخراج، صوت'),
    ]
    
    statuses = ['pending', 'pending', 'accepted', 'accepted', 'rejected']
    for i, (name, email, phone, gender, department, major, age, skills) in enumerate(extra_students):
        if not cursor.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            cursor.execute(
                'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, password_hash_fn('123456'), phone, 'student', department)
            )
            user_id = cursor.lastrowid
            cursor.execute(
                'INSERT INTO students (user_id, gender, major, age, skills) VALUES (?, ?, ?, ?, ?)',
                (user_id, gender, major, age, skills)
            )
            student_id = cursor.lastrowid
            status = statuses[i % len(statuses)]
            cursor.execute(
                'INSERT INTO applications (student_id, company_id, status) VALUES (?, ?, ?)',
                (student_id, company_id, status)
            )
    
    ahmed = cursor.execute('SELECT id FROM users WHERE email = ?', ('student@tawun.com',)).fetchone()
    if ahmed:
        student_row = cursor.execute('SELECT id FROM students WHERE user_id = ?', (ahmed['id'],)).fetchone()
        if student_row:
            existing = cursor.execute(
                'SELECT id FROM applications WHERE student_id = ? AND company_id = ?',
                (student_row['id'], company_id)
            ).fetchone()
            if not existing:
                cursor.execute(
                    'INSERT INTO applications (student_id, company_id, status) VALUES (?, ?, ?)',
                    (student_row['id'], company_id, 'pending')
                )
