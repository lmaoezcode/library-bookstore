from datetime import datetime, timedelta

from flask import jsonify, render_template, request, session

from cart.views import resolve_image_url
from db.db import get_db
from route.route import admin_required, login_required

from . import borrow_bp


DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def format_borrow_code(borrow_id):
    return f"MS-{borrow_id:06d}"


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def effective_borrow_status(status, due_date):
    if status == "borrowing":
        due = parse_datetime(due_date)
        if due and due < datetime.now():
            return "overdue"
    return status


def get_blacklist_entry(user_id):
    db = get_db()
    return db.execute(
        """
        SELECT id, reason, banned_until
        FROM blacklist
        WHERE user_id = ?
          AND (banned_until IS NULL OR banned_until > CURRENT_TIMESTAMP)
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def sync_overdue_borrows(db=None):
    owns_connection = db is None
    db = db or get_db()

    overdue_rows = db.execute(
        """
        SELECT id, borrow_id
        FROM borrow_items
        WHERE status = 'borrowing'
          AND due_date < CURRENT_TIMESTAMP
        """
    ).fetchall()

    updated_borrow_ids = set()
    if overdue_rows:
        for row in overdue_rows:
            db.execute("UPDATE borrow_items SET status = 'overdue' WHERE id = ?", (row["id"],))
            updated_borrow_ids.add(row["borrow_id"])

        for borrow_id in updated_borrow_ids:
            db.execute("UPDATE borrows SET status = 'overdue' WHERE id = ?", (borrow_id,))

        if owns_connection:
            db.commit()

    return len(overdue_rows)


@borrow_bp.route("/create", methods=["POST"])
@login_required
def create_borrow():
    data = request.get_json(silent=True) if request.is_json else request.form
    raw_book_ids = data.get("book_ids", []) if request.is_json else data.getlist("book_ids")

    if not raw_book_ids:
        return jsonify({"status": "failed", "message": "Vui long chon it nhat 1 quyen sach."}), 400

    try:
        unique_book_ids = []
        seen = set()
        for raw_id in raw_book_ids:
            book_id = int(raw_id)
            if book_id not in seen:
                seen.add(book_id)
                unique_book_ids.append(book_id)
    except (TypeError, ValueError):
        return jsonify({"status": "failed", "message": "Danh sach sach khong hop le."}), 400

    user_id = session.get("user_id")
    blacklist_entry = get_blacklist_entry(user_id)
    if blacklist_entry:
        if blacklist_entry["banned_until"]:
            banned_until = str(blacklist_entry["banned_until"])[:10]
            message = f"Tai khoan cua ban bi cam muon sach den {banned_until}."
        else:
            message = "Tai khoan cua ban bi cam muon sach vo thoi han."
        return jsonify({"status": "failed", "message": message}), 403

    borrow_date = parse_datetime(data.get("borrow_date")) or datetime.now()
    due_date = parse_datetime(data.get("return_date"))
    if not due_date:
        due_date = borrow_date + timedelta(days=14)
    if due_date.date() < borrow_date.date():
        return jsonify({"status": "failed", "message": "Ngay tra du kien phai sau ngay muon."}), 400

    phone = (data.get("phone") or "").strip()
    db = get_db()

    try:
        db.execute("BEGIN TRANSACTION")
        if phone:
            db.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))

        for book_id in unique_book_ids:
            book = db.execute(
                "SELECT title, COALESCE(available_for_borrow, 0) AS available_for_borrow FROM books WHERE id = ?",
                (book_id,),
            ).fetchone()
            if not book:
                raise ValueError(f"Sach ID {book_id} khong ton tai.")
            if int(book["available_for_borrow"] or 0) <= 0:
                raise ValueError(f"Sach '{book['title']}' da het luot muon.")

        cursor = db.execute("INSERT INTO borrows (user_id, status) VALUES (?, 'pending')", (user_id,))
        borrow_id = cursor.lastrowid

        for book_id in unique_book_ids:
            db.execute(
                """
                INSERT INTO borrow_items (borrow_id, book_id, due_date, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (borrow_id, book_id, due_date.strftime("%Y-%m-%d %H:%M:%S")),
            )

        db.commit()
        return jsonify(
            {
                "status": "success",
                "message": "Tao phieu muon thanh cong.",
                "borrow_id": borrow_id,
                "borrow_code": format_borrow_code(borrow_id),
                "total_books": len(unique_book_ids),
            }
        ), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/history", methods=["GET"])
@login_required
def get_history():
    sync_overdue_borrows()
    user_id = session.get("user_id")
    db = get_db()

    borrows = db.execute(
        """
        SELECT
            br.id,
            br.status,
            br.created_at,
            MAX(bi.due_date) AS due_date
        FROM borrows br
        JOIN borrow_items bi ON bi.borrow_id = br.id
        WHERE br.user_id = ?
        GROUP BY br.id, br.status, br.created_at
        ORDER BY br.created_at DESC
        """,
        (user_id,),
    ).fetchall()

    result = []
    for borrow in borrows:
        items = db.execute(
            """
            SELECT bi.*, bk.title
            FROM borrow_items bi
            JOIN books bk ON bk.id = bi.book_id
            WHERE bi.borrow_id = ?
            ORDER BY bi.id ASC
            """,
            (borrow["id"],),
        ).fetchall()
        result.append(
            {
                "borrow_id": borrow["id"],
                "borrow_code": format_borrow_code(borrow["id"]),
                "status": effective_borrow_status(borrow["status"], borrow["due_date"]),
                "created_at": borrow["created_at"],
                "items": [dict(item) for item in items],
            }
        )

    return jsonify({"status": "success", "data": result}), 200


@borrow_bp.route("/admin/list", methods=["GET"])
@admin_required
def admin_get_all():
    sync_overdue_borrows()
    db = get_db()
    rows = db.execute(
        """
        SELECT
            br.id,
            CASE
                WHEN br.status = 'borrowing' AND MAX(bi.due_date) < CURRENT_TIMESTAMP THEN 'overdue'
                ELSE br.status
            END AS status,
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
    for row in rows:
        item = dict(row)
        item["borrow_code"] = format_borrow_code(row["id"])
        data.append(item)
    return jsonify({"status": "success", "data": data}), 200


@borrow_bp.route("/admin/approve", methods=["POST"])
@admin_required
def admin_approve():
    data = request.get_json(silent=True) or request.form
    borrow_id = data.get("borrow_id")
    if not borrow_id:
        return jsonify({"status": "failed", "message": "Thieu ma phieu muon."}), 400

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute(
            "SELECT id, user_id, status FROM borrows WHERE id = ?",
            (borrow_id,),
        ).fetchone()
        if not borrow or borrow["status"] != "pending":
            raise ValueError("Phieu muon khong ton tai hoac da duoc xu ly.")

        blacklist_entry = db.execute(
            """
            SELECT id
            FROM blacklist
            WHERE user_id = ?
              AND (banned_until IS NULL OR banned_until > CURRENT_TIMESTAMP)
            LIMIT 1
            """,
            (borrow["user_id"],),
        ).fetchone()
        if blacklist_entry:
            raise ValueError("Nguoi dung hien dang trong danh sach den.")

        items = db.execute(
            """
            SELECT bi.id, bi.book_id, b.title, COALESCE(b.available_for_borrow, 0) AS available_for_borrow
            FROM borrow_items bi
            JOIN books b ON b.id = bi.book_id
            WHERE bi.borrow_id = ?
            ORDER BY bi.id ASC
            """,
            (borrow_id,),
        ).fetchall()
        if not items:
            raise ValueError("Phieu muon khong co sach.")

        for item in items:
            if int(item["available_for_borrow"] or 0) <= 0:
                raise ValueError(f"Sach '{item['title']}' da het luot muon.")

        db.execute(
            """
            UPDATE borrows
            SET status = 'approved',
                approved_at = CURRENT_TIMESTAMP,
                pickup_deadline = DATETIME(CURRENT_TIMESTAMP, '+3 days')
            WHERE id = ?
            """,
            (borrow_id,),
        )
        db.execute("UPDATE borrow_items SET status = 'approved' WHERE borrow_id = ?", (borrow_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Da duyet phieu muon."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/admin/send", methods=["POST"])
@admin_required
def admin_send_book():
    data = request.get_json(silent=True) or request.form
    borrow_id = data.get("borrow_id")
    if not borrow_id:
        return jsonify({"status": "failed", "message": "Thieu ma phieu muon."}), 400

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute(
            "SELECT id, status FROM borrows WHERE id = ?",
            (borrow_id,),
        ).fetchone()
        if not borrow or borrow["status"] != "approved":
            raise ValueError("Chi co the gui sach voi phieu da duyet.")

        items = db.execute(
            """
            SELECT bi.id, bi.book_id, b.title, COALESCE(b.available_for_borrow, 0) AS available_for_borrow
            FROM borrow_items bi
            JOIN books b ON b.id = bi.book_id
            WHERE bi.borrow_id = ?
            ORDER BY bi.id ASC
            """,
            (borrow_id,),
        ).fetchall()
        if not items:
            raise ValueError("Phieu muon khong co sach.")

        for item in items:
            if int(item["available_for_borrow"] or 0) <= 0:
                raise ValueError(f"Sach '{item['title']}' da het luot muon.")

        for item in items:
            db.execute(
                "UPDATE books SET available_for_borrow = available_for_borrow - 1 WHERE id = ?",
                (item["book_id"],),
            )

        db.execute(
            "UPDATE borrows SET status = 'shipping', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
            (borrow_id,),
        )
        db.execute("UPDATE borrow_items SET status = 'shipping' WHERE borrow_id = ?", (borrow_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Admin da xac nhan gui sach."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/admin/reject", methods=["POST"])
@admin_required
def admin_reject():
    data = request.get_json(silent=True) or request.form
    borrow_id = data.get("borrow_id")
    if not borrow_id:
        return jsonify({"status": "failed", "message": "Thieu ma phieu muon."}), 400

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute("SELECT status FROM borrows WHERE id = ?", (borrow_id,)).fetchone()
        if not borrow or borrow["status"] != "pending":
            raise ValueError("Phieu muon khong ton tai hoac da duoc xu ly.")

        db.execute("UPDATE borrows SET status = 'canceled' WHERE id = ?", (borrow_id,))
        db.execute("UPDATE borrow_items SET status = 'rejected' WHERE borrow_id = ?", (borrow_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Da tu choi phieu muon."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/admin/check_overdue", methods=["POST"])
@admin_required
def admin_check_overdue():
    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        total = sync_overdue_borrows(db)
        db.commit()
        return jsonify({"status": "success", "message": f"Da cap nhat {total} sach qua han."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/admin/return", methods=["POST"])
@admin_required
def admin_confirm_return():
    data = request.get_json(silent=True) or request.form
    borrow_id = data.get("borrow_id")
    if not borrow_id:
        return jsonify({"status": "failed", "message": "Thieu ma phieu muon."}), 400

    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute("SELECT status FROM borrows WHERE id = ?", (borrow_id,)).fetchone()
        if not borrow:
            raise ValueError("Khong tim thay phieu muon.")
        if borrow["status"] not in ("borrowing", "overdue", "return_pending"):
            raise ValueError("Chi co the xac nhan tra voi phieu dang muon, qua han hoac da duoc yeu cau tra.")

        items = db.execute(
            """
            SELECT id, book_id
            FROM borrow_items
            WHERE borrow_id = ?
              AND status IN ('borrowing', 'overdue', 'return_pending')
            """,
            (borrow_id,),
        ).fetchall()
        if not items:
            raise ValueError("Khong con sach nao can tra.")

        for item in items:
            db.execute(
                "UPDATE borrow_items SET status = 'returned', return_date = CURRENT_TIMESTAMP WHERE id = ?",
                (item["id"],),
            )
            db.execute(
                "UPDATE books SET available_for_borrow = available_for_borrow + 1 WHERE id = ?",
                (item["book_id"],),
            )

        db.execute(
            "UPDATE borrows SET status = 'returned', returned_at = CURRENT_TIMESTAMP, confirmed_return_at = CURRENT_TIMESTAMP WHERE id = ?",
            (borrow_id,),
        )
        db.commit()
        return jsonify({"status": "success", "message": "Da xac nhan tra sach."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/user/confirm_pickup", methods=["POST"])
@login_required
def user_confirm_pickup():
    data = request.get_json(silent=True) or {}
    borrow_id = data.get("borrow_id")
    user_id = session.get("user_id")
    db = get_db()

    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute(
            "SELECT status, user_id FROM borrows WHERE id = ?",
            (borrow_id,),
        ).fetchone()
        if not borrow or borrow["user_id"] != user_id or borrow["status"] != "shipping":
            raise ValueError("Phieu muon khong hop le.")

        db.execute("UPDATE borrows SET status = 'borrowing', borrowed_at = CURRENT_TIMESTAMP WHERE id = ?", (borrow_id,))
        db.execute("UPDATE borrow_items SET status = 'borrowing' WHERE borrow_id = ?", (borrow_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Da xac nhan nhan sach."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/user/request-return", methods=["POST"])
@login_required
def user_request_return():
    data = request.get_json(silent=True) or {}
    borrow_id = data.get("borrow_id")
    user_id = session.get("user_id")
    db = get_db()

    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute(
            "SELECT status, user_id FROM borrows WHERE id = ?",
            (borrow_id,),
        ).fetchone()
        if not borrow or borrow["user_id"] != user_id:
            raise ValueError("Phieu muon khong hop le.")

        current_status = borrow["status"]
        if current_status not in ("borrowing", "overdue"):
            raise ValueError("Chi co the gui yeu cau tra khi sach dang duoc muon.")

        db.execute(
            "UPDATE borrows SET status = 'return_pending', return_requested_at = CURRENT_TIMESTAMP WHERE id = ?",
            (borrow_id,),
        )
        db.execute(
            "UPDATE borrow_items SET status = 'return_pending' WHERE borrow_id = ? AND status IN ('borrowing', 'overdue')",
            (borrow_id,),
        )
        db.commit()
        return jsonify({"status": "success", "message": "Da gui yeu cau tra sach cho admin."}), 200
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "failed", "message": str(exc)}), 400


@borrow_bp.route("/", methods=["GET"])
def borrow_ui():
    book_ids = request.args.get("books", "")
    selected_books = []

    if book_ids:
        try:
            id_list = [int(value.strip()) for value in book_ids.split(",") if value.strip()]
            if id_list:
                db = get_db()
                rows = db.execute(
                    f"""
                    SELECT
                        id,
                        title,
                        author,
                        price,
                        COALESCE(rent_price, 0) AS rent_price,
                        cover_image,
                        description,
                        COALESCE(available_for_borrow, 0) AS available_for_borrow
                    FROM books
                    WHERE id IN ({",".join(["?"] * len(id_list))})
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
                            "author": row["author"] or "",
                            "price": row["price"],
                            "rent_price": row["rent_price"],
                            "description": row["description"],
                            "available_for_borrow": int(row["available_for_borrow"] or 0),
                            "image": resolve_image_url(row["cover_image"]),
                        }
                    )
        except ValueError:
            selected_books = []

    return render_template("borrow.html", selected_books=selected_books)
