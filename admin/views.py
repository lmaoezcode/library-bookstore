from flask import request, render_template, session, redirect, url_for, flash, jsonify
import pandas as pd
import sqlite3
from . import admin_bp
from werkzeug.security import generate_password_hash, check_password_hash

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        db = get_db()
        user= db.execute('SELECT * FROM users WHERE email = ? AND role="admin"', (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session['logged_in'] = True
            session['user_id']= user["id"]
            session["role"]=user["role"]
            flash("Đăng nhập thành công!", "success")
            target_url = url_for('index')
            return redirect(target_url)
        else:
            error = "Sai email hoặc mật khẩu!"
    return render_template('admin-login.html',error=error)

def get_db():
    conn = sqlite3.connect('db/library.sqlite')
    conn.row_factory=sqlite3.Row
    return conn
@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@admin_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        confirmation = request.form.get('confirmation')
        db = get_db()
        result=db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if result:
            error="Email already exists!"
        else:
            hashed_password = generate_password_hash(password)
            db.execute('INSERT INTO users (email, password,name, role) VALUES (?, ?,?,?)',(email, hashed_password,name,"admin"))
            db.commit()
            return redirect(url_for('admin.login'))
        return render_template('register.html', error=error)

    return render_template('register.html')


@admin_bp.route('/user/list', methods=['POST'])
def user_list():
    db=get_db()
    result=db.execute('SELECT * FROM users WHERE role="user"').fetchall()
    user = [dict(row) for row in result]
    if result:
        return jsonify({
            "status":"success",
            "user":user
        }),200
    else:
        return jsonify({
            "status": "failed",
            "message":"User not found!",
        }),200
