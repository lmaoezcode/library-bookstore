from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
import sqlite3
from route.route import login_required, admin_required

borrow_bp = Blueprint('borrow', __name__, url_prefix='/borrow')

def get_db():
    conn = sqlite3.connect('db/library.sqlite')
    conn.row_factory = sqlite3.Row
    return conn

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
