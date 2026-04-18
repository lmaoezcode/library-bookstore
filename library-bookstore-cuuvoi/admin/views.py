from datetime import datetime, timedelta

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from borrow.views import format_borrow_code
from db.db import get_db

from . import admin_bp


def effective_borrow_status(status, due_date):
    if status == "borrowing" and due_date:
        try:
            due = datetime.fromisoformat(str(due_date).replace(" ", "T"))
        except ValueError:
            due = None
        if due and due < datetime.now():
            return "overdue"
    return status


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE email = ? AND role = "admin"',
            (email,),
        ).fetchone()
        if user and (check_password_hash(user["password"], password) or user["password"] == password):
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["user_name"] = user["name"]
            flash("Dang nhap thanh cong!", "success")
            return redirect(url_for("admin.admin_dashboard"))
        error = "Sai email hoac mat khau!"
    return render_template("admin-login.html", error=error)


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    db = get_db()
    cursor = db.cursor()
    books = cursor.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.price,
            COALESCE(b.available_for_sale, 0) AS available_for_sale,
            COALESCE(b.available_for_borrow, 0) AS available_for_borrow,
            b.cover_image AS image,
            b.category_id AS category,
            COALESCE(c.name, 'Chua phan loai') AS category_name
        FROM books b
        LEFT JOIN categories c ON c.id = b.category_id
        ORDER BY b.id DESC
        """
    ).fetchall()

    order_requests = [dict(row) for row in cursor.execute(
        """
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
        """
    ).fetchall()]

    borrow_requests = []
    borrow_rows = cursor.execute(
        """
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
        """
    ).fetchall()
    for row in borrow_rows:
        item = dict(row)
        item["borrow_code"] = format_borrow_code(row["id"])
        item["status"] = effective_borrow_status(row["status"], row["due_date"])
        borrow_requests.append(item)

    blacklist_entries = cursor.execute(
        """
        SELECT
            bl.id,
            bl.reason,
            bl.banned_until,
            bl.created_at,
            u.name AS user_name,
            u.email AS user_email
        FROM blacklist bl
        JOIN users u ON u.id = bl.user_id
        ORDER BY bl.created_at DESC
        LIMIT 10
        """
    ).fetchall()

    return render_template(
        "admin.html",
        books=books,
        order_requests=order_requests,
        borrow_requests=borrow_requests,
        blacklist_entries=blacklist_entries,
    )


@admin_bp.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        confirmation = request.form.get("confirmation", "")
        db = get_db()

        if password != confirmation:
            error = "Mat khau xac nhan khong khop!"
        elif db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            error = "Email already exists!"
        else:
            hashed_password = generate_password_hash(password)
            db.execute(
                "INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, 'admin')",
                (email, hashed_password, name),
            )
            db.commit()
            return redirect(url_for("admin.login"))
    return render_template("register.html", error=error)


@admin_bp.route("/user/list", methods=["POST"])
def user_list():
    db = get_db()
    result = db.execute('SELECT * FROM users WHERE role = "user"').fetchall()
    users = [dict(row) for row in result]
    return jsonify({"status": "success", "user": users}), 200


@admin_bp.route("/orders/<int:order_id>/approve", methods=["POST"])
def approve_order(order_id):
    if session.get("role") != "admin":
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    order = db.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return jsonify({"status": "failed", "message": "Order not found"}), 404
    if order["status"] != "pending":
        return jsonify({"status": "failed", "message": "Order already processed"}), 400

    db.execute("UPDATE orders SET status = 'shipping' WHERE id = ?", (order_id,))
    db.commit()
    return jsonify({"status": "success", "message": "Order approved"}), 200


@admin_bp.route("/orders/<int:order_id>/reject", methods=["POST"])
def reject_order(order_id):
    if session.get("role") != "admin":
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    order = db.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return jsonify({"status": "failed", "message": "Order not found"}), 404
    if order["status"] != "pending":
        return jsonify({"status": "failed", "message": "Order already processed"}), 400

    db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    db.commit()
    return jsonify({"status": "success", "message": "Order rejected"}), 200


@admin_bp.route("/blacklist", methods=["GET"])
def blacklist():
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    db = get_db()
    cursor = db.cursor()
    blacklist_entries = cursor.execute(
        """
        SELECT
            bl.id,
            bl.reason,
            bl.banned_until,
            bl.created_at,
            u.name AS user_name,
            u.email AS user_email,
            a.name AS admin_name
        FROM blacklist bl
        JOIN users u ON u.id = bl.user_id
        LEFT JOIN users a ON a.id = bl.created_by
        ORDER BY bl.created_at DESC
        """
    ).fetchall()

    available_users = cursor.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE role = 'user'
          AND id NOT IN (
              SELECT user_id
              FROM blacklist
              WHERE banned_until IS NULL OR banned_until > CURRENT_TIMESTAMP
          )
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "blacklist.html",
        blacklist_entries=blacklist_entries,
        available_users=available_users,
    )


@admin_bp.route("/blacklist/add", methods=["POST"])
def add_to_blacklist():
    if session.get("role") != "admin":
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    user_id = request.form.get("user_id")
    reason = request.form.get("reason", "").strip()
    ban_type = request.form.get("ban_type", "temporary")
    ban_days = request.form.get("ban_days", "0")

    if not user_id or not reason:
        return jsonify({"status": "failed", "message": "Thieu thong tin"}), 400

    db = get_db()
    active_entry = db.execute(
        """
        SELECT id
        FROM blacklist
        WHERE user_id = ?
          AND (banned_until IS NULL OR banned_until > CURRENT_TIMESTAMP)
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if active_entry:
        return jsonify({"status": "failed", "message": "Nguoi dung da nam trong danh sach den."}), 400

    try:
        banned_until = None
        if ban_type == "temporary":
            days = max(1, int(ban_days or 0))
            banned_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        db.execute(
            """
            INSERT INTO blacklist (user_id, reason, banned_until, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, reason, banned_until, session.get("user_id")),
        )
        db.commit()
        return jsonify({"status": "success", "message": "Da them vao danh sach den."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@admin_bp.route("/blacklist/remove/<int:blacklist_id>", methods=["POST"])
def remove_from_blacklist(blacklist_id):
    if session.get("role") != "admin":
        return jsonify({"status": "failed", "message": "Unauthorized"}), 403

    db = get_db()
    db.execute("DELETE FROM blacklist WHERE id = ?", (blacklist_id,))
    db.commit()
    return jsonify({"status": "success", "message": "Da xoa khoi danh sach den."}), 200
