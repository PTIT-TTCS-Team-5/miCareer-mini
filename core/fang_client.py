"""FANG API Client — thin wrapper gọi FANG AI Core v2.

Tất cả logic AI (embed, vector search, LLM call) đã được chuyển sang FANG.
miCareer-mini chỉ gọi các hàm này để tương tác với FANG.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

FANG_BASE_URL = os.getenv("FANG_API_URL", "http://localhost:8000/v2").rstrip("/")
_TIMEOUT = 120  # giây — LLM call có thể mất khá lâu


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(path: str, payload: dict) -> dict:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.post(url, json=payload, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, params: dict | None = None) -> Any:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _patch(path: str, payload: dict, params: dict | None = None) -> dict:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.patch(url, json=payload, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _delete(path: str, params: dict | None = None) -> None:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.delete(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Chat API
# ---------------------------------------------------------------------------


def chat_query(
    job_app_id: int,
    hr_id: int,
    prompt: str,
    model_mode: str,
    conversation_id: str | None = None,
) -> dict:
    """Gửi prompt đến FANG, nhận JSON response.

    Returns:
        dict với các key:
            conversationId, messageId, response, model, modelMode,
            fallbackPath, latencyMs, topK, contextWarning (nullable)
    """
    payload: dict[str, Any] = {
        "jobAppId": job_app_id,
        "hrId": hr_id,
        "prompt": prompt,
        "modelMode": model_mode,
        "conversationId": conversation_id,
    }
    return _post("/chat/query", payload)


def list_conversations(hr_id: int, job_app_id: int) -> list[dict]:
    """Lấy danh sách conversations của HR cho 1 jobApp."""
    return _get("/chat/conversations", params={"hrId": hr_id, "jobAppId": job_app_id})


def get_conversation_messages(conversation_id: str) -> list[dict]:
    """Lấy lịch sử messages của 1 conversation (loại trừ system messages)."""
    return _get(f"/chat/conversations/{conversation_id}/messages")


def summarize_conversation(conversation_id: str) -> dict:
    """Gọi FANG tóm tắt hội thoại (Summarize & Continue)."""
    return _post(f"/chat/conversations/{conversation_id}/summarize", {})


def branch_new_conversation(conversation_id: str) -> dict:
    """Gọi FANG tạo hội thoại mới từ summary hội thoại cũ."""
    return _post(f"/chat/conversations/{conversation_id}/branch-new", {})


# ---------------------------------------------------------------------------
# Ingestion API
# ---------------------------------------------------------------------------


def trigger_ingestion(job_app_id: int, cv_snap_url: str) -> dict:
    """Kích hoạt pipeline parse → chunk → embed CV trên FANG.

    Returns:
        dict với key: jobId, jobAppId, status, createdAt
    """
    payload = {
        "jobAppId": job_app_id,
        "cvSnapUrl": cv_snap_url,
    }
    return _post("/ingestion/jobs", payload)


def get_ingestion_status(job_id: str) -> dict:
    """Kiểm tra trạng thái ingestion job.

    Returns:
        dict với key: jobId, jobAppId, status ('PENDING'|'PROCESSING'|'SUCCESS'|'FAILED'),
                       errorMsg (nullable), createdAt, updatedAt
    """
    return _get(f"/ingestion/jobs/{job_id}")


def poll_ingestion_until_done(
    job_id: str,
    interval_secs: float = 2.0,
    timeout_secs: float = 120.0,
) -> dict:
    """Polling trạng thái ingestion cho đến khi hoàn thành hoặc timeout.

    Returns:
        dict status cuối cùng
    Raises:
        TimeoutError nếu vượt timeout_secs
    """
    start = time.time()
    while True:
        status = get_ingestion_status(job_id)
        if status.get("status") in ("SUCCESS", "FAILED"):
            return status
        if time.time() - start > timeout_secs:
            raise TimeoutError(
                f"Ingestion job {job_id} chưa hoàn thành sau {timeout_secs}s."
            )
        time.sleep(interval_secs)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def health_check() -> bool:
    """Kiểm tra FANG API có đang chạy không."""
    try:
        resp = requests.get(f"{FANG_BASE_URL}/healthz", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JobPosting Agent API (C3)
# ---------------------------------------------------------------------------


def jobposting_agent_query(
    job_post_id: int,
    hr_id: int,
    prompt: str,
    conversation_id: str | None = None,
) -> dict:
    """Gửi prompt đến JobPosting Agent, nhận JSON response.

    Returns:
        dict với các key:
            conversationId, messageId, response, model, stepsUsed,
            toolCalls[], sourceJobAppIds[], workingSet, latencyMs, warnings[]
    """
    payload: dict[str, Any] = {
        "jobPostId": job_post_id,
        "hrId": hr_id,
        "prompt": prompt,
        "conversationId": conversation_id,
    }
    return _post("/agent/job-posting/query", payload)


def list_jobposting_agent_conversations(
    job_post_id: int,
    hr_id: int,
) -> list[dict]:
    """Lấy danh sách conversations của HR cho 1 jobPost.

    Returns:
        List of {conversationId, title, lastMessageAt, messageCount}
    """
    return _get(
        "/agent/job-posting/conversations",
        params={"jobPostId": job_post_id, "hrId": hr_id},
    )


def get_jobposting_agent_messages(
    conversation_id: str,
    include_tool_messages: bool = True,
    include_system: bool = False,
) -> list[dict]:
    """Lấy lịch sử messages của 1 JobPosting Agent conversation.

    Returns:
        List of {role, content, ...} — bao gồm tool_call/tool_result nếu include_tool_messages=True
    """
    return _get(
        f"/agent/job-posting/conversations/{conversation_id}/messages",
        params={
            "includeToolMessages": str(include_tool_messages).lower(),
            "includeSystem": str(include_system).lower(),
        },
    )


def rename_jobposting_agent_conversation(
    conversation_id: str,
    hr_id: int,
    title: str,
) -> dict:
    """Đổi tên 1 JobPosting Agent conversation.

    Returns:
        dict xác nhận update
    """
    return _patch(
        f"/agent/job-posting/conversations/{conversation_id}",
        payload={"title": title},
        params={"hrId": hr_id},
    )


def archive_jobposting_agent_conversation(
    conversation_id: str,
    hr_id: int,
) -> None:
    """Lưu trữ (xoá mềm) 1 JobPosting Agent conversation. Returns 204."""
    _delete(
        f"/agent/job-posting/conversations/{conversation_id}",
        params={"hrId": hr_id},
    )
