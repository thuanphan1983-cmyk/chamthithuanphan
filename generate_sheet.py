"""
Module generate_sheet.py - Trình sinh Phiếu Trả Lời Trắc Nghiệm & Tự Luận chuẩn Bộ GD&ĐT
Dùng để:
1. Sinh phiếu trắng chuẩn A4 (2100 x 2970 px) có 4 marker đen 10x10mm ở 4 góc để in ra giấy.
2. Sinh phiếu đã tô mẫu (Sample Filled Sheet) để kiểm thử toàn diện hệ thống OMR & Gemini AI.
"""

import cv2
import numpy as np
import os
import sys

# Đảm bảo in unicode ra console không bị lỗi mã hóa trên Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from omr_engine import (
    CANVAS_WIDTH, CANVAS_HEIGHT, BUBBLE_RADIUS,
    SBD_START_X, SBD_START_Y, SBD_STEP_X, SBD_STEP_Y,
    CODE_START_X, CODE_START_Y, CODE_STEP_X, CODE_STEP_Y,
    P1_COL1_X, P1_COL2_X, P1_START_Y, P1_STEP_Y, P1_STEP_OPT,
    P2_C1_X, P2_C2_X, P2_START_Y, P2_STEP_Y, P2_STEP_OPT,
    P3_START_X, P3_START_Y, P3_COL_GAP, P3_DIGIT_GAP, P3_ROW_STEP,
    ESSAY_X1, ESSAY_Y1, ESSAY_X2, ESSAY_Y2
)

def create_blank_sheet() -> np.ndarray:
    """Tạo phiếu thi trắng kích thước 2100 x 2970 px chuẩn Bộ GD&ĐT"""
    img = np.ones((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8) * 255

    # 1. Vẽ 4 Marker vuông đen ở 4 góc mép giấy (kích thước 80x80px ~ 10x10mm)
    marker_size = 80
    # Top-Left: tâm (100, 100)
    cv2.rectangle(img, (60, 60), (60 + marker_size, 60 + marker_size), (0, 0, 0), -1)
    # Top-Right: tâm (2000, 100)
    cv2.rectangle(img, (1960, 60), (1960 + marker_size, 60 + marker_size), (0, 0, 0), -1)
    # Bottom-Left: tâm (100, 2870)
    cv2.rectangle(img, (60, 2830), (60 + marker_size, 2830 + marker_size), (0, 0, 0), -1)
    # Bottom-Right: tâm (2000, 2870)
    cv2.rectangle(img, (1960, 2830), (1960 + marker_size, 2830 + marker_size), (0, 0, 0), -1)

    # 2. Header: Tiêu đề và thông tin kỳ thi
    cv2.putText(img, "BO GIAO DUC VA DAO TAO", (200, 120), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 0, 0), 2)
    cv2.putText(img, "PHIẾU TRẢ LỜI TRẮC NGHIỆM VÀ TỰ LUẬN", (650, 140), cv2.FONT_HERSHEY_DUPLEX, 1.4, (0, 0, 128), 3)
    cv2.putText(img, "KỲ THI TỐT NGHIỆP TRUNG HỌC PHỔ THÔNG - MÔN TOÁN", (580, 190), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 0, 0), 2)
    cv2.line(img, (200, 220), (1900, 220), (0, 0, 0), 2)

    # 3. Khối thông tin thí sinh (Viết tay)
    cv2.rectangle(img, (120, 250), (880, 880), (0, 0, 0), 2)
    cv2.putText(img, "THONG TIN THI SINH (Viet ro rang)", (140, 290), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, "1. Ho va ten: .....................................................", (140, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.putText(img, "2. Ngay sinh: ......../......../............   Lop: .............", (140, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.putText(img, "3. Truong: .........................................................", (140, 500), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.putText(img, "4. Phong thi so: .............   Hoi dong: ..................", (140, 570), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.putText(img, "5. Chu ky thi sinh: .............................................", (140, 640), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)

    # Khung hướng dẫn tô
    cv2.rectangle(img, (140, 690), (860, 850), (100, 100, 100), 1)
    cv2.putText(img, "HUONG DAN TO DUNG QUY CACH:", (160, 725), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 180), 2)
    cv2.circle(img, (220, 780), BUBBLE_RADIUS, (0, 0, 0), -1)
    cv2.putText(img, "To dung: Den kin", (260, 785), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 120, 0), 2)
    cv2.circle(img, (520, 780), BUBBLE_RADIUS, (0, 0, 0), 2)
    cv2.line(img, (505, 765), (535, 795), (0, 0, 200), 2)
    cv2.line(img, (505, 795), (535, 765), (0, 0, 200), 2)
    cv2.putText(img, "Sai quy cach: X, /", (560, 785), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)

    # 4. Khối Số Báo Danh (SBD) - 6 cột
    cv2.rectangle(img, (900, 250), (1480, 880), (0, 0, 0), 2)
    cv2.putText(img, "SO BAO DANH (6 so)", (980, 290), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)
    # Ô viết số trước khi tô
    for c in range(6):
        bx = SBD_START_X + c * SBD_STEP_X - 25
        cv2.rectangle(img, (bx, 330), (bx + 50, 380), (0, 0, 0), 1)

    # Lưới ô tô số 0..9
    for r in range(10):
        for c in range(6):
            cx = SBD_START_X + c * SBD_STEP_X
            cy = SBD_START_Y + r * SBD_STEP_Y
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, str(r), (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # 5. Khối Mã Đề Thi - 4 cột
    cv2.rectangle(img, (1500, 250), (1980, 880), (0, 0, 0), 2)
    cv2.putText(img, "MA DE THI (4 so)", (1580, 290), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)
    for c in range(4):
        bx = CODE_START_X + c * CODE_STEP_X - 25
        cv2.rectangle(img, (bx, 330), (bx + 50, 380), (0, 0, 0), 1)

    for r in range(10):
        for c in range(4):
            cx = CODE_START_X + c * CODE_STEP_X
            cy = CODE_START_Y + r * CODE_STEP_Y
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, str(r), (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # 6. Phần I: Trắc nghiệm 12 câu (3.0 điểm)
    cv2.rectangle(img, (120, 900), (1240, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN I: TRAC NGHIEM NHIEU LUA CHON (12 cau - 3.0 diem)", (140, 935), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 150), 2)
    
    opts = ["A", "B", "C", "D"]
    for q in range(1, 13):
        if q <= 6:
            base_x = P1_COL1_X
            row_idx = q - 1
            label_x = 140
        else:
            base_x = P1_COL2_X
            row_idx = q - 7
            label_x = 640

        cy = P1_START_Y + row_idx * P1_STEP_Y
        cv2.putText(img, f"Cau {q:02d}:", (label_x, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)

        for opt_idx, opt_char in enumerate(opts):
            cx = base_x + opt_idx * P1_STEP_OPT
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, opt_char, (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    # 7. Phần II: Đúng / Sai (2.0 điểm)
    cv2.rectangle(img, (1260, 900), (1680, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN II: DUNG / SAI (2.0d)", (1270, 935), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 150), 2)

    sub_letters = ["a", "b", "c", "d"]
    # Câu 1
    cv2.putText(img, "Cau 1:  [D] [S]", (1270, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    for r_idx, sub in enumerate(sub_letters):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cv2.putText(img, f"{sub})", (1270, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        # Ô Đúng
        cv2.circle(img, (P2_C1_X, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "D", (P2_C1_X - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        # Ô Sai
        cv2.circle(img, (P2_C1_X + P2_STEP_OPT, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "S", (P2_C1_X + P2_STEP_OPT - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Câu 2
    cv2.putText(img, "Cau 2:  [D] [S]", (1470, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    for r_idx, sub in enumerate(sub_letters):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cv2.putText(img, f"{sub})", (1470, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        # Ô Đúng
        cv2.circle(img, (P2_C2_X, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "D", (P2_C2_X - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        # Ô Sai
        cv2.circle(img, (P2_C2_X + P2_STEP_OPT, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "S", (P2_C2_X + P2_STEP_OPT - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # 8. Phần III: Trả lời ngắn (2.0 điểm, 4 câu)
    cv2.rectangle(img, (1700, 900), (1980, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN III: TRA LOI NGAN (2.0d)", (1705, 935), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 0, 150), 2)

    symbols = ["-", "."] + [str(i) for i in range(10)]
    for q in range(1, 5):
        q_bx = P3_START_X + (q - 1) * P3_COL_GAP
        cv2.putText(img, f"C{q}", (q_bx, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
        for c in range(4):
            cx = q_bx + c * P3_DIGIT_GAP
            for r_idx, sym in enumerate(symbols):
                cy = P3_START_Y + r_idx * P3_ROW_STEP
                cv2.circle(img, (cx, cy), 6, (0, 0, 0), 1)

    # 9. Phần IV: Tự luận (3.0 điểm - Khung viền đôi ở 45% nửa dưới trang A4)
    # Viền ngoài
    cv2.rectangle(img, (ESSAY_X1, ESSAY_Y1), (ESSAY_X2, ESSAY_Y2), (0, 0, 0), 4)
    # Viền trong (Double Border)
    cv2.rectangle(img, (ESSAY_X1 + 10, ESSAY_Y1 + 10), (ESSAY_X2 - 10, ESSAY_Y2 - 10), (0, 0, 0), 2)

    # Tiêu đề tự luận
    cv2.putText(img, "PHAN IV: TU LUAN (3.0 DIEM) - PHAN DANH CHO THI SINH TRINH BAY LOI GIAI CHI TIET", 
                (ESSAY_X1 + 40, ESSAY_Y1 + 55), cv2.FONT_HERSHEY_DUPLEX, 0.95, (0, 0, 128), 2)
    cv2.line(img, (ESSAY_X1 + 10, ESSAY_Y1 + 80), (ESSAY_X2 - 10, ESSAY_Y1 + 80), (0, 0, 0), 2)

    # Vùng Bài 1 (1.5 điểm)
    mid_essay_y = int((ESSAY_Y1 + ESSAY_Y2) / 2)
    cv2.putText(img, "BAI 1 (1.5 diem): Tim gia tri lon nhat va nho nhat cua ham so y = f(x) tren doan [1; 3]", 
                (ESSAY_X1 + 40, ESSAY_Y1 + 120), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 0), 2)
    
    # Đường phân cách giữa Bài 1 và Bài 2
    cv2.line(img, (ESSAY_X1 + 10, mid_essay_y), (ESSAY_X2 - 10, mid_essay_y), (0, 0, 0), 2)

    # Vùng Bài 2 (1.5 điểm)
    cv2.putText(img, "BAI 2 (1.5 diem): Tinh the tich khoi chop tu giac deu S.ABCD co canh day a, chieu cao h", 
                (ESSAY_X1 + 40, mid_essay_y + 45), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 0), 2)

    return img


def draw_dashed_line(img, pt1, pt2, color=(20, 20, 80), thickness=2, dash_len=10, gap_len=8):
    """Vẽ đường nét đứt đoạn chuẩn hình học không gian cho cạnh khuất"""
    dist = np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
    if dist == 0: return
    dashes = int(dist / (dash_len + gap_len))
    for i in range(dashes + 1):
        start_ratio = (i * (dash_len + gap_len)) / dist
        end_ratio = min(1.0, ((i * (dash_len + gap_len)) + dash_len) / dist)
        p1 = (int(pt1[0] + (pt2[0] - pt1[0]) * start_ratio), int(pt1[1] + (pt2[1] - pt1[1]) * start_ratio))
        p2 = (int(pt1[0] + (pt2[0] - pt1[0]) * end_ratio), int(pt1[1] + (pt2[1] - pt1[1]) * end_ratio))
        cv2.line(img, p1, p2, color, thickness)


def fill_sample_sheet(img: np.ndarray, sbd: str = "010008", exam_code: str = "101") -> np.ndarray:
    """
    Tô mẫu câu trả lời lên phiếu:
    - SBD: '010008'
    - Mã đề: '101' (tô 4 cột '0101')
    - Các ô trắc nghiệm Phần I, II, III
    - Khung tự luận Phần IV với chữ viết tay & hình vẽ khối chóp S.ABCD chuẩn Bộ GD&ĐT
    """
    filled = img.copy()

    def fill_bubble(cx: int, cy: int, r: int = BUBBLE_RADIUS):
        cv2.circle(filled, (cx, cy), r - 1, (20, 20, 20), -1)

    # 1. Tô SBD: '010008'
    sbd_str = str(sbd).zfill(6)
    for c, char in enumerate(sbd_str):
        row = int(char)
        cx = SBD_START_X + c * SBD_STEP_X
        cy = SBD_START_Y + row * SBD_STEP_Y
        fill_bubble(cx, cy)
        bx = SBD_START_X + c * SBD_STEP_X - 10
        cv2.putText(filled, char, (bx, 365), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # 2. Tô Mã Đề: '0101' (đại diện mã 101)
    code_str = str(exam_code).zfill(4)
    for c, char in enumerate(code_str):
        row = int(char)
        cx = CODE_START_X + c * CODE_STEP_X
        cy = CODE_START_Y + row * CODE_STEP_Y
        fill_bubble(cx, cy)
        bx = CODE_START_X + c * CODE_STEP_X - 10
        cv2.putText(filled, char, (bx, 365), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # 3. Tô Phần I: 12 câu (A, B, C, D)
    for q in range(1, 13):
        chosen_idx = (q - 1) % 4
        base_x = P1_COL1_X if q <= 6 else P1_COL2_X
        row_idx = (q - 1) if q <= 6 else (q - 7)
        cy = P1_START_Y + row_idx * P1_STEP_Y
        cx = base_x + chosen_idx * P1_STEP_OPT
        fill_bubble(cx, cy)

    # 4. Tô Phần II: 2 câu Đúng / Sai
    # Câu 1: a:D, b:S, c:D, d:S
    p2_c1_ans = [0, 1, 0, 1]
    for r_idx, ans_type in enumerate(p2_c1_ans):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cx = P2_C1_X if ans_type == 0 else (P2_C1_X + P2_STEP_OPT)
        fill_bubble(cx, cy)

    # Câu 2: a:S, b:D, c:D, d:S
    p2_c2_ans = [1, 0, 0, 1]
    for r_idx, ans_type in enumerate(p2_c2_ans):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cx = P2_C2_X if ans_type == 0 else (P2_C2_X + P2_STEP_OPT)
        fill_bubble(cx, cy)

    # 5. Tô Phần III: 4 câu
    # C1: 12.5 | C2: -3.4 | C3: 0.75 | C4: 100
    p3_ans = ["12.5", "-3.4", "0.75", "100"]
    symbols = ["-", "."] + [str(i) for i in range(10)]
    for q_idx, val in enumerate(p3_ans, start=1):
        q_bx = P3_START_X + (q_idx - 1) * P3_COL_GAP
        for col_idx, char in enumerate(val[:4]):
            if char in symbols:
                r_idx = symbols.index(char)
                cx = q_bx + col_idx * P3_DIGIT_GAP
                cy = P3_START_Y + r_idx * P3_ROW_STEP
                cv2.circle(filled, (cx, cy), 7, (20, 20, 20), -1)

    # 6. Giả lập chữ viết tay & hình vẽ ở Phần Tự Luận
    mid_essay_y = int((ESSAY_Y1 + ESSAY_Y2) / 2)

    # Lời giải Bài 1: GTLN, GTNN
    cv2.putText(filled, "Loi giai Bai 1:", (ESSAY_X1 + 50, ESSAY_Y1 + 160), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (20, 20, 80), 2)
    cv2.putText(filled, "+ TXD: D = [1; 3]. Ham so lien tuc tren [1; 3].", (ESSAY_X1 + 50, ESSAY_Y1 + 215), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ Dao ham: f'(x) = 3x^2 - 6x = 3x(x - 2).", (ESSAY_X1 + 50, ESSAY_Y1 + 270), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ f'(x) = 0 <=> x = 0 (loai vi khong thuoc [1; 3]), x = 2 (nhan).", (ESSAY_X1 + 50, ESSAY_Y1 + 325), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ Tinh cac gia tri: f(1) = 4, f(2) = 1, f(3) = 9.", (ESSAY_X1 + 50, ESSAY_Y1 + 380), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ Ket luan: Max f(x) = 9 (tai x = 3); Min f(x) = 1 (tai x = 2).", (ESSAY_X1 + 50, ESSAY_Y1 + 435), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)

    # Lời giải Bài 2: Khối chóp tứ giác đều S.ABCD
    cv2.putText(filled, "Loi giai Bai 2:", (ESSAY_X1 + 50, mid_essay_y + 80), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (20, 20, 80), 2)
    cv2.putText(filled, "+ Goi O la giao diem cua AC va BD => SO vuong goc (ABCD).", (ESSAY_X1 + 50, mid_essay_y + 135), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ ABCD la hinh vuong canh a => S_ABCD = a^2.", (ESSAY_X1 + 50, mid_essay_y + 190), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ Chieu cao khoi chop: h = SO.", (ESSAY_X1 + 50, mid_essay_y + 245), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ The tich khoi chop: V = (1/3) * S_ABCD * h = (1/3) * a^2 * h.", (ESSAY_X1 + 50, mid_essay_y + 300), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)
    cv2.putText(filled, "+ Ket luan: V = (a^2 * h) / 3 (dvtt).", (ESSAY_X1 + 50, mid_essay_y + 355), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.92, (20, 20, 80), 2)

    # 7. VẼ HÌNH HỌC KHÔNG GIAN KHỐI CHÓP S.ABCD (CHUẨN BỘ GD&ĐT: CẠNH THẤY NÉT LIỀN, KHUẤT NÉT ĐỨT)
    # Tọa độ các đỉnh
    pt_S = (1680, mid_essay_y + 100)
    pt_A = (1520, mid_essay_y + 270)
    pt_B = (1460, mid_essay_y + 420)
    pt_C = (1750, mid_essay_y + 460)
    pt_D = (1880, mid_essay_y + 310)
    pt_O = (1650, mid_essay_y + 365)

    color_geo = (30, 30, 80)
    # Cạnh khuất (vẽ nét đứt)
    draw_dashed_line(filled, pt_A, pt_B, color_geo, thickness=2)
    draw_dashed_line(filled, pt_A, pt_D, color_geo, thickness=2)
    draw_dashed_line(filled, pt_S, pt_A, color_geo, thickness=2)
    draw_dashed_line(filled, pt_S, pt_O, color_geo, thickness=2)
    draw_dashed_line(filled, pt_A, pt_C, color_geo, thickness=1, dash_len=6, gap_len=6)
    draw_dashed_line(filled, pt_B, pt_D, color_geo, thickness=1, dash_len=6, gap_len=6)

    # Cạnh thấy (vẽ nét liền)
    cv2.line(filled, pt_B, pt_C, color_geo, 2)
    cv2.line(filled, pt_C, pt_D, color_geo, 2)
    cv2.line(filled, pt_S, pt_B, color_geo, 2)
    cv2.line(filled, pt_S, pt_C, color_geo, 2)
    cv2.line(filled, pt_S, pt_D, color_geo, 2)

    # Nhãn đỉnh in hoa in nghiêng
    cv2.putText(filled, "S", (pt_S[0] - 8, pt_S[1] - 12), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, color_geo, 2)
    cv2.putText(filled, "A", (pt_A[0] - 25, pt_A[1] - 5), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, color_geo, 2)
    cv2.putText(filled, "B", (pt_B[0] - 25, pt_B[1] + 15), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, color_geo, 2)
    cv2.putText(filled, "C", (pt_C[0] + 10, pt_C[1] + 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, color_geo, 2)
    cv2.putText(filled, "D", (pt_D[0] + 10, pt_D[1] - 5), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, color_geo, 2)
    cv2.putText(filled, "O", (pt_O[0] + 5, pt_O[1] + 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.0, color_geo, 2)

    # Điền thông tin thí sinh
    cv2.putText(filled, "Tran Quoc Tuan", (350, 360), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (20, 20, 80), 2)
    cv2.putText(filled, "10/05/2007", (350, 430), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.9, (20, 20, 80), 2)
    cv2.putText(filled, "12A3", (680, 430), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.9, (20, 20, 80), 2)
    cv2.putText(filled, "THPT Chu Van An - Ha Noi", (300, 500), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.9, (20, 20, 80), 2)

    return filled

if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    # 1. Sinh phiếu trắng chuẩn A4
    blank = create_blank_sheet()
    blank_path = os.path.join(out_dir, "phieu_thi_chuan_A4.png")
    cv2.imwrite(blank_path, blank)
    print(f"Đã tạo phiếu thi trắng chuẩn A4: {blank_path}")

    # 2. Sinh phiếu kiểm thử mô phỏng hoàn chỉnh: SBD 010008, Mã đề 101
    sample_test = fill_sample_sheet(blank, sbd="010008", exam_code="101")
    sample_test_path = os.path.join(out_dir, "sample_test_sheet.png")
    cv2.imwrite(sample_test_path, sample_test)
    print(f"Đã tạo file ảnh bài thi mô phỏng SBD 010008 - Đề 101: {sample_test_path}")

    # 3. Đồng bộ thêm file sample_filled_sheet.png
    sample_path = os.path.join(out_dir, "sample_filled_sheet.png")
    cv2.imwrite(sample_path, sample_test)

