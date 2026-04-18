import os
import random
import sqlite3
import string
from datetime import datetime, timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from admin import admin_bp
from auth import auth_bp
from book import book_bp
from borrow import borrow_bp
from cart import cart_bp
from cart.views import ensure_cart, resolve_image_url
from db.db import get_db


def get_db_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "db", "library.sqlite")


def ensure_column(conn, table_name, column_name, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def ensure_table(conn, table_name, create_sql):
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        conn.execute(create_sql)


def ensure_borrow_status_schema(conn):
    borrows_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'borrows'"
    ).fetchone()
    borrow_items_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'borrow_items'"
    ).fetchone()

    borrows_sql = (borrows_sql_row[0] or "") if borrows_sql_row else ""
    borrow_items_sql = (borrow_items_sql_row[0] or "") if borrow_items_sql_row else ""

    needs_borrows_upgrade = "shipping" not in borrows_sql or "return_pending" not in borrows_sql
    needs_items_upgrade = "shipping" not in borrow_items_sql or "return_pending" not in borrow_items_sql

    if needs_borrows_upgrade:
        conn.execute("ALTER TABLE borrows RENAME TO borrows_old")
        conn.execute(
            """
            CREATE TABLE borrows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT CHECK(status IN (
                    'pending','approved','shipping','borrowing','return_pending','returned','overdue','canceled'
                )) DEFAULT 'pending',
                total_deposit REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME,
                pickup_deadline DATETIME,
                borrowed_at DATETIME,
                returned_at DATETIME,
                confirmed_return_at DATETIME,
                sent_at DATETIME,
                return_requested_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        old_columns = {row[1] for row in conn.execute("PRAGMA table_info(borrows_old)").fetchall()}
        select_sent_at = "sent_at" if "sent_at" in old_columns else "NULL AS sent_at"
        select_return_requested_at = (
            "return_requested_at" if "return_requested_at" in old_columns else "NULL AS return_requested_at"
        )
        conn.execute(
            f"""
            INSERT INTO borrows (
                id, user_id, status, total_deposit, created_at, approved_at, pickup_deadline,
                borrowed_at, returned_at, confirmed_return_at, sent_at, return_requested_at
            )
            SELECT
                id, user_id, status, total_deposit, created_at, approved_at, pickup_deadline,
                borrowed_at, returned_at, confirmed_return_at, {select_sent_at}, {select_return_requested_at}
            FROM borrows_old
            """
        )
        conn.execute("DROP TABLE borrows_old")

    if needs_items_upgrade:
        conn.execute("ALTER TABLE borrow_items RENAME TO borrow_items_old")
        conn.execute(
            """
            CREATE TABLE borrow_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrow_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                status TEXT CHECK(status IN (
                    'pending','approved','shipping','borrowing','return_pending','returned','overdue','rejected'
                )) DEFAULT 'pending',
                due_date DATETIME NOT NULL,
                return_date DATETIME,
                FOREIGN KEY (borrow_id) REFERENCES borrows(id) ON DELETE CASCADE,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO borrow_items (id, borrow_id, book_id, status, due_date, return_date)
            SELECT id, borrow_id, book_id, status, due_date, return_date
            FROM borrow_items_old
            """
        )
        conn.execute("DROP TABLE borrow_items_old")


def ensure_database_compatibility():
    conn = sqlite3.connect(get_db_path())
    try:
        ensure_column(conn, "users", "phone", "TEXT DEFAULT ''")

        ensure_column(conn, "books", "rent_price", "REAL DEFAULT 0")
        ensure_column(conn, "books", "description", "TEXT DEFAULT ''")
        ensure_column(conn, "books", "available_for_sale", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "books", "available_for_borrow", "INTEGER NOT NULL DEFAULT 0")

        book_columns = {row[1] for row in conn.execute("PRAGMA table_info(books)").fetchall()}
        if "available_quantity" in book_columns:
            conn.execute(
                """
                UPDATE books
                SET available_for_sale = CASE
                    WHEN COALESCE(available_for_sale, 0) = 0 THEN COALESCE(available_quantity, 0)
                    ELSE available_for_sale
                END
                """
            )
        if "total_quantity" in book_columns:
            conn.execute(
                """
                UPDATE books
                SET available_for_borrow = CASE
                    WHEN COALESCE(available_for_borrow, 0) = 0 THEN COALESCE(total_quantity, 0)
                    ELSE available_for_borrow
                END
                """
            )

        ensure_column(conn, "borrows", "approved_at", "DATETIME")
        ensure_column(conn, "borrows", "pickup_deadline", "DATETIME")
        ensure_column(conn, "borrows", "borrowed_at", "DATETIME")
        ensure_column(conn, "borrows", "returned_at", "DATETIME")
        ensure_column(conn, "borrows", "confirmed_return_at", "DATETIME")
        ensure_column(conn, "borrows", "sent_at", "DATETIME")
        ensure_column(conn, "borrows", "return_requested_at", "DATETIME")

        ensure_borrow_status_schema(conn)

        ensure_table(
            conn,
            "blacklist",
            """
            CREATE TABLE blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason TEXT,
                banned_until DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            )
            """,
        )
        conn.commit()
    finally:
        conn.close()


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_datetime_label(value):
    parsed = parse_datetime(value)
    if not parsed:
        return "-"
    return parsed.strftime("%d/%m/%Y %H:%M")


def normalize_borrow_status(status, due_date=None):
    if status == "borrowing":
        due = parse_datetime(due_date)
        if due and due < datetime.now():
            return "overdue"
    return status


def map_order_status(status):
    return {
        "pending": "Chờ duyệt",
        "shipping": "Đang giao",
        "delivered": "Đã giao",
        "cancelled": "Đã hủy",
    }.get(status, status or "-")


def map_borrow_status(status):
    return {
        "pending": "Đang yêu cầu",
        "approved": "Đã phê duyệt",
        "shipping": "Admin đã gửi sách",
        "borrowing": "Đang mượn sách",
        "return_pending": "Đang chờ admin xác nhận trả",
        "returned": "Đã trả sách",
        "overdue": "Quá hạn trả sách",
        "rejected": "Đã từ chối",
        "canceled": "Đã từ chối",
    }.get(status, status or "-")


def build_mock_payment(book_ids, amount):
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return {
        "gateway": "MockPay",
        "transaction_id": f"MOCK-{random_part}",
        "status": "paid",
        "amount": float(amount or 0),
        "currency": "VND",
        "book_ids": book_ids,
        "paid_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def create_app():
    ensure_database_compatibility()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-change-me"
    app.json.ensure_ascii = False
    app.permanent_session_lifetime = timedelta(days=30)

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(book_bp)
    app.register_blueprint(borrow_bp)
    app.register_blueprint(cart_bp)

    @app.route("/")
    def index():
        db = get_db()
        rows = db.execute(
            """
            SELECT id, title, author, price, cover_image, description, available_for_sale, available_for_borrow
            FROM books
            WHERE COALESCE(available_for_sale, 0) > 0 OR COALESCE(available_for_borrow, 0) > 0
            ORDER BY id DESC
            LIMIT 4
            """
        ).fetchall()

        latest_books = []
        for row in rows:
            latest_books.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "author": row["author"] or "Chua ro tac gia",
                    "price": float(row["price"] or 0),
                    "price_display": "{:,.0f}d".format(float(row["price"] or 0)).replace(",", "."),
                    "description": row["description"],
                    "image_url": resolve_image_url(row["cover_image"]),
                    "available_for_sale": int(row["available_for_sale"] or 0),
                    "available_for_borrow": int(row["available_for_borrow"] or 0),
                }
            )

        return render_template("index.html", latest_books=latest_books)

    @app.route("/my-account")
    def my_account():
        user_id = session.get("user_id", 1)
        db = get_db()

        user_row = db.execute(
            "SELECT id, name, email, phone, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user_row:
            return redirect(url_for("auth.login"))

        order_rows = db.execute(
            """
            SELECT
                o.id,
                o.status,
                o.total_price,
                o.created_at,
                GROUP_CONCAT(COALESCE(b.title, 'Sach da xoa') || ' x' || oi.quantity, ', ') AS items
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN books b ON b.id = oi.book_id
            WHERE o.user_id = ?
            GROUP BY o.id, o.status, o.total_price, o.created_at
            ORDER BY o.created_at DESC, o.id DESC
            """,
            (user_id,),
        ).fetchall()

        borrow_rows = db.execute(
            """
            SELECT
                br.id,
                br.status,
                br.created_at,
                MAX(bi.due_date) AS due_date,
                GROUP_CONCAT(COALESCE(b.title, 'Sach da xoa'), ', ') AS items
            FROM borrows br
            JOIN borrow_items bi ON bi.borrow_id = br.id
            LEFT JOIN books b ON b.id = bi.book_id
            WHERE br.user_id = ?
            GROUP BY br.id, br.status, br.created_at
            ORDER BY br.created_at DESC, br.id DESC
            """,
            (user_id,),
        ).fetchall()

        order_history = [
            {
                "id": row["id"],
                "book_titles": row["items"] or "-",
                "created_at_raw": row["created_at"] or "",
                "created_at_label": format_datetime_label(row["created_at"]),
                "total_price_display": "{:,.0f}d".format(float(row["total_price"] or 0)).replace(",", "."),
                "status": row["status"],
                "status_label": map_order_status(row["status"]),
            }
            for row in order_rows
        ]

        borrow_history = []
        for row in borrow_rows:
            effective_status = normalize_borrow_status(row["status"], row["due_date"])
            borrow_history.append(
                {
                    "id": row["id"],
                    "borrow_code": f"MS-{row['id']:06d}",
                    "book_titles": row["items"] or "-",
                    "created_at_raw": row["created_at"] or "",
                    "created_at_label": format_datetime_label(row["created_at"]),
                    "due_date_label": format_datetime_label(row["due_date"]),
                    "status_label": map_borrow_status(effective_status),
                    "status": effective_status,
                }
            )

        all_history = [
            {
                "type": "Mua",
                "type_badge_class": "bg-dark",
                "book_titles": item["book_titles"],
                "time_label": item["created_at_label"],
                "status_label": item["status_label"],
                "sort_key": item["created_at_raw"],
            }
            for item in order_history
        ] + [
            {
                "type": "Muon",
                "type_badge_class": "bg-secondary",
                "book_titles": item["book_titles"],
                "time_label": item["created_at_label"],
                "status_label": item["status_label"],
                "sort_key": item["created_at_raw"],
            }
            for item in borrow_history
        ]
        all_history.sort(key=lambda item: item["sort_key"], reverse=True)

        user_profile = {
            "id": user_row["id"],
            "name": user_row["name"] or "Nguoi dung",
            "email": user_row["email"] or "",
            "phone": user_row["phone"] or "",
            "role": user_row["role"] or "user",
            "created_at_label": format_datetime_label(user_row["created_at"]),
        }

        return render_template(
            "my-account.html",
            user=user_profile,
            all_history=all_history,
            order_history=order_history,
            borrow_history=borrow_history,
        )

    @app.post("/my-account/update")
    def update_my_account():
        user_id = session.get("user_id", 1)
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name:
            flash("Ten nguoi dung khong duoc de trong.", "danger")
            return redirect(url_for("my_account"))

        db = get_db()
        db.execute("UPDATE users SET name = ?, phone = ? WHERE id = ?", (name, phone, user_id))
        db.commit()
        session["user_name"] = name
        flash("Cap nhat thong tin thanh cong.", "success")
        return redirect(url_for("my_account"))

    @app.route("/wishlist")
    def wishlist():
        wishlist_ids = session.get("wishlist_ids", [])
        items = []
        if wishlist_ids:
            db = get_db()
            placeholders = ",".join(["?"] * len(wishlist_ids))
            rows = db.execute(
                f"""
                SELECT id, title, author, price, cover_image, available_for_sale, available_for_borrow
                FROM books
                WHERE id IN ({placeholders})
                ORDER BY id DESC
                """,
                wishlist_ids,
            ).fetchall()
            for row in rows:
                items.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "author": row["author"] or "Chua ro tac gia",
                        "price": row["price"],
                        "price_display": "{:,.0f}d".format(float(row["price"] or 0)).replace(",", "."),
                        "image": resolve_image_url(row["cover_image"]),
                        "available_for_sale": int(row["available_for_sale"] or 0),
                        "available_for_borrow": int(row["available_for_borrow"] or 0),
                    }
                )
        return render_template("wishlist.html", items=items)

    @app.post("/wishlist/add/<int:book_id>")
    def add_to_wishlist(book_id):
        wishlist_ids = session.get("wishlist_ids", [])
        if book_id not in wishlist_ids:
            wishlist_ids.append(book_id)
            session["wishlist_ids"] = wishlist_ids
        return redirect(request.referrer or url_for("wishlist"))

    @app.post("/wishlist/remove/<int:book_id>")
    def remove_from_wishlist(book_id):
        session["wishlist_ids"] = [item for item in session.get("wishlist_ids", []) if item != book_id]
        return redirect(request.referrer or url_for("wishlist"))

    @app.post("/wishlist/move-to-cart/<int:book_id>")
    def move_wishlist_to_cart(book_id):
        db = get_db()
        cart_id = ensure_cart()
        book = db.execute("SELECT available_for_sale FROM books WHERE id = ?", (book_id,)).fetchone()

        if book and int(book["available_for_sale"] or 0) > 0:
            item = db.execute(
                "SELECT quantity FROM cart_items WHERE book_id = ? AND cart_id = ?",
                (book_id, cart_id),
            ).fetchone()
            if item:
                new_quantity = min(int(item["quantity"]) + 1, int(book["available_for_sale"]))
                db.execute(
                    "UPDATE cart_items SET quantity = ? WHERE book_id = ? AND cart_id = ?",
                    (new_quantity, book_id, cart_id),
                )
            else:
                db.execute(
                    "INSERT INTO cart_items (book_id, cart_id, quantity) VALUES (?, ?, 1)",
                    (book_id, cart_id),
                )
            db.commit()

        session["wishlist_ids"] = [item for item in session.get("wishlist_ids", []) if item != book_id]
        return redirect(url_for("cart.view_cart"))

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/payments")
    def payments():
        book_ids = request.args.get("books", "")
        selected_books = []
        total_amount = 0

        if book_ids:
            try:
                id_list = [int(value.strip()) for value in book_ids.split(",") if value.strip()]
                if id_list:
                    db = get_db()
                    placeholders = ",".join(["?"] * len(id_list))
                    selected_books = db.execute(
                        f"""
                        SELECT id, title, author, price, rent_price, cover_image, description
                        FROM books
                        WHERE id IN ({placeholders})
                        """,
                        id_list,
                    ).fetchall()
                    total_amount = sum(float(book["price"] or 0) for book in selected_books)
            except ValueError:
                selected_books = []
                total_amount = 0

        return render_template(
            "payments.html",
            selected_books=selected_books,
            total_amount=total_amount,
            total_amount_display="{:,.0f}d".format(total_amount).replace(",", "."),
        )

    @app.post("/payments/api/mock")
    def mock_payment_api():
        raw_book_ids = request.form.getlist("book_ids")
        if not raw_book_ids and request.is_json:
            raw_book_ids = (request.get_json(silent=True) or {}).get("book_ids", [])

        try:
            book_ids = [int(book_id) for book_id in raw_book_ids]
        except (TypeError, ValueError):
            return jsonify({"status": "failed", "message": "Danh sach sach khong hop le."}), 400

        if not book_ids:
            return jsonify({"status": "failed", "message": "Chua co sach de thanh toan."}), 400

        db = get_db()
        placeholders = ",".join(["?"] * len(book_ids))
        books = db.execute(
            f"SELECT id, price FROM books WHERE id IN ({placeholders})",
            book_ids,
        ).fetchall()
        amount = sum(float(book["price"] or 0) for book in books)
        payload = build_mock_payment(book_ids, amount)
        return jsonify({"status": "success", "payment": payload})

    @app.post("/payments/create")
    def create_payment_order():
        user_id = session.get("user_id", 1)
        raw_book_ids = request.form.getlist("book_ids")
        cart_id = ensure_cart()

        if not raw_book_ids:
            return redirect(url_for("cart.view_cart"))

        try:
            book_ids = [int(book_id) for book_id in raw_book_ids]
        except ValueError:
            return redirect(url_for("cart.view_cart"))

        db = get_db()
        placeholders = ",".join(["?"] * len(book_ids))
        books = db.execute(
            f"""
            SELECT id, title, price, available_for_sale
            FROM books
            WHERE id IN ({placeholders})
            """,
            book_ids,
        ).fetchall()
        if not books:
            return redirect(url_for("cart.view_cart"))

        db.execute("BEGIN TRANSACTION")
        try:
            total_price = sum(float(book["price"] or 0) for book in books)
            payment = build_mock_payment(book_ids, total_price)
            cursor = db.execute(
                """
                INSERT INTO orders (user_id, total_price, status, address, phone, payment_method)
                VALUES (?, ?, 'pending', ?, ?, 'BANK')
                """,
                (user_id, total_price, f"Dummy payment {payment['transaction_id']}", "0000000000"),
            )
            order_id = cursor.lastrowid

            for book in books:
                if int(book["available_for_sale"] or 0) <= 0:
                    raise ValueError(f"Sach '{book['title']}' da het hang.")
                db.execute(
                    "INSERT INTO order_items (order_id, book_id, quantity, price) VALUES (?, ?, ?, ?)",
                    (order_id, book["id"], 1, book["price"]),
                )
                db.execute(
                    "UPDATE books SET available_for_sale = available_for_sale - 1 WHERE id = ?",
                    (book["id"],),
                )

            db.execute(
                f"DELETE FROM cart_items WHERE cart_id = ? AND book_id IN ({placeholders})",
                [cart_id, *book_ids],
            )
            db.commit()
        except Exception:
            db.rollback()
            return redirect(url_for("payments", books=",".join(str(book_id) for book_id in book_ids)))

        flash("Thanh toan gia lap thanh cong. Don hang da duoc tao de admin duyet.", "success")
        return redirect(url_for("my_account"))

    @app.post("/orders/<int:order_id>/confirm-delivery")
    def confirm_delivery(order_id):
        user_id = session.get("user_id")
        if not user_id:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login"))

        db = get_db()
        order = db.execute(
            "SELECT id, user_id, status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not order or int(order["user_id"]) != int(user_id):
            flash("Không tìm thấy đơn hàng hợp lệ.", "danger")
            return redirect(url_for("my_account"))
        if order["status"] != "shipping":
            flash("Đơn hàng này chưa ở trạng thái đang giao.", "warning")
            return redirect(url_for("my_account"))

        db.execute("UPDATE orders SET status = 'delivered' WHERE id = ?", (order_id,))
        db.commit()
        flash("Đã xác nhận nhận được sách mua.", "success")
        return redirect(url_for("my_account"))

    @app.context_processor
    def inject_header_state():
        cart_id = ensure_cart()
        db = get_db()
        count = db.execute("SELECT SUM(quantity) FROM cart_items WHERE cart_id = ?", (cart_id,)).fetchone()[0]
        wishlist_ids = session.get("wishlist_ids", [])
        return {
            "cart_count": count or 0,
            "wishlist_count": len(wishlist_ids),
            "wishlist_ids": set(wishlist_ids),
        }

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
