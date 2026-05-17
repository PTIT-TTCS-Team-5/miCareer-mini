"""NMAIex API Client — gọi các endpoint NMAIex ranking và master data.

Nguyên tắc thin client: chỉ forward request/response, không chứa business logic.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

FANG_BASE_URL = os.getenv("FANG_API_URL", "http://localhost:8000/v2").rstrip("/")
_TIMEOUT = 30  # Master data calls không cần timeout dài


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(path: str, params: dict | None = None) -> Any:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _patch(path: str, payload: dict) -> dict:
    url = f"{FANG_BASE_URL}{path}"
    resp = requests.patch(url, json=payload, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Master Data (Province, Skill, Level, Category)
# ---------------------------------------------------------------------------


def get_provinces() -> list[dict]:
    """Lấy danh sách tỉnh/thành theo vùng.

    Returns:
        List of {region_id, region_name, provinces: [{province_id, province_name}]}
    """
    return _get("/nmaiex/master/provinces")


def get_skills() -> list[dict]:
    """Lấy danh sách skills trong catalog.

    Returns:
        List of {skill_id, skill_name}
    """
    return _get("/nmaiex/master/skills")


def get_levels() -> list[dict]:
    """Lấy danh sách cấp bậc công việc.

    Returns:
        List of {level_id, level_name, description}
    """
    return _get("/nmaiex/master/levels")


def get_categories() -> list[dict]:
    """Lấy danh sách danh mục nghề nghiệp.

    Returns:
        List of {category_id, category_name, description}
    """
    return _get("/nmaiex/master/categories")


def load_all_master_data() -> dict:
    """Load toàn bộ master data trong 1 lần gọi (dùng để cache vào session_state).

    Returns:
        {
            "provinces": [...],  # grouped by region
            "skills": [...],
            "levels": [...],
            "categories": [...],
        }
    """
    return {
        "provinces": get_provinces(),
        "skills": get_skills(),
        "levels": get_levels(),
        "categories": get_categories(),
    }


# ---------------------------------------------------------------------------
# Job Management API
# ---------------------------------------------------------------------------


def get_job_detail(job_id: int) -> dict:
    """Lấy chi tiết job posting kèm structured data (provId, levels, categories, skills).

    Returns:
        dict với tất cả thông tin job bao gồm structured NMAIex data
    """
    return _get(f"/nmaiex/jobs/{job_id}")


def update_job_content(job_id: int, title: str, description: str) -> dict:
    """Cập nhật nội dung text của job (title, description).

    Backend sẽ trigger re-ingest async — ranking có thể tạm thời kém chính xác.

    Returns:
        {job_id, reingestion_status: "queued"}
    """
    return _patch(
        f"/nmaiex/jobs/{job_id}/content",
        {
            "title": title,
            "description": description,
        },
    )


def update_job_structured(
    job_id: int,
    *,
    prov_id: str | None = None,
    level_ids: list[int] | None = None,
    cat_ids: list[int] | None = None,
    skill_ids: list[int] | None = None,
    custom_skill_texts: list[str] | None = None,
    min_salary: int | None = None,
    max_salary: int | None = None,
    work_mode: str | None = None,
) -> dict:
    """Cập nhật metadata cấu trúc của job (không trigger re-embed).

    Xử lý tức thì (synchronous).

    Returns:
        {job_id, updated_fields: [...]}
    """
    payload: dict[str, Any] = {}
    if prov_id is not None:
        payload["provId"] = prov_id
    if level_ids is not None:
        payload["levelIds"] = level_ids
    if cat_ids is not None:
        payload["catIds"] = cat_ids
    if skill_ids is not None:
        payload["skillIds"] = skill_ids
    if custom_skill_texts is not None:
        payload["custom_skills"] = custom_skill_texts
    if min_salary is not None:
        payload["minSalary"] = min_salary
    if max_salary is not None:
        payload["maxSalary"] = max_salary
    if work_mode is not None:
        payload["workMode"] = work_mode

    return _patch(f"/nmaiex/jobs/{job_id}/structured", payload)


# ---------------------------------------------------------------------------
# Candidate Management API
# ---------------------------------------------------------------------------


def update_candidate(
    candidate_id: int,
    *,
    bio: str | None = None,
    cv_url: str | None = None,
) -> dict:
    """Cập nhật thông tin candidate (bio, cvUrl).

    Returns:
        {candidate_id, updated_fields: [...]}
    """
    payload: dict[str, Any] = {}
    if bio is not None:
        payload["bio"] = bio
    if cv_url is not None:
        payload["cvUrl"] = cv_url

    return _patch(f"/nmaiex/candidates/{candidate_id}", payload)


# ---------------------------------------------------------------------------
# Ranking API (Phase 3)
# ---------------------------------------------------------------------------


def get_candidates_ranking(job_id: int, params: dict | None = None) -> list[dict]:
    """Lấy danh sách ứng viên được xếp hạng cho 1 Job.

    Params:
        province_id, work_mode, limit
    """
    return _get(f"/nmaiex/ranking/candidates/{job_id}", params=params)


def get_jobs_ranking(candidate_id: int, params: dict | None = None) -> list[dict]:
    """Lấy danh sách công việc phù hợp cho 1 Ứng viên.

    Params:
        province_id, work_mode, limit
    """
    return _get(f"/nmaiex/ranking/jobs/{candidate_id}", params=params)
