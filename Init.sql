INSERT INTO categories (name) VALUES ('Văn học');      -- ID sẽ là 1
INSERT INTO categories (name) VALUES ('Kinh tế');      -- ID sẽ là 2
INSERT INTO categories (name) VALUES ('Công nghệ');    -- ID sẽ là 3
INSERT INTO categories (name) VALUES ('Kỹ năng sống'); -- ID sẽ là 4

SELECT * FROM users;


-- SÁCH VĂN HỌC (category_id = 1)
INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Số Đỏ', 'Vũ Trọng Phụng', 'Tác phẩm hiện thực phê phán kinh điển.', 85000, 5000, 1, 'so_do.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Lão Hạc', 'Nam Cao', 'Câu chuyện cảm động về người nông dân.', 45000, 2000, 1, 'lao_hac.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Mắt Biếc', 'Nguyễn Nhật Ánh', 'Chuyện tình buồn của Ngạn và Hà Lan.', 110000, 8000, 1, 'mat_biec.jpg');

-- SÁCH KINH TẾ (category_id = 2)
INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Cha Giàu Cha Nghèo', 'Robert Kiyosaki', 'Bài học về tư duy tài chính.', 150000, 10000, 2, 'rich_dad.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Kinh Tế Học Cơ Bản', 'Thomas Sowell', 'Kiến thức kinh tế cho mọi người.', 220000, 15000, 2, 'economics.jpg');

-- SÁCH CÔNG NGHỆ (category_id = 3)
INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Clean Code', 'Robert C. Martin', 'Kỹ thuật viết mã sạch và dễ bảo trì.', 350000, 25000, 3, 'clean_code.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Hành Trình Python', 'Nhiều tác giả', 'Hướng dẫn lập trình Python từ số 0.', 180000, 10000, 3, 'python_dev.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Thiết Kế Hệ Thống', 'Alex Xu', 'Xây dựng hệ thống quy mô lớn.', 450000, 30000, 3, 'system_design.jpg');

-- SÁCH KỸ NĂNG (category_id = 4)
INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Đắc Nhân Tâm', 'Dale Carnegie', 'Nghệ thuật giao tiếp và chinh phục lòng người.', 95000, 5000, 4, 'dac_nhan_tam.jpg');

INSERT INTO books (title, author, description, price, rent_price, category_id, cover_image)
VALUES ('Atomic Habits', 'James Clear', 'Thay đổi nhỏ, kết quả lớn.', 165000, 9000, 4, 'habits.jpg');


SELECT * FROM books;