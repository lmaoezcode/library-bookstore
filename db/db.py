import sqlite3
import os

def get_db():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'db', 'library.sqlite')
    conn = sqlite3.connect(db_path)
    conn.row_factory=sqlite3.Row
    return conn