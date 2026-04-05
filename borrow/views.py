from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request, session

from cart.views import resolve_image_url
from db.db import get_db
from route.route import admin_required, login_required

from . import borrow_bp


def format_borrow_code(borrow_id):
    return f"MS-{borrow_id:06d}"


@borrow_bp.route("/create", methods=["POST"])
@login_required
def create_borrow():
    data = request.get_json(silent=True) if request.is_json else request.form
    raw_book_ids = data.get("book_ids", []) if request.is_json else data.getlist("book_ids")

    if not raw_book_ids:
        return jsonify({"status": "failed", "message": "Vui lòng chọn ít nhất 1 quyển sách"}), 400

    try:
        unique_book_ids = []
        seen = set()
        for raw_id in raw_book_ids:
            book_id = int(raw_id)
            if book_id not in seen:
                seen.add(book_id)
                unique_book_ids.append(book_id)
    except (TypeError, ValueError):
        return jsonify({"status": "failed", "message": "Danh sách sách không hợp lệ."}), 400

    user_id = session.get("user_id")
    db = get_db()

    try:
        db.execute("BEGIN TRANSACTION")

        cursor = db.execute(
            "INSERT INTO borrows (user_id, status) VALUES (?, ?)",
            (user_id, "pending"),
        )
        borrow_id = cursor.lastrowid
        borrow_code = format_borrow_code(borrow_id)

        due_date_raw = data.get("return_date")
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d") if due_date_raw else datetime.now() + timedelta(days=14)

        for book_id in unique_book_ids:
            book = db.execute(
                "SELECT title, available_for_borrow FROM books WHERE id = ?",
                (book_id,),
            ).fetchone()

            if not book:
                raise Exception(f"Sách ID {book_id} không tồn tại.")
            if int(book["available_for_borrow"] or 0) <= 0:
                raise Exception(f"Sách '{book['title']}' đã cạn lượt mượn.")

            db.execute(
                "UPDATE books SET available_for_borrow = available_for_borrow - 1 WHERE id = ?",
                (book_id,),
            )
            db.execute(
                "INSERT INTO borrow_items (borrow_id, book_id, due_date, status) VALUES (?, ?, ?, ?)",
                (borrow_id, book_id, due_date.strftime("%Y-%m-%d %H:%M:%S"), "pending"),
            )

        db.commit()
        return jsonify(
            {
                "status": "success",
                "message": "Tạo phiếu mượn thành công!",
                "borrow_id": borrow_id,
                "borrow_code": borrow_code,
                "total_books": len(unique_book_ids),
            }
        ), 201
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400


@borrow_bp.route("/history", methods=["GET"])
@login_required
def get_history():
    user_id = session.get("user_id")
    db = get_db()

    borrows = db.execute(
        "SELECT * FROM borrows WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()

    result = []
    for borrow in borrows:
        items = db.execute(
            """
            SELECT bi.*, bk.title
            FROM borrow_items bi
            JOIN books bk ON bi.book_id = bk.id
            WHERE bi.borrow_id = ?
            """,
            (borrow["id"],),
        ).fetchall()

        result.append(
            {
                "borrow_id": borrow["id"],
                "borrow_code": format_borrow_code(borrow["id"]),
                "status": borrow["status"],
                "created_at": borrow["created_at"],
                "items": [dict(item) for item in items],
            }
        )

    return jsonify({"status": "success", "data": result}), 200


@borrow_bp.route("/admin/list", methods=["GET"])
@admin_required
def admin_get_all():
    db = get_db()
    borrows = db.execute(
        """
        SELECT
            br.id,
            br.status,
            br.created_at,
            br.approved_at,
            u.name AS user_name,
            GROUP_CONCAT(b.title, ', ') AS book_titles,
            MAX(bi.due_date) AS due_date
        FROM borrows br
        JOIN users u ON u.id = br.user_id
        JOIN borrow_items bi ON bi.borrow_id = br.id
        JOIN books b ON b.id = bi.book_id
        GROUP BY br.id, br.status, br.created_at, br.approved_at, u.name
        ORDER BY br.created_at DESC
        """
    ).fetchall()

    data = []
    for row in borrows:
        item = dict(row)
        item["borrow_code"] = format_borrow_code(row["id"])
        data.append(item)

    return jsonify({"status": "success", "data": data}), 200


@borrow_bp.route("/admin/approve", methods=["POST"])
@admin_required
def admin_approve():
    data = request.get_json()
    borrow_id = data.get("borrow_id")

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute("SELECT status FROM borrows WHERE id = ?", (borrow_id,)).fetchone()

        if not borrow or borrow["status"] != "pending":
            raise Exception("Phiếu mượn không tồn tại hoặc đã được xử lý.")

        db.execute("UPDATE borrows SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?", (borrow_id,))
        db.execute("UPDATE borrow_items SET status = 'approved' WHERE borrow_id = ?", (borrow_id,))

        db.commit()
        return jsonify({"status": "success", "message": "Đã duyệt phiếu mượn."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400


@borrow_bp.route("/admin/return_item", methods=["POST"])
@admin_required
def admin_return_item():
    data = request.get_json()
    item_id = data.get("item_id")

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        item = db.execute("SELECT book_id, status, borrow_id FROM borrow_items WHERE id = ?", (item_id,)).fetchone()

        if not item:
            raise Exception("Không tìm thấy dữ liệu mượn sách này.")
        if item["status"] == "returned":
            raise Exception("Sách này đã được trả.")

        book_id = item["book_id"]
        borrow_id = item["borrow_id"]

        db.execute("UPDATE borrow_items SET status = 'returned', return_date = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        db.execute("UPDATE books SET available_for_borrow = available_for_borrow + 1 WHERE id = ?", (book_id,))

        remaining = db.execute(
            "SELECT COUNT(*) FROM borrow_items WHERE borrow_id = ? AND status != 'returned'",
            (borrow_id,),
        ).fetchone()[0]
        if remaining == 0:
            db.execute("UPDATE borrows SET status = 'returned', returned_at = CURRENT_TIMESTAMP WHERE id = ?", (borrow_id,))

        db.commit()
        return jsonify({"status": "success", "message": "Xác nhận trả sách thành công, đã cập nhật tồn kho."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400


@borrow_bp.route("/", methods=["GET"])
def borrow_ui():
    book_ids = request.args.get("books", "")
    selected_books = []

    if book_ids:
        try:
            id_list = [int(i.strip()) for i in book_ids.split(",") if i.strip()]
            db = get_db()
            rows = db.execute(
                f"""
                SELECT id, title, author, price, rent_price, cover_image, description
                FROM books
                WHERE id IN ({','.join(['?'] * len(id_list))})
                """,
                id_list,
            ).fetchall()

            seen = set()
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                selected_books.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "author": row["author"],
                        "price": row["price"],
                        "rent_price": row["rent_price"],
                        "description": row["description"],
                        "image": resolve_image_url(row["cover_image"]),
                    }
                )
        except ValueError:
            selected_books = []

    return render_template("borrow.html", selected_books=selected_books)
