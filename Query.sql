INSERT INTO users (name, email, password, role) VALUES
('Alice', 'alice@gmail.com', 'hash1', 'user'),
('Bob', 'bob@gmail.com', 'hash2', 'user'),
('Charlie', 'charlie@gmail.com', 'hash3', 'admin'),
('David', 'david@gmail.com', 'hash4', 'user'),
('Eve', 'eve@gmail.com', 'hash5', 'user'),
('Frank', 'frank@gmail.com', 'hash6', 'user'),
('Grace', 'grace@gmail.com', 'hash7', 'user'),
('Henry', 'henry@gmail.com', 'hash8', 'user'),
('Ivy', 'ivy@gmail.com', 'hash9', 'user'),
('Jack', 'jack@gmail.com', 'hash10', 'user');


INSERT INTO categories (name) VALUES
('Fiction'),
('Science'),
('Technology'),
('History'),
('Math'),
('Programming'),
('AI'),
('Business'),
('Self-help'),
('Novel');


INSERT INTO books (title, author, description, price, promo_price, category_id, total_quantity, available_quantity)
VALUES
('Clean Code', 'Robert C. Martin', 'A Handbook of Agile Software Craftsmanship', 300, 250, 6, 50, 50),

('The Pragmatic Programmer', 'Andrew Hunt & David Thomas', 'Journey to Mastery for developers', 320, 280, 6, 40, 40),

('Introduction to Algorithms', 'Thomas H. Cormen', 'Classic algorithms book (CLRS)', 500, 450, 5, 30, 30),

('Artificial Intelligence: A Modern Approach', 'Stuart Russell', 'AI foundational textbook', 550, 500, 7, 20, 20),

('Deep Learning', 'Ian Goodfellow', 'Deep learning theory and practice', 600, 520, 7, 25, 25),

('Atomic Habits', 'James Clear', 'Self improvement strategies', 200, 150, 9, 60, 60),

('Rich Dad Poor Dad', 'Robert Kiyosaki', 'Personal finance classic', 180, 140, 8, 70, 70),

('Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', 'History of human evolution', 250, 200, 4, 45, 45),

('The Lean Startup', 'Eric Ries', 'Startup methodology and innovation', 220, 180, 8, 35, 35),

('Design Patterns: Elements of Reusable Object-Oriented Software', 'Erich Gamma', 'Classic design patterns (GoF)', 400, 350, 6, 30, 30);

INSERT INTO inventory (book_id, stock_sell, stock_rent) VALUES
(1, 50, 10),
(2, 40, 8),
(3, 30, 6),
(4, 20, 5),
(5, 10, 2),
(6, 25, 7),
(7, 35, 9),
(8, 45, 11),
(9, 60, 12),
(10, 70, 15);


INSERT INTO carts (user_id) VALUES
(1),(2),(3),(4),(5),(6),(7),(8),(9),(10);


INSERT INTO cart_items (cart_id, book_id, quantity) VALUES
(1,1,2),
(2,2,1),
(3,3,3),
(4,4,1),
(5,5,2),
(6,6,1),
(7,7,2),
(8,8,1),
(9,9,3),
(10,10,1);


INSERT INTO orders (user_id, total_price, address, phone, status)
VALUES
(1, 780, 'Hà Nội', '090000001', 'pending'),        -- Clean Code (250x2) + Pragmatic (280)
(2, 450, 'HCM', '090000002', 'processing'),       -- CLRS (450)
(3, 1000, 'Đà Nẵng', '090000003', 'pending'),     -- AI Modern (500x2)
(4, 520, 'Hải Phòng', '090000004', 'delivered'),  -- Deep Learning (520)
(5, 300, 'Cần Thơ', '090000005', 'pending'),      -- Atomic Habits (150x2)
(6, 140, 'Hà Nội', '090000006', 'cancelled'),     -- Rich Dad (140)
(7, 200, 'HCM', '090000007', 'shipping'),         -- Sapiens (200)
(8, 360, 'Đà Nẵng', '090000008', 'pending'),      -- Lean Startup (180x2)
(9, 350, 'Hải Phòng', '090000009', 'processing'), -- Design Patterns (350)
(10, 500, 'Cần Thơ', '090000010', 'pending');     -- Clean Code (250x2)

INSERT INTO order_items (order_id, book_id, book_title, quantity, price)
VALUES
-- Order 1
(1, 1, 'Clean Code', 2, 250),
(1, 2, 'The Pragmatic Programmer', 1, 280),

-- Order 2
(2, 3, 'Introduction to Algorithms', 1, 450),

-- Order 3
(3, 4, 'Artificial Intelligence: A Modern Approach', 2, 500),

-- Order 4
(4, 5, 'Deep Learning', 1, 520),

-- Order 5
(5, 6, 'Atomic Habits', 2, 150),

-- Order 6
(6, 7, 'Rich Dad Poor Dad', 1, 140),

-- Order 7
(7, 8, 'Sapiens: A Brief History of Humankind', 1, 200),

-- Order 8
(8, 9, 'The Lean Startup', 2, 180),

-- Order 9
(9, 10, 'Design Patterns: Elements of Reusable Object-Oriented Software', 1, 350),

-- Order 10
(10, 1, 'Clean Code', 2, 250);

INSERT INTO borrows (user_id, status) VALUES
(1,'pending'),
(2,'approved'),
(3,'borrowing'),
(4,'returned'),
(5,'pending'),
(6,'approved'),
(7,'borrowing'),
(8,'returned'),
(9,'pending'),
(10,'approved');


INSERT INTO borrow_items (borrow_id, book_id, due_date) VALUES
(1,1,'2026-05-01'),
(2,2,'2026-05-02'),
(3,3,'2026-05-03'),
(4,4,'2026-05-04'),
(5,5,'2026-05-05'),
(6,6,'2026-05-06'),
(7,7,'2026-05-07'),
(8,8,'2026-05-08'),
(9,9,'2026-05-09'),
(10,10,'2026-05-10');



SELECT * FROM books;
SELECT * FROM borrows;