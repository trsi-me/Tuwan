# منصة تعاون - نظام تنظيم التدريب التعاوني الجامعي

## 1. شرح فكرة المشروع

منصة تعاون هي نظام ويب جامعي يربط بين ثلاثة أطراف رئيسية في عملية التدريب التعاوني: الطلاب الجامعيين، والجهات الحكومية والخاصة المستضيفة للتدريب، والمشرفين الأكاديميين. تهدف المنصة إلى تنظيم عملية التنسيق بين هذه الأطراف وتسهيل إدارة طلبات التدريب ومتابعة حالاتها.

## 2. المشكلة التي يحلها المشروع

- **تشتت التنسيق**: عدم وجود قناة موحدة للتواصل بين الطلاب والجهات والمشرفين.
- **صعوبة المتابعة**: صعوبة تتبع حالة طلبات التدريب لكل طالب.
- **إدارة الملفات**: حاجة الطلاب لرفع السير الذاتية وتخزينها بشكل منظم.
- **الفصل بين الأدوار**: كل طرف يحتاج لوحة تحكم خاصة بمهامه (الطالب، الجهة، المشرف).

## 3. الفئة المستهدفة

- **الطلاب**: طلاب الجامعة المسجلون في برنامج التدريب التعاوني.
- **الجهات**: المؤسسات الحكومية والخاصة التي تستقبل متدربين.
- **المشرفون الأكاديميون**: أعضاء هيئة التدريس المشرفون على برامج التدريب.

## 4. التقنيات المستخدمة

| الطبقة | التقنية |
|--------|---------|
| الواجهة الأمامية | HTML, CSS, JavaScript |
| الواجهة الخلفية | Python, Flask |
| قاعدة البيانات | SQLite |
| الخط | IBM Plex Sans Arabic |

## 5. هيكل المشروع

```
Tawun
│
├── app.py                 # التطبيق الرئيسي ومسارات Flask
├── config.py              # إعدادات المشروع
├── database.py            # تهيئة قاعدة البيانات
├── requirements.txt       # متطلبات Python
│
├── database
│   └── database.db        # قاعدة بيانات SQLite
│
├── templates              # قوالب HTML
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register_student.html
│   ├── register_company.html
│   ├── register_supervisor.html
│   ├── dashboard_student.html
│   ├── dashboard_company.html
│   ├── dashboard_supervisor.html
│   ├── profile.html
│   ├── edit_profile.html
│   └── about.html
│
├── static
│   ├── css/style.css
│   ├── js/main.js
│   ├── images
│   └── uploads/cv         # السير الذاتية المرفوعة
│
└── assets
    ├── fonts              # خط IBM Plex Sans Arabic
    └── images             # الشعار Logo.png
```

## 6. شرح قاعدة البيانات

### جدول users
يخزن بيانات المستخدمين الأساسية لجميع الأدوار.

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | INTEGER | المفتاح الأساسي |
| name | TEXT | الاسم |
| email | TEXT | البريد الإلكتروني (فريد) |
| password | TEXT | كلمة المرور مشفرة |
| phone | TEXT | رقم الجوال |
| role | TEXT | الدور: student, company, supervisor |
| department | TEXT | القسم |
| created_at | TIMESTAMP | تاريخ الإنشاء |

### جدول students
بيانات إضافية للطلاب.

| العمود | النوع | الوصف |
|--------|-------|-------|
| user_id | INTEGER | مفتاح خارجي لـ users |
| gender | TEXT | الجنس |
| major | TEXT | التخصص |
| age | INTEGER | العمر |
| skills | TEXT | المهارات |
| cv_file | TEXT | اسم ملف السيرة الذاتية |

### جدول companies
بيانات إضافية للجهات.

| العمود | النوع | الوصف |
|--------|-------|-------|
| user_id | INTEGER | مفتاح خارجي لـ users |
| organization_type | TEXT | نوع الجهة (حكومية/خاصة) |
| organization_category | TEXT | تصنيف الجهة |

### جدول supervisors
بيانات إضافية للمشرفين.

| العمود | النوع | الوصف |
|--------|-------|-------|
| user_id | INTEGER | مفتاح خارجي لـ users |
| department | TEXT | القسم |

### جدول applications
طلبات التدريب المقدمة من الطلاب للجهات.

| العمود | النوع | الوصف |
|--------|-------|-------|
| id | INTEGER | المفتاح الأساسي |
| student_id | INTEGER | مفتاح خارجي لـ students |
| company_id | INTEGER | مفتاح خارجي لـ companies |
| status | TEXT | pending, accepted, rejected |
| created_at | TIMESTAMP | تاريخ التقديم |

## 7. شرح الخوارزميات

### نظام المصادقة
- **التسجيل**: تشفير كلمة المرور باستخدام `werkzeug.security.generate_password_hash` (طريقة pbkdf2).
- **تسجيل الدخول**: التحقق من البريد وكلمة المرور ثم إنشاء جلسة (session) تحتوي على `user_id` و `role`.
- **حماية الصفحات**: ديكوراتور `@login_required(role=None)` يتحقق من وجود الجلسة ونوع المستخدم قبل السماح بالوصول.

### رفع الملفات
- التحقق من الامتداد (pdf, doc, docx) والحد الأقصى 5 ميجابايت.
- تسمية الملف بـ `email_filename` لتجنب التكرار.
- تخزين الملفات في `static/uploads/cv/`.

### تدفق الطلبات
1. الطالب يقدم طلباً لجهة من لوحة التحكم.
2. يتم إدراج سجل في `applications` بحالة `pending`.
3. الجهة تعرض المتقدمين ويمكنها قبول أو رفض كل طلب.
4. عند القبول/الرفض يتم تحديث `status` في الجدول.

## 8. كيفية تشغيل المشروع

### 9. تنصيب المتطلبات

```bash
pip install -r requirements.txt
```

### 10. تشغيل Flask

```bash
python app.py
```

### 11. ربط قاعدة البيانات

يتم إنشاء قاعدة البيانات تلقائياً عند أول تشغيل للتطبيق عبر استدعاء `init_db()` في نهاية ملف `app.py`. الملف `database/database.db` يُنشأ تلقائياً ولا يحتاج إعداد يدوي.

### الوصول للمنصة

افتح المتصفح على:

```
http://127.0.0.1:5000
```

### الحسابات التجريبية

كلمة المرور لجميع الحسابات: `123456`

| الدور | البريد الإلكتروني |
|-------|-------------------|
| طالب | student@tawun.com |
| جهة حكومية | company@tawun.com |
| مشرف أكاديمي | supervisor@tawun.com |

## 12. شرح تدفق النظام

1. **الزائر** يفتح الصفحة الرئيسية ويمكنه تسجيل الدخول أو إنشاء حساب.
2. **إنشاء الحساب**: اختيار نوع الحساب (طالب/جهة/مشرف) ثم تعبئة النموذج المناسب.
3. **تسجيل الدخول**: إدخال البريد وكلمة المرور، ثم التوجيه للوحة التحكم حسب الدور.
4. **الطالب**: يعرض بياناته، السيرة، المهارات، قائمة الجهات للتقديم، وحالة طلباته.
5. **الجهة**: تعرض المتقدمين (ذكور/إناث)، المقبولين، المرفوضين، مع إمكانية القبول والرفض والتواصل.
6. **المشرف**: يعرض الجهات، المتدربين، وطلبات التدريب بحالاتها.

## 13. شرح أهم الأكواد

### ديكوراتور حماية الصفحات (app.py)

```python
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
```

يضمن أن المستخدم مسجل وأن دوره مطابق للصفحة المطلوبة.

### تهيئة قاعدة البيانات (database.py)

```python
def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (...)''')
    # ... باقي الجداول
    conn.commit()
    conn.close()
```

ينشئ مجلد قاعدة البيانات والجداول عند عدم وجودها.

### رفع السيرة الذاتية (app.py)

```python
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# في تسجيل الطالب:
if 'cv_file' in request.files and request.files['cv_file'].filename:
    file = request.files['cv_file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = f"{email}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
        cv_file = unique_name
```

يتحقق من نوع الملف ويحفظه باسم فريد مرتبط بالبريد.
