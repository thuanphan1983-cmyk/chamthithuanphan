"""
Module main.py - Ứng dụng Web API chấm thi trắc nghiệm & tự luận chuẩn phong cách TNMaker
Framework: FastAPI + Uvicorn + OpenCV + OpenPyXL + SQLite + Gemini AI
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
from typing import Optional, Dict, Any

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
    init_db, get_answer_key, save_answer_key, list_all_keys,
    save_result, update_essay_result, mark_essay_failed,
    get_all_results, get_result_by_id
)
from omr_engine import process_omr
from ai_grader import grade_essay_with_gemini
from excel_exporter import export_exam_results_to_excel

app = FastAPI(
    title="TNMaker AI Exam Grader",
    description="Hệ thống chấm thi trắc nghiệm và tự luận di động thông minh",
    version="1.0.0"
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
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Khởi tạo DB ngay khi module load để đảm bảo sẵn sàng trên Vercel Serverless
init_db()

# Mount thư mục uploads để xem lại ảnh bài thi
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def startup_event():
    """Khởi tạo cơ sở dữ liệu khi khởi động server"""
    init_db()


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
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Ứng dụng Chấm thi TNMaker AI đang khởi động...</h1>"


@app.post("/scan")
@app.post("/api/scan")
async def scan_exam_sheet(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    base64_image: Optional[str] = Form(None),
    exam_code_override: Optional[str] = Form(None)
):
    """
    Endpoint chấm thi cốt lõi:
    - Bắt góc tự động, nắn phẳng ảnh Perspective Warp về chuẩn 2100 x 2970
    - Nhận diện SBD (6 số), Mã đề (4 số)
    - Chấm Phần I (12 câu), Phần II (Đúng/Sai), Phần III (Trả lời ngắn) bằng OMR (< 150ms)
    - Cắt vùng tự luận và kích hoạt Background Task chấm bằng Gemini AI
    - Trả về điểm OMR tức thì để máy phát âm thanh "Beep" và hiện kết quả ngay lập tức
    """
    # 1. Đọc dữ liệu ảnh từ File Upload hoặc Base64 từ Camera
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

    # 2. Xử lý OMR và nắn góc
    # Lấy đáp án sơ bộ
    target_code = exam_code_override or "0101"
    key_data = get_answer_key(target_code) or {}

    omr_res = process_omr(image_bgr, key_data)
    
    # Nếu mã đề đọc được khác với mã ban đầu và có trong CSDL, chấm lại theo mã đề thực tế
    detected_code = omr_res["exam_code"]
    if detected_code and detected_code != target_code:
        alt_key = get_answer_key(detected_code)
        if alt_key and alt_key["exam_code"] == detected_code:
            key_data = alt_key
            omr_res = process_omr(image_bgr, key_data)

    sbd = omr_res["sbd"]
    exam_code = omr_res["exam_code"]
    score_p1 = omr_res["score_p1"]
    score_p2 = omr_res["score_p2"]
    score_p3 = omr_res["score_p3"]
    omr_total = omr_res["omr_total"]

    # 3. Lưu ảnh nắn phẳng và ảnh tự luận
    timestamp = int(time.time() * 1000)
    warped_filename = f"warped_{sbd}_{timestamp}.jpg"
    essay_filename = f"essay_{sbd}_{timestamp}.jpg"

    warped_path = os.path.join(UPLOAD_DIR, warped_filename)
    essay_path = os.path.join(UPLOAD_DIR, essay_filename)

    cv2.imwrite(warped_path, omr_res["warped_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(essay_path, omr_res["essay_bgr"], [cv2.IMWRITE_JPEG_QUALITY, 90])

    # 4. Lưu bài thi vào SQLite với trạng thái tự luận PENDING
    rubric = key_data.get("essay_rubric", {})
    result_id = save_result(
        sbd=sbd,
        exam_code=exam_code,
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

    # 5. Kích hoạt Background Task để Gemini AI chấm tự luận
    background_tasks.add_task(background_grade_essay, result_id, essay_path, rubric)

    # 6. Trả về kết quả OMR tức thì
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
        "message": "Quét OMR thành công! Gemini AI đang chấm tự luận ngầm."
    }


@app.get("/results")
@app.get("/api/results")
def list_results():
    """Lấy danh sách tất cả các bài thi đã chấm, sắp xếp SBD tăng dần"""
    return get_all_results()


@app.get("/results/{result_id}")
@app.get("/api/results/{result_id}")
def get_single_result(result_id: int):
    """Lấy chi tiết một bài thi để cập nhật tiến độ chấm tự luận của AI"""
    res = get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài thi.")
    return res


@app.get("/debug-path")
def debug_path_endpoint(request: Request):
    return {
        "url": str(request.url),
        "path": request.url.path,
        "scope_path": request.scope.get("path"),
        "root_path": request.scope.get("root_path")
    }

@app.get("/keys")
@app.get("/api/keys")
def get_all_exam_keys():
    """Lấy danh sách các mã đề thi đã nạp vào hệ thống"""
    keys = list_all_keys()
    details = []
    for k in keys:
        full_data = get_answer_key(k["exam_code"])
        if full_data:
            details.append(full_data)
    return details


@app.post("/set-keys")
@app.post("/api/set-keys")
async def create_or_update_key(data: Dict[str, Any]):
    """Thêm hoặc cập nhật đáp án chuẩn cho mã đề thi"""
    exam_code = data.get("exam_code", "").strip()
    if not exam_code:
        raise HTTPException(status_code=400, detail="Mã đề thi không được để trống.")

    title = data.get("exam_title", f"Đề thi mã {exam_code}")
    p1 = data.get("part1_keys", {})
    p2 = data.get("part2_keys", {})
    p3 = data.get("part3_keys", {})
    rubric = data.get("essay_rubric", {})

    save_answer_key(exam_code, title, p1, p2, p3, rubric)
    return {"success": True, "message": f"Đã lưu đáp án cho mã đề {exam_code}."}


@app.get("/export-excel")
@app.get("/api/export-excel")
def export_excel():
    """
    Xuất toàn bộ kết quả bài thi ra file Excel (.xlsx):
    - Tự động sắp xếp tăng dần theo Số Báo Danh (SBD)
    - Giữ nguyên định dạng chuỗi 6 ký tự
    - Bảng biểu chuẩn màu Navy #1F4E78, Tổng điểm in đậm đỏ #C00000
    - Trả về luồng file tải trực tiếp
    """
    results = get_all_results()
    excel_stream = export_exam_results_to_excel(results)

    filename = f"Bang_Diem_Thi_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@app.get("/download-sheet")
@app.get("/api/download-sheet")
def download_blank_sheet():
    """Tải file ảnh phiếu thi trắng chuẩn A4 (2100 x 2970 px) để in ra giấy"""
    sheet_path = os.path.join(BASE_DIR, "phieu_thi_chuan_A4.png")
    if not os.path.exists(sheet_path):
        import generate_sheet
        blank = generate_sheet.create_blank_sheet()
        cv2.imwrite(sheet_path, blank)
    return FileResponse(sheet_path, media_type="image/png", filename="phieu_thi_chuan_A4.png")


@app.get("/sample-sheet")
@app.get("/api/sample-sheet")
def download_sample_sheet():
    """Tải file ảnh phiếu thi đã tô mẫu (SBD 010008 - Đề 101) để kiểm thử"""
    test_path = os.path.join(BASE_DIR, "sample_test_sheet.png")
    if os.path.exists(test_path):
        return FileResponse(test_path, media_type="image/png", filename="sample_test_sheet.png")
    
    sample_path = os.path.join(BASE_DIR, "sample_filled_sheet.png")
    if not os.path.exists(sample_path):
        import generate_sheet
        blank = generate_sheet.create_blank_sheet()
        sample = generate_sheet.fill_sample_sheet(blank, sbd="010008", exam_code="101")
        cv2.imwrite(sample_path, sample)
        cv2.imwrite(test_path, sample)
    return FileResponse(sample_path, media_type="image/png", filename="sample_test_sheet.png")


@app.post("/grade-sample")
@app.post("/api/grade-sample")
async def grade_sample_instant(background_tasks: BackgroundTasks):
    """Route kiểm thử tức thì: Chấm trực tiếp file sample_test_sheet.png (SBD 010008 - Đề 101)"""
    test_path = os.path.join(BASE_DIR, "sample_test_sheet.png")
    if not os.path.exists(test_path):
        test_path = os.path.join(BASE_DIR, "sample_filled_sheet.png")
    
    if not os.path.exists(test_path):
        import generate_sheet
        blank = generate_sheet.create_blank_sheet()
        sample = generate_sheet.fill_sample_sheet(blank, sbd="010008", exam_code="101")
        cv2.imwrite(test_path, sample)

    with open(test_path, "rb") as f:
        img_bytes = f.read()

    np_arr = np.frombuffer(img_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    key_data = get_answer_key("101") or get_answer_key("0101") or {}
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
        sbd=sbd,
        exam_code=exam_code,
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
        "message": f"Chấm thành công bài mẫu SBD {sbd} - Mã đề {exam_code}! Gemini AI đang chấm tự luận ngầm."
    }
