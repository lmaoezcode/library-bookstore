from flask import jsonify, request
from datetime import datetime, timedelta
from . import borrow_bp
from db.db import get_db
@borrow_bp.route('/',methods=['POST'])
def index():
    db=get_db()
    result=db.execute('select * from borrows')
    if result:
        borrow = [dict(row) for row in result]
        return jsonify({
            "status":"success",
            "borrow":borrow,
        }),200
    return jsonify({
        "status":"failed",
        "message":"Borrow operation failed"
    }),200
@borrow_bp.route('/item',methods=['POST'])
def get_item():
    data=request.get_json()
    borrow_id=data.get('borrow_id')

    db=get_db()
    result=db.execute('select * from borrow_items WHERE borrow_id=?',(borrow_id,))
    if result:
        borrow_item = [dict(row) for row in result]
        return jsonify({
            "status":"success",
            "borrow_item":borrow_item,
        }),200
    return jsonify({
        "status":"failed",
        "message":"Borrow operation failed"
    }),200
@borrow_bp.route('/create', methods=['POST'])
def create():
    db = get_db()
    data = request.get_json()

    user_id = data.get('user_id')
    total_deposit = data.get('total_deposit', 0)
    items = data.get('items', [])

    if not user_id or not items:
        return jsonify({
            "status": "failed",
            "message": "Missing user_id or items"
        }), 400

    try:
        db.execute("BEGIN")

        #11️Tạo phiếu mượn
        cursor = db.execute(
            "INSERT INTO borrows (user_id, total_deposit) VALUES (?, ?)",
            (user_id, total_deposit)
        )
        borrow_id = cursor.lastrowid

        # 2️Insert từng sách vào borrow_items
        for item in items:
            book_id = item.get("book_id")
            due_date = item.get("due_date")

            if not book_id or not due_date:
                raise Exception("Invalid item data")

            db.execute(
                """
                INSERT INTO borrow_items (borrow_id, book_id, due_date)
                VALUES (?, ?, ?)
                """,
                (borrow_id, book_id, due_date)
            )

        db.commit()

        return jsonify({
            "status": "success",
            "borrow_id": borrow_id
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "failed",
            "message": str(e)
        }), 500


@borrow_bp.route('/approve',methods=['POST'])
def approve():
    data = request.get_json()
    borrow_id = data.get('borrow_id')

    db = get_db()

    try:
        result = approve_borrow(db, borrow_id)

        return jsonify({
            "status": "success",
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "message": str(e)
        }), 400

def approve_borrow(conn, borrow_id, pickup_hours=48):
    try:
        conn.execute("BEGIN")

        # 1. Check borrow
        borrow = conn.execute(
            "SELECT status FROM borrows WHERE id=?",
            (borrow_id,)
        ).fetchone()

        if not borrow:
            raise Exception("Borrow not found")

        if borrow[0] != 'pending':
            raise Exception("Borrow is not pending")

        # 2. Lấy items
        items = conn.execute(
            "SELECT id, book_id FROM borrow_items WHERE borrow_id=?",
            (borrow_id,)
        ).fetchall()

        if not items:
            raise Exception("No borrow items found")

        item_results = []  # 👈 quan trọng

        # 3. Xử lý từng item
        for item_id, book_id in items:

            book = conn.execute(
                "SELECT available_quantity FROM books WHERE id=?",
                (book_id,)
            ).fetchone()

            if book and book[0] > 0:
                # trừ sách
                conn.execute(
                    "UPDATE books SET available_quantity = available_quantity - 1 WHERE id=?",
                    (book_id,)
                )

                status = "approved"
            else:
                status = "rejected"

            # update item
            conn.execute(
                "UPDATE borrow_items SET status=? WHERE id=?",
                (status, item_id)
            )

            # 👇 lưu kết quả chi tiết
            item_results.append({
                "item_id": item_id,
                "book_id": book_id,
                "status": status
            })

        # 4. Tính trạng thái tổng
        approved_count = sum(1 for i in item_results if i["status"] == "approved")
        rejected_count = len(item_results) - approved_count

        if approved_count == 0:
            borrow_status = 'canceled'
        elif rejected_count == 0:
            borrow_status = 'approved'
        else:
            borrow_status = 'partial'

        # 5. Update borrow
        pickup_deadline = datetime.now() + timedelta(hours=pickup_hours)

        conn.execute(
            """
            UPDATE borrows
            SET status=?,
                approved_at=CURRENT_TIMESTAMP,
                pickup_deadline=?
            WHERE id=?
            """,
            (borrow_status, pickup_deadline, borrow_id)
        )

        conn.commit()

        # 👇 RETURN CHUẨN API
        return {
            "borrow_id": borrow_id,
            "borrow_status": borrow_status,
            "items": item_results
        }

    except Exception as e:
        conn.rollback()
        raise e


