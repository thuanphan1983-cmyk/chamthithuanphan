"""
Module main.py - Ứng dụng Web API chấm thi trắc nghiệm & tự luận chuẩn phong cách TNMaker
Hỗ trợ:
- Quản lý bài kiểm tra (Exams): Chọn mẫu phiếu 3 phần hoặc 4 phần, tùy chỉnh số câu và điểm từng phần.
- Xuất phiếu in A4 cho cả 2 loại: Mẫu 3 phần (TN + Đ/S + TLN) và Mẫu 4 phần (TN + Đ/S + TLN + Tự luận).
- Chấm điểm OMR tức thì bằng Perspective Warp bắt 4 góc và Background Task Gemini AI.
- Xuất file Excel bảng điểm chuẩn mực Bộ GD&ĐT.
"""

import os
import sys
import io
import time
import json
import base64
import tempfile
import cv2
import numpy as np
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Đảm bảo in unicode ra console trên Windows không bị lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database import (
    init_db, create_exam, get_exam, list_exams, delete_exam,
    get_answer_key, save_answer_key, list_all_keys,
    save_result, update_essay_result, mark_essay_failed,
    get_all_results, get_result_by_id
)
from omr_engine import process_omr
from ai_grader import grade_essay_with_gemini
from excel_exporter import export_exam_results_to_excel
import generate_sheet

app = FastAPI(
    title="TNMaker AI Exam Grader Pro",
    description="Hệ thống chấm thi trắc nghiệm và tự luận di động thông minh phong cách TNMaker",
    version="2.0.0"
)

# Kích hoạt CORS để hỗ trợ Mobile Web và PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình đường dẫn linh hoạt hỗ trợ cả Local và Vercel Serverless
IS_VERCEL = os.getenv("VERCEL") == "1" or "VERCEL" in os.environ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_VERCEL:
    UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "uploads")
else:
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Khởi tạo DB ngay khi module load để đảm bảo sẵn sàng trên Vercel Serverless
init_db()

# Mount thư mục uploads để xem lại ảnh bài thi
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def background_grade_essay(result_id: int, essay_path: str, rubric: dict):
    """Xử lý ngầm việc chấm bài tự luận bằng Gemini AI để phản hồi OMR tức thì"""
    try:
        essay_result = grade_essay_with_gemini(essay_path, rubric)
        score_essay = essay_result.get("tong_diem_tu_luan", 0.0)
        update_essay_result(result_id, score_essay, essay_result)
        print(f"[AI Grader] Đã hoàn tất chấm tự luận cho bài ID {result_id}: {score_essay} điểm.")
    except Exception as e:
        mark_essay_failed(result_id, str(e))
        print(f"[AI Grader] Lỗi chấm tự luận cho bài ID {result_id}: {e}")


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Giao diện Web App di động phong cách TNMaker"""
    for file_path in [
        os.path.join(PUBLIC_DIR, "index.html"),
        os.path.join(TEMPLATES_DIR, "index.html")
    ]:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>Ứng dụng Chấm thi TNMaker AI đang khởi động...</h1>"


# ==============================================================================
# 1. API QUẢN LÝ BÀI KIỂM TRA (EXAMS) & TÙY CHỈNH THANG ĐIỂM
# ==============================================================================

@app.get("/exams")
@app.get("/api/exams")
def get_exams_list():
    """Lấy danh sách tất cả các bài kiểm tra có trong hệ thống"""
    return list_exams()


@app.post("/exams")
@app.post("/api/exams")
async def create_new_exam(data: Dict[str, Any]):
    """
    Tạo bài kiểm tra mới:
    - Chọn loại phiếu: '3_part' (100% trắc nghiệm) hoặc '4_part' (có tự luận)
    - Tùy chỉnh số câu & điểm từng phần: Phần I, Phần II, Phần III, Phần IV
    """
    title = data.get("title", "Bài kiểm tra Toán").strip()
    sheet_type = data.get("sheet_type", "4_part")
    p1_num = int(data.get("p1_num", 12))
    p1_points = float(data.get("p1_points", 0.25))
    p2_num = int(data.get("p2_num", 2))
    p2_mode = data.get("p2_mode", "progressive")
    p3_num = int(data.get("p3_num", 4))
    p3_points = float(data.get("p3_points", 0.5))
    p4_num = int(data.get("p4_num", 2 if sheet_type == "4_part" else 0))
    p4_points = float(data.get("p4_points", 1.5 if sheet_type == "4_part" else 0.0))
    total_points = float(data.get("total_points", 10.0))

    exam_id = create_exam(
        title=title,
        sheet_type=sheet_type,
        p1_num=p1_num,
        p1_points=p1_points,
        p2_num=p2_num,
        p2_mode=p2_mode,
        p3_num=p3_num,
        p3_points=p3_points,
        p4_num=p4_num,
        p4_points=p4_points,
        total_points=total_points
    )

    # Khởi tạo đáp án mặc định cho mã đề 101 trong bài thi mới
    sample_part1 = {str(i): ["A", "B", "C", "D"][(i - 1) % 4] for i in range(1, p1_num + 1)}
    sample_part2 = {str(i): {"a": "D", "b": "S", "c": "D", "d": "S"} for i in range(1, p2_num + 1)}
    sample_part3 = {str(i): "12.5" for i in range(1, p3_num + 1)}
    sample_rubric = {
        "bai_1": {"de_bai": "Bài toán ứng dụng hàm số", "thang_diem": p4_points, "tieu_chi": []},
        "bai_2": {"de_bai": "Hình học không gian", "thang_diem": p4_points, "tieu_chi": []}
    } if sheet_type == "4_part" else {}

    save_answer_key("101", f"{title} - Mã 101", sample_part1, sample_part2, sample_part3, sample_rubric, exam_id=exam_id)

    return {"success": True, "exam_id": exam_id, "message": f"Đã tạo bài kiểm tra: {title}"}


@app.get("/exams/{exam_id}")
@app.get("/api/exams/{exam_id}")
def get_single_exam(exam_id: int):
    """Lấy thông tin chi tiết cấu hình của một bài kiểm tra"""
    exam = get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài kiểm tra.")
    keys = list_all_keys(exam_id=exam_id)
    exam["keys"] = keys
    return exam


@app.delete("/exams/{exam_id}")
@app.delete("/api/exams/{exam_id}")
def delete_single_exam(exam_id: int):
    """Xóa một bài kiểm tra"""
    delete_exam(exam_id)
    return {"success": True, "message": "Đã xóa bài kiểm tra thành công."}


# ==============================================================================
# 2. API XUẤT MẪU PHIẾU THI (3 PHẦN & 4 PHẦN)
# ==============================================================================

@app.get("/download-sheet")
@app.get("/api/download-sheet")
def download_sheet_by_type(type: str = "4_part"):
    """
    Tải file ảnh phiếu thi trắng chuẩn A4 (2100 x 2970 px) để in ra giấy
    Hỗ trợ 2 loại phiếu:
    - type=3_part: Phiếu 3 phần (100% Trắc nghiệm: TN + Đ/S + TLN)
    - type=4_part: Phiếu 4 phần (Có tự luận)
    """
    filename = "phieu_thi_3_phan_A4.png" if type == "3_part" else "phieu_thi_4_phan_A4.png"
    candidate_paths = [
        os.path.join(BASE_DIR, filename),
        os.path.join(PUBLIC_DIR, filename),
        os.path.join(tempfile.gettempdir(), filename)
    ]
    found_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            found_path = p
            break

    if not found_path:
        out_path = os.path.join(tempfile.gettempdir() if IS_VERCEL else BASE_DIR, filename)
        if type == "3_part":
            img = generate_sheet.create_sheet_3part()
        else:
            img = generate_sheet.create_sheet_4part()
        cv2.imwrite(out_path, img)
        found_path = out_path

    return FileResponse(found_path, media_type="image/png", filename=filename)


@app.get("/sample-sheet")
@app.get("/api/sample-sheet")
def download_sample_sheet(type: str = "4_part"):
    """Tải file ảnh bài làm mô phỏng để kiểm thử nhanh"""
    filename = "sample_test_sheet.png"
    candidate_paths = [
        os.path.join(BASE_DIR, filename),
        os.path.join(PUBLIC_DIR, filename),
        os.path.join(tempfile.gettempdir(), filename)
    ]
    found_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            found_path = p
            break

    if not found_path:
        out_path = os.path.join(tempfile.gettempdir() if IS_VERCEL else BASE_DIR, filename)
        blank = generate_sheet.create_sheet_4part()
        sample = generate_sheet.fill_sample_sheet(blank, sbd="010008", exam_code="101", sheet_type="4_part")
        cv2.imwrite(out_path, sample)
        found_path = out_path

    return FileResponse(found_path, media_type="image/png", filename=filename)


# ==============================================================================
# 3. API CHẤM THI OMR & TỰ LUẬN
# ==============================================================================

@app.post("/scan")
@app.post("/api/scan")
async def scan_exam_sheet(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    base64_image: Optional[str] = Form(None),
    exam_id: int = Form(1),
    exam_code_override: Optional[str] = Form(None)
):
    """
    Endpoint chấm thi cốt lõi:
    - Bắt 4 góc tự động, nắn phẳng Perspective Warp về 2100 x 2970
    - Nhận diện SBD (6 số) & Mã đề (4 số)
    - Chấm điểm linh hoạt dựa trên cấu hình bài kiểm tra (3 phần hoặc 4 phần)
    - Phản hồi tức thì (< 150ms) để điện thoại phát tiếng BEEP & rung máy
    """
    img_bytes = None
    if file and file.filename:
        img_bytes = await file.read()
    elif base64_image:
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]
        img_bytes = base64.b64decode(base64_image)

    if not img_bytes:
        raise HTTPException(status_code=400, detail="Vui lòng gửi file ảnh hoặc chuỗi base64.")

    np_arr = np.frombuffer(img_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Không thể giải mã hình ảnh.")

    # Lấy cấu hình bài kiểm tra
    exam = get_exam(exam_id) or get_exam(1)
    sheet_type = exam.get("sheet_type", "4_part") if exam else "4_part"

    # Lấy đáp án khớp mã đề
    target_code = exam_code_override or "101"
    key_data = get_answer_key(target_code, exam_id=exam["id"]) or {}

    # Chạy pipeline OMR
    omr_res = process_omr(image_bgr, key_data)

    detected_code = omr_res["exam_code"]
    if detected_code and detected_code != target_code:
        alt_key = get_answer_key(detected_code, exam_id=exam["id"])
        if alt_key:
            key_data = alt_key
            omr_res = process_omr(image_bgr, key_data)

    sbd = omr_res["sbd"]
    exam_code = omr_res["exam_code"]
    score_p1 = omr_res["score_p1"]
    score_p2 = omr_res["score_p2"]
    score_p3 = omr_res["score_p3"]
    omr_total = omr_res["omr_total"]

    timestamp = int(time.time() * 1000)
    warped_filename = f"warped_{sbd}_{timestamp}.jpg"
    essay_filename = f"essay_{sbd}_{timestamp}.jpg"

    warped_path = os.path.join(UPLOAD_DIR, warped_filename)
    essay_path = os.path.join(UPLOAD_DIR, essay_filename)

    cv2.imwrite(warped_path, omr_res["warped_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])

    # Nếu là mẫu 4 phần (có tự luận), crop tự luận và gửi Gemini AI
    if sheet_type == "4_part":
        cv2.imwrite(essay_path, omr_res["essay_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])
        rubric = key_data.get("essay_rubric", {})
        result_id = save_result(
            exam_id=exam["id"],
            sbd=sbd,
            exam_code=exam_code,
            sheet_type=sheet_type,
            score_p1=score_p1,
            score_p2=score_p2,
            score_p3=score_p3,
            score_essay=0.0,
            total_score=omr_total,
            details_p1=omr_res["details_p1"],
            details_p2=omr_res["details_p2"],
            details_p3=omr_res["details_p3"],
            essay_feedback={"status": "Đang chấm tự luận ngầm bằng AI..."},
            essay_status="PENDING",
            warped_image_path=f"/uploads/{warped_filename}",
            essay_image_path=f"/uploads/{essay_filename}"
        )
        background_tasks.add_task(background_grade_essay, result_id, essay_path, rubric)
        essay_status = "PENDING"
    else:
        # Mẫu 3 phần: 100% trắc nghiệm -> Hoàn tất ngay lập tức
        result_id = save_result(
            exam_id=exam["id"],
            sbd=sbd,
            exam_code=exam_code,
            sheet_type=sheet_type,
            score_p1=score_p1,
            score_p2=score_p2,
            score_p3=score_p3,
            score_essay=0.0,
            total_score=omr_total,
            details_p1=omr_res["details_p1"],
            details_p2=omr_res["details_p2"],
            details_p3=omr_res["details_p3"],
            essay_feedback={"nhan_xet": "Bài thi 100% trắc nghiệm."},
            essay_status="SKIPPED",
            warped_image_path=f"/uploads/{warped_filename}",
            essay_image_path=""
        )
        essay_status = "SKIPPED"

    return {
        "success": True,
        "result_id": result_id,
        "sbd": sbd,
        "exam_code": exam_code,
        "sheet_type": sheet_type,
        "is_aligned": omr_res["is_aligned"],
        "scores": {
            "p1": score_p1,
            "p2": score_p2,
            "p3": score_p3,
            "omr_total": omr_total,
            "essay": 0.0,
            "total": omr_total
        },
        "details": {
            "p1": omr_res["details_p1"],
            "p2": omr_res["details_p2"],
            "p3": omr_res["details_p3"]
        },
        "essay_status": essay_status,
        "warped_url": f"/uploads/{warped_filename}",
        "essay_url": f"/uploads/{essay_filename}" if sheet_type == "4_part" else "",
        "message": f"Chấm thành công SBD {sbd} - Đề {exam_code}!"
    }


@app.post("/grade-sample")
@app.post("/api/grade-sample")
async def grade_sample_instant(background_tasks: BackgroundTasks, exam_id: int = 1):
    """Route kiểm thử tức thì: Chấm trực tiếp file sample_test_sheet.png"""
    filename = "sample_test_sheet.png"
    candidate_paths = [
        os.path.join(BASE_DIR, filename),
        os.path.join(PUBLIC_DIR, filename),
        os.path.join(tempfile.gettempdir(), filename)
    ]
    test_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            test_path = p
            break

    if not test_path:
        out_path = os.path.join(tempfile.gettempdir() if IS_VERCEL else BASE_DIR, filename)
        blank = generate_sheet.create_sheet_4part()
        sample = generate_sheet.fill_sample_sheet(blank, sbd="010008", exam_code="101", sheet_type="4_part")
        cv2.imwrite(out_path, sample)
        test_path = out_path

    with open(test_path, "rb") as f:
        img_bytes = f.read()

    np_arr = np.frombuffer(img_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    key_data = get_answer_key("101", exam_id=exam_id) or {}
    omr_res = process_omr(image_bgr, key_data)

    sbd = omr_res["sbd"]
    exam_code = omr_res["exam_code"]
    score_p1 = omr_res["score_p1"]
    score_p2 = omr_res["score_p2"]
    score_p3 = omr_res["score_p3"]
    omr_total = omr_res["omr_total"]

    timestamp = int(time.time() * 1000)
    warped_filename = f"warped_{sbd}_{timestamp}.jpg"
    essay_filename = f"essay_{sbd}_{timestamp}.jpg"

    warped_path = os.path.join(UPLOAD_DIR, warped_filename)
    essay_path = os.path.join(UPLOAD_DIR, essay_filename)

    cv2.imwrite(warped_path, omr_res["warped_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(essay_path, omr_res["essay_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])

    rubric = key_data.get("essay_rubric", {})
    result_id = save_result(
        exam_id=exam_id,
        sbd=sbd,
        exam_code=exam_code,
        sheet_type="4_part",
        score_p1=score_p1,
        score_p2=score_p2,
        score_p3=score_p3,
        score_essay=0.0,
        total_score=omr_total,
        details_p1=omr_res["details_p1"],
        details_p2=omr_res["details_p2"],
        details_p3=omr_res["details_p3"],
        essay_feedback={"status": "Đang chấm tự luận ngầm bằng AI..."},
        essay_status="PENDING",
        warped_image_path=f"/uploads/{warped_filename}",
        essay_image_path=f"/uploads/{essay_filename}"
    )

    background_tasks.add_task(background_grade_essay, result_id, essay_path, rubric)

    return {
        "success": True,
        "result_id": result_id,
        "sbd": sbd,
        "exam_code": exam_code,
        "is_aligned": omr_res["is_aligned"],
        "scores": {
            "p1": score_p1,
            "p2": score_p2,
            "p3": score_p3,
            "omr_total": omr_total,
            "essay": 0.0,
            "total": omr_total
        },
        "details": {
            "p1": omr_res["details_p1"],
            "p2": omr_res["details_p2"],
            "p3": omr_res["details_p3"]
        },
        "essay_status": "PENDING",
        "warped_url": f"/uploads/{warped_filename}",
        "essay_url": f"/uploads/{essay_filename}",
        "message": f"Chấm thành công bài mẫu SBD {sbd} - Mã đề {exam_code}!"
    }


# ==============================================================================
# 4. API BẢNG ĐIỂM, ĐÁP ÁN & XUẤT EXCEL
# ==============================================================================

@app.get("/results")
@app.get("/api/results")
def list_results(exam_id: Optional[int] = None):
    """Lấy danh sách tất cả các bài thi đã chấm, sắp xếp SBD tăng dần"""
    return get_all_results(exam_id=exam_id)


@app.get("/results/{result_id}")
@app.get("/api/results/{result_id}")
def get_single_result(result_id: int):
    """Lấy chi tiết một bài thi để cập nhật tiến độ chấm tự luận của AI"""
    res = get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi.")
    return res


@app.get("/keys")
@app.get("/api/keys")
def get_all_exam_keys(exam_id: Optional[int] = None):
    """Lấy danh sách các mã đề thi đã nạp vào hệ thống"""
    keys = list_all_keys(exam_id=exam_id)
    details = []
    for k in keys:
        full_data = get_answer_key(k["exam_code"], exam_id=k.get("exam_id"))
        if full_data:
            details.append(full_data)
    return details


@app.post("/set-keys")
@app.post("/api/set-keys")
async def create_or_update_key(data: Dict[str, Any]):
    """Thêm hoặc cập nhật đáp án chuẩn cho mã đề thi"""
    exam_id = int(data.get("exam_id", 1))
    exam_code = data.get("exam_code", "").strip()
    if not exam_code:
        raise HTTPException(status_code=400, detail="Mã đề thi không được để trống.")

    title = data.get("exam_title", f"Đề thi mã {exam_code}")
    p1 = data.get("part1_keys", {})
    p2 = data.get("part2_keys", {})
    p3 = data.get("part3_keys", {})
    rubric = data.get("essay_rubric", {})

    save_answer_key(exam_code, title, p1, p2, p3, rubric, exam_id=exam_id)
    return {"success": True, "message": f"Đã lưu đáp án cho mã đề {exam_code}."}


@app.get("/export-excel")
@app.get("/api/export-excel")
def export_excel(exam_id: Optional[int] = None):
    """
    Xuất toàn bộ kết quả bài thi ra file Excel (.xlsx):
    - Tự động sắp xếp tăng dần theo Số Báo Danh (SBD)
    - Giữ nguyên định dạng chuỗi 6 ký tự
    - Bảng biểu chuẩn màu Navy #1F4E78, Tổng điểm in đậm đỏ #C00000
    - Trả về luồng file tải trực tiếp
    """
    results = get_all_results(exam_id=exam_id)
    exam = get_exam(exam_id) if exam_id else None
    title = f"BẢNG ĐIỂM - {exam['title'].upper()}" if exam else "BẢNG TỔNG HỢP KẾT QUẢ ĐIỂM THI KHẢO SÁT"

    excel_stream = export_exam_results_to_excel(results, exam_title=title)
    filename = f"Bang_Diem_Thi_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
