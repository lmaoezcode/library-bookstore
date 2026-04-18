import os
from urllib.parse import unquote

from flask import flash, jsonify, redirect, render_template, request, url_for

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
    if image.startswith(("http://", "https://")):
        return image
    if image.startswith("static/"):
        return url_for("static", filename=image[len("static/"):])
    if image.startswith("upload/"):
        return url_for("static", filename=image)
    return url_for("static", filename=f"images/{image}")


def build_book_card(row):
    description = (row["description"] or "").strip()
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"] or "Chua ro tac gia",
        "price": float(row["price"] or 0),
        "price_display": "{:,.0f}d".format(float(row["price"] or 0)).replace(",", "."),
        "description": (description[:150] + "...") if len(description) > 150 else description,
        "image": resolve_image_url(row["cover_image"]),
        "image_url": resolve_image_url(row["cover_image"]),
        "available_for_sale": int(row["available_for_sale"] or 0),
        "available_for_borrow": int(row["available_for_borrow"] or 0),
        "category_name": row["category_name"] or "Chua phan loai",
        "rent_price": float(row["rent_price"] or 0),
    }


def fetch_book_detail(book_id):
    db = get_db()
    return db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.description,
            b.price,
            COALESCE(b.rent_price, 0) AS rent_price,
            b.cover_image,
            COALESCE(b.available_for_sale, 0) AS available_for_sale,
            COALESCE(b.available_for_borrow, 0) AS available_for_borrow,
            COALESCE(c.name, 'Chua phan loai') AS category_name
        FROM books b
        LEFT JOIN categories c ON c.id = b.category_id
        WHERE b.id = ?
        """,
        (book_id,),
    ).fetchone()


@book_bp.route("/add", methods=["POST"])
@admin_required
def add_book():
    db = get_db()

    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    category_id = request.form.get("category_id")
    price = request.form.get("price", 0)
    rent_price = request.form.get("rent_price", 0)
    description = request.form.get("description", "").strip()
    available_for_sale = request.form.get("available_for_sale", 0)
    available_for_borrow = request.form.get("available_for_borrow", 0)

    if not title or not author:
        return jsonify({"status": "error", "message": "Thieu thong tin sach."}), 400

    cover_img = request.files.get("cover_image")
    cover_path = None

    try:
        if cover_img and cover_img.filename and allowed_file(cover_img.filename):
            filename = f"cover_{title.replace(' ', '_')}_{cover_img.filename}"
            cover_img.save(os.path.join(UPLOAD_FOLDER, filename))
            cover_path = f"upload/books/{filename}"

        db.execute(
            """
            INSERT INTO books (
                title,
                author,
                category_id,
                description,
                price,
                rent_price,
                cover_image,
                available_for_sale,
                available_for_borrow
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                author,
                category_id or None,
                description,
                float(price or 0),
                float(rent_price or 0),
                cover_path or "book.png",
                max(0, int(available_for_sale or 0)),
                max(0, int(available_for_borrow or 0)),
            ),
        )
        db.commit()
        return jsonify({"status": "success", "message": "Them sach thanh cong."}), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500


@book_bp.route("/list", methods=["GET"])
def list_books():
    db = get_db()
    rows = db.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    return jsonify({"status": "success", "books": [dict(row) for row in rows], "total": len(rows)})


@book_bp.route("/<int:id>", methods=["GET"])
def book(id):
    row = fetch_book_detail(id)
    if row:
        return jsonify(dict(row))
    flash("Book not found", "warning")
    return jsonify({"status": "failed", "message": "Book not found"}), 404


@book_bp.route("/search", methods=["POST"])
def search():
    search_text = request.form.get("search_text", "").strip()
    if not search_text:
        return jsonify({"status": "error", "message": "Vui long nhap tu khoa."}), 400

    db = get_db()
    param = f"%{search_text}%"
    rows = db.execute(
        """
        SELECT *
        FROM books
        WHERE title LIKE ? OR author LIKE ?
        ORDER BY id DESC
        """,
        (param, param),
    ).fetchall()
    return jsonify({"status": "success", "count": len(rows), "data": [dict(row) for row in rows]})


@book_bp.route("/searchI", methods=["GET", "POST"])
def searchI():
    search_text = (
        request.args.get("search_text", "").strip()
        if request.method == "GET"
        else request.form.get("search_text", "").strip()
    )

    if not search_text:
        return jsonify({"status": "success", "keyword": "", "total": 0, "data": []})

    db = get_db()
    param = f"%{search_text}%"
    rows = db.execute(
        """
        SELECT id, title, author
        FROM books
        WHERE title LIKE ? OR author LIKE ?
        ORDER BY
            CASE WHEN title LIKE ? THEN 0 ELSE 1 END,
            title COLLATE NOCASE ASC
        LIMIT 8
        """,
        (param, param, param),
    ).fetchall()

    data = [{"id": row["id"], "title": row["title"], "author": row["author"] or ""} for row in rows]
    return jsonify({"status": "success", "keyword": search_text, "total": len(data), "data": data})


@book_bp.route("/update/<int:id>", methods=["PUT"])
@admin_required
def update_book(id):
    data = request.get_json(silent=True) or {}
    db = get_db()

    book_row = db.execute("SELECT * FROM books WHERE id = ?", (id,)).fetchone()
    if not book_row:
        return jsonify({"status": "error", "message": "Khong tim thay sach de cap nhat."}), 404

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
        return jsonify({"status": "success", "message": f"Da cap nhat sach ID {id}."})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500


@book_bp.route("/delete/<int:id>", methods=["DELETE"])
@admin_required
def delete_book(id):
    db = get_db()
    book_row = db.execute("SELECT id FROM books WHERE id = ?", (id,)).fetchone()
    if not book_row:
        return jsonify({"status": "error", "message": "Sach khong ton tai."}), 404

    try:
        db.execute("DELETE FROM books WHERE id = ?", (id,))
        db.commit()
        return jsonify({"status": "success", "message": f"Da xoa sach ID {id}."})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500


@book_bp.route("/delete-many", methods=["POST"])
@admin_required
def delete_many_books():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("book_ids") or request.form.getlist("book_ids")

    try:
        book_ids = sorted({int(book_id) for book_id in raw_ids})
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Danh sach sach khong hop le."}), 400

    if not book_ids:
        return jsonify({"status": "error", "message": "Chua chon sach de xoa."}), 400

    placeholders = ", ".join(["?"] * len(book_ids))
    existing_rows = db.execute(f"SELECT id FROM books WHERE id IN ({placeholders})", book_ids).fetchall()
    existing_ids = {row["id"] for row in existing_rows}
    if len(existing_ids) != len(book_ids):
        return jsonify({"status": "error", "message": "Co sach khong con ton tai."}), 404

    try:
        db.execute(f"DELETE FROM books WHERE id IN ({placeholders})", book_ids)
        db.commit()
        return jsonify({"status": "success", "message": f"Da xoa {len(book_ids)} sach.", "deleted_ids": book_ids})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500


@book_bp.route("", methods=["GET"])
@book_bp.route("/", methods=["GET"])
@book_bp.route("/all", methods=["GET"])
def books_ui():
    db = get_db()
    cursor = db.cursor()

    search_text = request.args.get("search_text", "").strip()
    selected_categories = [value for value in request.args.getlist("category_id") if value.strip()]
    selected_author = request.args.get("author", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort", "newest").strip() or "newest"

    conditions = ["(COALESCE(b.available_for_sale, 0) > 0 OR COALESCE(b.available_for_borrow, 0) > 0)"]
    params = []

    if search_text:
        conditions.append("(b.title LIKE ? OR b.author LIKE ?)")
        keyword = f"%{search_text}%"
        params.extend([keyword, keyword])

    if selected_categories:
        placeholders = ", ".join(["?"] * len(selected_categories))
        conditions.append(f"CAST(b.category_id AS TEXT) IN ({placeholders})")
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

    rows = cursor.execute(
        f"""
        SELECT
            b.id,
            b.title,
            b.author,
            b.description,
            b.price,
            COALESCE(b.rent_price, 0) AS rent_price,
            b.cover_image,
            COALESCE(b.available_for_sale, 0) AS available_for_sale,
            COALESCE(b.available_for_borrow, 0) AS available_for_borrow,
            COALESCE(c.name, 'Chua phan loai') AS category_name
        FROM books b
        LEFT JOIN categories c ON c.id = b.category_id
        WHERE {" AND ".join(conditions)}
        ORDER BY {order_by}
        """,
        params,
    ).fetchall()

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
        WHERE COALESCE(available_for_sale, 0) > 0 OR COALESCE(available_for_borrow, 0) > 0
        """
    ).fetchone()

    default_max_price = int(price_bounds["max_price"] or 0)
    current_max_price = max_price if max_price is not None else default_max_price

    return render_template(
        "books.html",
        danh_sach_sach=[build_book_card(row) for row in rows],
        search_text=search_text,
        categories=categories,
        authors=authors,
        selected_categories=selected_categories,
        selected_author=selected_author,
        max_price=current_max_price,
        default_max_price=default_max_price,
        min_price=int(price_bounds["min_price"] or 0),
        sort_by=sort_by,
    )


@book_bp.route("/detail/<int:book_id>", methods=["GET"])
def books_detail_ui(book_id):
    row = fetch_book_detail(book_id)
    if not row:
        flash("Khong tim thay sach.", "warning")
        return redirect(url_for("book.books_ui"))

    next_url = request.args.get("next", "").strip()
    back_url = next_url if next_url else url_for("book.books_ui")
    book = build_book_card(row)
    book["description"] = row["description"] or ""
    return render_template("book-detail.html", book=book, back_url=back_url)


@book_bp.route("/author/<path:author_name>", methods=["GET"])
def author_books_ui(author_name):
    decoded_author_name = unquote(author_name)
    db = get_db()
    rows = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.description,
            b.price,
            COALESCE(b.rent_price, 0) AS rent_price,
            b.cover_image,
            COALESCE(b.available_for_sale, 0) AS available_for_sale,
            COALESCE(b.available_for_borrow, 0) AS available_for_borrow,
            COALESCE(c.name, 'Chua phan loai') AS category_name
        FROM books b
        LEFT JOIN categories c ON c.id = b.category_id
        WHERE b.author = ?
          AND (COALESCE(b.available_for_sale, 0) > 0 OR COALESCE(b.available_for_borrow, 0) > 0)
        ORDER BY b.id DESC
        """,
        (decoded_author_name,),
    ).fetchall()

    books = [build_book_card(row) for row in rows]
    return render_template(
        "author.html",
        author_name=decoded_author_name,
        danh_sach_sach=books,
        total_books=len(books),
    )
