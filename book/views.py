import os

from flask import request, render_template, session, redirect, url_for, flash, current_app, jsonify
import sqlite3
from . import book_bp
from db.db import get_db
from route.route import admin_required
from werkzeug.security import generate_password_hash, check_password_hash

UPLOAD_FOLDER='static/upload/books'
ALLOWED_EXTENSIONS={'pdf','png','jpg','jpeg'}

os.makedirs(UPLOAD_FOLDER,exist_ok=True)

@book_bp.route('/add', methods=['POST'])
def add_book():
    db = get_db()

    # 1. Lấy thông tin text từ form
    title = request.form.get('title')
    author = request.form.get('author')
    category_id = request.form.get('category_id')
    price = request.form.get('price', 0)

    if not title or not author:
        return jsonify({"status": "error", "message": "Thiếu thông tin sách"}), 400

    # 2. Xử lý file PDF
    pdf_file = request.files.get('pdf_file')
    preview_img = request.files.get('preview_file')
    cover_img = request.files.get('cover_image')
    pdf_path = None
    preview_path = None
    cover_path = None

    try:
        # Lưu file PDF
        if pdf_file and allowed_file(pdf_file.filename):
            pdf_filename = f"pdf_{title.replace(' ', '_')}_{pdf_file.filename}"
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
            pdf_file.save(pdf_path)

        # Lưu file Ảnh Preview
        if preview_img and allowed_file(preview_img.filename):
            img_filename = f"prev_{title.replace(' ', '_')}_{preview_img.filename}"
            preview_path = os.path.join(UPLOAD_FOLDER, img_filename)
            preview_img.save(preview_path)

        # Anh preview
        if cover_img and allowed_file(cover_img.filename):
            img_filename = f"prev_{title.replace(' ', '_')}_{cover_img.filename}"
            cover_path = os.path.join(UPLOAD_FOLDER, img_filename)
            cover_img.save(cover_path)
        # 3. Lưu vào Database
        query = '''
                INSERT INTO books (title, author, category_id, price, pdf_full, pdf_preview, cover_image)
                VALUES (?, ?, ?, ?, ?, ?,?) \
                '''
        db.execute(query, (title, author, category_id, price, pdf_path, preview_path,cover_path))
        db.commit()




        return jsonify({
            "status": "success",
            "message": "Thêm sách và file thành công!",
            "data": {
                "pdf_url": pdf_path,
                "preview_url": preview_path,
                "cover_url": cover_path,
            }
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


@book_bp.route('/list',methods=['GET'])
def list():
    db=get_db()

    query='SELECT * FROM books ORDER BY id DESC'
    result=db.execute(query).fetchall()
    books=[dict(row) for row in result]
    return jsonify({
        'status':'success',
        'books':books,
        'total':len(books)
    })



@book_bp.route('/<int:id>',methods=['GET'])
def book(id):
    db=get_db()
    query='SELECT * FROM books WHERE id = ?'
    result=db.execute(query,(id,)).fetchone()
    if result:
        book=dict(result)
        return jsonify(book)
    else:
        flash('Book not found')
        return jsonify({
            "status":"failed",
            "message":"book not found",

        },200)


@book_bp.route('/search', methods=['POST'])
def search():
    # Lấy nội dung tìm kiếm từ form
    search_text = request.form.get('search_text', '').strip()

    if not search_text:
        return jsonify({"status": "error", "message": "Vui lòng nhập từ khóa"}), 400

    db = get_db()

    # Sử dụng LIKE và dấu % để tìm kiếm "chứa cụm từ này"
    query = 'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?'

    # Tạo tham số tìm kiếm: %nội dung%
    param = f'%{search_text}%'

    # Dùng fetchall() để lấy TOÀN BỘ kết quả trùng khớp
    results = db.execute(query, (param, param)).fetchall()

    # Chuyển thành list dict
    books = [dict(row) for row in results]

    return jsonify({
        "status": "success",
        "count": len(books),
        "data": books
    })


@book_bp.route('/searchI', methods=['POST'])
def searchI():
    # 1. Lấy dữ liệu từ Form (Nút search ấn sẽ gửi cái này)
    search_text = request.form.get('search_text', '').strip()

    # 2. Kiểm tra nếu người dùng để trống mà đã ấn search
    if not search_text:
        # Nếu dùng API thì trả về JSON, nếu dùng Web thì redirect về trang chủ
        return jsonify({"status": "error", "message": "Ban chưa nhập gì cả!"}), 400

    db = get_db()

    # 3. Truy vấn "Gần đúng" với LIKE (Tìm cả tiêu đề và tác giả)
    # Dấu % giúp tìm kiếm linh hoạt: %Python% sẽ ra "Lập trình Python", "Python cơ bản"...
    query = '''
            SELECT b.*, c.name as category_name
            FROM books b
                     LEFT JOIN categories c ON b.category_id = c.id
            WHERE b.title LIKE ? \
               OR b.author LIKE ?
            ORDER BY b.id DESC \
            '''

    search_param = f"%{search_text}%"
    results = db.execute(query, (search_param, search_param)).fetchall()

    # 4. Chuyển đổi dữ liệu để trả về
    books = [dict(row) for row in results]

    # 5. Trả về kết quả
    return jsonify({
        "status": "success",
        "keyword": search_text,
        "total": len(books),
        "data": books
    })



@book_bp.route('/update/<int:id>', methods=['PUT'])
def update_book(id):
    data = request.get_json()
    db = get_db()

    # Kiểm tra xem sách có tồn tại không trước khi update
    book = db.execute('SELECT * FROM books WHERE id = ?', (id,)).fetchone()
    if not book:
        return jsonify({"status": "error", "message": "Không tìm thấy sách để cập nhật"}), 404

    # Lấy dữ liệu mới hoặc giữ nguyên dữ liệu cũ nếu không gửi
    title = data.get('title', book['title'])
    author = data.get('author', book['author'])
    category_id = data.get('category_id', book['category_id'])
    price = data.get('price', book['price'])

    try:
        db.execute(
            'UPDATE books SET title = ?, author = ?, category_id = ?, price = ? WHERE id = ?',
            (title, author, category_id, price, id)
        )
        db.commit()
        return jsonify({"status": "success", "message": f"Đã cập nhật sách ID {id}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@book_bp.route('/delete/<int:id>', methods=['DELETE'])
@admin_required
def delete_book(id):
    db = get_db()

    # Kiểm tra tồn tại
    book = db.execute('SELECT * FROM books WHERE id = ?', (id,)).fetchone()
    if not book:
        return jsonify({"status": "error", "message": "Sách không tồn tại"}), 404

    try:
        db.execute('DELETE FROM books WHERE id = ?', (id,))
        db.commit()
        return jsonify({"status": "success", "message": f"Đã xóa vĩnh viễn sách ID {id}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

