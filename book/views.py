from flask import request, render_template, session, redirect, url_for, flash, current_app, jsonify
import sqlite3
from . import book_bp
from db.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash



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
        return redirect(url_for('book.list'))


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