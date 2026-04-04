from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import sqlite3
from db.db import get_db

app = Flask(__name__)
app.secret_key = "secret123"


# ================= HELPER =================
def get_cart_items(user_id):
    """Lấy danh sách sản phẩm trong giỏ hàng theo user_id"""
    db = get_db()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    cursor.execute("""
        SELECT b.id, b.title, b.price, b.cover_image, ci.quantity
        FROM cart_items ci
        JOIN books b ON b.id = ci.book_id
        WHERE ci.user_id = ?
    """, (user_id,))
    return cursor.fetchall()


# ================= ROUTES =================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/books")
def books():
    # Hiển thị danh sách sách từ DB
    db = get_db()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    cursor.execute("SELECT id, title, price, cover_image FROM books")
    books_list = cursor.fetchall()
    return render_template("books.html", books=books_list)


# ================= VIEW CART =================
@app.route("/cart")
def view_cart():
    user_id = session.get('user_id', 1)
    rows = get_cart_items(user_id)  # lấy từ DB

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "title": row["title"],
            "price": row["price"],
            "quantity": row["quantity"],
            "image": f"images/{row['cover_image'] or 'default.jpg'}"
        })

    subtotal = sum(float(item["price"]) * item["quantity"] for item in items)
    shipping_fee = 20000 if items else 0
    total = subtotal + shipping_fee

    return render_template("cart.html", items=items, subtotal=subtotal, shipping=shipping_fee, total=total)


# ================= ADD TO CART =================
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    book_id = data.get("id")
    user_id = session.get("user_id", 1)  # demo, có thể lấy từ login

    db = get_db()
    cursor = db.cursor()

    # Kiểm tra đã có trong giỏ chưa
    cursor.execute("SELECT quantity FROM cart_items WHERE book_id = ? AND user_id = ?", (book_id, user_id))
    item = cursor.fetchone()

    if item:
        cursor.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE book_id = ? AND user_id = ?", (book_id, user_id))
    else:
        cursor.execute("INSERT INTO cart_items (book_id, user_id, quantity) VALUES (?, ?, ?)", (book_id, user_id, 1))

    db.commit()
    return jsonify({"status": "success", "message": "Đã thêm vào giỏ hàng"})

# ================= UPDATE QUANTITY =================
@app.route("/update_cart", methods=["POST"])
def update_cart():
    book_id = request.form.get("book_id")
    quantity = int(request.form.get("quantity", 1))
    user_id = session.get('user_id', 1)

    db = get_db()
    cursor = db.cursor()

    if quantity > 0:
        cursor.execute(
            "UPDATE cart_items SET quantity = ? WHERE book_id = ? AND user_id = ?",
            (quantity, book_id, user_id)
        )
    else:
        cursor.execute(
            "DELETE FROM cart_items WHERE book_id = ? AND user_id = ?",
            (book_id, user_id)
        )

    db.commit()
    return redirect(url_for("view_cart"))


# ================= REMOVE ITEM =================
@app.route("/remove_from_cart/<int:book_id>", methods=["POST"])
def remove_from_cart(book_id):
    user_id = session.get('user_id', 1)
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM cart_items WHERE book_id = ? AND user_id = ?", (book_id, user_id))
    db.commit()
    return redirect(url_for("view_cart"))


if __name__ == "__main__":
    app.run(debug=True)