"""
Module database.py - Quản lý cơ sở dữ liệu SQLite cho hệ thống chấm thi OMR & AI
Hỗ trợ quản lý bài kiểm tra (Exams), lựa chọn mẫu phiếu (3 phần / 4 phần),
tùy chỉnh số câu và thang điểm từng phần, quản lý đáp án các mã đề và kết quả chấm.
Hỗ trợ cả môi trường Local và Vercel Serverless.
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
        
        # 1. Bảng Quản lý Bài Kiểm Tra (Exams)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                sheet_type TEXT NOT NULL DEFAULT '4_part', -- '3_part' hoặc '4_part'
                p1_num INTEGER NOT NULL DEFAULT 12,        -- Số câu trắc nghiệm nhiều lựa chọn
                p1_points REAL NOT NULL DEFAULT 0.25,      -- Điểm mỗi câu TN
                p2_num INTEGER NOT NULL DEFAULT 2,         -- Số câu Đúng/Sai
                p2_mode TEXT NOT NULL DEFAULT 'progressive',-- Cách tính điểm: 'progressive' (chuẩn BGD: 0.1, 0.25, 0.5, 1.0)
                p3_num INTEGER NOT NULL DEFAULT 4,         -- Số câu trả lời ngắn
                p3_points REAL NOT NULL DEFAULT 0.5,       -- Điểm mỗi câu trả lời ngắn
                p4_num INTEGER NOT NULL DEFAULT 2,         -- Số bài tự luận (0 nếu là phiếu 3 phần)
                p4_points REAL NOT NULL DEFAULT 1.5,       -- Điểm mỗi bài tự luận
                total_points REAL NOT NULL DEFAULT 10.0,   -- Tổng điểm đề thi
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Bảng Đáp án các Mã đề thi (Answer Keys)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL DEFAULT 1,
                exam_code TEXT NOT NULL,                  -- Ví dụ '101', '102'
                exam_title TEXT DEFAULT 'Kiểm tra Toán THPT',
                part1_keys TEXT NOT NULL,                 -- JSON: {"1": "A", "2": "B", ...}
                part2_keys TEXT NOT NULL,                 -- JSON: {"1": {"a": "D", "b": "S", ...}}
                part3_keys TEXT NOT NULL,                 -- JSON: {"1": "12.5", "2": "-3.4", ...}
                essay_rubric TEXT NOT NULL,                -- JSON barem tiêu chí và lời giải tự luận
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(exam_id, exam_code)
            )
        """)
        
        # 3. Bảng Kết quả bài thi của thí sinh (Results)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL DEFAULT 1,
                sbd TEXT NOT NULL,                        -- Số báo danh (6 ký tự, ví dụ '010008')
                exam_code TEXT NOT NULL,                  -- Mã đề (ví dụ '101')
                sheet_type TEXT DEFAULT '4_part',         -- '3_part' hoặc '4_part'
                score_p1 REAL DEFAULT 0.0,                -- Điểm phần I
                score_p2 REAL DEFAULT 0.0,                -- Điểm phần II
                score_p3 REAL DEFAULT 0.0,                -- Điểm phần III
                score_essay REAL DEFAULT 0.0,             -- Điểm phần IV tự luận
                total_score REAL DEFAULT 0.0,             -- Tổng điểm bài thi
                details_p1 TEXT,                          -- JSON chi tiết câu chọn, đúng/sai phần 1
                details_p2 TEXT,                          -- JSON chi tiết các ý a, b, c, d phần 2
                details_p3 TEXT,                          -- JSON chi tiết đáp số nhận diện phần 3
                essay_feedback TEXT,                      -- JSON nhận xét, phân tích lỗi sai từ Gemini AI
                essay_status TEXT DEFAULT 'PENDING',      -- PENDING / COMPLETED / SKIPPED / ERROR
                warped_image_path TEXT,                   -- Đường dẫn lưu ảnh phiếu đã nắn thẳng
                essay_image_path TEXT,                    -- Đường dẫn lưu ảnh vùng tự luận đã cắt
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tự động di trú bảng nếu đã tồn tại từ phiên bản cũ (Migration)
        for col_def in [
            ("answer_keys", "exam_id", "INTEGER NOT NULL DEFAULT 1"),
            ("results", "exam_id", "INTEGER NOT NULL DEFAULT 1"),
            ("results", "sheet_type", "TEXT DEFAULT '4_part'"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]} {col_def[2]}")
            except sqlite3.OperationalError:
                pass  # Cột đã tồn tại
        
        conn.commit()

        # Nạp dữ liệu mặc định nếu chưa có bài thi nào
        cursor.execute("SELECT COUNT(*) FROM exams")
        if cursor.fetchone()[0] == 0:
            # Bài thi 1: Mẫu 4 phần (TN + Đ/S + TLN + Tự luận)
            cursor.execute("""
                INSERT INTO exams (id, title, sheet_type, p1_num, p1_points, p2_num, p2_mode, p3_num, p3_points, p4_num, p4_points, total_points)
                VALUES (1, 'Khảo sát Toán 12 - Mẫu 4 Phần (Có Tự Luận)', '4_part', 12, 0.25, 2, 'progressive', 4, 0.5, 2, 1.5, 10.0)
            """)

            # Bài thi 2: Mẫu 3 phần (100% Trắc nghiệm: TN + Đ/S + TLN)
            cursor.execute("""
                INSERT INTO exams (id, title, sheet_type, p1_num, p1_points, p2_num, p2_mode, p3_num, p3_points, p4_num, p4_points, total_points)
                VALUES (2, 'Thi thử Tốt nghiệp THPT - Mẫu 3 Phần (100% Trắc Nghiệm)', '3_part', 12, 0.25, 4, 'progressive', 6, 0.5, 0, 0.0, 10.0)
            """)

            # Đáp án mẫu cho Bài thi 1 (Mã 101 và 102)
            sample_part1 = {str(i): ["A", "B", "C", "D"][(i - 1) % 4] for i in range(1, 13)}
            sample_part2 = {
                "1": {"a": "D", "b": "S", "c": "D", "d": "S"},
                "2": {"a": "S", "b": "D", "c": "D", "d": "S"}
            }
            sample_part3 = {
                "1": "12.5", "2": "-3.4", "3": "0.75", "4": "100"
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

            for code in ["101", "0101"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (exam_id, exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                """, (code, f"Đề thi Khảo sát Toán THPT - Mã {code}", json.dumps(sample_part1, ensure_ascii=False), json.dumps(sample_part2, ensure_ascii=False), json.dumps(sample_part3, ensure_ascii=False), json.dumps(sample_rubric, ensure_ascii=False)))

            # Mã 102
            sample_part1_102 = {str(i): ["B", "C", "D", "A"][(i - 1) % 4] for i in range(1, 13)}
            for code in ["102", "0102"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (exam_id, exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                """, (code, f"Đề thi Khảo sát Toán THPT - Mã {code}", json.dumps(sample_part1_102, ensure_ascii=False), json.dumps(sample_part2, ensure_ascii=False), json.dumps(sample_part3, ensure_ascii=False), json.dumps(sample_rubric, ensure_ascii=False)))

            # Đáp án mẫu cho Bài thi 2 (Mẫu 3 phần)
            sample_part2_4q = {
                "1": {"a": "D", "b": "S", "c": "D", "d": "S"},
                "2": {"a": "S", "b": "D", "c": "D", "d": "S"},
                "3": {"a": "D", "b": "D", "c": "S", "d": "S"},
                "4": {"a": "S", "b": "S", "c": "D", "d": "D"}
            }
            sample_part3_6q = {
                "1": "12.5", "2": "-3.4", "3": "0.75", "4": "100", "5": "2025", "6": "0.5"
            }
            for code in ["101", "0101"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (exam_id, exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                    VALUES (2, ?, ?, ?, ?, ?, '{}')
                """, (code, f"Đề 3 Phần Chuẩn Bộ GD&ĐT - Mã {code}", json.dumps(sample_part1, ensure_ascii=False), json.dumps(sample_part2_4q, ensure_ascii=False), json.dumps(sample_part3_6q, ensure_ascii=False)))

            conn.commit()


# ==============================================================================
# HÀM QUẢN LÝ BÀI KIỂM TRA (EXAMS)
# ==============================================================================

def create_exam(
    title: str,
    sheet_type: str = "4_part",
    p1_num: int = 12,
    p1_points: float = 0.25,
    p2_num: int = 2,
    p2_mode: str = "progressive",
    p3_num: int = 4,
    p3_points: float = 0.5,
    p4_num: int = 2,
    p4_points: float = 1.5,
    total_points: float = 10.0
) -> int:
    """Tạo mới một bài kiểm tra với cấu hình mẫu phiếu và thang điểm tùy chỉnh"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exams (title, sheet_type, p1_num, p1_points, p2_num, p2_mode, p3_num, p3_points, p4_num, p4_points, total_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, sheet_type, p1_num, p1_points, p2_num, p2_mode, p3_num, p3_points, p4_num, p4_points, total_points))
        conn.commit()
        return cursor.lastrowid

def get_exam(exam_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin cấu hình chi tiết của một bài kiểm tra"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        row = cursor.fetchone()
        if not row:
            # Fallback lấy bài thi đầu tiên
            cursor.execute("SELECT * FROM exams ORDER BY id ASC LIMIT 1")
            row = cursor.fetchone()
        return dict(row) if row else None

def list_exams() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các bài kiểm tra có trong hệ thống"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]

def delete_exam(exam_id: int):
    """Xóa một bài kiểm tra cùng đáp án và kết quả liên quan"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
        cursor.execute("DELETE FROM answer_keys WHERE exam_id = ?", (exam_id,))
        cursor.execute("DELETE FROM results WHERE exam_id = ?", (exam_id,))
        conn.commit()


# ==============================================================================
# HÀM QUẢN LÝ ĐÁP ÁN (ANSWER KEYS)
# ==============================================================================

def get_answer_key(exam_code: str, exam_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Lấy đáp án và barem chấm theo mã đề thi và bài kiểm tra
    Hỗ trợ cả dạng '101' lẫn '0101'
    """
    code_raw = str(exam_code).strip()
    code_zfilled = code_raw.zfill(4)
    code_lstripped = code_raw.lstrip("0") or "0"

    with get_connection() as conn:
        cursor = conn.cursor()
        if exam_id:
            cursor.execute("""
                SELECT * FROM answer_keys 
                WHERE exam_id = ? AND (exam_code = ? OR exam_code = ? OR exam_code = ?)
                ORDER BY id ASC LIMIT 1
            """, (exam_id, code_raw, code_zfilled, code_lstripped))
        else:
            cursor.execute("""
                SELECT * FROM answer_keys 
                WHERE exam_code = ? OR exam_code = ? OR exam_code = ?
                ORDER BY id ASC LIMIT 1
            """, (code_raw, code_zfilled, code_lstripped))
            
        row = cursor.fetchone()
        if not row:
            # Fallback lấy mã đầu tiên của bài thi
            if exam_id:
                cursor.execute("SELECT * FROM answer_keys WHERE exam_id = ? ORDER BY id ASC LIMIT 1", (exam_id,))
            else:
                cursor.execute("SELECT * FROM answer_keys ORDER BY id ASC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None

        return {
            "id": row["id"],
            "exam_id": row["exam_id"],
            "exam_code": row["exam_code"],
            "exam_title": row["exam_title"],
            "part1_keys": json.loads(row["part1_keys"]),
            "part2_keys": json.loads(row["part2_keys"]),
            "part3_keys": json.loads(row["part3_keys"]),
            "essay_rubric": json.loads(row["essay_rubric"]) if row["essay_rubric"] else {}
        }

def save_answer_key(exam_code: str, exam_title: str, part1: dict, part2: dict, part3: dict, rubric: dict, exam_id: int = 1):
    """Thêm hoặc cập nhật đáp án cho một mã đề trong bài thi"""
    code_norm = str(exam_code).strip().zfill(4)
    code_raw = str(exam_code).strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        for c in set([code_norm, code_raw]):
            cursor.execute("""
                INSERT INTO answer_keys (exam_id, exam_code, exam_title, part1_keys, part2_keys, part3_keys, essay_rubric)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exam_id, exam_code) DO UPDATE SET
                    exam_title = excluded.exam_title,
                    part1_keys = excluded.part1_keys,
                    part2_keys = excluded.part2_keys,
                    part3_keys = excluded.part3_keys,
                    essay_rubric = excluded.essay_rubric
            """, (
                exam_id, c, exam_title,
                json.dumps(part1, ensure_ascii=False),
                json.dumps(part2, ensure_ascii=False),
                json.dumps(part3, ensure_ascii=False),
                json.dumps(rubric, ensure_ascii=False)
            ))
        conn.commit()

def list_all_keys(exam_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Danh sách các mã đề thi đã có trong hệ thống"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if exam_id:
            cursor.execute("SELECT exam_id, exam_code, exam_title, created_at FROM answer_keys WHERE exam_id = ? ORDER BY exam_code ASC", (exam_id,))
        else:
            cursor.execute("SELECT exam_id, exam_code, exam_title, created_at FROM answer_keys ORDER BY exam_id ASC, exam_code ASC")
        return [dict(r) for r in cursor.fetchall()]


# ==============================================================================
# HÀM QUẢN LÝ KẾT QUẢ CHẤM (RESULTS)
# ==============================================================================

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
    essay_image_path: str,
    exam_id: int = 1,
    sheet_type: str = "4_part"
) -> int:
    """Lưu kết quả chấm bài thi vào SQLite"""
    sbd_norm = str(sbd).strip().zfill(6)
    code_norm = str(exam_code).strip().zfill(4)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO results (
                exam_id, sbd, exam_code, sheet_type, score_p1, score_p2, score_p3, score_essay, total_score,
                details_p1, details_p2, details_p3, essay_feedback, essay_status,
                warped_image_path, essay_image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exam_id, sbd_norm, code_norm, sheet_type,
            round(score_p1, 2), round(score_p2, 2), round(score_p3, 2), round(score_essay, 2), round(total_score, 2),
            json.dumps(details_p1, ensure_ascii=False),
            json.dumps(details_p2, ensure_ascii=False),
            json.dumps(details_p3, ensure_ascii=False),
            json.dumps(essay_feedback, ensure_ascii=False) if essay_feedback else "{}",
            essay_status, warped_image_path, essay_image_path
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
                SET score_essay = ?, total_score = ?, essay_feedback = ?, essay_status = 'COMPLETED'
                WHERE id = ?
            """, (round(score_essay, 2), new_total, json.dumps(essay_feedback, ensure_ascii=False), result_id))
            conn.commit()

def mark_essay_failed(result_id: int, error_msg: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE results
            SET essay_status = 'ERROR', essay_feedback = ?
            WHERE id = ?
        """, (json.dumps({"error": error_msg}, ensure_ascii=False), result_id))
        conn.commit()

def get_all_results(exam_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các bài thi đã chấm, sắp xếp SBD tăng dần"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if exam_id:
            cursor.execute("SELECT * FROM results WHERE exam_id = ? ORDER BY sbd ASC, id DESC", (exam_id,))
        else:
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
