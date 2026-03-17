# -*- coding: utf-8 -*-

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

SECRET_KEY = os.environ.get('SECRET_KEY', 'tawun-secret-key-2026')
DEBUG = True
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'cv')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
AVATAR_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
ALLOWED_AVATAR_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
