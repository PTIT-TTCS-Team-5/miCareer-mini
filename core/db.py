import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def get_hr_user(username: str, password: str):
    """Giả lập đăng nhập HR"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT u.userId, u.userName, h.posId, h.compId
                    FROM "user" u
                    JOIN HR h ON u.userId = h.userId
                    WHERE u.userName = %s AND u.pwd = %s AND u.role = 'HR'
                ''', (username, password))
                return cur.fetchone()
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def get_job_postings_by_company(comp_id: int):
    """Lấy danh sách các jobs của công ty HR"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT jobPostId, title, description, expAt
                FROM JOBPOSTING
                WHERE compId = %s
                ORDER BY createdAt DESC
            ''', (comp_id,))
            return cur.fetchall()

def get_applications_for_job(job_post_id: int):
    """Lấy danh sách ứng viên apply cho job"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT ja.jobAppId, ja.stat, ja.appliedAt, u.userName, u.fName, u.lName, u.email
                FROM JOBAPPLICATION ja
                JOIN CANDIDATE c ON ja.candidateId = c.userId
                JOIN "user" u ON c.userId = u.userId
                WHERE ja.jobPostId = %s
                ORDER BY ja.appliedAt DESC
            ''', (job_post_id,))
            return cur.fetchall()

def get_application_detail(job_app_id: int):
    """Lấy chi tiết 1 ứng viên kèm url CV"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT ja.jobAppId, ja.cvSnapUrl, ja.stat, u.fName, u.lName, u.email
                FROM JOBAPPLICATION ja
                JOIN "user" u ON ja.candidateId = u.userId
                WHERE ja.jobAppId = %s
            ''', (job_app_id,))
            return cur.fetchone()

def search_document_chunks(job_app_id: int, query_embedding: list, top_k: int = 3):
    """Tìm kiếm vector gần nhất"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Dùng phép toán <=> của pgvector để tìm khoảng cách cosine
            cur.execute('''
                SELECT chunkId, content, metadata
                FROM AIDOCUMENTCHUNK
                WHERE jobAppId = %s
                ORDER BY embedding <=> %s::halfvec
                LIMIT %s
            ''', (job_app_id, query_embedding, top_k))
            return cur.fetchall()

def log_ai_query(job_app_id: int, hr_id: int, prompt: str, response: str, top_k: int, latency_ms: int):
    """Ghi log vào CSDL FANG"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO AIQUERYLOG (jobAppId, hrId, prompt, response, topK, latencyMs)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (job_app_id, hr_id, prompt, response, top_k, latency_ms))
        conn.commit()
