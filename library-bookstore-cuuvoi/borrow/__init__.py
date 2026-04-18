from flask import Blueprint

borrow_bp = Blueprint('borrow', __name__, url_prefix='/borrow')

from . import views