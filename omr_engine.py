"""
Module omr_engine.py - Bộ xử lý Thị giác máy tính & OMR (Optical Mark Recognition)
Nhiệm vụ:
1. Phát hiện 4 marker góc hình vuông đen (10x10mm) và nắn thẳng ảnh (Perspective Warp) về kích thước chuẩn 2100 x 2970 px.
2. Bóc tách và nhận diện Số Báo Danh (SBD - 6 cột) và Mã Đề Thi (4 cột).
3. Chấm trắc nghiệm Phần I (12 câu A, B, C, D - 0.25đ/câu).
4. Chấm trắc nghiệm Đúng/Sai Phần II (2 câu x 4 ý a,b,c,d - lũy tiến 0.10, 0.25, 0.50, 1.00đ).
5. Chấm trả lời ngắn Phần III (4 câu, mỗi câu 4 cột số thực - 0.50đ/câu).
6. Tự động cắt vùng làm bài Tự Luận Phần IV (45% nửa dưới trang A4) chuẩn bị cho Gemini AI.
"""

import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional, List

# Kích thước chuẩn A4 sau khi nắn góc (Perspective Warp)
CANVAS_WIDTH = 2100
CANVAS_HEIGHT = 2970

# Bán kính ô tròn tô đáp án
BUBBLE_RADIUS = 16

# ==============================================================================
# HỆ TỌA ĐỘ CHUẨN CÁC VÙNG TRÊN PHIẾU THI (2100 x 2970 px)
# ==============================================================================

# 1. Khối Số Báo Danh (SBD): 6 cột (0 đến 9)
SBD_START_X = 930
SBD_START_Y = 430
SBD_STEP_X = 70
SBD_STEP_Y = 40

# 2. Khối Mã Đề Thi: 4 cột (0 đến 9)
CODE_START_X = 1530
CODE_START_Y = 430
CODE_STEP_X = 75
CODE_STEP_Y = 40

# 3. Phần I - 12 câu trắc nghiệm nhiều lựa chọn (chia 2 cột hiển thị: Câu 1-6 và Câu 7-12)
# Mỗi câu có 4 phương án: A, B, C, D
P1_COL1_X = 220    # Cột 1: Câu 1 đến 6
P1_COL2_X = 720    # Cột 2: Câu 7 đến 12
P1_START_Y = 970
P1_STEP_Y = 70
P1_STEP_OPT = 65   # Khoảng cách giữa các ô A, B, C, D

# 4. Phần II - Đúng / Sai (2 câu, mỗi câu 4 ý a, b, c, d)
# Mỗi ý có 2 ô: [Đ] và [S]
P2_C1_X = 1330     # Vị trí X của ô [Đ] Câu 1
P2_C2_X = 1530     # Vị trí X của ô [Đ] Câu 2
P2_START_Y = 985   # Tọa độ Y của ý a)
P2_STEP_Y = 65     # Khoảng cách giữa các ý a, b, c, d
P2_STEP_OPT = 65   # Khoảng cách giữa ô [Đ] và ô [S]

# 5. Phần III - Trả lời ngắn (4 câu, mỗi câu 4 cột: -, ., 0..9)
P3_START_X = 1715
P3_START_Y = 980   # Tọa độ Y của hàng đầu tiên (dấu '-')
P3_COL_GAP = 70    # Khoảng cách giữa các câu
P3_DIGIT_GAP = 16  # Khoảng cách giữa các cột trong 1 câu
P3_ROW_STEP = 38   # Khoảng cách giữa các hàng

# 6. Phần IV - Khung Tự luận (45% nửa dưới trang A4)
ESSAY_X1 = 100
ESSAY_Y1 = 1560
ESSAY_X2 = 2000
ESSAY_Y2 = 2860


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Sắp xếp 4 tọa độ đỉnh theo thứ tự chuẩn:
    [0]: Top-Left, [1]: Top-Right, [2]: Bottom-Right, [3]: Bottom-Left
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # Top-Left có tổng x + y nhỏ nhất
    rect[2] = pts[np.argmax(s)]      # Bottom-Right có tổng x + y lớn nhất

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # Top-Right có y - x nhỏ nhất (hoặc x - y lớn nhất)
    rect[3] = pts[np.argmax(diff)]   # Bottom-Left có y - x lớn nhất
    return rect


def detect_markers_and_warp(image_bgr: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Tự động phát hiện 4 marker vuông đen ở 4 góc mép giấy và nắn thẳng ảnh về 2100x2970.
    Nếu không thấy đủ 4 marker nhỏ, tự động fallback tìm mép giấy lớn hoặc chuẩn hóa kích thước.
    """
    orig_h, orig_w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 8
    )

    # 1. Tìm các contour của marker vuông đen
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    marker_centers = []
    
    total_area = orig_w * orig_h
    min_marker_area = total_area * 0.00008  # Tối thiểu khoảng 0.008% diện tích ảnh
    max_marker_area = total_area * 0.05     # Tối đa khoảng 5% diện tích ảnh

    for c in contours:
        area = cv2.contourArea(c)
        if min_marker_area < area < max_marker_area:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = float(w) / h
                if 0.70 <= aspect_ratio <= 1.35:
                    # Kiểm tra độ đậm đặc bên trong contour
                    mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(mask, [c], -1, 255, -1)
                    mean_val = cv2.mean(gray, mask=mask)[0]
                    # Marker đen phải có giá trị xám trung bình thấp
                    if mean_val < 110:
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cX = int(M["m10"] / M["m00"])
                            cY = int(M["m01"] / M["m00"])
                            marker_centers.append([cX, cY])

    # Lọc bỏ các tâm bị trùng nhau quá gần
    filtered_centers = []
    for pt in marker_centers:
        too_close = False
        for f in filtered_centers:
            if np.hypot(pt[0] - f[0], pt[1] - f[1]) < (orig_w * 0.05):
                too_close = True
                break
        if not too_close:
            filtered_centers.append(pt)

    # Nếu tìm được ít nhất 4 marker ở 4 góc:
    if len(filtered_centers) >= 4:
        pts = np.array(filtered_centers, dtype="float32")
        # Phân nhóm về 4 góc phần tư của ảnh
        mid_x, mid_y = orig_w / 2, orig_h / 2
        tl = [p for p in pts if p[0] < mid_x and p[1] < mid_y]
        tr = [p for p in pts if p[0] >= mid_x and p[1] < mid_y]
        br = [p for p in pts if p[0] >= mid_x and p[1] >= mid_y]
        bl = [p for p in pts if p[0] < mid_x and p[1] >= mid_y]

        if tl and tr and br and bl:
            # Chọn marker gần góc cực nhất trong mỗi nhóm
            p_tl = min(tl, key=lambda p: p[0]**2 + p[1]**2)
            p_tr = min(tr, key=lambda p: (orig_w - p[0])**2 + p[1]**2)
            p_br = min(br, key=lambda p: (orig_w - p[0])**2 + (orig_h - p[1])**2)
            p_bl = min(bl, key=lambda p: p[0]**2 + (orig_h - p[1])**2)

            src = np.array([p_tl, p_tr, p_br, p_bl], dtype="float32")
            # Tọa độ đích tâm 4 marker trên ảnh 2100 x 2970
            dst = np.array([
                [100, 100],
                [2000, 100],
                [2000, 2870],
                [100, 2870]
            ], dtype="float32")

            M = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(image_bgr, M, (CANVAS_WIDTH, CANVAS_HEIGHT))
            return warped, True

    # 2. Fallback: Tìm contour mép giấy A4 lớn nhất
    paper_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    for c in paper_contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(c) > (total_area * 0.35):
            pts = approx.reshape(4, 2).astype("float32")
            rect = order_points(pts)
            dst = np.array([
                [0, 0],
                [CANVAS_WIDTH - 1, 0],
                [CANVAS_WIDTH - 1, CANVAS_HEIGHT - 1],
                [0, CANVAS_HEIGHT - 1]
            ], dtype="float32")
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(image_bgr, M, (CANVAS_WIDTH, CANVAS_HEIGHT))
            return warped, False

    # 3. Fallback cuối cùng: Ảnh đã căn vừa khung, resize về chuẩn 2100 x 2970
    warped = cv2.resize(image_bgr, (CANVAS_WIDTH, CANVAS_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    return warped, False


def get_bubble_density(gray_thresh: np.ndarray, cx: int, cy: int, radius: int = BUBBLE_RADIUS) -> float:
    """
    Tính mật độ điểm đen (Pixel Density) bên trong vùng ô tròn.
    Đã trừ đi viền ngoài 3px để loại bỏ nét in sẵn của ô tròn.
    """
    h, w = gray_thresh.shape
    r = radius - 3
    x1, y1 = max(0, cx - r), max(0, cy - r)
    x2, y2 = min(w, cx + r), min(h, cy + r)

    roi = gray_thresh[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0

    # Tạo mask hình tròn bên trong
    mask = np.zeros(roi.shape, dtype=np.uint8)
    local_cx, local_cy = cx - x1, cy - y1
    cv2.circle(mask, (local_cx, local_cy), r, 255, -1)

    black_pixels = np.count_nonzero((roi == 255) & (mask == 255))
    total_mask_pixels = np.count_nonzero(mask == 255)

    if total_mask_pixels == 0:
        return 0.0
    return float(black_pixels) / float(total_mask_pixels)


def read_sbd(thresh: np.ndarray) -> str:
    """
    Đọc Số Báo Danh (SBD) gồm 6 cột (chữ số từ 0 đến 9).
    Trả về chuỗi 6 ký tự, ví dụ: '010001'.
    """
    sbd_digits = []
    for col in range(6):
        cx = SBD_START_X + col * SBD_STEP_X
        densities = []
        for row in range(10):  # Chữ số 0 đến 9
            cy = SBD_START_Y + row * SBD_STEP_Y
            density = get_bubble_density(thresh, cx, cy)
            densities.append((density, row))
        
        densities.sort(key=lambda x: x[0], reverse=True)
        top_density, top_digit = densities[0]
        second_density, _ = densities[1]

        # Kiểm tra điều kiện tô rõ ràng
        if top_density >= 0.35 and (top_density - second_density >= 0.12):
            sbd_digits.append(str(top_digit))
        elif top_density >= 0.40:
            sbd_digits.append(str(top_digit))
        else:
            sbd_digits.append(str(top_digit) if top_density > 0.25 else "0")

    return "".join(sbd_digits)


def read_exam_code(thresh: np.ndarray) -> str:
    """
    Đọc Mã Đề Thi gồm 4 cột (chữ số từ 0 đến 9).
    Trả về chuỗi 4 ký tự, ví dụ: '0101'.
    """
    code_digits = []
    for col in range(4):
        cx = CODE_START_X + col * CODE_STEP_X
        densities = []
        for row in range(10):
            cy = CODE_START_Y + row * CODE_STEP_Y
            density = get_bubble_density(thresh, cx, cy)
            densities.append((density, row))

        densities.sort(key=lambda x: x[0], reverse=True)
        top_density, top_digit = densities[0]
        second_density, _ = densities[1]

        if top_density >= 0.35 and (top_density - second_density >= 0.12):
            code_digits.append(str(top_digit))
        elif top_density >= 0.40:
            code_digits.append(str(top_digit))
        else:
            code_digits.append(str(top_digit) if top_density > 0.25 else "1")

    return "".join(code_digits)


def grade_part1(thresh: np.ndarray, answer_key: Dict[str, str]) -> Tuple[float, Dict[str, Any]]:
    """
    Chấm Phần I - Trắc nghiệm 12 câu, 4 lựa chọn (A, B, C, D).
    Mỗi câu đúng được 0.25 điểm. Tối đa 3.0 điểm.
    """
    options = ["A", "B", "C", "D"]
    total_score = 0.0
    details = {}

    for q_idx in range(1, 13):
        # Xác định vị trí cột và hàng của câu
        if q_idx <= 6:
            base_x = P1_COL1_X
            row_idx = q_idx - 1
        else:
            base_x = P1_COL2_X
            row_idx = q_idx - 7

        cy = P1_START_Y + row_idx * P1_STEP_Y
        densities = []

        for opt_idx, opt_char in enumerate(options):
            cx = base_x + opt_idx * P1_STEP_OPT
            d = get_bubble_density(thresh, cx, cy)
            densities.append((d, opt_char))

        densities.sort(key=lambda x: x[0], reverse=True)
        top_d, top_opt = densities[0]
        second_d, _ = densities[1]

        chosen = None
        if top_d >= 0.35 and (top_d - second_d >= 0.12):
            chosen = top_opt
        elif top_d >= 0.45:
            chosen = top_opt

        correct_ans = answer_key.get(str(q_idx), "").upper()
        is_correct = (chosen == correct_ans) and (chosen is not None)
        score = 0.25 if is_correct else 0.0
        total_score += score

        details[str(q_idx)] = {
            "chosen": chosen if chosen else "Trống",
            "correct": correct_ans,
            "is_correct": is_correct,
            "score": score
        }

    return round(total_score, 2), details


def grade_part2(thresh: np.ndarray, answer_key: Dict[str, Dict[str, str]]) -> Tuple[float, Dict[str, Any]]:
    """
    Chấm Phần II - Đúng / Sai (2 câu, mỗi câu 4 ý a, b, c, d).
    Áp dụng cách tính điểm lũy tiến chuẩn Bộ GD&ĐT cho mỗi câu:
      - Đúng 1 ý: 0.10 điểm
      - Đúng 2 ý: 0.25 điểm
      - Đúng 3 ý: 0.50 điểm
      - Đúng cả 4 ý: 1.00 điểm
    Tối đa: 2.0 điểm (mỗi câu tối đa 1.0 điểm).
    """
    score_table = {0: 0.0, 1: 0.10, 2: 0.25, 3: 0.50, 4: 1.00}
    total_score = 0.0
    details = {}
    sub_keys = ["a", "b", "c", "d"]

    for q_idx, base_x in [(1, P2_C1_X), (2, P2_C2_X)]:
        q_key = str(q_idx)
        correct_sub_dict = answer_key.get(q_key, {})
        num_correct = 0
        sub_details = {}

        for row_idx, sub_item in enumerate(sub_keys):
            cy = P2_START_Y + row_idx * P2_STEP_Y
            # Ô 'Đúng'
            d_d = get_bubble_density(thresh, base_x, cy)
            # Ô 'Sai'
            d_s = get_bubble_density(thresh, base_x + P2_STEP_OPT, cy)

            chosen = None
            if d_d >= 0.35 and d_d - d_s >= 0.10:
                chosen = "D"
            elif d_s >= 0.35 and d_s - d_d >= 0.10:
                chosen = "S"
            elif d_d >= 0.45:
                chosen = "D"
            elif d_s >= 0.45:
                chosen = "S"

            target_val = correct_sub_dict.get(sub_item, "").upper()
            is_sub_correct = (chosen == target_val) and (chosen is not None)
            if is_sub_correct:
                num_correct += 1

            sub_details[sub_item] = {
                "chosen": chosen if chosen else "Trống",
                "correct": target_val,
                "is_correct": is_sub_correct
            }

        q_score = score_table.get(num_correct, 0.0)
        total_score += q_score
        details[q_key] = {
            "num_correct": num_correct,
            "score": q_score,
            "items": sub_details
        }

    return round(total_score, 2), details


def grade_part3(thresh: np.ndarray, answer_key: Dict[str, str]) -> Tuple[float, Dict[str, Any]]:
    """
    Chấm Phần III - Trả lời ngắn (4 câu).
    Mỗi câu gồm 4 cột số thực (hàng 0: '-', hàng 1: '.', hàng 2..11: '0'..'9').
    Mỗi câu đúng được 0.50 điểm. Tối đa 2.0 điểm.
    """
    total_score = 0.0
    details = {}
    symbols = ["-", "."] + [str(i) for i in range(10)]

    for q_idx in range(1, 5):
        q_key = str(q_idx)
        q_base_x = P3_START_X + (q_idx - 1) * P3_COL_GAP
        chars = []

        for col in range(4):
            cx = q_base_x + col * P3_DIGIT_GAP
            densities = []

            for row_idx, sym in enumerate(symbols):
                cy = P3_START_Y + row_idx * P3_ROW_STEP
                d = get_bubble_density(thresh, cx, cy, radius=8)
                densities.append((d, sym))

            densities.sort(key=lambda x: x[0], reverse=True)
            top_d, top_sym = densities[0]
            second_d, _ = densities[1]

            if top_d >= 0.35 and (top_d - second_d >= 0.12):
                chars.append(top_sym)
            elif top_d >= 0.40:
                chars.append(top_sym)

        detected_val = "".join(chars).strip()
        correct_val = str(answer_key.get(q_key, "")).strip().replace(",", ".")

        # Chuẩn hóa để so sánh số thực
        is_correct = False
        if detected_val:
            val_norm = detected_val.replace(",", ".")
            if val_norm == correct_val:
                is_correct = True
            else:
                try:
                    if abs(float(val_norm) - float(correct_val)) < 1e-4:
                        is_correct = True
                except ValueError:
                    pass

        score = 0.50 if is_correct else 0.0
        total_score += score
        details[q_key] = {
            "detected": detected_val if detected_val else "Trống",
            "correct": correct_val,
            "is_correct": is_correct,
            "score": score
        }

    return round(total_score, 2), details


def crop_essay_region(warped_bgr: np.ndarray) -> np.ndarray:
    """
    Cắt riêng vùng làm bài Tự luận (Khung viền đôi Bounding Box ở 45% nửa dưới trang A4).
    Kích thước chuẩn: Y từ 1560 đến 2860, X từ 100 đến 2000.
    """
    return warped_bgr[ESSAY_Y1:ESSAY_Y2, ESSAY_X1:ESSAY_X2].copy()


def process_omr(image_bgr: np.ndarray, key_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pipeline xử lý toàn diện:
    - Bắt 4 góc và nắn thẳng ảnh
    - Đọc SBD, Mã đề
    - Chấm Phần I, II, III OMR
    - Trích xuất vùng Tự luận
    """
    # 1. Perspective Warp
    warped, is_aligned = detect_markers_and_warp(image_bgr)

    # 2. Tiền xử lý ngưỡng nhị phân cho OMR
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
    )

    # 3. Đọc thông tin định danh
    sbd = read_sbd(thresh)
    detected_code = read_exam_code(thresh)

    # Lấy đáp án khớp mã đề thi (hoặc dùng key_data truyền vào)
    p1_keys = key_data.get("part1_keys", {})
    p2_keys = key_data.get("part2_keys", {})
    p3_keys = key_data.get("part3_keys", {})

    # 4. Chấm Phần I, II, III OMR
    score_p1, details_p1 = grade_part1(thresh, p1_keys)
    score_p2, details_p2 = grade_part2(thresh, p2_keys)
    score_p3, details_p3 = grade_part3(thresh, p3_keys)

    omr_total = round(score_p1 + score_p2 + score_p3, 2)

    # 5. Cắt ảnh tự luận
    essay_img = crop_essay_region(warped)

    return {
        "is_aligned": is_aligned,
        "sbd": sbd,
        "exam_code": detected_code,
        "score_p1": score_p1,
        "score_p2": score_p2,
        "score_p3": score_p3,
        "omr_total": omr_total,
        "details_p1": details_p1,
        "details_p2": details_p2,
        "details_p3": details_p3,
        "warped_bgr": warped,
        "essay_bgr": essay_img
    }
