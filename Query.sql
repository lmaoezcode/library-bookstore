
-- BẬT CHẾ ĐỘ KIỂM TRA KHÓA NGOẠI (Rất quan trọng trong SQLite)
PRAGMA foreign_keys = ON;

-- 1. BẢNG NGƯỜI DÙNG (USERS)
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL, -- Lưu ý: Password phải được lưu dưới dạng chuỗi đã Hash (Werkzeug)
    role TEXT CHECK (role IN ('user','admin')) DEFAULT 'user', -- Quyền hạn: người dùng hoặc quản trị
    status TEXT CHECK(status IN ('active','locked')) DEFAULT 'active', -- Trạng thái: đang hoạt động hoặc bị khóa
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- Thời điểm tạo tài khoản
);
SELECT * FROM users;
SELECT * FROM borrow_items;
-- 2. BẢNG DANH MỤC (CATEGORIES)
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE -- Tên danh mục không được trùng nhau
);

-- 3. BẢNG SÁCH (BOOKS)
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, -- Tên sách
    author TEXT, -- Tác giả
    description TEXT, -- Mô tả nội dung
    price REAL NOT NULL CHECK(price >= 0), -- Giá bán (không được âm)
    rent_price REAL DEFAULT 0 CHECK(rent_price >= 0), -- Giá cho thuê (nếu có)
    category_id INTEGER, -- Liên kết với bảng danh mục
    cover_image TEXT, -- Đường dẫn ảnh bìa
    pdf_full TEXT, -- Đường dẫn file đọc toàn bộ (cho người đã mua)
    pdf_preview TEXT, -- Đường dẫn file đọc thử (cho mọi người)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Nếu xóa danh mục, các sách thuộc danh mục đó sẽ được đặt category_id về NULL thay vì bị xóa mất sách
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- 4. BẢNG KHO HÀNG (INVENTORY)
CREATE TABLE inventory (
    book_id INTEGER PRIMARY KEY, -- Mỗi cuốn sách chỉ có 1 dòng quản lý kho
    stock_sell INTEGER DEFAULT 0 CHECK(stock_sell >= 0), -- Số lượng sách để bán còn lại
    stock_rent INTEGER DEFAULT 0 CHECK(stock_rent >= 0), -- Số lượng sách để cho mượn còn lại
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- Thời điểm cập nhật kho gần nhất

    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE -- Nếu xóa sách, dữ liệu kho của sách đó cũng biến mất
);

-- 5. BẢNG GIỎ HÀNG (CARTS)
CREATE TABLE carts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, -- Mỗi giỏ hàng phải thuộc về một người dùng
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 6. CHI TIẾT GIỎ HÀNG (CART_ITEMS)
CREATE TABLE cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1 CHECK(quantity > 0), -- Số lượng mua tối thiểu là 1

    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- 7. BẢNG ĐƠN HÀNG (ORDERS)
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_price REAL NOT NULL CHECK(total_price >= 0), -- Tổng tiền thanh toán
    status TEXT CHECK(status IN ('pending', 'shipping', 'delivered', 'cancelled')) DEFAULT 'pending', -- Trạng thái đơn
    address TEXT NOT NULL, -- Địa chỉ giao hàng (bắt buộc)
    phone TEXT NOT NULL, -- Số điện thoại nhận hàng (bắt buộc)
    payment_method TEXT CHECK(payment_method IN ('COD', 'BANK')) DEFAULT 'COD', -- Phương thức thanh toán
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL -- Giữ lại đơn hàng ngay cả khi xóa user để thống kê kế toán
);

-- 8. CHI TIẾT ĐƠN HÀNG (ORDER_ITEMS)
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    price REAL NOT NULL, -- Lưu giá tại thời điểm mua (để tránh lỗi khi sau này sách đổi giá)

    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
);

-- 9. BẢNG QUẢN LÝ MƯỢN SÁCH (BORROWS)
CREATE TABLE borrows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT CHECK(status IN ('borrowing', 'returned', 'overdue')) DEFAULT 'borrowing', -- Đang mượn | Đã trả | Quá hạn
    total_deposit REAL DEFAULT 0, -- Tiền đặt cọc mượn sách (nếu có)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 10. CHI TIẾT MƯỢN SÁCH (BORROW_ITEMS)
CREATE TABLE borrow_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    borrow_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date DATETIME DEFAULT CURRENT_TIMESTAMP, -- Ngày mượn
    due_date DATETIME NOT NULL, -- Ngày phải trả (hạn định)
    return_date DATETIME, -- Ngày thực tế trả sách (NULL nếu chưa trả)

    FOREIGN KEY (borrow_id) REFERENCES borrows(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
);

-- CHÈN DỮ LIỆU MẪU (Lưu ý: Mật khẩu này chỉ để test)
INSERT INTO users (name, email, password, role) VALUES ('Admin Website', 'admin@gmail.com', '8888', 'admin');
INSERT INTO categories (name) VALUES ('Văn học'), ('Kinh tế'), ('Công nghệ');