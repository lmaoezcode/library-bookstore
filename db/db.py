import sqlite3

def get_db():
    conn = sqlite3.connect('db/library.sqlite')
    conn.row_factory=sqlite3.Row
    return conn