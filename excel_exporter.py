"""
Module excel_exporter.py - Xuất bảng điểm thi môn Toán chuẩn Bộ GD&ĐT sang định dạng Excel (.xlsx)
Nhiệm vụ:
1. Nhận danh sách kết quả bài thi từ SQLite.
2. Tự động sắp xếp tăng dần theo Số Báo Danh (SBD) và BẢO LƯU định dạng chuỗi 6 ký tự ("010001", "010002"...).
3. Định dạng OpenPyXL chuyên nghiệp:
   - Header bảng màu xanh navy đậm (#1F4E78), chữ trắng đậm (Bold).
   - Đường viền mảnh (Thin Border) cho toàn bộ các ô dữ liệu.
   - Điểm số căn giữa (Center), định dạng số thập phân 2 chữ số `0.00`.
   - Cột Tổng Điểm in đậm, màu đỏ nổi bật (#C00000).
   - Tự động căn chỉnh độ rộng cột tối ưu.
"""

import io
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_exam_results_to_excel(results: List[Dict[str, Any]], exam_title: str = "BẢNG TỔNG HỢP KẾT QUẢ ĐIỂM THI KHẢO SÁT") -> io.BytesIO:
    """
    Tạo workbook Excel từ danh sách kết quả bài thi, trả về io.BytesIO stream sẵn sàng gửi về client.
    """
    # 1. Sắp xếp danh sách kết quả tăng dần theo Số Báo Danh (SBD) dạng chuỗi
    sorted_results = sorted(results, key=lambda x: str(x.get("sbd", "")).strip().zfill(6))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bang_Diem"
    ws.views.sheetView[0].showGridLines = True

    # 2. Định nghĩa Style màu sắc chuẩn
    COLOR_NAVY = "1F4E78"       # Xanh navy đậm cho Header
    COLOR_SUB_HEADER = "D9E1F2" # Xanh nhạt cho thông tin phụ
    COLOR_RED = "C00000"        # Đỏ đậm cho Tổng Điểm

    font_title = Font(name="Times New Roman", size=16, bold=True, color="1F4E78")
    font_subtitle = Font(name="Times New Roman", size=11, italic=True)
    font_header = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
    font_data = Font(name="Times New Roman", size=11)
    font_sbd = Font(name="Times New Roman", size=11, bold=True)
    font_total = Font(name="Times New Roman", size=11, bold=True, color=COLOR_RED)

    fill_header = PatternFill(start_color=COLOR_NAVY, end_color=COLOR_NAVY, fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    thin_border_side = Side(style='thin', color='B0B0B0')
    border_all = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # 3. Thêm Tiêu đề báo cáo
    ws.merge_cells("A1:I1")
    ws["A1"] = exam_title.upper()
    ws["A1"].font = font_title
    ws["A1"].alignment = align_center
    ws.row_dimensions[1].height = 35

    ws.merge_cells("A2:I2")
    ws["A2"] = "Thang điểm 10.0 | Quy chuẩn: TN (3.0đ) - Đúng/Sai (2.0đ) - Trả lời ngắn (2.0đ) - Tự luận (3.0đ)"
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = align_center
    ws.row_dimensions[2].height = 20

    # Dòng trống
    ws.row_dimensions[3].height = 10

    # 4. Định nghĩa danh sách các Cột
    headers = [
        ("STT", 6),
        ("Số Báo Danh", 15),
        ("Mã Đề", 12),
        ("Điểm Phần I\n(Trắc nghiệm)", 16),
        ("Điểm Phần II\n(Đúng / Sai)", 16),
        ("Điểm Phần III\n(Trả lời ngắn)", 16),
        ("Điểm Tự Luận\n(Phần IV)", 16),
        ("Tổng Điểm\n(Thang 10)", 16),
        ("Nhận Xét Tự Luận\n(Gemini AI)", 35)
    ]

    header_row_idx = 4
    ws.row_dimensions[header_row_idx].height = 36

    for col_idx, (col_name, col_width) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.value = col_name
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_all
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    # 5. Ghi dữ liệu từng thí sinh
    current_row = 5
    for idx, item in enumerate(sorted_results, start=1):
        ws.row_dimensions[current_row].height = 24
        is_even = (idx % 2 == 0)

        # STT
        c1 = ws.cell(row=current_row, column=1, value=idx)
        c1.font = font_data
        c1.alignment = align_center
        c1.border = border_all

        # Số Báo Danh (BẢO LƯU CHUỖI 6 CHỮ SỐ, KHÔNG BỎ SỐ 0 ĐẦU)
        sbd_str = str(item.get("sbd", "")).strip().zfill(6)
        c2 = ws.cell(row=current_row, column=2, value=sbd_str)
        c2.number_format = '@'  # Định dạng Text thuần túy trong Excel
        c2.font = font_sbd
        c2.alignment = align_center
        c2.border = border_all

        # Mã Đề (Chuỗi 4 ký tự)
        code_str = str(item.get("exam_code", "")).strip().zfill(4)
        c3 = ws.cell(row=current_row, column=3, value=code_str)
        c3.number_format = '@'
        c3.font = font_data
        c3.alignment = align_center
        c3.border = border_all

        # Điểm Phần I (TN)
        p1 = float(item.get("score_p1", 0.0))
        c4 = ws.cell(row=current_row, column=4, value=p1)
        c4.number_format = '0.00'
        c4.font = font_data
        c4.alignment = align_center
        c4.border = border_all

        # Điểm Phần II (Đ/S)
        p2 = float(item.get("score_p2", 0.0))
        c5 = ws.cell(row=current_row, column=5, value=p2)
        c5.number_format = '0.00'
        c5.font = font_data
        c5.alignment = align_center
        c5.border = border_all

        # Điểm Phần III (TLN)
        p3 = float(item.get("score_p3", 0.0))
        c6 = ws.cell(row=current_row, column=6, value=p3)
        c6.number_format = '0.00'
        c6.font = font_data
        c6.alignment = align_center
        c6.border = border_all

        # Điểm Tự Luận
        p_essay = float(item.get("score_essay", 0.0))
        c7 = ws.cell(row=current_row, column=7, value=p_essay)
        c7.number_format = '0.00'
        c7.font = font_data
        c7.alignment = align_center
        c7.border = border_all

        # Tổng Điểm (IN ĐẬM MÀU ĐỎ NỔI BẬT)
        p_total = float(item.get("total_score", 0.0))
        c8 = ws.cell(row=current_row, column=8, value=p_total)
        c8.number_format = '0.00'
        c8.font = font_total
        c8.alignment = align_center
        c8.border = border_all

        # Nhận Xét Tự Luận
        feedback = item.get("essay_feedback", {})
        nhan_xet = ""
        if isinstance(feedback, dict):
            nhan_xet = feedback.get("nhan_xet", "")
            if not nhan_xet and "error" in feedback:
                nhan_xet = f"Lỗi: {feedback['error']}"
        elif isinstance(feedback, str):
            nhan_xet = feedback

        c9 = ws.cell(row=current_row, column=9, value=nhan_xet or "Chưa có nhận xét")
        c9.font = font_data
        c9.alignment = align_left
        c9.border = border_all

        # Kẻ sọc mờ (Zebra striping) cho các hàng chẵn
        if is_even:
            for c in [c1, c2, c3, c4, c5, c6, c7, c8, c9]:
                c.fill = fill_zebra

        current_row += 1

    # 6. Dòng Thống kê tổng quan (Trung bình, Cao nhất, Thấp nhất)
    if sorted_results:
        summary_row = current_row
        ws.row_dimensions[summary_row].height = 26
        ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=3)
        cell_sum_label = ws.cell(row=summary_row, column=1, value="ĐIỂM TRUNG BÌNH CẢ LỚP")
        cell_sum_label.font = Font(name="Times New Roman", size=11, bold=True, color="1F4E78")
        cell_sum_label.alignment = align_center
        cell_sum_label.fill = PatternFill(start_color=COLOR_SUB_HEADER, end_color=COLOR_SUB_HEADER, fill_type="solid")

        # Viền cho các ô merge
        for col in range(1, 4):
            ws.cell(row=summary_row, column=col).border = border_all
            ws.cell(row=summary_row, column=col).fill = PatternFill(start_color=COLOR_SUB_HEADER, end_color=COLOR_SUB_HEADER, fill_type="solid")

        for col_idx, col_letter in [(4, "D"), (5, "E"), (6, "F"), (7, "G"), (8, "H")]:
            cell_avg = ws.cell(
                row=summary_row,
                column=col_idx,
                value=f"=AVERAGE({col_letter}5:{col_letter}{summary_row - 1})"
            )
            cell_avg.number_format = '0.00'
            cell_avg.font = Font(name="Times New Roman", size=11, bold=True)
            cell_avg.alignment = align_center
            cell_avg.fill = PatternFill(start_color=COLOR_SUB_HEADER, end_color=COLOR_SUB_HEADER, fill_type="solid")
            cell_avg.border = border_all

        c_empty = ws.cell(row=summary_row, column=9, value="")
        c_empty.fill = PatternFill(start_color=COLOR_SUB_HEADER, end_color=COLOR_SUB_HEADER, fill_type="solid")
        c_empty.border = border_all

    # Ghi vào BytesIO stream
    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    return output_stream
