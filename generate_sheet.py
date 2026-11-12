"""
Module generate_sheet.py - Trình sinh Phiếu Trả Lời Trắc Nghiệm chuẩn Bộ GD&ĐT
Hỗ trợ 2 loại phiếu:
1. Mẫu 3 phần (100% Trắc nghiệm): Trắc nghiệm + Đúng/Sai + Trả lời ngắn.
2. Mẫu 4 phần: Trắc nghiệm + Đúng/Sai + Trả lời ngắn + Khung Tự luận (45% nửa dưới).
Đều có 4 Marker đen hình vuông chuẩn 10x10mm ở 4 góc ngoài mép giấy để bắt góc và nắn phẳng.
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

def draw_markers_and_header(img: np.ndarray, title: str, subtitle: str = "PHIẾU TRẢ LỜI TRẮC NGHIỆM") -> np.ndarray:
    """Vẽ 4 Marker vuông đen ở 4 góc và phần Header tiêu đề chuẩn Bộ GD&ĐT"""
    marker_size = 80
    # Top-Left: tâm (100, 100)
    cv2.rectangle(img, (60, 60), (60 + marker_size, 60 + marker_size), (0, 0, 0), -1)
    # Top-Right: tâm (2000, 100)
    cv2.rectangle(img, (1960, 60), (1960 + marker_size, 60 + marker_size), (0, 0, 0), -1)
    # Bottom-Left: tâm (100, 2870)
    cv2.rectangle(img, (60, 2830), (60 + marker_size, 2830 + marker_size), (0, 0, 0), -1)
    # Bottom-Right: tâm (2000, 2870)
    cv2.rectangle(img, (1960, 2830), (1960 + marker_size, 2830 + marker_size), (0, 0, 0), -1)

    # Header
    cv2.putText(img, "BO GIAO DUC VA DAO TAO", (200, 120), cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, subtitle, (620, 140), cv2.FONT_HERSHEY_DUPLEX, 1.35, (0, 0, 128), 3)
    cv2.putText(img, title, (580, 190), cv2.FONT_HERSHEY_DUPLEX, 1.05, (0, 0, 0), 2)
    cv2.line(img, (200, 220), (1900, 220), (0, 0, 0), 2)

    # Khối thông tin thí sinh (Viết tay)
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

    # Khối Số Báo Danh (SBD) - 6 cột
    cv2.rectangle(img, (900, 250), (1480, 880), (0, 0, 0), 2)
    cv2.putText(img, "SO BAO DANH (6 so)", (980, 290), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)
    for c in range(6):
        bx = SBD_START_X + c * SBD_STEP_X - 25
        cv2.rectangle(img, (bx, 330), (bx + 50, 380), (0, 0, 0), 1)

    for r in range(10):
        for c in range(6):
            cx = SBD_START_X + c * SBD_STEP_X
            cy = SBD_START_Y + r * SBD_STEP_Y
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, str(r), (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Khối Mã Đề Thi - 4 cột
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

    return img


# ==============================================================================
# 1. SINH PHIẾU LOẠI 4 PHẦN (CÓ TỰ LUẬN)
# ==============================================================================

def create_sheet_4part(title: str = "KY THI TOT NGHIEP THPT - MON TOAN (CO TU LUAN)") -> np.ndarray:
    """Sinh phiếu 4 phần: Trắc nghiệm (12 câu) + Đúng/Sai (2 câu) + Trả lời ngắn (4 câu) + Tự luận (45% dưới)"""
    img = np.ones((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8) * 255
    img = draw_markers_and_header(img, title, subtitle="PHIẾU TRẢ LỜI TRẮC NGHIỆM VÀ TỰ LUẬN")

    # Phần I: Trắc nghiệm 12 câu
    cv2.rectangle(img, (120, 900), (1240, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN I: TRAC NGHIEM NHIEU LUA CHON (12 cau - 3.0 diem)", (140, 935), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 150), 2)
    opts = ["A", "B", "C", "D"]
    for q in range(1, 13):
        base_x = P1_COL1_X if q <= 6 else P1_COL2_X
        row_idx = (q - 1) if q <= 6 else (q - 7)
        label_x = 140 if q <= 6 else 640
        cy = P1_START_Y + row_idx * P1_STEP_Y
        cv2.putText(img, f"Cau {q:02d}:", (label_x, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
        for opt_idx, opt_char in enumerate(opts):
            cx = base_x + opt_idx * P1_STEP_OPT
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, opt_char, (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    # Phần II: Đúng / Sai (2 câu)
    cv2.rectangle(img, (1260, 900), (1680, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN II: DUNG / SAI (2.0d)", (1270, 935), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 150), 2)
    sub_letters = ["a", "b", "c", "d"]
    # Câu 1
    cv2.putText(img, "Cau 1:  [D] [S]", (1270, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    for r_idx, sub in enumerate(sub_letters):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cv2.putText(img, f"{sub})", (1270, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.circle(img, (P2_C1_X, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "D", (P2_C1_X - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        cv2.circle(img, (P2_C1_X + P2_STEP_OPT, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "S", (P2_C1_X + P2_STEP_OPT - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Câu 2
    cv2.putText(img, "Cau 2:  [D] [S]", (1470, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    for r_idx, sub in enumerate(sub_letters):
        cy = P2_START_Y + r_idx * P2_STEP_Y
        cv2.putText(img, f"{sub})", (1470, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.circle(img, (P2_C2_X, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "D", (P2_C2_X - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        cv2.circle(img, (P2_C2_X + P2_STEP_OPT, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
        cv2.putText(img, "S", (P2_C2_X + P2_STEP_OPT - 6, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Phần III: Trả lời ngắn (4 câu)
    cv2.rectangle(img, (1700, 900), (1980, 1500), (0, 0, 0), 2)
    cv2.putText(img, "PHAN III: TRA LOI NGAN", (1705, 935), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 0, 150), 2)
    symbols = ["-", "."] + [str(i) for i in range(10)]
    for q in range(1, 5):
        q_bx = P3_START_X + (q - 1) * P3_COL_GAP
        cv2.putText(img, f"C{q}", (q_bx, 965), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
        for c in range(4):
            cx = q_bx + c * P3_DIGIT_GAP
            for r_idx, sym in enumerate(symbols):
                cy = P3_START_Y + r_idx * P3_ROW_STEP
                cv2.circle(img, (cx, cy), 6, (0, 0, 0), 1)

    # Phần IV: Khung Tự Luận (45% nửa dưới trang A4)
    cv2.rectangle(img, (ESSAY_X1, ESSAY_Y1), (ESSAY_X2, ESSAY_Y2), (0, 0, 0), 4)
    cv2.rectangle(img, (ESSAY_X1 + 10, ESSAY_Y1 + 10), (ESSAY_X2 - 10, ESSAY_Y2 - 10), (0, 0, 0), 2)
    cv2.putText(img, "PHAN IV: TU LUAN (3.0 DIEM) - PHAN DANH CHO THI SINH TRINH BAY LOI GIAI CHI TIET", 
                (ESSAY_X1 + 40, ESSAY_Y1 + 55), cv2.FONT_HERSHEY_DUPLEX, 0.95, (0, 0, 128), 2)
    cv2.line(img, (ESSAY_X1 + 10, ESSAY_Y1 + 80), (ESSAY_X2 - 10, ESSAY_Y1 + 80), (0, 0, 0), 2)

    mid_essay_y = int((ESSAY_Y1 + ESSAY_Y2) / 2)
    cv2.putText(img, "BAI 1 (1.5 diem): Tim gia tri lon nhat va nho nhat cua ham so y = f(x) tren doan [1; 3]", 
                (ESSAY_X1 + 40, ESSAY_Y1 + 120), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 0), 2)
    cv2.line(img, (ESSAY_X1 + 10, mid_essay_y), (ESSAY_X2 - 10, mid_essay_y), (0, 0, 0), 2)
    cv2.putText(img, "BAI 2 (1.5 diem): Tinh the tich khoi chop tu giac deu S.ABCD co canh day a, chieu cao h", 
                (ESSAY_X1 + 40, mid_essay_y + 45), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 0), 2)

    return img


# ==============================================================================
# 2. SINH PHIẾU LOẠI 3 PHẦN (100% TRẮC NGHIỆM CHUẨN BỘ GD&ĐT 2025)
# ==============================================================================

def create_sheet_3part(title: str = "KY THI TOT NGHIEP THPT - FORM 3 PHAN TRAC NGHIEM") -> np.ndarray:
    """Sinh phiếu 3 phần: Trắc nghiệm (lên đến 24 câu) + Đúng/Sai (4 câu) + Trả lời ngắn (6 câu)"""
    img = np.ones((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8) * 255
    img = draw_markers_and_header(img, title, subtitle="PHIẾU TRẢ LỜI TRẮC NGHIỆM (100% TRẮC NGHIỆM)")

    # 1. Phần I: Trắc nghiệm (Bố trí 24 câu rộng rãi, chia 4 cột: 1-6, 7-12, 13-18, 19-24)
    cv2.rectangle(img, (120, 900), (1980, 1650), (0, 0, 0), 2)
    cv2.putText(img, "PHAN I: TRAC NGHIEM NHIEU LUA CHON (A, B, C, D)", (140, 935), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 150), 2)
    opts = ["A", "B", "C", "D"]
    col_offsets = [150, 600, 1050, 1500]

    for q in range(1, 25):
        col_idx = (q - 1) // 6
        row_idx = (q - 1) % 6
        base_x = col_offsets[col_idx] + 100
        cy = 990 + row_idx * 100
        cv2.putText(img, f"Cau {q:02d}:", (col_offsets[col_idx], cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
        for opt_idx, opt_char in enumerate(opts):
            cx = base_x + opt_idx * 65
            cv2.circle(img, (cx, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, opt_char, (cx - 7, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    # 2. Phần II: Đúng / Sai (4 câu, bố trí ở nửa dưới bên trái)
    cv2.rectangle(img, (120, 1700), (1030, 2800), (0, 0, 0), 2)
    cv2.putText(img, "PHAN II: DUNG / SAI (4 cau, moi cau 4 y a, b, c, d)", (140, 1740), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 150), 2)

    sub_letters = ["a", "b", "c", "d"]
    p2_col_x = [150, 580]  # Câu 1, 2 ở cột trái; Câu 3, 4 ở cột phải
    for q_idx in range(1, 5):
        c_col = (q_idx - 1) // 2
        c_row = (q_idx - 1) % 2
        base_x = p2_col_x[c_col]
        start_y = 1780 + c_row * 480
        cv2.putText(img, f"Cau {q_idx}: [D] [S]", (base_x, start_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        for r_idx, sub in enumerate(sub_letters):
            cy = start_y + 80 + r_idx * 85
            cv2.putText(img, f"{sub})", (base_x, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
            # Ô Đúng
            cv2.circle(img, (base_x + 90, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, "D", (base_x + 84, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
            # Ô Sai
            cv2.circle(img, (base_x + 160, cy), BUBBLE_RADIUS, (0, 0, 0), 2)
            cv2.putText(img, "S", (base_x + 154, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # 3. Phần III: Trả lời ngắn (6 câu, bố trí ở nửa dưới bên phải)
    cv2.rectangle(img, (1070, 1700), (1980, 2800), (0, 0, 0), 2)
    cv2.putText(img, "PHAN III: TRA LOI NGAN (6 cau so thuc)", (1090, 1740), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 150), 2)

    symbols = ["-", "."] + [str(i) for i in range(10)]
    for q in range(1, 7):
        q_col = (q - 1) % 3
        q_row = (q - 1) // 3
        q_bx = 1110 + q_col * 290
        q_by = 1790 + q_row * 480
        cv2.putText(img, f"Cau {q}:", (q_bx, q_by + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
        for c in range(4):
            cx = q_bx + 10 + c * 20
            for r_idx, sym in enumerate(symbols):
                cy = q_by + 55 + r_idx * 32
                cv2.circle(img, (cx, cy), 6, (0, 0, 0), 1)

    return img


# ==============================================================================
# 3. TÔ MẪU PHIẾU ĐỂ KIỂM THỬ OMR & TỰ LUẬN
# ==============================================================================

def draw_dashed_line(img, pt1, pt2, color=(20, 20, 80), thickness=2, dash_len=10, gap_len=8):
    """Vẽ nét đứt đoạn chuẩn hình học không gian"""
    dist = np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
    if dist == 0: return
    dashes = int(dist / (dash_len + gap_len))
    for i in range(dashes + 1):
        start_ratio = (i * (dash_len + gap_len)) / dist
        end_ratio = min(1.0, ((i * (dash_len + gap_len)) + dash_len) / dist)
        p1 = (int(pt1[0] + (pt2[0] - pt1[0]) * start_ratio), int(pt1[1] + (pt2[1] - pt1[1]) * start_ratio))
        p2 = (int(pt1[0] + (pt2[0] - pt1[0]) * end_ratio), int(pt1[1] + (pt2[1] - pt1[1]) * end_ratio))
        cv2.line(img, p1, p2, color, thickness)

def fill_sample_sheet(img: np.ndarray, sbd: str = "010008", exam_code: str = "101", sheet_type: str = "4_part") -> np.ndarray:
    """Tô mẫu câu trả lời lên phiếu để kiểm thử hệ thống OMR và AI tự luận"""
    filled = img.copy()

    def fill_bubble(cx: int, cy: int, r: int = BUBBLE_RADIUS):
        cv2.circle(filled, (cx, cy), r - 1, (20, 20, 20), -1)

    # 1. Tô SBD
    sbd_str = str(sbd).zfill(6)
    for c, char in enumerate(sbd_str):
        row = int(char)
        cx = SBD_START_X + c * SBD_STEP_X
        cy = SBD_START_Y + row * SBD_STEP_Y
        fill_bubble(cx, cy)
        bx = SBD_START_X + c * SBD_STEP_X - 10
        cv2.putText(filled, char, (bx, 365), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # 2. Tô Mã Đề
    code_str = str(exam_code).zfill(4)
    for c, char in enumerate(code_str):
        row = int(char)
        cx = CODE_START_X + c * CODE_STEP_X
        cy = CODE_START_Y + row * CODE_STEP_Y
        fill_bubble(cx, cy)
        bx = CODE_START_X + c * CODE_STEP_X - 10
        cv2.putText(filled, char, (bx, 365), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    if sheet_type == "4_part":
        # Tô Phần I: 12 câu
        for q in range(1, 13):
            chosen_idx = (q - 1) % 4
            base_x = P1_COL1_X if q <= 6 else P1_COL2_X
            row_idx = (q - 1) if q <= 6 else (q - 7)
            cy = P1_START_Y + row_idx * P1_STEP_Y
            cx = base_x + chosen_idx * P1_STEP_OPT
            fill_bubble(cx, cy)

        # Tô Phần II: 2 câu Đúng / Sai
        p2_c1_ans = [0, 1, 0, 1]
        for r_idx, ans_type in enumerate(p2_c1_ans):
            cy = P2_START_Y + r_idx * P2_STEP_Y
            cx = P2_C1_X if ans_type == 0 else (P2_C1_X + P2_STEP_OPT)
            fill_bubble(cx, cy)

        p2_c2_ans = [1, 0, 0, 1]
        for r_idx, ans_type in enumerate(p2_c2_ans):
            cy = P2_START_Y + r_idx * P2_STEP_Y
            cx = P2_C2_X if ans_type == 0 else (P2_C2_X + P2_STEP_OPT)
            fill_bubble(cx, cy)

        # Tô Phần III: 4 câu
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

        # Khung tự luận
        mid_essay_y = int((ESSAY_Y1 + ESSAY_Y2) / 2)
        cv2.putText(filled, "Loi giai Bai 1: f'(x) = 3x^2 - 6x = 0 => Max f(x)=9, Min f(x)=1", (ESSAY_X1 + 50, ESSAY_Y1 + 180), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.95, (20, 20, 80), 2)
        cv2.putText(filled, "Loi giai Bai 2: SO vuong goc day ABCD => The tich V = (1/3)*a^2*h", (ESSAY_X1 + 50, mid_essay_y + 100), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.95, (20, 20, 80), 2)

        # Hình chóp tứ giác đều S.ABCD
        pt_S = (1680, mid_essay_y + 100)
        pt_A = (1520, mid_essay_y + 270)
        pt_B = (1460, mid_essay_y + 420)
        pt_C = (1750, mid_essay_y + 460)
        pt_D = (1880, mid_essay_y + 310)
        pt_O = (1650, mid_essay_y + 365)
        color_geo = (30, 30, 80)

        draw_dashed_line(filled, pt_A, pt_B, color_geo)
        draw_dashed_line(filled, pt_A, pt_D, color_geo)
        draw_dashed_line(filled, pt_S, pt_A, color_geo)
        draw_dashed_line(filled, pt_S, pt_O, color_geo)
        cv2.line(filled, pt_B, pt_C, color_geo, 2)
        cv2.line(filled, pt_C, pt_D, color_geo, 2)
        cv2.line(filled, pt_S, pt_B, color_geo, 2)
        cv2.line(filled, pt_S, pt_C, color_geo, 2)
        cv2.line(filled, pt_S, pt_D, color_geo, 2)

    return filled


if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    # 1. Sinh phiếu 4 phần chuẩn
    p4 = create_sheet_4part()
    cv2.imwrite(os.path.join(out_dir, "phieu_thi_4_phan_A4.png"), p4)
    cv2.imwrite(os.path.join(out_dir, "phieu_thi_chuan_A4.png"), p4)
    print("Đã tạo phiếu thi 4 phần chuẩn A4.")

    # 2. Sinh phiếu 3 phần chuẩn (100% trắc nghiệm)
    p3 = create_sheet_3part()
    cv2.imwrite(os.path.join(out_dir, "phieu_thi_3_phan_A4.png"), p3)
    print("Đã tạo phiếu thi 3 phần chuẩn A4.")

    # 3. Sinh phiếu bài làm mô phỏng 010008 - Đề 101
    sample = fill_sample_sheet(p4, sbd="010008", exam_code="101", sheet_type="4_part")
    cv2.imwrite(os.path.join(out_dir, "sample_test_sheet.png"), sample)
    cv2.imwrite(os.path.join(out_dir, "sample_filled_sheet.png"), sample)
    print("Đã tạo bài làm mẫu mô phỏng.")
