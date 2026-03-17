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
    conn.commit()
    conn.close()

def seed_default_users(password_hash_fn):
    conn = get_db_connection()
    cursor = conn.cursor()
    default_password = password_hash_fn('123456')
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('student@tawun.com',)).fetchone():
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('أحمد الطالب', 'student@tawun.com', default_password, '0501234567', 'student', 'علوم الحاسب')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO students (user_id, gender, major, age, skills) VALUES (?, ?, ?, ?, ?)',
            (user_id, 'male', 'هندسة البرمجيات', 22, 'Python, JavaScript, SQL')
        )
    
    company_user = cursor.execute('SELECT id FROM users WHERE email = ?', ('company@tawun.com',)).fetchone()
    if not company_user:
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('شركة/جهة حكومية التدريبية', 'company@tawun.com', default_password, '0507654321', 'company', 'علوم الحاسب')
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
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('د. محمد المشرف', 'supervisor@tawun.com', default_password, '', 'supervisor', 'علوم الحاسب')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO supervisors (user_id, department) VALUES (?, ?)',
            (user_id, 'علوم الحاسب')
        )
    
    seed_default_applicants(cursor, password_hash_fn)
    
    conn.commit()
    conn.close()


def seed_default_applicants(cursor, password_hash_fn):
    company_user = cursor.execute('SELECT id FROM users WHERE email = ?', ('company@tawun.com',)).fetchone()
    if not company_user:
        return
    company_row = cursor.execute('SELECT id FROM companies WHERE user_id = ?', (company_user['id'],)).fetchone()
    if not company_row:
        return
    company_id = company_row['id']
    
    extra_students = [
        ('سارة أحمد', 'sara@tawun.com', '0501112233', 'female', 'نظم المعلومات', 21, 'Excel, تحليل البيانات'),
        ('خالد العتيبي', 'khalid@tawun.com', '0502223344', 'male', 'هندسة الحاسب', 23, 'Java, Python, DevOps'),
        ('نورة السعيد', 'noura@tawun.com', '0503334455', 'female', 'علوم الحاسب', 20, 'Web Development, React'),
        ('عمر الشمري', 'omar@tawun.com', '0504445566', 'male', 'تقنية المعلومات', 22, 'Networking, أمن المعلومات'),
        ('فاطمة القحطاني', 'fatima@tawun.com', '0505556677', 'female', 'هندسة البرمجيات', 21, 'UI/UX, Figma'),
    ]
    
    statuses = ['pending', 'pending', 'accepted', 'accepted', 'rejected']
    for i, (name, email, phone, gender, major, age, skills) in enumerate(extra_students):
        if not cursor.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            cursor.execute(
                'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, password_hash_fn('123456'), phone, 'student', major)
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
