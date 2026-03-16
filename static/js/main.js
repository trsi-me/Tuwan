/**
 * منصة تعاون - السكربت الرئيسي
 */

document.addEventListener('DOMContentLoaded', function() {
    var navToggle = document.getElementById('navToggle');
    var navLinks = document.getElementById('navLinks');
    if (navToggle && navLinks) {
        navToggle.addEventListener('click', function() {
            navLinks.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', navLinks.classList.contains('active'));
        });
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 576 && navLinks.classList.contains('active') && !navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            }
        });
    }
    // إخفاء التنبيهات تلقائياً بعد 5 ثوان
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // التحقق من صحة الملفات المرفوعة
    const fileInputs = document.querySelectorAll('input[type="file"][accept]');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const allowedTypes = input.getAttribute('accept').split(',').map(s => s.trim().replace('.', ''));
                const ext = file.name.split('.').pop().toLowerCase();
                if (!allowedTypes.includes(ext)) {
                    alert('نوع الملف غير مسموح. الملفات المسموحة: ' + input.getAttribute('accept'));
                    this.value = '';
                }
                var maxSize = input.name === 'avatar_file' ? 2 * 1024 * 1024 : 5 * 1024 * 1024;
                if (file.size > maxSize) {
                    alert(input.name === 'avatar_file' ? 'حجم الصورة يتجاوز 2 ميجابايت' : 'حجم الملف يتجاوز 5 ميجابايت');
                    this.value = '';
                }
            }
        });
    });
});
