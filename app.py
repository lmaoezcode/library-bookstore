from flask import Flask, render_template

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/books')
def books():
    return render_template('books.html')

@app.route('/book/<int:id>')
def book_detail(id):
    return render_template('books-detail.html')

@app.route('/cart')
def cart():
    return render_template('cart.html')

@app.route('/wishlist')
def wishlist():
    return render_template('wishlist.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('login.html')  # tạm dùng chung

@app.route('/account')
def account():
    return render_template('my-account.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)