from flask import jsonify, redirect, render_template, request, session, url_for

from . import cart_bp
from db.db import get_db


def resolve_image_url(image):
    image = image or "default.jpg"
    if image.startswith("http://") or image.startswith("https://"):
        return image
    if image.startswith("static/"):
        return url_for("static", filename=image[len("static/"):])
    if image.startswith("upload/"):
        return url_for("static", filename=image)
    return url_for("static", filename=f"images/{image}")


def ensure_cart():
    if "cart_id" in session:
        return session["cart_id"]

    db = get_db()
    cursor = db.cursor()
    user_id = session.get("user_id", 1)
    cursor.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
    db.commit()
    session["cart_id"] = cursor.lastrowid
    return session["cart_id"]


def get_cart_items(cart_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.price,
            b.cover_image,
            b.available_for_sale,
            ci.quantity
        FROM cart_items ci
        JOIN books b ON b.id = ci.book_id
        WHERE ci.cart_id = ?
        ORDER BY ci.id DESC
        """,
        (cart_id,),
    )
    return cursor.fetchall()


@cart_bp.route("/cart")
def view_cart():
    cart_id = ensure_cart()
    rows = get_cart_items(cart_id)

    items = []
    for row in rows:
        price = float(row["price"] or 0)
        quantity = int(row["quantity"] or 0)
        items.append(
            {
                "id": row["id"],
                "title": row["title"],
                "author": row["author"] or "Chưa rõ tác giả",
                "price": price,
                "price_display": "{:,.0f}đ".format(price).replace(",", "."),
                "quantity": quantity,
                "line_total": price * quantity,
                "line_total_display": "{:,.0f}đ".format(price * quantity).replace(",", "."),
                "available_for_sale": row["available_for_sale"],
                "image": resolve_image_url(row["cover_image"]),
            }
        )

    subtotal = sum(item["line_total"] for item in items)
    shipping_fee = 20000 if items else 0
    total = subtotal + shipping_fee

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        subtotal_display="{:,.0f}đ".format(subtotal).replace(",", "."),
        shipping=shipping_fee,
        shipping_display="{:,.0f}đ".format(shipping_fee).replace(",", "."),
        total=total,
        total_display="{:,.0f}đ".format(total).replace(",", "."),
    )


@cart_bp.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    wants_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    data = request.get_json(silent=True) if request.is_json else None
    book_id = (data or {}).get("id") if request.is_json else request.form.get("book_id")
    quantity = (data or {}).get("quantity", 1) if request.is_json else request.form.get("quantity", 1)

    try:
        book_id = int(book_id)
        quantity = max(1, int(quantity))
    except (TypeError, ValueError):
        message = "Dữ liệu giỏ hàng không hợp lệ."
        if wants_json:
            return jsonify({"status": "error", "message": message}), 400
        return redirect(url_for("cart.view_cart"))

    cart_id = ensure_cart()
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id, title, price, available_for_sale
        FROM books
        WHERE id = ?
        """,
        (book_id,),
    )
    book = cursor.fetchone()

    if not book:
        message = "Không tìm thấy sách."
        if wants_json:
            return jsonify({"status": "error", "message": message}), 404
        return redirect(url_for("cart.view_cart"))

    if quantity > int(book["available_for_sale"] or 0):
        message = "Số lượng vượt quá tồn kho hiện tại."
        if wants_json:
            return jsonify({"status": "error", "message": message}), 400
        return redirect(url_for("cart.view_cart"))

    cursor.execute("SELECT quantity FROM cart_items WHERE book_id = ? AND cart_id = ?", (book_id, cart_id))
    item = cursor.fetchone()

    if item:
        new_quantity = min(int(item["quantity"]) + quantity, int(book["available_for_sale"] or 0))
        cursor.execute(
            "UPDATE cart_items SET quantity = ? WHERE book_id = ? AND cart_id = ?",
            (new_quantity, book_id, cart_id),
        )
    else:
        cursor.execute(
            "INSERT INTO cart_items (book_id, cart_id, quantity) VALUES (?, ?, ?)",
            (book_id, cart_id, quantity),
        )

    db.commit()

    if wants_json:
        cart_count = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE cart_id = ?",
            (cart_id,),
        ).fetchone()[0]
        return jsonify(
            {
                "status": "success",
                "message": "Đã thêm vào giỏ hàng",
                "cart_count": int(cart_count or 0),
            }
        )
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/update_cart", methods=["POST"])
def update_cart():
    cart_id = ensure_cart()
    book_id = request.form.get("book_id")
    quantity = request.form.get("quantity", 1)

    try:
        book_id = int(book_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return redirect(url_for("cart.view_cart"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT available_for_sale FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if not book:
        return redirect(url_for("cart.view_cart"))

    if quantity <= 0:
        cursor.execute("DELETE FROM cart_items WHERE book_id = ? AND cart_id = ?", (book_id, cart_id))
    else:
        quantity = min(quantity, int(book["available_for_sale"] or 0))
        cursor.execute(
            "UPDATE cart_items SET quantity = ? WHERE book_id = ? AND cart_id = ?",
            (quantity, book_id, cart_id),
        )

    db.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/remove_from_cart/<int:book_id>", methods=["POST"])
def remove_from_cart(book_id):
    cart_id = ensure_cart()
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE book_id = ? AND cart_id = ?", (book_id, cart_id))
    db.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/remove_selected", methods=["POST"])
def remove_selected():
    cart_id = ensure_cart()
    selected_ids = request.form.getlist("selected_book_ids")

    try:
        selected_ids = [int(book_id) for book_id in selected_ids]
    except ValueError:
        return redirect(url_for("cart.view_cart"))

    if selected_ids:
        db = get_db()
        placeholders = ",".join(["?"] * len(selected_ids))
        db.execute(
            f"DELETE FROM cart_items WHERE cart_id = ? AND book_id IN ({placeholders})",
            [cart_id, *selected_ids],
        )
        db.commit()

    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/clear", methods=["POST"])
def clear_cart():
    cart_id = ensure_cart()
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
    db.commit()
    return redirect(url_for("cart.view_cart"))
