# app.py
from datetime import timedelta

from flask import Flask, render_template, request, redirect, url_for, session, abort,jsonify
from db.db import get_db
import sqlite3
from order import order_bp
from borrow import borrow_bp
from auth import auth_bp
from admin import admin_bp
from book import book_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'super_secret_key_dev'
    app.json.ensure_ascii = False
    app.permanent_session_lifetime = timedelta(days=30)
    app.register_blueprint(order_bp)
    app.register_blueprint(borrow_bp)

    app.register_blueprint(auth_bp)

    app.register_blueprint(admin_bp)

    app.register_blueprint(book_bp)

    def get_cart_id():
        if "cart_id" not in session:
            session["cart_id"] = 1  # demo (sau có thể random)
        return session["cart_id"]


    # ------------------ Trang chủ ------------------
    @app.route('/')
    def index():
        return render_template('index.html')


    # ------------------ Danh sách sách ------------------



    # ------------------ Login/Logout ------------------
    # @app.route('/login', methods=['GET', 'POST'])
    # def login():
    #     if request.method == 'POST':
    #         fullname = request.form.get('fullname')
    #         email = request.form.get('email', '')
    #         password = request.form.get('password', '')
    #
    #         if email == 'admin@gmail.com' and password == 'admin':
    #             session['user_name'] = 'Administrator'
    #             session['role'] = 'admin'
    #             return redirect(url_for('admin_dashboard'))
    #
    #         if fullname:
    #             session['user_name'] = fullname
    #         elif email:
    #             session['user_name'] = email.split('@')[0]
    #         else:
    #             session['user_name'] = 'Người dùng'
    #         session['role'] = 'user'
    #
    #         return redirect(url_for('index'))
    #
    #     return render_template('login.html')


    @app.route('/logout')
    def logout():
        session.pop('user_name', None)
        session.pop('role', None)
        return redirect(url_for('index'))


    # ------------------ Admin ------------------
    @app.route('/admin')
    def admin_dashboard():
        if session.get('role') != 'admin':
            return redirect(url_for('index'))

        db = get_db()
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, title, author, price, rent_price, cover_image, description
            FROM books
            ORDER BY created_at DESC
        """)
        books = cursor.fetchall()
        return render_template('admin.html', books=books)


    # ------------------ Borrow ------------------



    # ------------------ Payments ------------------
    @app.route('/payments')
    def payments():
        book_ids = request.args.get('books', '')
        selected_books = []
        if book_ids:
            try:
                id_list = [int(i.strip()) for i in book_ids.split(',')]
                db = get_db()
                db.row_factory = sqlite3.Row
                cursor = db.cursor()
                query = f"SELECT id, title, author, price, rent_price, cover_image, description FROM books WHERE id IN ({','.join(['?']*len(id_list))})"
                cursor.execute(query, id_list)
                selected_books = cursor.fetchall()
            except ValueError:
                pass
        return render_template('payments.html', selected_books=selected_books)


    # ------------------ My Account ------------------
    @app.route('/my-account')
    def my_account():
        user = session.get('user_name', 'Người dùng')
        return render_template('my-account.html', user_name=user)


    # ------------------ Other pages ------------------
    @app.route('/wishlist')
    def wishlist():
        return render_template('wishlist.html')


    @app.route('/about')
    def about():
        return render_template('about.html')


    @app.route('/contact')
    def contact():
        return render_template('contact.html')


    @app.route("/add_to_cart_form", methods=["POST"])
    def add_to_cart_form():
        book_id = request.form.get("book_id")
        cart_id = get_cart_id()

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT quantity FROM cart_items WHERE book_id = ? AND cart_id = ?",
            (book_id, cart_id)
        )
        item = cursor.fetchone()

        if item:
            cursor.execute(
                "UPDATE cart_items SET quantity = quantity + 1 WHERE book_id = ? AND cart_id = ?",
                (book_id, cart_id)
            )
        else:
            cursor.execute(
                "INSERT INTO cart_items (cart_id, book_id, quantity) VALUES (?, ?, ?)",
                (cart_id, book_id, 1)
            )

        db.commit()
        return redirect(url_for("view_cart"))
    # ------------------ Cart ------------------
    @app.route('/cart')
    def view_cart():
        cart_id = get_cart_id()

        db = get_db()
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute("""
            SELECT b.id, b.title, b.author, b.price, b.cover_image, ci.quantity
            FROM cart_items ci
            JOIN books b ON b.id = ci.book_id
            WHERE ci.cart_id = ?
        """, (cart_id,))

        cart_items = cursor.fetchall()

        return render_template('cart.html', cart_items=cart_items)

    @app.context_processor
    def inject_cart_count():
        cart_id = get_cart_id()
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT SUM(quantity) FROM cart_items WHERE cart_id = ?",
            (cart_id,)
        )
        count = cursor.fetchone()[0]

        return dict(cart_count=count or 0)

    return app

# ------------------ Run server ------------------
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)