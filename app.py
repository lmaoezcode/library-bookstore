from flask import Flask, render_template, abort, request

app = Flask(__name__)

# Dữ liệu sách dùng chung
BOOKS_DATA = [
    {
        'id': 1,
        'title': 'Làm Chủ Code',
        'author': 'ByteBooks',
        'price': '120.000đ',
        'old_price': '150.000đ',
        'category': 'Công nghệ / Lập trình',
        'pages': 280,
        'image': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=800',
        'can_buy': True
    },
    {
        'id': 2,
        'title': 'Con Đường Khoa Học',
        'author': 'John Carter',
        'price': '150.000đ',
        'old_price': '190.000đ',
        'category': 'Khoa học / Đời sống',
        'pages': 320,
        'image': 'https://images.unsplash.com/photo-1581090700227-1e37b190418e?w=800',
        'can_buy': True
    },
    {
        'id': 3,
        'title': 'Tư Duy Quyết Định',
        'author': 'Robin Sharma',
        'price': '90.000đ',
        'old_price': '110.000đ',
        'category': 'Kỹ năng / Sống đẹp',
        'pages': 210,
        'image': 'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800',
        'can_buy': False
    }
]

# ----- CÁC ĐƯỜNG DẪN (ROUTES) -----

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/books')
def books():
    return render_template('books.html', danh_sach_sach=BOOKS_DATA)

@app.route('/books/<int:book_id>')
def books_detail(book_id):
    # Tìm cuốn sách có id khớp với id trên đường dẫn
    book = next((b for b in BOOKS_DATA if b['id'] == book_id), None)
    
    if book is None:
        abort(404)
        
    return render_template('book-detail.html', book=book)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/borrow')
def borrow():
    # Lấy danh sách ID sách được truyền từ giỏ hàng qua GET request (ví dụ: ?books=1,2)
    book_ids = request.args.get('books', '')
    selected_books = []
    if book_ids:
        try:
            id_list = [int(i.strip()) for i in book_ids.split(',')]
            selected_books = [b for b in BOOKS_DATA if b['id'] in id_list]
        except ValueError:
            pass
    return render_template('borrow.html', selected_books=selected_books)

@app.route('/my-account')
def my_account():
    return render_template('my-account.html')

@app.route('/cart')
def cart():
    # Gửi toàn bộ BOOKS_DATA để mô phỏng giỏ hàng, thực tế sẽ lấy danh sách trong session/db
    return render_template('cart.html', cart_items=BOOKS_DATA)

@app.route('/payments')
def payments():
    book_ids = request.args.get('books', '')
    selected_books = []
    if book_ids:
        try:
            id_list = [int(i.strip()) for i in book_ids.split(',')]
            selected_books = [b for b in BOOKS_DATA if b['id'] in id_list]
        except ValueError:
            pass
    return render_template('payments.html', selected_books=selected_books)

@app.route('/wishlist')
def wishlist():
    return render_template('wishlist.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Chạy server
if __name__ == '__main__':
    app.run(debug=True)