"""Database layer — truy vấn quan hệ (relational queries).

Chỉ chứa các truy vấn đọc/ghi dữ liệu quan hệ (login, job, application).
KHÔNG truy vấn vector DB hay gọi AI — đó là trách nhiệm của FANG.
"""

import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


# ---------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------


def get_hr_user(username: str, password: str):
    """Đăng nhập HR — trả về dict user hoặc None."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.userId, u.userName, h.posId, h.compId
                    FROM "user" u
                    JOIN HR h ON u.userId = h.userId
                    WHERE u.userName = %s AND u.pwd = %s AND u.role = 'HR'
                """,
                    (username, password),
                )
                return cur.fetchone()
    except Exception as e:
        print(f"DB Error [get_hr_user]: {e}")
        return None


def get_job_postings_by_company(comp_id: int):
    """Lấy danh sách jobs của công ty HR."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jobPostId, title, description, expAt
                FROM JOBPOSTING
                WHERE compId = %s
                ORDER BY createdAt DESC
            """,
                (comp_id,),
            )
            return cur.fetchall()


def get_applications_for_job(job_post_id: int):
    """Lấy danh sách ứng viên apply cho job."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ja.jobAppId, ja.stat, ja.appliedAt,
                       u.userName, u.fName, u.lName, u.email
                FROM JOBAPPLICATION ja
                JOIN CANDIDATE c ON ja.candidateId = c.userId
                JOIN "user" u ON c.userId = u.userId
                WHERE ja.jobPostId = %s
                ORDER BY ja.appliedAt DESC
            """,
                (job_post_id,),
            )
            return cur.fetchall()


def get_application_detail(job_app_id: int):
    """Lấy chi tiết 1 ứng viên kèm cvSnapUrl."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ja.jobAppId, ja.cvSnapUrl, ja.stat,
                       u.fName, u.lName, u.email
                FROM JOBAPPLICATION ja
                JOIN "user" u ON ja.candidateId = u.userId
                WHERE ja.jobAppId = %s
            """,
                (job_app_id,),
            )
            return cur.fetchone()


def get_ingestion_job_for_app(job_app_id: int):
    """Lấy AIINDEXJOB mới nhất cho 1 jobApp (dùng ở HR để check status)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jobId, stat, errorMsg, createdAt, updatedAt
                FROM AIINDEXJOB
                WHERE jobAppId = %s
                ORDER BY createdAt DESC
                LIMIT 1
            """,
                (job_app_id,),
            )
            return cur.fetchone()


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


def get_candidate_user(username: str, password: str):
    """Đăng nhập Candidate — trả về dict user hoặc None."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.userId, u.userName, u.fName, u.lName, u.email
                    FROM "user" u
                    JOIN CANDIDATE c ON u.userId = c.userId
                    WHERE u.userName = %s AND u.pwd = %s AND u.role = 'CANDIDATE'
                """,
                    (username, password),
                )
                return cur.fetchone()
    except Exception as e:
        print(f"DB Error [get_candidate_user]: {e}")
        return None


def get_all_job_postings():
    """Lấy tất cả job đang tuyển (public listing cho candidate)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jp.jobPostId, jp.title, jp.description,
                       jp.requirements, jp.expAt, c.compName
                FROM JOBPOSTING jp
                JOIN COMPANY c ON jp.compId = c.compId
                WHERE jp.expAt >= CURRENT_DATE
                ORDER BY jp.createdAt DESC
            """,
            )
            return cur.fetchall()


def get_candidate_existing_cv(candidate_id: int):
    """Lấy cvSnapUrl từ application gần nhất của candidate (nếu có)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cvSnapUrl
                FROM JOBAPPLICATION
                WHERE candidateId = %s
                  AND cvSnapUrl IS NOT NULL
                ORDER BY appliedAt DESC
                LIMIT 1
            """,
                (candidate_id,),
            )
            row = cur.fetchone()
            return row["cvsnapurl"] if row else None


def has_applied(candidate_id: int, job_post_id: int) -> bool:
    """Kiểm tra candidate đã apply job này chưa."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM JOBAPPLICATION
                WHERE candidateId = %s AND jobPostId = %s
                LIMIT 1
            """,
                (candidate_id, job_post_id),
            )
            return cur.fetchone() is not None


def create_application(candidate_id: int, job_post_id: int, cv_snap_url: str) -> int:
    """Tạo JOBAPPLICATION mới, trả về jobAppId."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO JOBAPPLICATION (candidateId, jobPostId, cvSnapUrl, stat, appliedAt)
                VALUES (%s, %s, %s, 'APPLIED', CURRENT_TIMESTAMP)
                RETURNING jobAppId
            """,
                (candidate_id, job_post_id, cv_snap_url),
            )
            row = cur.fetchone()
        conn.commit()
    return row["jobappid"]
