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
    
    # جدول المستخدمين
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
    
    # جدول الطلاب
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
    
    # جدول الجهات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            organization_type TEXT,
            organization_category TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # جدول المشرفين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            department TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # جدول الطلبات
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
    
    if not cursor.execute('SELECT id FROM users WHERE email = ?', ('company@tawun.com',)).fetchone():
        cursor.execute(
            'INSERT INTO users (name, email, password, phone, role, department) VALUES (?, ?, ?, ?, ?, ?)',
            ('شركة التدريب', 'company@tawun.com', default_password, '0507654321', 'company', 'علوم الحاسب')
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO companies (user_id, organization_type, organization_category) VALUES (?, ?, ?)',
            (user_id, 'government', 'وزارة')
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
    
    conn.commit()
    conn.close()
