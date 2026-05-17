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
                    SELECT u.userid, u.username, h.posid, h.compid
                    FROM "user" u
                    JOIN hr h ON u.userid = h.userid
                    WHERE u.username = %s AND u.pwd = %s AND u.role = 'HR'
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
                SELECT jobpostid, title, description, expat
                FROM jobposting
                WHERE compid = %s
                ORDER BY createdat DESC
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
                SELECT ja.jobappid, ja.stat, ja.appliedat,
                       u.username, u.fname, u.lname, u.email
                FROM jobapplication ja
                JOIN candidate c ON ja.candidateid = c.userid
                JOIN "user" u ON c.userid = u.userid
                WHERE ja.jobpostid = %s
                ORDER BY ja.appliedat DESC
            """,
                (job_post_id,),
            )
            return cur.fetchall()


def get_application_detail(job_app_id: int):
    """Lấy chi tiết 1 ứng viên kèm cvsnapurl."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ja.jobappid, ja.cvsnapurl, ja.stat,
                       u.fname, u.lname, u.email
                FROM jobapplication ja
                JOIN "user" u ON ja.candidateid = u.userid
                WHERE ja.jobappid = %s
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
                SELECT indexjobid, stat, errormsg, createdat, finishedat
                FROM aiindexjob
                WHERE jobappid = %s
                ORDER BY createdat DESC
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
                    SELECT u.userid, u.username, u.fname, u.lname, u.email,
                           c.bio, c.cvurl
                    FROM "user" u
                    JOIN candidate c ON u.userid = c.userid
                    WHERE u.username = %s AND u.pwd = %s AND u.role = 'CANDIDATE'
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
                SELECT jp.jobpostid, jp.title, jp.description,
                       jp.expat, c.compname
                FROM jobposting jp
                JOIN company c ON jp.compid = c.compid
                WHERE jp.expat >= CURRENT_DATE
                ORDER BY jp.createdat DESC
            """,
            )
            return cur.fetchall()


def get_candidate_existing_cv(candidate_id: int):
    """Lấy cvsnapurl từ application gần nhất của candidate (nếu có)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cvsnapurl
                FROM jobapplication
                WHERE candidateid = %s
                  AND cvsnapurl IS NOT NULL
                ORDER BY appliedat DESC
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
                SELECT 1 FROM jobapplication
                WHERE candidateid = %s AND jobpostid = %s
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
                INSERT INTO jobapplication (candidateid, jobpostid, cvsnapurl, stat, appliedat)
                VALUES (%s, %s, %s, 'APPLIED', CURRENT_TIMESTAMP)
                RETURNING jobappid
            """,
                (candidate_id, job_post_id, cv_snap_url),
            )
            row = cur.fetchone()
        conn.commit()
    return row["jobappid"]


def update_candidate_cv_url(candidate_id: int, cv_url: str) -> None:
    """Cập nhật cvurl trong bảng candidate (CV gốc của ứng viên)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE candidate SET cvurl = %s
                WHERE userid = %s
            """,
                (cv_url, candidate_id),
            )
        conn.commit()


def get_candidate_bio_and_cv(candidate_id: int) -> dict | None:
    """Lấy bio và cvurl hiện tại của candidate."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bio, cvurl FROM candidate WHERE userid = %s
            """,
                (candidate_id,),
            )
            return cur.fetchone()
