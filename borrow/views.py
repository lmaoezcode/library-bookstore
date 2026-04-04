from flask import request, jsonify, session, render_template
from datetime import datetime, timedelta
import sqlite3
from route.route import login_required, admin_required
from . import borrow_bp

def get_db():
    conn = sqlite3.connect('db/library.sqlite')
    conn.row_factory = sqlite3.Row
    return conn

@borrow_bp.route('/')
def borrow():
    book_ids = request.args.get('books', '')
    selected_books = []
    if book_ids:
        try:
            id_list = [int(i.strip()) for i in book_ids.split(',')]
            db = get_db()
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            query = f"SELECT id, title, author, price, rent_price, cover_image, description FROM books WHERE id IN ({','.join(['?']*len(id_list))})"
            cursor.execute(query, id_list)
            selected_books = cursor.fetchall()
        except ValueError:
            pass
    return render_template('borrow.html', selected_books=selected_books)


@borrow_bp.route('/list', methods=['POST'])
def list_all_borrows():
    db = get_db()

    borrows = db.execute("""
        SELECT b.*, u.name as user_name
        FROM borrows b
        LEFT JOIN users u ON b.user_id = u.id
        ORDER BY b.created_at DESC
    """).fetchall()

    result = []

    for b in borrows:
        items = db.execute("""
            SELECT bi.*, bk.title
            FROM borrow_items bi
            JOIN books bk ON bi.book_id = bk.id
            WHERE bi.borrow_id = ?
        """, (b['id'],)).fetchall()

        result.append({
            "borrow": dict(b),
            "items": [dict(i) for i in items]
        })

    return jsonify(result)

@borrow_bp.route('/create', methods=['POST'])
@login_required
def create_borrow():
    data = request.get_json()
    book_ids = data.get('book_ids', [])

    if not book_ids:
        return jsonify({"status": "failed", "message": "Vui lòng chọn ít nhất 1 quyển sách"}), 400

    user_id = session.get('user_id')
    db = get_db()
    
    try:
        db.execute("BEGIN TRANSACTION")

        cursor = db.execute(
            "INSERT INTO borrows (user_id, status) VALUES (?, ?)", 
            (user_id, 'pending')
        )
        borrow_id = cursor.lastrowid
        
        due_date = datetime.now() + timedelta(days=14)

        for book_id in book_ids:
            book = db.execute("SELECT title, available_quantity FROM books WHERE id = ?", (book_id,)).fetchone()
            
            if not book:
                raise Exception(f"Sách ID {book_id} không tồn tại.")
            if book['available_quantity'] <= 0:
                raise Exception(f"Sách '{book['title']}' đã hết hàng.")

            db.execute(
                "UPDATE books SET available_quantity = available_quantity - 1 WHERE id = ?", 
                (book_id,)
            )

            db.execute(
                "INSERT INTO borrow_items (borrow_id, book_id, due_date, status) VALUES (?, ?, ?, ?)",
                (borrow_id, book_id, due_date.strftime('%Y-%m-%d %H:%M:%S'), 'pending')
            )

        db.commit()
        return jsonify({"status": "success", "message": "Tạo phiếu mượn thành công!", "borrow_id": borrow_id}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400

@borrow_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    user_id = session.get('user_id')
    db = get_db()
    
    borrows = db.execute("SELECT * FROM borrows WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    
    result = []
    for b in borrows:
        items = db.execute(
            "SELECT bi.*, bk.title FROM borrow_items bi JOIN books bk ON bi.book_id = bk.id WHERE bi.borrow_id = ?", 
            (b['id'],)
        ).fetchall()
        
        result.append({
            "borrow_id": b['id'],
            "status": b['status'],
            "created_at": b['created_at'],
            "items": [dict(item) for item in items]
        })
        
    return jsonify({"status": "success", "data": result}), 200

@borrow_bp.route('/admin/list', methods=['GET'])
@admin_required
def admin_get_all():
    db = get_db()
    borrows = db.execute("SELECT * FROM borrows ORDER BY created_at DESC").fetchall()
    return jsonify({"status": "success", "data": [dict(b) for b in borrows]}), 200

@borrow_bp.route('/admin/approve', methods=['POST'])
@admin_required
def admin_approve():
    data = request.get_json()
    borrow_id = data.get('borrow_id')
    
    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        borrow = db.execute("SELECT status FROM borrows WHERE id = ?", (borrow_id,)).fetchone()
        
        if not borrow or borrow['status'] != 'pending':
            raise Exception("Phiếu mượn không tồn tại hoặc đã được xử lý.")

        db.execute("UPDATE borrows SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?", (borrow_id,))
        db.execute("UPDATE borrow_items SET status = 'approved' WHERE borrow_id = ?", (borrow_id,))
        
        db.commit()
        return jsonify({"status": "success", "message": "Đã duyệt phiếu mượn."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400

@borrow_bp.route('/admin/return_item', methods=['POST'])
@admin_required
def admin_return_item():
    data = request.get_json()
    item_id = data.get('item_id')
    
    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        item = db.execute("SELECT book_id, status, borrow_id FROM borrow_items WHERE id = ?", (item_id,)).fetchone()
        
        if not item:
            raise Exception("Không tìm thấy dữ liệu mượn sách này.")
        if item['status'] == 'returned':
            raise Exception("Sách này đã được trả.")
            
        book_id, borrow_id = item['book_id'], item['borrow_id']

        db.execute("UPDATE borrow_items SET status = 'returned', return_date = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        db.execute("UPDATE books SET available_quantity = available_quantity + 1 WHERE id = ?", (book_id,))
        
        remaining = db.execute("SELECT COUNT(*) FROM borrow_items WHERE borrow_id = ? AND status != 'returned'", (borrow_id,)).fetchone()[0]
        if remaining == 0:
            db.execute("UPDATE borrows SET status = 'returned', returned_at = CURRENT_TIMESTAMP WHERE id = ?", (borrow_id,))

        db.commit()
        return jsonify({"status": "success", "message": "Xác nhận trả sách thành công, đã cập nhật tồn kho."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400



@borrow_bp.route('/update_status', methods=['POST'])
def update_status():
    data = request.get_json()
    borrow_id = data.get('borrow_id')
    new_status = data.get('new_status')

    db = get_db()

    try:
        result = update_borrow_status(db, borrow_id, new_status)

        return jsonify({
            "status": "success",
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "message": str(e)
        }), 400

def update_borrow_status(conn, borrow_id, new_status, pickup_hours=48):
    try:
        conn.execute("BEGIN")

        # 1. Check borrow
        borrow = conn.execute(
            "SELECT status FROM borrows WHERE id=?",
            (borrow_id,)
        ).fetchone()

        if not borrow:
            raise Exception("Borrow not found")

        current_status = borrow[0]
        if current_status == "canceled":
            raise Exception("Canceled borrow cannot be updated")
        # 2. Lấy items
        items = conn.execute(
            "SELECT id, book_id, status FROM borrow_items WHERE borrow_id=?",
            (borrow_id,)
        ).fetchall()

        if not items:
            raise Exception("No borrow items found")

        item_results = []

        # =========================
        # CASE 1: APPROVE (giữ nguyên logic)
        # =========================
        if new_status == "approved":

            if current_status != "pending":
                raise Exception("Only pending borrow can be approved")

            for item_id, book_id, _ in items:

                book = conn.execute(
                    "SELECT available_quantity FROM books WHERE id=?",
                    (book_id,)
                ).fetchone()

                if book and book[0] > 0:
                    conn.execute(
                        "UPDATE books SET available_quantity = available_quantity - 1 WHERE id=?",
                        (book_id,)
                    )
                    status = "approved"
                else:
                    status = "rejected"

                conn.execute(
                    "UPDATE borrow_items SET status=? WHERE id=?",
                    (status, item_id)
                )

                item_results.append({
                    "item_id": item_id,
                    "book_id": book_id,
                    "status": status
                })

            approved_count = sum(1 for i in item_results if i["status"] == "approved")
            rejected_count = len(item_results) - approved_count

            if approved_count == 0:
                borrow_status = 'canceled'
            elif rejected_count == 0:
                borrow_status = 'approved'
            else:
                borrow_status = 'partial'

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

        # =========================
        # CASE 2: RETURNED (CỘNG LẠI SÁCH)
        # =========================
        elif new_status == "returned":

            if current_status not in ["borrowing"]:
                raise Exception("Only borrowing can be returned")

            for item_id, book_id, item_status in items:

                # chỉ cộng lại những item đã được duyệt
                if item_status == "approved":
                    conn.execute(
                        "UPDATE books SET available_quantity = available_quantity + 1 WHERE id=?",
                        (book_id,)
                    )

                conn.execute(
                    "UPDATE borrow_items SET status='returned', return_date=CURRENT_TIMESTAMP WHERE id=?",
                    (item_id,)
                )

                item_results.append({
                    "item_id": item_id,
                    "book_id": book_id,
                    "status": "returned"
                })

            conn.execute(
                """
                UPDATE borrows
                SET status='returned',
                    returned_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (borrow_id,)
            )

            borrow_status = "returned"

        # =========================
        # CASE 3: OTHER STATUS
        # =========================
        else:
            conn.execute(
                "UPDATE borrows SET status=? WHERE id=?",
                (new_status, borrow_id)
            )

            borrow_status = new_status

        conn.commit()

        return {
            "borrow_id": borrow_id,
            "borrow_status": borrow_status,
            "items": item_results
        }

    except Exception as e:
        conn.rollback()
        raise e

