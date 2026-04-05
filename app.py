import os
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for

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


def ensure_database_compatibility():
    conn = sqlite3.connect(get_db_path())
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "phone" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
            conn.execute(
                """
                UPDATE users
                SET phone = COALESCE(
                    (
                        SELECT o.phone
                        FROM orders o
                        WHERE o.user_id = users.id
                          AND o.phone IS NOT NULL
                          AND TRIM(o.phone) != ''
                        ORDER BY o.created_at DESC, o.id DESC
                        LIMIT 1
                    ),
                    ''
                )
                """
            )
            conn.commit()
    finally:
        conn.close()


def format_datetime_label(value):
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def map_order_status(status):
    return {
        "pending": "Chờ duyệt",
        "shipping": "Đang giao",
        "delivered": "Đã giao",
        "cancelled": "Đã hủy",
    }.get(status, status or "-")


def map_borrow_status(status):
    return {
        "pending": "Chờ duyệt",
        "approved": "Đã duyệt",
        "borrowing": "Đang mượn",
        "returned": "Đã trả",
        "overdue": "Quá hạn",
        "canceled": "Đã hủy",
    }.get(status, status or "-")


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
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT id, title, author, price, cover_image, description, available_for_sale, available_for_borrow
            FROM books
            WHERE available_for_sale > 0 OR available_for_borrow > 0
            ORDER BY id ASC
            LIMIT 4
            """
        ).fetchall()

        latest_books = []
        for row in rows:
            latest_books.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "author": row["author"] or "Chưa rõ tác giả",
                    "price": row["price"],
                    "price_display": "{:,.0f}đ".format(row["price"] if row["price"] else 0).replace(",", "."),
                    "description": row["description"],
                    "image_url": resolve_image_url(row["cover_image"]),
                    "available_for_sale": row["available_for_sale"],
                    "available_for_borrow": row["available_for_borrow"],
                }
            )

        return render_template("index.html", latest_books=latest_books)

    @app.route("/my-account")
    def my_account():
        user_id = session.get("user_id", 1)
        db = get_db()
        db.row_factory = sqlite3.Row

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
                GROUP_CONCAT(COALESCE(b.title, 'Sách đã xóa') || ' x' || oi.quantity, ', ') AS items
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
                GROUP_CONCAT(COALESCE(b.title, 'Sách đã xóa'), ', ') AS items
            FROM borrows br
            JOIN borrow_items bi ON bi.borrow_id = br.id
            LEFT JOIN books b ON b.id = bi.book_id
            WHERE br.user_id = ?
            GROUP BY br.id, br.status, br.created_at
            ORDER BY br.created_at DESC, br.id DESC
            """,
            (user_id,),
        ).fetchall()

        order_history = []
        for row in order_rows:
            order_history.append(
                {
                    "id": row["id"],
                    "book_titles": row["items"] or "-",
                    "created_at_raw": row["created_at"] or "",
                    "created_at_label": format_datetime_label(row["created_at"]),
                    "total_price_display": "{:,.0f}đ".format(row["total_price"] or 0).replace(",", "."),
                    "status_label": map_order_status(row["status"]),
                }
            )

        borrow_history = []
        for row in borrow_rows:
            borrow_history.append(
                {
                    "id": row["id"],
                    "borrow_code": f"MS-{row['id']:06d}",
                    "book_titles": row["items"] or "-",
                    "created_at_raw": row["created_at"] or "",
                    "created_at_label": format_datetime_label(row["created_at"]),
                    "due_date_label": format_datetime_label(row["due_date"]),
                    "status_label": map_borrow_status(row["status"]),
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
                "type": "Mượn",
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
            "name": user_row["name"] or "Người dùng",
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
            flash("Tên người dùng không được để trống.", "danger")
            return redirect(url_for("my_account"))

        db = get_db()
        db.execute(
            "UPDATE users SET name = ?, phone = ? WHERE id = ?",
            (name, phone, user_id),
        )
        db.commit()
        session["user_name"] = name
        flash("Cập nhật thông tin thành công.", "success")
        return redirect(url_for("my_account"))

    @app.route("/wishlist")
    def wishlist():
        wishlist_ids = session.get("wishlist_ids", [])
        items = []

        if wishlist_ids:
            db = get_db()
            db.row_factory = sqlite3.Row
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
                        "author": row["author"] or "Chưa rõ tác giả",
                        "price": row["price"],
                        "price_display": "{:,.0f}đ".format(row["price"] if row["price"] else 0).replace(",", "."),
                        "image": resolve_image_url(row["cover_image"]),
                        "available_for_sale": row["available_for_sale"],
                        "available_for_borrow": row["available_for_borrow"],
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
        cursor = db.cursor()
        cart_id = ensure_cart()

        book = cursor.execute(
            "SELECT available_for_sale FROM books WHERE id = ?",
            (book_id,),
        ).fetchone()

        if book and int(book["available_for_sale"] or 0) > 0:
            item = cursor.execute(
                "SELECT quantity FROM cart_items WHERE book_id = ? AND cart_id = ?",
                (book_id, cart_id),
            ).fetchone()
            if item:
                new_quantity = min(int(item["quantity"]) + 1, int(book["available_for_sale"]))
                cursor.execute(
                    "UPDATE cart_items SET quantity = ? WHERE book_id = ? AND cart_id = ?",
                    (new_quantity, book_id, cart_id),
                )
            else:
                cursor.execute(
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
        if book_ids:
            try:
                id_list = [int(i.strip()) for i in book_ids.split(",") if i.strip()]
                db = get_db()
                db.row_factory = sqlite3.Row
                placeholders = ",".join(["?"] * len(id_list))
                query = f"""
                    SELECT id, title, author, price, rent_price, cover_image, description
                    FROM books
                    WHERE id IN ({placeholders})
                """
                selected_books = db.execute(query, id_list).fetchall()
            except ValueError:
                selected_books = []
        return render_template("payments.html", selected_books=selected_books)

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
        db.row_factory = sqlite3.Row
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
            cursor = db.execute(
                """
                INSERT INTO orders (user_id, total_price, status, address, phone, payment_method)
                VALUES (?, ?, 'pending', ?, ?, 'BANK')
                """,
                (user_id, total_price, "Thanh toán online", "0000000000"),
            )
            order_id = cursor.lastrowid

            for book in books:
                if int(book["available_for_sale"] or 0) <= 0:
                    raise ValueError(f"Sách '{book['title']}' đã hết hàng.")
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

        flash("Thanh toán thành công!", "success")
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
