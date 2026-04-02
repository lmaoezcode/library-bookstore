import base64
from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Vui lòng đăng nhập để tiếp tục!", "warning")

            # BƯỚC 1: Lấy URL hiện tại mà khách đang đứng
            current_url = request.url

            # BƯỚC 2: Mã hóa Base64 dạng URL-Safe (Thay + / bằng - _)
            # encode('utf-8') để sang Bytes -> b64encode để mã hóa -> decode('utf-8') để lại String cho URL
            next_encoded = base64.urlsafe_b64encode(current_url.encode('utf-8')).decode('utf-8')

            # BƯỚC 3: Đẩy sang trang login kèm theo "mảnh giấy ghi chú" đã mã hóa
            return redirect(url_for('auth.login', next=next_encoded))

        return f(*args, **kwargs)

    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check đăng nhập
        if 'user_id' not in session:
            return jsonify({"status": "error", "message": "Vui lòng đăng nhập"}), 401

        # 2. Check quyền Admin (trong Session)
        if session.get('role') != 'admin':
            return jsonify({"status": "error", "message": "Chỉ Admin mới có quyền này"}), 403

        return f(*args, **kwargs)

    return decorated_function