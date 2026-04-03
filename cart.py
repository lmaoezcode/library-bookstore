from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
app.secret_key = "secret123"


# ================= HOME =================
@app.route("/")
def home():
    return render_template("index.html")


# ================= ABOUT =================
@app.route("/about")
def about():
    return render_template("about.html")


# ================= CONTACT =================
@app.route("/contact")
def contact():
    return render_template("contact.html")


# ================= BOOKS =================
@app.route("/books")
def books():
    return render_template("books.html")


# ================= ACCOUNT =================
@app.route("/account")
def account():
    return render_template("my-account.html")


# ================= WISHLIST =================
@app.route("/wishlist")
def wishlist():
    return render_template("wishlist.html")


# ================= CART DATA (GIẢ LẬP) =================
cart = [
    {
        "id": 1,
        "title": "Book 1",
        "publisher": "NXB A",
        "price": 100000,
        "quantity": 1,
        "image": "images/book1.png"
    },
    {
        "id": 2,
        "title": "Book 2",
        "publisher": "NXB B",
        "price": 150000,
        "quantity": 2,
        "image": "images/book2.png"
    }
]


# ================= VIEW CART =================

from db.db import get_db
import sqlite3

@app.route("/cart")
def view_cart():
    db = get_db()
    db.row_factory = sqlite3.Row  # QUAN TRỌNG
    cursor = db.cursor()

    # 👉 JOIN cart_items với books
    cursor.execute("""
        SELECT 
            b.id,
            b.title,
            b.price,
            b.cover_image,
            ci.quantity
        FROM cart_items ci
        JOIN books b ON b.id = ci.book_id
    """)

    rows = cursor.fetchall()

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "title": row["title"],
            "price": row["price"],
            "quantity": row["quantity"],
            "image": f"images/{row['cover_image'] or 'default.jpg'}"
        })

    subtotal = sum(item["price"] * item["quantity"] for item in items)
    shipping_fee = 20000
    total = subtotal + shipping_fee

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        shipping=shipping_fee,
        total=total
    )

# ================= UPDATE CART =================
@app.route("/update_cart", methods=["POST"])
def update_cart():
    book_id = int(request.form.get("book_id"))
    quantity = int(request.form.get("quantity"))

    for item in cart:
        if item["id"] == book_id:
            item["quantity"] = quantity

    return redirect(url_for("view_cart"))


# ================= REMOVE =================
@app.route("/remove_from_cart/<int:book_id>", methods=["POST"])
def remove_from_cart(book_id):
    global cart
    cart = [item for item in cart if item["id"] != book_id]

    return redirect(url_for("view_cart"))


# ================= CHECKOUT =================
@app.route("/checkout", methods=["POST"])
def checkout():
    return "Checkout thành công!"


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)