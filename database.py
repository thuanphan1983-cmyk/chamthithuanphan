"""
Module database.py - Quản lý cơ sở dữ liệu SQLite cho hệ thống chấm thi OMR & AI
Lưu trữ thông tin cấu hình đề thi, đáp án chuẩn, barem tự luận và kết quả bài làm.
"""

import sqlite3
import json
import os
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime

# Hỗ trợ cả môi trường Local và Vercel Serverless (chỉ cho phép ghi vào /tmp)
IS_VERCEL = os.getenv("VERCEL") == "1" or "VERCEL" in os.environ
if IS_VERCEL:
    DB_PATH = os.path.join(tempfile.gettempdir(), "exam_grader.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "exam_grader.db")

def get_connection():
    """Tạo kết nối tới cơ sở dữ liệu SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo các bảng cơ sở dữ liệu và nạp dữ liệu mẫu ban đầu nếu trống"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Bảng đề thi và đáp án chuẩn
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_code TEXT UNIQUE NOT NULL,
                exam_title TEXT DEFAULT 'Kiểm tra Toán THPT',
                part1_keys TEXT NOT NULL,  -- JSON: {"1": "A", "2": "B", ... "12": "D"}
                part2_keys TEXT NOT NULL,  -- JSON: {"1": {"a": "D", "b": "S", ...}, "2": {...}}
                part3_keys TEXT NOT NULL,  -- JSON: {"1": "12.5", "2": "-3.4", ...}
                essay_rubric TEXT NOT NULL, -- JSON: barem tiêu chí và lời giải chuẩn bài 1, bài 2
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Bảng kết quả bài thi của thí sinh
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sbd TEXT NOT NULL,              -- Số báo danh (6 ký tự, ví dụ '010001')
                exam_code TEXT NOT NULL,        -- Mã đề (ví dụ '0101')
                score_p1 REAL DEFAULT 0.0,      -- Điểm phần I (tối đa 3.0đ)
                score_p2 REAL DEFAULT 0.0,      -- Điểm phần II (tối đa 2.0đ)
                score_p3 REAL DEFAULT 0.0,      -- Điểm phần III (tối đa 2.0đ)
                score_essay REAL DEFAULT 0.0,   -- Điểm phần IV tự luận (tối đa 3.0đ)
                total_score REAL DEFAULT 0.0,   -- Tổng điểm (thang 10.0)
                details_p1 TEXT,                -- JSON chi tiết câu chọn, đúng/sai phần 1
                details_p2 TEXT,                -- JSON chi tiết các ý a, b, c, d phần 2
                details_p3 TEXT,                -- JSON chi tiết đáp số nhận diện phần 3
                essay_feedback TEXT,            -- JSON nhận xét, phân tích lỗi sai từ Gemini AI
                essay_status TEXT DEFAULT 'PENDING', -- PENDING / COMPLETED / SKIPPED / ERROR
                warped_image_path TEXT,         -- Đường dẫn lưu ảnh phiếu đã nắn thẳng
                essay_image_path TEXT,          -- Đường dẫn lưu ảnh vùng tự luận đã cắt
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()

        # Nạp dữ liệu đáp án mẫu cho mã đề "101", "102", "0101" và "0102" nếu chưa có
        cursor.execute("SELECT COUNT(*) FROM answer_keys WHERE exam_code = '101' OR exam_code = '0101'")
        if cursor.fetchone()[0] == 0:
            sample_part1 = {str(i): ["A", "B", "C", "D"][(i - 1) % 4] for i in range(1, 13)}
            sample_part2 = {
                "1": {"a": "D", "b": "S", "c": "D", "d": "S"},
                "2": {"a": "S", "b": "D", "c": "D", "d": "S"}
            }
            sample_part3 = {
                "1": "12.5",
                "2": "-3.4",
                "3": "0.75",
                "4": "100"
            }
            sample_rubric = {
                "bai_1": {
                    "de_bai": "Tìm giá trị lớn nhất và nhỏ nhất của hàm số y = f(x) trên đoạn [1; 3].",
                    "thang_diem": 1.5,
                    "tieu_chi": [
                        {"buoc": "Tập xác định & Đạo hàm f'(x)", "diem": 0.5},
                        {"buoc": "Tìm nghiệm của f'(x) trong khoảng (1; 3)", "diem": 0.5},
                        {"buoc": "Tính giá trị tại các mút và kết luận Max, Min", "diem": 0.5}
                    ]
                },
                "bai_2": {
                    "de_bai": "Tính thể tích khối chóp tứ giác đều S.ABCD có cạnh đáy a, chiều cao h.",
                    "thang_diem": 1.5,
                    "tieu_chi": [
                        {"buoc": "Xác định chân đường cao và diện tích đáy S_ABCD", "diem": 0.5},
                        {"buoc": "Công thức thể tích V = (1/3)*S*h", "diem": 0.5},
                        {"buoc": "Tính toán và kết luận đúng đơn vị", "diem": 0.5}
                    ]
                }
            }
            
            # Thêm mã đề 101 và 0101
            for code in ["101", "0101"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    f"Đề thi Khảo sát Toán THPT - Mã {code}",
                    json.dumps(sample_part1, ensure_ascii=False),
                    json.dumps(sample_part2, ensure_ascii=False),
                    json.dumps(sample_part3, ensure_ascii=False),
                    json.dumps(sample_rubric, ensure_ascii=False)
                ))
            
            # Mã đề 102 và 0102
            sample_part1_102 = {str(i): ["B", "C", "D", "A"][(i - 1) % 4] for i in range(1, 13)}
            for code in ["102", "0102"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    f"Đề thi Khảo sát Toán THPT - Mã {code}",
                    json.dumps(sample_part1_102, ensure_ascii=False),
                    json.dumps(sample_part2, ensure_ascii=False),
                    json.dumps(sample_part3, ensure_ascii=False),
                    json.dumps(sample_rubric, ensure_ascii=False)
                ))
            
            conn.commit()

def get_answer_key(exam_code: str) -> Optional[Dict[str, Any]]:
    """Lấy đáp án và barem chấm theo mã đề thi (hỗ trợ cả dạng 3 số như '101' hoặc 4 số như '0101')"""
    code_raw = str(exam_code).strip()
    code_zfilled = code_raw.zfill(4)
    code_lstripped = code_raw.lstrip("0") or "0"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM answer_keys 
            WHERE exam_code = ? OR exam_code = ? OR exam_code = ?
            ORDER BY id ASC LIMIT 1
        """, (code_raw, code_zfilled, code_lstripped))
        row = cursor.fetchone()
        if not row:
            # Fallback lấy mã đầu tiên nếu không khớp
            cursor.execute("SELECT * FROM answer_keys ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None

        return {
            "id": row["id"],
            "exam_code": row["exam_code"],
            "exam_title": row["exam_title"],
            "part1_keys": json.loads(row["part1_keys"]),
            "part2_keys": json.loads(row["part2_keys"]),
            "part3_keys": json.loads(row["part3_keys"]),
            "essay_rubric": json.loads(row["essay_rubric"]) if row["essay_rubric"] else {}
        }

def save_answer_key(exam_code: str, exam_title: str, part1: dict, part2: dict, part3: dict, rubric: dict):
    """Thêm hoặc cập nhật đáp án cho một mã đề"""
    code_norm = str(exam_code).strip().zfill(4)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO answer_keys (exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(exam_code) DO UPDATE SET
                exam_title = excluded.exam_title,
                part1_keys = excluded.part1_keys,
                part2_keys = excluded.part2_keys,
                part3_keys = excluded.part3_keys,
                essay_rubric = excluded.essay_rubric
        """, (
            code_norm,
            exam_title,
            json.dumps(part1, ensure_ascii=False),
            json.dumps(part2, ensure_ascii=False),
            json.dumps(part3, ensure_ascii=False),
            json.dumps(rubric, ensure_ascii=False)
        ))
        conn.commit()

def list_all_keys() -> List[Dict[str, Any]]:
    """Danh sách các mã đề thi đã có trong hệ thống"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT exam_code, exam_title, created_at FROM answer_keys ORDER BY exam_code ASC")
        return [dict(r) for r in cursor.fetchall()]

def save_result(
    sbd: str,
    exam_code: str,
    score_p1: float,
    score_p2: float,
    score_p3: float,
    score_essay: float,
    total_score: float,
    details_p1: dict,
    details_p2: dict,
    details_p3: dict,
    essay_feedback: dict,
    essay_status: str,
    warped_image_path: str,
    essay_image_path: str
) -> int:
    """Lưu kết quả chấm thi vào SQLite và trả về result_id"""
    sbd_norm = str(sbd).strip().zfill(6)
    code_norm = str(exam_code).strip().zfill(4)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO results (
                sbd, exam_code, score_p1, score_p2, score_p3, score_essay, total_score,
                details_p1, details_p2, details_p3, essay_feedback, essay_status,
                warped_image_path, essay_image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sbd_norm,
            code_norm,
            round(score_p1, 2),
            round(score_p2, 2),
            round(score_p3, 2),
            round(score_essay, 2),
            round(total_score, 2),
            json.dumps(details_p1, ensure_ascii=False),
            json.dumps(details_p2, ensure_ascii=False),
            json.dumps(details_p3, ensure_ascii=False),
            json.dumps(essay_feedback, ensure_ascii=False) if essay_feedback else "{}",
            essay_status,
            warped_image_path,
            essay_image_path
        ))
        conn.commit()
        return cursor.lastrowid

def update_essay_result(result_id: int, score_essay: float, essay_feedback: dict):
    """Cập nhật điểm và nhận xét tự luận sau khi Gemini hoàn thành ngầm"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT score_p1, score_p2, score_p3 FROM results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        if row:
            new_total = round(row["score_p1"] + row["score_p2"] + row["score_p3"] + score_essay, 2)
            cursor.execute("""
                UPDATE results
                SET score_essay = ?,
                    total_score = ?,
                    essay_feedback = ?,
                    essay_status = 'COMPLETED'
                WHERE id = ?
            """, (
                round(score_essay, 2),
                new_total,
                json.dumps(essay_feedback, ensure_ascii=False),
                result_id
            ))
            conn.commit()

def mark_essay_failed(result_id: int, error_msg: str):
    """Đánh dấu chấm tự luận thất bại"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE results
            SET essay_status = 'ERROR',
                essay_feedback = ?
            WHERE id = ?
        """, (json.dumps({"error": error_msg}, ensure_ascii=False), result_id))
        conn.commit()

def get_all_results() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các bài thi đã chấm, sắp xếp SBD tăng dần"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results ORDER BY sbd ASC, id DESC")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["details_p1"] = json.loads(d["details_p1"]) if d["details_p1"] else {}
            d["details_p2"] = json.loads(d["details_p2"]) if d["details_p2"] else {}
            d["details_p3"] = json.loads(d["details_p3"]) if d["details_p3"] else {}
            d["essay_feedback"] = json.loads(d["essay_feedback"]) if d["essay_feedback"] else {}
            results.append(d)
        return results

def get_result_by_id(result_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết một bài thi"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["details_p1"] = json.loads(d["details_p1"]) if d["details_p1"] else {}
        d["details_p2"] = json.loads(d["details_p2"]) if d["details_p2"] else {}
        d["details_p3"] = json.loads(d["details_p3"]) if d["details_p3"] else {}
        d["essay_feedback"] = json.loads(d["essay_feedback"]) if d["essay_feedback"] else {}
        return d
