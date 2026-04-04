from flask import request, jsonify
from sqlite3 import IntegrityError
from . import order_bp
from db.db import get_db


@order_bp.route('/', methods=['POST'])
def order():
    db = get_db()
    result=db.execute("""SELECT
        o.id,
        o.user_id,
        u.name,
        o.total_price,
        o.payment_method,
        o.status
    FROM orders o
    JOIN users u ON u.id = o.user_id
    ORDER BY o.id DESC""").fetchall()
    if result:
        orders=[dict(row) for row in result]
        return jsonify({
            "status":"success",
            "orders":orders,
            "total":len(orders)
        }),200
    else:
        return jsonify({
            "status":"failed",
            "message":"no orders found"
        })

@order_bp.route('/create', methods=['POST'])
def create_order():
    data = request.get_json()

    user_id = data.get('user_id')
    address = data.get('address')
    phone = data.get('phone')
    payment_method = data.get('payment_method', 'COD')
    items = data.get('items', [])

    if not (user_id and address and phone and items):
        return jsonify({"status": "failed", "message": "Missing required fields"}), 400

    db = get_db()
    try:
        # --- 1️ Check tất cả sách tồn tại và có đủ available_quantity
        book_ids = [item['book_id'] for item in items]
        placeholders = ','.join(['?']*len(book_ids))
        query = f'SELECT id, title, available_quantity, price, promo_price FROM books WHERE id IN ({placeholders})'
        books = db.execute(query, book_ids).fetchall()
        books_dict = {b['id']: b for b in books}

        total_price = 0
        for item in items:
            book = books_dict.get(item['book_id'])
            if not book:
                return jsonify({"status": "failed", "message": f"Book ID {item['book_id']} not found"}), 400
            if item['quantity'] > book['available_quantity']:
                return jsonify({"status": "failed", "message": f"Book '{book['title']}' only has {book['available_quantity']} available"}), 400


        # --- 2️ Tính tổng tiền
        for item in items:
            book = books_dict.get(item['book_id'])
            if book['promo_price'] > 0:
                total_price += book['promo_price'] * item['quantity']
                continue
            total_price +=book['price'] * item['quantity']

        # --- 3️ Bắt đầu transaction
        db.execute("BEGIN")

        # Tạo order
        cur = db.execute(
            '''
            INSERT INTO orders (user_id, total_price, status, address, phone, payment_method)
            VALUES (?, ?, 'pending', ?, ?, ?)
            ''',
            (user_id, total_price, address, phone, payment_method)
        )
        order_id = cur.lastrowid

        # Tạo order_items và trừ available_quantity
        for item in items:
            book = books_dict[item['book_id']]
            if book['promo_price'] > 0:
                db.execute(
                    'INSERT INTO order_items (order_id, book_id, book_title, quantity, price) VALUES (?, ?, ?, ?, ?)',
                    (order_id, item['book_id'], book['title'], item['quantity'], book['promo_price'])
                )
            else:
                db.execute(
                    'INSERT INTO order_items (order_id, book_id, book_title, quantity, price) VALUES (?, ?, ?, ?, ?)',
                    (order_id, item['book_id'], book['title'], item['quantity'], book['price'])
                )
            # Update available_quantity
            db.execute(
                'UPDATE books SET available_quantity = available_quantity - ? WHERE id = ?',
                (item['quantity'], item['book_id'])
            )

        db.commit()

        return jsonify({
            "status": "success",
            "order_id": order_id,
            "total_price": total_price
        }), 201

    except IntegrityError as e:
        db.rollback()
        return jsonify({"status": "failed", "message": str(e)}), 400

    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": "Internal server error","error":e}), 500


@order_bp.route('/update_status', methods=['POST'])
def update_order_status():
    data = request.get_json()
    order_id = data.get('order_id')
    new_status = data.get('new_status')

    if not (order_id and new_status):
        return jsonify({"status": "failed", "message": "Missing order_id or new_status"}), 400

    db = get_db()
    try:
        order = db.execute('SELECT status FROM orders WHERE id = ?', (order_id,)).fetchone()
        if not order:
            return jsonify({"status": "failed", "message": "Order not found"}), 404

        current_status = order['status']

        # Kiểm tra transition hợp lệ
        valid_transitions = {
            'pending': ['processing', 'cancelled'],
            'processing': ['ready_to_ship', 'cancelled'],
            'ready_to_ship': ['shipping', 'cancelled'],
            'shipping': ['delivered', 'cancelled'],
            'delivered': [],
            'cancelled': []
        }

        if new_status not in valid_transitions[current_status]:
            return jsonify({
                "status": "failed",
                "message": f"Cannot change status from '{current_status}' to '{new_status}'"
            }), 400

        # Update status
        db.execute('UPDATE orders SET status = ? WHERE id = ?', (new_status, order_id))
        db.commit()

        return jsonify({
            "status": "success",
            "order_id": order_id,
            "old_status": current_status,
            "new_status": new_status
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"status": "failed", "message": "Internal server error", "error": str(e)}), 500