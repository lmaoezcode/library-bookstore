import base64
from datetime import timedelta

from flask import request, render_template, session, redirect, url_for, flash, current_app
import sqlite3
from . import auth_bp
from werkzeug.security import generate_password_hash, check_password_hash


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        confirmation = request.form.get('confirmation')
        if not confirmation:
            error = "Please agree with Term and Condition!"
            return render_template('register.html', error=error)
        db = get_db()
        result=db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if result:
            error="Email already exists!"
        else:
            hashed_password = generate_password_hash(password)
            db.execute('INSERT INTO users (email, password,name) VALUES (?, ?,?)',(email, hashed_password,name))
            db.commit()
            return redirect(url_for('admin.login'))
        return render_template('register.html', error=error)

    return render_template('register.html')
def get_db():
    conn = sqlite3.connect('db/library.sqlite')
    conn.row_factory=sqlite3.Row
    return conn

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        db = get_db()
        user= db.execute('SELECT * FROM users WHERE email = ? AND role="user"', (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session['logged_in'] = True
            session['user_id']= user["id"]
            flash("Đăng nhập thành công!", "success")
            if remember:
                # Nếu tích vào Remember: Session tồn tại lâu (ví dụ 30 ngày)
                session.permanent = True

            else:
                # Nếu không tích: Session mất khi đóng trình duyệt
                session.permanent = False
            next_encoded = request.args.get('next')
            target_url = url_for('index')  # Mặc định về trang chủ
            if next_encoded:
                try:
                    # Giải mã ngược lại
                    decoded_bytes = base64.urlsafe_b64decode(next_encoded)
                    target_url = decoded_bytes.decode('utf-8')

                    # BẢO MẬT: Chỉ redirect nếu là link nội bộ (tránh Open Redirect)
                    if not target_url.startswith(request.host_url):
                        target_url = url_for('index')

                except Exception:
                    # Nếu chuỗi Base64 lỗi, cứ cho về trang chủ cho an toàn
                    target_url = url_for('index')
            return redirect(target_url)
        else:
            error = "Sai email hoặc mật khẩu!"
    return render_template('login.html',error=error)
@auth_bp.route('/logout')
def logout():
    session.clear() # Xóa sạch session
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for('auth.login'))