from datetime import timedelta

from flask import Flask,request, render_template
import pandas as pd
from admin import (admin_bp)
from auth import auth_bp
from book import book_bp
from route.route import login_required
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret-change-me'  # cần cho flash/session
    app.json.ensure_ascii = False
    app.permanent_session_lifetime = timedelta(days=30)
    # Đăng ký các blueprint
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(book_bp)
    @app.route("/index", methods=["GET"])
    @login_required
    def index():
        return "Hello World!"
    return app
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
