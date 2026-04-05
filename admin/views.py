from flask import request, render_template, session, redirect, url_for, flash, jsonify
import sqlite3
from . import admin_bp
from db.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
from borrow.views import format_borrow_code

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        db = get_db()
        user= db.execute('SELECT * FROM users WHERE email = ? AND role="admin"', (email,)).fetchone()
        if user and (check_password_hash(user["password"], password) or user["password"] == password):
            session['logged_in'] = True
            session['user_id']= user["id"]
            session["role"]=user["role"]
            flash("Đăng nhập thành công!", "success")
            return "Logged in"
        else:
            error = "Sai email hoặc mật khẩu!"
    return render_template('admin-login.html',error=error)


@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    db = get_db()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            b.id,
            b.title,
            b.author,
            b.price,
            b.cover_image AS image,
            b.category_id AS category,
            COALESCE(c.name, 'Chưa phân loại') AS category_name
        FROM books b
        LEFT JOIN categories c ON c.id = b.category_id
        ORDER BY b.id DESC
    """)
    books = cursor.fetchall()
    cursor.execute("""
        SELECT
            o.id,
            o.status,
            o.total_price,
            o.payment_method,
            o.created_at,
            u.name AS user_name,
            u.email AS user_email,
            GROUP_CONCAT(b.title || ' x' || oi.quantity, ', ') AS product_summary
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN order_items oi ON oi.order_id = o.id
        JOIN books b ON b.id = oi.book_id
        GROUP BY o.id, o.status, o.total_price, o.payment_method, o.created_at, u.name, u.email
        ORDER BY o.created_at DESC
    """)
    order_requests = [dict(row) for row in cursor.fetchall()]
    cursor.execute("""
        SELECT
            br.id,
            br.status,
            br.created_at,
            u.name AS user_name,
            GROUP_CONCAT(b.title, ', ') AS book_titles,
            MAX(bi.due_date) AS due_date
        FROM borrows br
        JOIN users u ON u.id = br.user_id
        JOIN borrow_items bi ON bi.borrow_id = br.id
        JOIN books b ON b.id = bi.book_id
        GROUP BY br.id, br.status, br.created_at, u.name
        ORDER BY br.created_at DESC
    """)
    borrow_requests = []
    for row in cursor.fetchall():
        item = dict(row)
        item["borrow_code"] = format_borrow_code(row["id"])
        borrow_requests.append(item)

    return render_template('admin.html', books=books, order_requests=order_requests, borrow_requests=borrow_requests)

@admin_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        confirmation = request.form.get('confirmation')
        db = get_db()
        result=db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if result:
            error="Email already exists!"
        else:
            hashed_password = generate_password_hash(password)
            db.execute('INSERT INTO users (email, password,name, role) VALUES (?, ?,?,?)',(email, hashed_password,name,"admin"))
            db.commit()
            return redirect(url_for('admin.login'))
        return render_template('register.html', error=error)

    return render_template('register.html')


@admin_bp.route('/user/list', methods=['POST'])
def user_list():
    db=get_db()
    result=db.execute('SELECT * FROM users WHERE role="user"').fetchall()
    user = [dict(row) for row in result]
    if result:
        return jsonify({
            "status":"success",
            "user":user
        }),200
    else:
        return jsonify({
            "status": "failed",
            "message":"User not found!",
        }),200


@admin_bp.route('/orders/<int:order_id>/approve', methods=['POST'])
def approve_order(order_id):
    if session.get('role') != 'admin':
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    order = db.execute('SELECT status FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order:
        return jsonify({"status": "failed", "message": "Order not found"}), 404
    if order['status'] != 'pending':
        return jsonify({"status": "failed", "message": "Order already processed"}), 400

    db.execute("UPDATE orders SET status = 'shipping' WHERE id = ?", (order_id,))
    db.commit()
    return jsonify({"status": "success", "message": "Order approved"}), 200


@admin_bp.route('/orders/<int:order_id>/reject', methods=['POST'])
def reject_order(order_id):
    if session.get('role') != 'admin':
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    order = db.execute('SELECT status FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order:
        return jsonify({"status": "failed", "message": "Order not found"}), 404
    if order['status'] != 'pending':
        return jsonify({"status": "failed", "message": "Order already processed"}), 400

    db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    db.commit()
    return jsonify({"status": "success", "message": "Order rejected"}), 200


@admin_bp.route('/borrows/<int:borrow_id>/reject', methods=['POST'])
def reject_borrow(borrow_id):
    if session.get('role') != 'admin':
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    borrow = db.execute('SELECT status FROM borrows WHERE id = ?', (borrow_id,)).fetchone()
    if not borrow:
        return jsonify({"status": "failed", "message": "Borrow request not found"}), 404
    if borrow['status'] != 'pending':
        return jsonify({"status": "failed", "message": "Borrow request already processed"}), 400

    db.execute("BEGIN TRANSACTION")
    try:
        book_rows = db.execute('SELECT book_id FROM borrow_items WHERE borrow_id = ?', (borrow_id,)).fetchall()
        for row in book_rows:
            db.execute('UPDATE books SET available_for_borrow = available_for_borrow + 1 WHERE id = ?', (row['book_id'],))
        db.execute("UPDATE borrows SET status = 'canceled' WHERE id = ?", (borrow_id,))
        db.execute("UPDATE borrow_items SET status = 'rejected' WHERE borrow_id = ?", (borrow_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Borrow request rejected"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400
