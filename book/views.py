import os
import sqlite3

from flask import abort, flash, jsonify, make_response, render_template, request, url_for

from db.db import get_db
from route.route import admin_required

from . import book_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "upload", "books")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def resolve_image_url(image):
    image = image or "default.jpg"
    if image.startswith("http://") or image.startswith("https://"):
        return image
    if image.startswith("static/"):
        return url_for("static", filename=image[len("static/"):])
    if image.startswith("upload/"):
        return url_for("static", filename=image)
    return url_for("static", filename=f"images/{image}")


@book_bp.route("/add", methods=["POST"])
def add_book():
    db = get_db()

    title = request.form.get("title")
    author = request.form.get("author")
    category_id = request.form.get("category_id")
    price = request.form.get("price", 0)

    if not title or not author:
        return jsonify({"status": "error", "message": "Thi\u1ebfu th\u00f4ng tin s\u00e1ch"}), 400

    pdf_file = request.files.get("pdf_file")
    preview_img = request.files.get("preview_file")
    cover_img = request.files.get("cover_image")

    pdf_path = None
    preview_path = None
    cover_path = None

    try:
        if pdf_file and allowed_file(pdf_file.filename):
            pdf_filename = f"pdf_{title.replace(' ', '_')}_{pdf_file.filename}"
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
            pdf_file.save(pdf_path)

        if preview_img and allowed_file(preview_img.filename):
            img_filename = f"prev_{title.replace(' ', '_')}_{preview_img.filename}"
            preview_path = os.path.join(UPLOAD_FOLDER, img_filename)
            preview_img.save(preview_path)

        if cover_img and allowed_file(cover_img.filename):
            img_filename = f"prev_{title.replace(' ', '_')}_{cover_img.filename}"
            cover_path = os.path.join(UPLOAD_FOLDER, img_filename)
            cover_img.save(cover_path)

        query = """
            INSERT INTO books (title, author, category_id, price, pdf_full, pdf_preview, cover_image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        db.execute(query, (title, author, category_id, price, pdf_path, preview_path, cover_path))
        db.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Th\u00eam s\u00e1ch v\u00e0 file th\u00e0nh c\u00f4ng!",
                "data": {
                    "pdf_url": pdf_path,
                    "preview_url": preview_path,
                    "cover_url": cover_path,
                },
            }
        ), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@book_bp.route("/list", methods=["GET"])
def list():
    db = get_db()
    result = db.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    books = [dict(row) for row in result]
    return jsonify({"status": "success", "books": books, "total": len(books)})


@book_bp.route("/<int:id>", methods=["GET"])
def book(id):
    db = get_db()
    result = db.execute("SELECT * FROM books WHERE id = ?", (id,)).fetchone()
    if result:
        return jsonify(dict(result))

    flash("Book not found")
    return jsonify({"status": "failed", "message": "book not found"}), 200


@book_bp.route("/search", methods=["POST"])
def search():
    search_text = request.form.get("search_text", "").strip()

    if not search_text:
        return jsonify({"status": "error", "message": "Vui l\u00f2ng nh\u1eadp t\u1eeb kh\u00f3a"}), 400

    db = get_db()
    query = "SELECT * FROM books WHERE title LIKE ? OR author LIKE ?"
    param = f"%{search_text}%"
    results = db.execute(query, (param, param)).fetchall()
    books = [dict(row) for row in results]

    return jsonify({"status": "success", "count": len(books), "data": books})


@book_bp.route("/searchI", methods=["POST"])
def searchI():
    search_text = request.form.get("search_text", "").strip()

    if not search_text:
        return jsonify({"status": "error", "message": "B\u1ea1n ch\u01b0a nh\u1eadp g\u00ec c\u1ea3!"}), 400

    db = get_db()
    query = """
        SELECT b.*, c.name as category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.title LIKE ? OR b.author LIKE ?
        ORDER BY b.id DESC
    """

    search_param = f"%{search_text}%"
    results = db.execute(query, (search_param, search_param)).fetchall()
    books = [dict(row) for row in results]

    return jsonify(
        {
            "status": "success",
            "keyword": search_text,
            "total": len(books),
            "data": books,
        }
    )


@book_bp.route("/update/<int:id>", methods=["PUT"])
def update_book(id):
    data = request.get_json()
    db = get_db()

    book_row = db.execute("SELECT * FROM books WHERE id = ?", (id,)).fetchone()
    if not book_row:
        return jsonify({"status": "error", "message": "Kh\u00f4ng t\u00ecm th\u1ea5y s\u00e1ch \u0111\u1ec3 c\u1eadp nh\u1eadt"}), 404

    title = data.get("title", book_row["title"])
    author = data.get("author", book_row["author"])
    category_id = data.get("category_id", book_row["category_id"])
    price = data.get("price", book_row["price"])

    try:
        db.execute(
            "UPDATE books SET title = ?, author = ?, category_id = ?, price = ? WHERE id = ?",
            (title, author, category_id, price, id),
        )
        db.commit()
        return jsonify({"status": "success", "message": f"\u0110\u00e3 c\u1eadp nh\u1eadt s\u00e1ch ID {id}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@book_bp.route("/delete/<int:id>", methods=["DELETE"])
@admin_required
def delete_book(id):
    db = get_db()

    book_row = db.execute("SELECT * FROM books WHERE id = ?", (id,)).fetchone()
    if not book_row:
        return jsonify({"status": "error", "message": "S\u00e1ch kh\u00f4ng t\u1ed3n t\u1ea1i"}), 404

    try:
        db.execute("DELETE FROM books WHERE id = ?", (id,))
        db.commit()
        return jsonify({"status": "success", "message": f"\u0110\u00e3 x\u00f3a v\u0129nh vi\u1ec5n s\u00e1ch ID {id}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@book_bp.route("/delete-many", methods=["POST"])
@admin_required
def delete_many_books():
    db = get_db()

    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("book_ids") or request.form.getlist("book_ids")

    try:
        book_ids = sorted({int(book_id) for book_id in raw_ids})
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Danh sách sách không hợp lệ"}), 400

    if not book_ids:
        return jsonify({"status": "error", "message": "Chưa chọn sách để xóa"}), 400

    placeholders = ", ".join(["?"] * len(book_ids))
    existing_rows = db.execute(
        f"SELECT id FROM books WHERE id IN ({placeholders})",
        book_ids,
    ).fetchall()
    existing_ids = {row["id"] for row in existing_rows}

    if len(existing_ids) != len(book_ids):
        return jsonify({"status": "error", "message": "Có sách không còn tồn tại"}), 404

    try:
        db.execute(f"DELETE FROM books WHERE id IN ({placeholders})", book_ids)
        db.commit()
        return jsonify(
            {
                "status": "success",
                "message": f"Đã xóa {len(book_ids)} sách đã chọn",
                "deleted_ids": book_ids,
            }
        )
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@book_bp.route("", methods=["GET"])
@book_bp.route("/", methods=["GET"])
@book_bp.route("/all", methods=["GET"])
def books_ui():
    db = get_db()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    search_text = request.args.get("search_text", "").strip()
    selected_categories = [value for value in request.args.getlist("category_id") if value.strip()]
    selected_author = request.args.get("author", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort", "newest").strip() or "newest"

    conditions = ["(b.available_for_sale > 0 OR b.available_for_borrow > 0)"]
    params = []

    if search_text:
        conditions.append("(b.title LIKE ? OR b.author LIKE ?)")
        keyword = f"%{search_text}%"
        params.extend([keyword, keyword])

    if selected_categories:
        placeholders = ", ".join(["?"] * len(selected_categories))
        conditions.append(f"b.category_id IN ({placeholders})")
        params.extend(selected_categories)

    if selected_author:
        conditions.append("b.author = ?")
        params.append(selected_author)

    max_price = None
    if max_price_raw:
        try:
            max_price = max(0, int(max_price_raw))
            conditions.append("b.price <= ?")
            params.append(max_price)
        except ValueError:
            max_price = None

    sort_options = {
        "newest": "b.id DESC",
        "price_asc": "b.price ASC, b.id DESC",
        "price_desc": "b.price DESC, b.id DESC",
        "title_asc": "b.title COLLATE NOCASE ASC, b.id DESC",
    }
    order_by = sort_options.get(sort_by, sort_options["newest"])

    query = f"""
        SELECT
            b.id,
            b.title,
            b.author,
            b.price,
            b.cover_image,
            b.description,
            b.available_for_sale,
            b.available_for_borrow,
            b.category_id,
            c.name AS category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
    """
    rows = cursor.execute(query, params).fetchall()

    categories = cursor.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()
    authors = cursor.execute(
        """
        SELECT DISTINCT author
        FROM books
        WHERE author IS NOT NULL AND TRIM(author) != ''
        ORDER BY author COLLATE NOCASE
        """
    ).fetchall()

    price_bounds = cursor.execute(
        """
        SELECT
            COALESCE(MIN(price), 0) AS min_price,
            COALESCE(MAX(price), 0) AS max_price
        FROM books
        WHERE available_for_sale > 0 OR available_for_borrow > 0
        """
    ).fetchone()

    default_max_price = int(price_bounds["max_price"] or 0)
    current_max_price = max_price if max_price is not None else default_max_price

    danh_sach_sach = []
    for row in rows:
        danh_sach_sach.append(
            {
                "id": row["id"],
                "title": row["title"],
                "author": row["author"] or "Ch\u01b0a r\u00f5 t\u00e1c gi\u1ea3",
                "price": row["price"],
                "price_display": "{:,.0f}\u0111".format(row["price"] if row["price"] else 0).replace(",", "."),
                "description": row["description"][:150] + "..." if row["description"] else "",
                "image": resolve_image_url(row["cover_image"]),
                "available_for_sale": row["available_for_sale"],
                "available_for_borrow": row["available_for_borrow"],
                "category_name": row["category_name"] or "Ch\u01b0a ph\u00e2n lo\u1ea1i",
            }
        )

    return render_template(
        "books.html",
        danh_sach_sach=danh_sach_sach,
        search_text=search_text,
        categories=categories,
        authors=authors,
        selected_categories={str(value) for value in selected_categories},
        selected_author=selected_author,
        max_price=current_max_price,
        default_max_price=default_max_price,
        min_price=int(price_bounds["min_price"] or 0),
        sort_by=sort_by,
    )


@book_bp.route("/<int:book_id>/detail", methods=["GET"])
def books_detail_ui(book_id):
    db = get_db()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.price,
            b.cover_image,
            b.description,
            b.available_for_sale,
            b.available_for_borrow,
            c.name AS category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.id = ?
        """,
        (book_id,),
    )
    book_row = cursor.fetchone()

    if not book_row:
        abort(404)

    book_data = {
        "id": book_row["id"],
        "title": book_row["title"],
        "author": book_row["author"],
        "price": book_row["price"],
        "price_display": "{:,.0f}\u0111".format(book_row["price"] if book_row["price"] else 0).replace(",", "."),
        "description": book_row["description"] or "",
        "image": resolve_image_url(book_row["cover_image"]),
        "image_url": resolve_image_url(book_row["cover_image"]),
        "available_for_sale": book_row["available_for_sale"],
        "available_for_borrow": book_row["available_for_borrow"],
        "category_name": book_row["category_name"] or "Ch\u01b0a ph\u00e2n lo\u1ea1i",
    }

    back_url = request.args.get("next", "").strip()
    if not back_url.startswith("/book"):
        back_url = url_for("book.books_ui")

    response = make_response(render_template("book-detail.html", book=book_data, back_url=back_url))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
