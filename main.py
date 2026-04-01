from flask import Flask, session, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'devomate_secret_key_2026'  # Để mã hóa Session

# Kết nối Database (Trỏ đúng vào file .db của nhóm)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bookstore.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- MODELS PHẦN C ---
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # Lấy từ phần Auth của bạn B
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    book_id = db.Column(db.Integer, nullable=False)  # Liên kết ID sách của bạn B
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
@app.route('/')
def home():
    return redirect(url_for('view_cart'))

@app.route('/account')
def account():
    return "Account Page"

@app.route('/wishlist')
def wishlist():
    return "Wishlist Page"

@app.route('/books')
def books():
    return "Books Page"

@app.route('/contact')
def contact():
    return "Contact Page"

@app.route('/about')
def about():
    return "<h1>About Page</h1>"
# --- ROUTES & API PHẦN C ---

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_display = []
    subtotal = 0
    shipping_fee = 50

    for bid_str, qty in cart.items():
        # Lấy thông tin từ bảng 'book' của bạn B
        book = db.session.execute(f"SELECT * FROM book WHERE id={bid_str}").fetchone()
        if book:
            item_total = book.price * qty
            subtotal += item_total
            cart_display.append({
                "id": book.id,
                "title": book.title,
                "publisher": getattr(book, 'publisher', 'N/A'),  # Nếu B chưa có cột publisher thì hiện N/A
                "price": book.price,
                "image": book.image_url,
                "quantity": qty,
                "item_total": item_total
            })

    total = subtotal + shipping_fee if subtotal > 0 else 0
    return render_template('cart.html', items=cart_display, subtotal=subtotal, shipping=shipping_fee, total=total)


@app.route('/cart/update', methods=['POST'])
def update_cart():
    data = request.json
    bid = str(data.get('book_id'))
    qty = int(data.get('quantity'))

    cart = session.get('cart', {})
    if bid in cart:
        if qty > 0:
            cart[bid] = qty
        else:
            cart.pop(bid)
    session['cart'] = cart
    session.modified = True
    return jsonify({"success": True})


@app.route('/cart/remove/<int:book_id>', methods=['POST'])
def remove_from_cart(book_id):
    cart = session.get('cart', {})
    cart.pop(str(book_id), None)
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart: return redirect(url_for('view_cart'))

    try:
        # Giả định user_id = 1 từ phần Login
        new_order = Order(user_id=1, total_price=0)
        db.session.add(new_order)
        db.session.flush()

        final_total = 0
        for bid, qty in cart.items():
            book = db.session.execute(f"SELECT price, stock FROM book WHERE id={bid}").fetchone()
            if not book or book.stock < qty:
                raise Exception(f"Sách ID {bid} không đủ tồn kho")

            # Trừ tồn kho trong bảng của bạn B
            db.session.execute(f"UPDATE book SET stock = stock - {qty} WHERE id = {bid}")

            item = OrderItem(order_id=new_order.id, book_id=int(bid), price=book.price, quantity=qty)
            final_total += (book.price * qty)
            db.session.add(item)

        new_order.total_price = final_total + 50  # Cộng phí ship
        db.session.commit()
        session.pop('cart', None)
        return "<h1>Đặt hàng thành công!</h1><a href='/'>Quay lại trang chủ</a>"
    except Exception as e:
        db.session.rollback()
        return f"Lỗi: {str(e)}"


if __name__ == '__main__':
    app.run(debug=True)