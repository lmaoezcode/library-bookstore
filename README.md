# 📚 Bookstore & Library Online
Bài tập nhóm Lập Trình Web: website thư viện kiêm nhà sách trực tuyến

## 👥 Thành viên

- **Hoàng Phúc Lâm - 11236139 (Trưởng nhóm)**: Frontend, Git, Tích hợp
- **Phạm Hùng Mạnh - 11236151**: Backend – Auth, Books, Users
- **Trần Trung Hiếu - 11236107**: Backend – Cart, Orders
- **Phạm Hùng Dương - 11236091**: Backend – Borrow, Admin

## 🛠 Công nghệ sử dụng

- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Backend**: Python, Flask, Flask-Login
- **Database**: SQLite
- **Version control**: Git, GitHub

## 📁 Cấu trúc thư mục dự án
```text
bookstore-library/
├── app.py                   # File chính để chạy ứng dụng
├── models.py                # Định nghĩa các bảng Database (Dùng chung)
├── database.db              # File SQLite (Nằm ở thư mục gốc cho dễ quản lý)
├── requirements.txt         # Danh sách thư viện
├── blueprints/              # Chia nhỏ code logic (Cho B, C, D)
│   ├── auth.py
│   ├── store.py
│   └── library.py
├── static/                  # File tĩnh 
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── uploads/             # Nơi chứa ảnh bìa sách và PDF
└── templates/               # Giao diện HTML
    ├── base.html            # File khung (Navbar, Footer)
    ├── index.html           # Trang chủ
    ├── auth/                # Folder chứa login.html, register.html
    ├── store/               # Folder chứa cart.html, checkout.html
    └── library/             # Folder chứa my_books.html, reader.html
```

## 🚀 Cách chạy dự án (sẽ cập nhật)

### Backend
1. Clone repo: `git clone <https://github.com/lmaoezcode/library-bookstore>`
2. Di chuyển vào thư mục `backend`
3. Tạo virtual environment: `python -m venv venv`
4. Kích hoạt venv:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
5. Cài dependencies: `pip install -r requirements.txt`
6. Chạy Flask: `python app.py`
7. Backend chạy tại `http://localhost:5000`

### Frontend
- Mở trực tiếp file `frontend/index.html` bằng trình duyệt.

## 📌 Quy trình làm việc

- **Git**: Mỗi người làm nhánh riêng, commit message theo format `[Tên] Nội dung`
- **Merge**: Trưởng nhóm (A) sẽ merge vào `main`
- **API Documentation**: Cập nhật trong file `API.md`

## 📅 Lịch trình 5 ngày

| Ngày | Mục tiêu |
|------|----------|
| 0 | Setup repo, Trello, skeleton code |
| 1 | Hoàn thiện các chức năng cơ bản |
| 2 | Phát triển API và frontend |
| 3 | Kết nối frontend với API thật |
| 4 | Hoàn thiện admin, tích hợp |
| 5 | Merge, kiểm thử, demo |

## 🧪 Tính năng chính

### Khách (chưa đăng nhập)
- Xem danh sách sách, chi tiết sách, tìm kiếm

### Người dùng (đã đăng nhập)
- Đăng nhập/đăng ký
- Giỏ hàng, đặt hàng (mua sách)
- Mượn sách (tạo phiếu mượn)
- Lịch sử đơn hàng, lịch sử mượn

### Admin
- Quản lý sách (thêm, sửa, xóa)
- Duyệt đơn hàng
- Duyệt phiếu mượn
- 
(to be continued)
