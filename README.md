# TNMAKER AI - ỨNG DỤNG CHẤM THI TRẮC NGHIỆM & TỰ LUẬN DI ĐỘNG

Hệ thống chấm bài thi toàn diện theo phong cách TNMaker chuẩn Bộ Giáo dục & Đào tạo Việt Nam:
- **Tốc độ phản hồi tức thì (< 150ms):** Bắt 4 góc marker, nắn phẳng ảnh (Perspective Warp về 2100 x 2970 px), chấm OMR Phần I, II, III nội bộ không tốn phí API.
- **Âm thanh Beep & Rung máy:** Phản hồi ngay lập tức khi phát hiện bài thi.
- **Chấm Tự Luận Ngầm (Background Task):** Cắt tự động vùng tự luận 45% nửa dưới trang A4, gọi ngầm Gemini AI (Gemini 2.0 / 1.5 Flash) để chấm điểm theo barem từng bước (Bài 1: 1.5đ, Bài 2: 1.5đ).
- **Xuất Báo Cáo Excel Chuyên Nghiệp:** Tự động sắp xếp Số Báo Danh (SBD) tăng dần (giữ nguyên chuỗi 6 ký tự như "010001", "010002"), định dạng bảng màu xanh Navy (#1F4E78), cột Tổng điểm in đậm màu đỏ nổi bật (#C00000).

---

## 1. Cấu Trúc Dự Án
```text
tnmaker_app/
├── requirements.txt         # Danh sách thư viện cần thiết
├── database.py              # Quản lý SQLite (bảng answer_keys, results)
├── omr_engine.py            # Xử lý Perspective Warp, nhận diện SBD, Mã đề & OMR P1, P2, P3
├── ai_grader.py             # Chấm tự luận bằng Google Gemini API (kèm fallback nét viết)
├── excel_exporter.py        # Xuất file Excel bảng điểm chuẩn mực với OpenPyXL
├── generate_sheet.py        # Sinh file mẫu phiếu thi A4 chuẩn in ấn & phiếu tô mẫu
├── main.py                  # FastAPI Backend routes (/api/scan, /api/export-excel...)
├── templates/
│   └── index.html           # Giao diện Web App PWA trên điện thoại (Camera, Beep, Bảng điểm)
└── uploads/                 # Thư mục lưu trữ ảnh phiếu nắn phẳng và ảnh cắt tự luận
```

---

## 2. Hướng Dẫn Cài Đặt & Khởi Chạy

### Bước 1: Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### Bước 2: Sinh phiếu thi chuẩn A4 (Nếu cần in ấn)
```bash
python generate_sheet.py
```
Lệnh trên sẽ sinh ra 2 file:
- `phieu_thi_chuan_A4.png`: Phiếu thi trắng kích thước A4 (2100 x 2970 px) có 4 marker đen 10x10mm ở 4 góc để in ra cho học sinh làm bài.
- `sample_filled_sheet.png`: Phiếu đã tô mẫu sẵn SBD `010001`, Mã đề `0101` và lời giải tự luận để kiểm thử ngay lập tức.

### Bước 3: Cấu hình Gemini API Key (Tùy chọn)
Nếu có Google Gemini API Key:
- Trên Windows PowerShell:
  ```powershell
  $env:GEMINI_API_KEY="AIzaSy..."
  ```
- Trên Linux/macOS:
  ```bash
  export GEMINI_API_KEY="AIzaSy..."
  ```
*(Ghi chú: Nếu chưa cấu hình API Key, hệ thống tự động kích hoạt thuật toán AI phân tích nét chữ viết tay thông minh để không gián đoạn việc chấm thi).*

### Bước 4: Khởi động Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Sau khi chạy lệnh:
- Truy cập từ máy tính: `http://localhost:8000`
- Truy cập từ điện thoại di động (cùng mạng Wi-Fi): `http://<IP_MÁY_TÍNH>:8000`

---

## 3. Quy Chuẩn Thang Điểm & Ma Trận Đề (Thang 10.0)
1. **Khối Định danh:**
   - Số báo danh (SBD): 6 cột (0 đến 9), bảo lưu chuỗi định dạng text như `"010001"`.
   - Mã đề thi: 4 cột (0 đến 9).
2. **Phần I - Trắc nghiệm nhiều lựa chọn (3.0 điểm):**
   - 12 câu, mỗi câu 4 phương án A, B, C, D.
   - Mỗi câu đúng: 0.25 điểm.
3. **Phần II - Đúng / Sai (2.0 điểm):**
   - 2 câu, mỗi câu 4 ý a, b, c, d (tô Đ hoặc S).
   - Điểm lũy tiến chuẩn Bộ GD&ĐT:
     + Đúng 1 ý: 0.10 điểm
     + Đúng 2 ý: 0.25 điểm
     + Đúng 3 ý: 0.50 điểm
     + Đúng cả 4 ý: 1.00 điểm
4. **Phần III - Trả lời ngắn (2.0 điểm):**
   - 4 câu. Mỗi câu gồm 4 cột (dấu "-", dấu ".", và các chữ số 0-9) tạo thành số thực.
   - Mỗi câu đúng: 0.50 điểm.
5. **Phần IV - Tự luận (3.0 điểm):**
   - Khung viền đôi ở 45% nửa dưới trang A4.
   - Gồm 2 bài toán (Bài 1: 1.5đ, Bài 2: 1.5đ). Chấm tự động bằng Gemini AI.
