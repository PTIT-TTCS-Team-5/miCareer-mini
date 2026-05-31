"""miCareer-mini — thin Streamlit UI.

Kiến trúc:
- miCareer-mini CHỈ hiển thị UI và gọi FANG API.
- Mọi logic AI (embed, vector search, LLM call) đều nằm ở FANG.

Các trang:
  HR:        login_hr → jobs → applications → app_detail (RAG chat)
  Candidate: login_candidate → candidate_jobs → candidate_apply
"""

import os

import streamlit as st

from core import db, fang_client, nmaiex_client
from core.cloudinary_upload import upload_cv_pdf

# Dev mode: hiển thị score_breakdown badge trên kết quả ranking
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="miCareer-mini",
    layout="wide",
    page_icon="🎯",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

_defaults = {
    "role": None,  # "hr" | "candidate"
    "current_page": "home",
    "hr_user": None,
    "candidate_user": None,
    "selected_job_id": None,
    "selected_app_id": None,
    "conversation_id": None,
    "apply_job_id": None,
    "apply_job_title": None,
    # NMAIex additions
    "nmaiex_master": None,  # cache master data (provinces/skills/levels/categories)
    "hr_edit_job_id": None,  # job đang được HR chỉnh sửa
    "selected_job_detail": None,  # Candidate side job detail modal
    "selected_job_data": None,  # Candidate side job data for modal
    # Phase 3: Ranking
    "hr_ranking_job_id": None,  # job HR đang xem AI ranking
    "hr_ranking_job_title": None,
    # C3: JobPosting Agent — dùng prefix jobposting_agent_ để tránh collision
    "jobposting_agent_job_id": None,  # jobPostId đang mở agent
    "jobposting_agent_job_title": None,  # cached title cho header/sidebar
    "jobposting_agent_conversation_id": None,  # conversation hiện tại (chỉ agent này)
    "jobposting_agent_conversations": [],  # danh sách conversations cho job hiện tại
    "jobposting_agent_messages": [],  # messages của conversation đang chọn
    "jobposting_agent_working_set": None,  # last response working set
    "jobposting_agent_source_job_app_ids": [],  # last response source IDs
    "jobposting_agent_last_tool_calls": [],  # tool calls từ turn hiện tại
    "jobposting_agent_warnings": [],  # last response warnings
    "jobposting_agent_error": None,  # last user-facing error
    "jobposting_agent_pending_prompt": None,  # prompt đang chờ gửi
    "jobposting_agent_is_loading": False,  # True khi đang gọi API
    "jobposting_agent_rename_title": "",  # rename input cho conversation đang chọn
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# NMAIex master data cache loader
# ---------------------------------------------------------------------------


def _ensure_master_data():
    """Load master data một lần rồi cache vào session_state."""
    if st.session_state.nmaiex_master is None:
        try:
            st.session_state.nmaiex_master = nmaiex_client.load_all_master_data()
        except Exception as e:
            st.warning(f"⚠️ Không tải được master data từ FANG: {e}")
            st.session_state.nmaiex_master = {}
    return st.session_state.nmaiex_master


# ---------------------------------------------------------------------------
# Navigation helper
# ---------------------------------------------------------------------------


def go(page: str):
    st.session_state.current_page = page
    st.rerun()


# ---------------------------------------------------------------------------
# MODEL MODE options (7 lựa chọn theo implementation_plan)
# ---------------------------------------------------------------------------

MODEL_MODES = {
    "🤖 Auto-Lite (Gemini → GPT → Claude)": "auto-lite",
    "🤖 Auto-Pro (Gemini Pro → GPT-5.5)": "auto-pro",
    "💚 Gemini Flash Lite": "gemini-flash",
    "💚 GPT-5.4 mini": "gpt-mini",
    "💚 Claude 4.5 Haiku": "claude-haiku",
    "🔶 Gemini 3.1 Pro": "gemini-pro",
    "🔶 GPT-5.5 (Flagship)": "gpt-full",
}


# ===========================================================================
# HOME — chọn role
# ===========================================================================


def page_home():
    st.markdown("# 🎯 miCareer-mini")
    st.markdown("#### Chào mừng bạn đến với hệ thống tuyển dụng nội bộ")
    st.divider()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown("### 🏢 HR / Nhà tuyển dụng")
        st.write("Đánh giá ứng viên với AI Co-pilot.")
        if st.button("Đăng nhập HR", use_container_width=True, key="btn_goto_hr"):
            st.session_state.role = "hr"
            go("login_hr")
    with col2:
        st.markdown("### 👤 Ứng viên")
        st.write("Xem job và nộp CV của bạn.")
        if st.button(
            "Đăng nhập Ứng viên", use_container_width=True, key="btn_goto_cand"
        ):
            st.session_state.role = "candidate"
            go("login_candidate")


# ===========================================================================
# HR PAGES
# ===========================================================================


def page_login_hr():
    st.title("🔐 HR Login")
    with st.form("login_hr_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Đăng nhập", use_container_width=True)

    if submit:
        user = db.get_hr_user(username, password)
        if user:
            st.session_state.hr_user = user
            go("hr_jobs")
        else:
            st.error("Sai tài khoản hoặc mật khẩu HR!")

    if st.button("← Quay lại trang chủ", key="back_home_hr"):
        go("home")


def page_hr_jobs():
    user = st.session_state.hr_user
    st.title(f"👋 Xin chào, {user['username']}")
    st.subheader("Danh sách tin tuyển dụng của công ty")

    jobs = db.get_job_postings_by_company(user["compid"])
    if not jobs:
        st.info("Công ty bạn chưa có tin tuyển dụng nào.")
        return

    for j in jobs:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                st.markdown(f"**{j['title']}**")
                st.caption(f"Hết hạn: {j['expat']}")
            with col2:
                if st.button(
                    "Xem job",
                    key=f"hr_view_job_{j['jobpostid']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_job_id = j["jobpostid"]
                    go("hr_job_view")
            with col3:
                if st.button(
                    "Xem ứng viên",
                    key=f"hr_app_list_{j['jobpostid']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_job_id = j["jobpostid"]
                    go("hr_applications")
            with col4:
                if st.button(
                    "🤖 Agent",
                    key=f"hr_job_agent_{j['jobpostid']}",
                    use_container_width=True,
                    help="Mở Job Agent để phân tích ứng viên bằng AI",
                ):
                    _open_jobposting_agent(j["jobpostid"], j["title"])

    st.divider()
    if st.button("🚪 Đăng xuất", key="logout_hr", use_container_width=True):
        st.session_state.hr_user = None
        go("home")


def page_hr_job_view():
    """Trang xem chi tiết job của HR."""
    if st.button("← Quay lại danh sách Job", key="back_hr_jobs_from_view"):
        go("hr_jobs")

    job_id = st.session_state.selected_job_id
    if not job_id:
        st.error("Không có job nào được chọn.")
        go("hr_jobs")
        return

    # Load job detail từ DB
    job = db.get_job_posting_detail(job_id)
    if not job:
        st.error("Không tìm thấy job.")
        go("hr_jobs")
        return

    st.title(f"📋 {job['title']}")
    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Thông tin Job")
        st.write(f"**Công ty:** {job.get('compname', 'N/A')}")
        st.write(f"**Hết hạn nộp:** {job['expat']}")
        if job.get("description"):
            st.markdown("**Mô tả công việc:**")
            st.markdown(job.get("description", ""))
        if job.get("minSalary") or job.get("maxSalary"):
            min_sal = job.get("minSalary", 0)
            max_sal = job.get("maxSalary", 0)
            st.markdown(f"**Mức lương:** {min_sal:,.0f} — {max_sal:,.0f} VNĐ")

    with col2:
        st.markdown("### Hành động")
        if st.button(
            "✏️ Sửa Job",
            type="primary",
            use_container_width=True,
            key=f"edit_job_detail_{job_id}",
        ):
            st.session_state.hr_edit_job_id = job_id
            go("hr_job_edit")

        if st.button(
            "👥 Danh sách ứng viên",
            use_container_width=True,
            key=f"apps_from_view_{job_id}",
        ):
            st.session_state.selected_job_id = job_id
            go("hr_applications")

        if st.button(
            "🤖 Hỏi Agent về job này",
            use_container_width=True,
            key=f"job_agent_from_view_{job_id}",
            help="Mở Job Agent để phân tích toàn bộ ứng viên của job này bằng AI",
        ):
            job_title_val = job.get("title")
            _open_jobposting_agent(job_id, job_title_val)


def page_hr_job_edit():
    """Phase 1.5 — Form sửa Job Posting với 2 nút Save tách biệt."""
    if st.button("← Quay lại danh sách Job", key="back_hr_jobs_from_edit"):
        go("hr_jobs")

    job_id = st.session_state.hr_edit_job_id
    if not job_id:
        st.error("Không có job nào được chọn.")
        go("hr_jobs")
        return

    master = _ensure_master_data()

    # Load job detail từ NMAIex API
    try:
        job = nmaiex_client.get_job_detail(job_id)
    except Exception as e:
        err_str = str(e)
        if "404" in err_str or "Not Found" in err_str:
            st.warning(
                f"⚠️ Job ID `{job_id}` chưa có dữ liệu NMAIex (structured data). "
                "Hãy đảm bảo job này đã được seed vào FANG DB. "
                "Bạn vẫn có thể xem job trong danh sách."
            )
        else:
            st.error(f"❌ Không tải được thông tin job: {e}")
        if st.button("← Quay lại danh sách Job (do lỗi)", key="back_on_job_err"):
            go("hr_jobs")
        return

    st.title(f"✏️ Chỉnh sửa Job: {job.get('title', job_id)}")
    st.divider()

    # ── TAB: Content vs Settings ──
    tab_content, tab_settings = st.tabs(["📝 Nội dung", "⚙️ Cài đặt & Kỹ năng"])

    # ─────────────────────────────────────────
    # TAB 1: CONTENT (title + description)
    # ─────────────────────────────────────────
    with tab_content:
        st.info(
            "💡 Lưu nội dung sẽ **kích hoạt re-ingest** — ranking có thể tạm thời kém chính xác trong vài phút."
        )
        new_title = st.text_input(
            "Tiêu đề Job", value=job.get("title", ""), key="edit_title"
        )
        new_desc = st.text_area(
            "Mô tả công việc",
            value=job.get("description", ""),
            height=300,
            key="edit_desc",
        )

        if st.button(
            "💾 Lưu Nội dung",
            type="primary",
            use_container_width=True,
            key="save_content",
        ):
            if not new_title.strip():
                st.error("Tiêu đề không được để trống.")
            else:
                with st.spinner("Đang lưu và kích hoạt re-ingest..."):
                    try:
                        result = nmaiex_client.update_job_content(
                            job_id, new_title.strip(), new_desc.strip()
                        )
                        st.success(
                            "✅ Nội dung đã được lưu. Nội dung đang được cập nhật, ranking có thể chưa chính xác trong vài phút."
                        )
                        st.caption(
                            f"Re-ingest status: `{result.get('reingestion_status', 'queued')}`"
                        )
                        st.session_state.nmaiex_master = (
                            None  # invalidate cache nếu cần
                        )
                    except Exception as e:
                        st.error(f"❌ Lỗi khi lưu nội dung: {e}")

    # ─────────────────────────────────────────
    # TAB 2: SETTINGS (structured metadata)
    # ─────────────────────────────────────────
    with tab_settings:
        st.info("⚡ Lưu cài đặt xử lý tức thì, không cần re-embed.")

        # --- Province (2 cấp: Region → Province) ---
        st.subheader("📍 Địa điểm")
        provinces_data = master.get("provinces", [])
        region_map = {r["region_name"]: r for r in provinces_data}
        region_names = list(region_map.keys())

        current_prov_id = job.get("prov_id") or job.get("provId")
        # Tìm region hiện tại
        default_region_idx = 0
        for i, r in enumerate(provinces_data):
            if any(p["province_id"] == current_prov_id for p in r.get("provinces", [])):
                default_region_idx = i
                break

        sel_region = st.selectbox(
            "Vùng", region_names, index=default_region_idx, key="sel_region"
        )
        prov_list = region_map[sel_region]["provinces"] if sel_region else []
        prov_options = {p["province_name"]: p["province_id"] for p in prov_list}
        default_prov_idx = 0
        prov_names = list(prov_options.keys())
        for i, (name, pid) in enumerate(prov_options.items()):
            if pid == current_prov_id:
                default_prov_idx = i
                break
        sel_prov_name = st.selectbox(
            "Tỉnh/Thành phố", prov_names, index=default_prov_idx, key="sel_prov"
        )
        sel_prov_id = prov_options.get(sel_prov_name, "")

        # --- Work Mode ---
        work_modes = ["ONSITE", "HYBRID", "REMOTE"]
        current_wm = job.get("workMode") or job.get("work_mode") or "ONSITE"
        wm_idx = work_modes.index(current_wm) if current_wm in work_modes else 0
        sel_work_mode = st.selectbox(
            "Hình thức làm việc", work_modes, index=wm_idx, key="sel_workmode"
        )

        st.divider()

        # --- Levels ---
        st.subheader("🎯 Cấp bậc")
        levels_data = master.get("levels", [])
        level_name_to_id = {lvl["level_name"]: lvl["level_id"] for lvl in levels_data}
        current_level_ids = job.get("level_ids") or []
        default_level_names = [
            lvl["level_name"]
            for lvl in levels_data
            if lvl["level_id"] in current_level_ids
        ]
        sel_level_names = st.multiselect(
            "Cấp bậc yêu cầu",
            list(level_name_to_id.keys()),
            default=default_level_names,
            key="sel_levels",
        )
        sel_level_ids = [level_name_to_id[n] for n in sel_level_names]

        st.divider()

        # --- Categories ---
        st.subheader("📂 Danh mục nghề")
        cats_data = master.get("categories", [])
        cat_name_to_id = {c["category_name"]: c["category_id"] for c in cats_data}
        current_cat_ids = job.get("cat_ids") or []
        default_cat_names = [
            c["category_name"] for c in cats_data if c["category_id"] in current_cat_ids
        ]
        sel_cat_names = st.multiselect(
            "Danh mục",
            list(cat_name_to_id.keys()),
            default=default_cat_names,
            key="sel_cats",
        )
        sel_cat_ids = [cat_name_to_id[n] for n in sel_cat_names]

        st.divider()

        # --- Skills (Hybrid: catalog + custom) ---
        st.subheader("🛠️ Kỹ năng yêu cầu")
        skills_data = master.get("skills", [])
        skill_name_to_id = {s["skill_name"]: s["skill_id"] for s in skills_data}
        current_skill_ids = job.get("skill_ids") or []
        default_skill_names = [
            s["skill_name"] for s in skills_data if s["skill_id"] in current_skill_ids
        ]
        sel_skill_names = st.multiselect(
            "Skills từ catalog",
            list(skill_name_to_id.keys()),
            default=default_skill_names,
            key="sel_skills",
        )
        sel_skill_ids = [skill_name_to_id[n] for n in sel_skill_names]

        st.caption("Thêm kỹ năng tùy chỉnh (không có trong catalog):")
        custom_skills_raw = st.text_input(
            "Nhập skill tùy ý, cách nhau bằng dấu phẩy",
            value=",".join(job.get("custom_skill_texts") or []),
            placeholder="VD: Kubernetes, CI/CD GitLab, Agile Scrum",
            key="custom_skills",
        )
        custom_skill_texts = [
            s.strip() for s in custom_skills_raw.split(",") if s.strip()
        ]
        if custom_skill_texts:
            st.info(f"🔖 Custom skills sẽ được gửi: {', '.join(custom_skill_texts)}")

        st.divider()

        # --- Salary ---
        st.subheader("💰 Mức lương (VNĐ)")
        col_sal1, col_sal2 = st.columns(2)
        with col_sal1:
            min_sal = st.number_input(
                "Lương tối thiểu",
                min_value=0,
                step=500_000,
                value=job.get("min_salary") or job.get("minSalary") or 0,
                format="%d",
                key="min_salary",
            )
        with col_sal2:
            max_sal = st.number_input(
                "Lương tối đa",
                min_value=0,
                step=500_000,
                value=job.get("max_salary") or job.get("maxSalary") or 0,
                format="%d",
                key="max_salary",
            )
        if min_sal > 0 or max_sal > 0:
            st.caption(f"Range: {min_sal:,} — {max_sal:,} VNĐ")
        else:
            st.caption("Lương: Thỏa thuận")

        st.divider()

        if st.button(
            "⚡ Lưu Cài đặt",
            type="primary",
            use_container_width=True,
            key="save_structured",
        ):
            with st.spinner("Đang lưu cài đặt..."):
                try:
                    result = nmaiex_client.update_job_structured(
                        job_id,
                        prov_id=sel_prov_id or None,
                        level_ids=sel_level_ids,
                        cat_ids=sel_cat_ids,
                        skill_ids=sel_skill_ids,
                        custom_skill_texts=(
                            custom_skill_texts if custom_skill_texts else None
                        ),
                        min_salary=min_sal if min_sal > 0 else None,
                        max_salary=max_sal if max_sal > 0 else None,
                        work_mode=sel_work_mode,
                    )
                    updated = result.get("updated_fields", [])
                    st.success(
                        f"✅ Cài đặt đã được cập nhật! Fields: {', '.join(updated) if updated else 'OK'}"
                    )
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu cài đặt: {e}")


def _render_score_badge(item: dict):
    """Dev Mode: hiển thị score_breakdown chi tiết bên dưới mỗi card kết quả ranking."""
    if not DEV_MODE:
        return
    bd = item.get("score_breakdown") or {}
    parts = []
    if "rrf_score" in bd:
        parts.append(f"RRF={bd['rrf_score']:.3f}")
    if "skill_overlap" in bd:
        parts.append(f"Skill={bd['skill_overlap']:.3f}")
    if "exact_overlap" in bd:
        parts.append(f"Exact={bd['exact_overlap']:.3f}")
    if "fuzzy_overlap" in bd:
        parts.append(f"Fuzzy={bd['fuzzy_overlap']:.3f}")
    if "seniority_penalty" in bd:
        parts.append(f"SenPenalty={bd['seniority_penalty']:.3f}")
    if "title_score" in bd:
        parts.append(f"Title={bd['title_score']:.3f}")
    if "salary_adjustment" in bd:
        parts.append(f"Salary={bd['salary_adjustment']:.3f}")
    if parts:
        st.caption(f"🔬 **[DEV]** {' | '.join(parts)}")


def _render_hr_ranking_tab(job_id: int):
    """Nội dung tab AI Ranking trong trang Danh sách Ứng viên (Phase 3)."""
    master = _ensure_master_data()
    st.markdown("### 🤖 AI Ranking — Xếp hạng ứng viên phù hợp nhất")
    st.info(
        "Hệ thống NMAIex sẽ xếp hạng tất cả ứng viên đã nộp đơn dựa trên "
        "vector similarity, kỹ năng và mức độ phù hợp cấp bậc."
    )

    # --- Filters ---
    with st.expander("⚙️ Bộ lọc nâng cao", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            provinces_data = master.get("provinces", [])
            region_map = {r["region_name"]: r for r in provinces_data}
            sel_region_r = st.selectbox(
                "Vùng", [""] + list(region_map.keys()), key=f"rank_region_{job_id}"
            )
            prov_list_r = region_map[sel_region_r]["provinces"] if sel_region_r else []
            prov_opts_r = {"(Tất cả)": None} | {
                p["province_name"]: p["province_id"] for p in prov_list_r
            }
            sel_prov_r = st.selectbox(
                "Tỉnh/Thành phố", list(prov_opts_r.keys()), key=f"rank_prov_{job_id}"
            )
            filter_prov = prov_opts_r[sel_prov_r]
        with col2:
            work_mode_opts = {
                "(Tất cả)": None,
                "ONSITE": "ONSITE",
                "HYBRID": "HYBRID",
                "REMOTE": "REMOTE",
            }
            sel_wm_r = st.selectbox(
                "Hình thức", list(work_mode_opts.keys()), key=f"rank_wm_{job_id}"
            )
            filter_wm = work_mode_opts[sel_wm_r]
        with col3:
            filter_limit = st.number_input(
                "Số kết quả",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                key=f"rank_limit_{job_id}",
            )

    # State variables for tab ranking
    state_key_results = f"hr_ranking_results_tab_{job_id}"
    state_key_warning = f"hr_ranking_warning_tab_{job_id}"
    state_key_error = f"hr_ranking_error_tab_{job_id}"
    state_key_returned = f"hr_ranking_returned_tab_{job_id}"
    state_key_total = f"hr_ranking_total_tab_{job_id}"

    if state_key_results not in st.session_state:
        st.session_state[state_key_results] = None
    if state_key_warning not in st.session_state:
        st.session_state[state_key_warning] = None
    if state_key_error not in st.session_state:
        st.session_state[state_key_error] = None
    if state_key_returned not in st.session_state:
        st.session_state[state_key_returned] = 0
    if state_key_total not in st.session_state:
        st.session_state[state_key_total] = 0

    if st.button(
        "🚀 Chạy AI Ranking",
        type="primary",
        use_container_width=True,
        key=f"run_rank_{job_id}",
    ):
        st.session_state[state_key_results] = None
        st.session_state[state_key_warning] = None
        st.session_state[state_key_error] = None

        params: dict = {"limit": filter_limit}
        if filter_prov:
            params["province_id"] = filter_prov
        if filter_wm:
            params["work_mode"] = filter_wm

        with st.spinner("⚙️ NMAIex đang tính toán ranking..."):
            try:
                result = nmaiex_client.get_candidates_ranking(job_id, params=params)
                # API trả về dict hoặc list
                if isinstance(result, dict):
                    candidates = result.get("results", [])
                    total = result.get("total_candidates", len(candidates))
                    returned = result.get("returned", len(candidates))
                else:
                    candidates = result
                    total = len(candidates)
                    returned = len(candidates)

                st.session_state[state_key_results] = candidates
                st.session_state[state_key_returned] = returned
                st.session_state[state_key_total] = total

            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.session_state[state_key_warning] = (
                        "⚠️ Job này chưa có dữ liệu NMAIex (chưa được seed structured data). "
                        "Hãy vào **Sửa Job** → **Cài đặt** để cấu hình trước khi ranking."
                    )
                else:
                    st.session_state[state_key_error] = (
                        f"❌ Lỗi khi gọi AI Ranking: {e}"
                    )

    # Render results
    if st.session_state[state_key_warning]:
        st.warning(st.session_state[state_key_warning])
    if st.session_state[state_key_error]:
        st.error(st.session_state[state_key_error])

    if st.session_state[state_key_results] is not None:
        candidates = st.session_state[state_key_results]
        returned = st.session_state[state_key_returned]
        total = st.session_state[state_key_total]

        st.success(f"✅ Tìm thấy **{returned}** ứng viên phù hợp (pool: {total})")

        if not candidates:
            st.info("Không có ứng viên phù hợp với bộ lọc hiện tại.")
        else:
            for i, c in enumerate(candidates, 1):
                score = c.get("match_score", 0)
                score_pct = f"{score * 100:.1f}%"
                name = c.get(
                    "candidate_name", f"Candidate #{c.get('candidate_id', '?')}"
                )
                cand_id = c.get("candidate_id")

                with st.container(border=True):
                    col_rank, col_info, col_score, col_action = st.columns([1, 5, 2, 1])
                    with col_rank:
                        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
                        st.markdown(f"## {medal}")
                    with col_info:
                        st.markdown(f"**{name}**")
                        if cand_id:
                            st.caption(f"Candidate ID: {cand_id}")
                    with col_score:
                        st.metric("Match Score", score_pct)
                    with col_action:
                        if st.button(
                            "Xem", key=f"rank_view_{cand_id}", use_container_width=True
                        ):
                            # Find the application for this candidate
                            app = db.get_application_by_job_and_candidate(
                                job_id, cand_id
                            )
                            if app:
                                st.session_state.selected_app_id = app["jobappid"]
                                st.session_state.conversation_id = None
                                go("hr_app_detail")
                _render_score_badge(c)


def page_hr_ai_ranking():
    """Phase 3 — Trang AI Ranking riêng (truy cập từ nút trong danh sách Job)."""
    if st.button("← Quay lại danh sách Job", key="back_from_ai_ranking"):
        go("hr_jobs")

    job_id = st.session_state.hr_ranking_job_id
    job_title = st.session_state.hr_ranking_job_title or f"Job #{job_id}"

    # Entry point: Phân tích bằng Agent (secondary action)
    if job_id and st.button(
        "🤖 Phân tích bằng Agent",
        key="ranking_to_job_agent",
        help="Mở Job Agent để phân tích ứng viên chi tiết hơn",
    ):
        _open_jobposting_agent(job_id, job_title)

    if not job_id:
        st.error("Không có job nào được chọn.")
        go("hr_jobs")
        return

    st.title(f"🤖 AI Ranking: {job_title}")
    st.divider()
    _render_hr_ranking_tab(job_id)


def page_hr_applications():

    if st.button("← Quay lại danh sách Job", key="back_jobs"):
        go("hr_jobs")

    job_id = st.session_state.selected_job_id
    st.title("📋 Danh sách ứng viên")

    # Entry point: Mở Job Agent cho job này
    if job_id and st.button(
        "🤖 Mở Job Agent",
        key="open_job_agent_from_apps",
        help="Phân tích toàn bộ ứng viên của job này bằng AI Agent",
    ):
        _open_jobposting_agent(job_id)

    master = _ensure_master_data()

    # --- Filters ---
    with st.expander("⚙️ Bộ lọc nâng cao", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            provinces_data = master.get("provinces", [])
            region_map = {r["region_name"]: r for r in provinces_data}
            sel_region_r = st.selectbox(
                "Vùng", [""] + list(region_map.keys()), key=f"rank_region_{job_id}"
            )
            prov_list_r = region_map[sel_region_r]["provinces"] if sel_region_r else []
            prov_opts_r = {"(Tất cả)": None} | {
                p["province_name"]: p["province_id"] for p in prov_list_r
            }
            sel_prov_r = st.selectbox(
                "Tỉnh/Thành phố", list(prov_opts_r.keys()), key=f"rank_prov_{job_id}"
            )
            filter_prov = prov_opts_r[sel_prov_r]
        with col2:
            work_mode_opts = {
                "(Tất cả)": None,
                "ONSITE": "ONSITE",
                "HYBRID": "HYBRID",
                "REMOTE": "REMOTE",
            }
            sel_wm_r = st.selectbox(
                "Hình thức", list(work_mode_opts.keys()), key=f"rank_wm_{job_id}"
            )
            filter_wm = work_mode_opts[sel_wm_r]
        with col3:
            filter_limit = st.number_input(
                "Số kết quả",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                key=f"rank_limit_{job_id}",
            )

    st.divider()
    st.markdown("### 🤖 AI Ranking — Xếp hạng ứng viên phù hợp nhất")
    st.info(
        "Hệ thống NMAIex sẽ xếp hạng tất cả ứng viên đã nộp đơn dựa trên "
        "vector similarity, kỹ năng và mức độ phù hợp cấp bậc."
    )

    # State variables for application list ranking
    state_key_results = f"hr_ranking_results_app_{job_id}"
    state_key_warning = f"hr_ranking_warning_app_{job_id}"
    state_key_error = f"hr_ranking_error_app_{job_id}"
    state_key_returned = f"hr_ranking_returned_app_{job_id}"
    state_key_total = f"hr_ranking_total_app_{job_id}"

    if state_key_results not in st.session_state:
        st.session_state[state_key_results] = None
    if state_key_warning not in st.session_state:
        st.session_state[state_key_warning] = None
    if state_key_error not in st.session_state:
        st.session_state[state_key_error] = None
    if state_key_returned not in st.session_state:
        st.session_state[state_key_returned] = 0
    if state_key_total not in st.session_state:
        st.session_state[state_key_total] = 0

    if st.button(
        "🚀 Chạy AI Ranking",
        type="primary",
        use_container_width=True,
        key=f"run_rank_{job_id}",
    ):
        st.session_state[state_key_results] = None
        st.session_state[state_key_warning] = None
        st.session_state[state_key_error] = None

        params: dict = {"limit": filter_limit}
        if filter_prov:
            params["province_id"] = filter_prov
        if filter_wm:
            params["work_mode"] = filter_wm

        with st.spinner("⚙️ NMAIex đang tính toán ranking..."):
            try:
                result = nmaiex_client.get_candidates_ranking(job_id, params=params)
                # API trả về dict hoặc list
                if isinstance(result, dict):
                    candidates = result.get("results", [])
                    total = result.get("total_candidates", len(candidates))
                    returned = result.get("returned", len(candidates))
                else:
                    candidates = result
                    total = len(candidates)
                    returned = len(candidates)

                st.session_state[state_key_results] = candidates
                st.session_state[state_key_returned] = returned
                st.session_state[state_key_total] = total

            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.session_state[state_key_warning] = (
                        "⚠️ Job này chưa có dữ liệu NMAIex (chưa được seed structured data). "
                        "Hãy vào **Sửa Job** → **Cài đặt** để cấu hình trước khi ranking."
                    )
                else:
                    st.session_state[state_key_error] = (
                        f"❌ Lỗi khi gọi AI Ranking: {e}"
                    )

    # Render results
    if st.session_state[state_key_warning]:
        st.warning(st.session_state[state_key_warning])
    if st.session_state[state_key_error]:
        st.error(st.session_state[state_key_error])

    if st.session_state[state_key_results] is not None:
        candidates = st.session_state[state_key_results]
        returned = st.session_state[state_key_returned]
        total = st.session_state[state_key_total]

        st.success(f"✅ Tìm thấy **{returned}** ứng viên phù hợp (pool: {total})")

        if not candidates:
            st.info("Không có ứng viên phù hợp với bộ lọc hiện tại.")
        else:
            for i, c in enumerate(candidates, 1):
                score = c.get("match_score", 0)
                score_pct = f"{score * 100:.1f}%"
                name = c.get(
                    "candidate_name", f"Candidate #{c.get('candidate_id', '?')}"
                )
                cand_id = c.get("candidate_id")

                with st.container(border=True):
                    col_rank, col_info, col_score, col_action = st.columns([1, 5, 2, 1])
                    with col_rank:
                        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
                        st.markdown(f"## {medal}")
                    with col_info:
                        st.markdown(f"**{name}**")
                        if cand_id:
                            st.caption(f"Candidate ID: {cand_id}")
                    with col_score:
                        st.metric("Match Score", score_pct)
                    with col_action:
                        if st.button(
                            "Xem",
                            key=f"hr_rank_view_{cand_id}_{job_id}",
                            use_container_width=True,
                        ):
                            # Find the application for this candidate
                            app = db.get_application_by_job_and_candidate(
                                job_id, cand_id
                            )
                            if app:
                                st.session_state.selected_app_id = app["jobappid"]
                                st.session_state.conversation_id = None
                                go("hr_app_detail")
                            else:
                                st.error(
                                    "❌ Không tìm thấy application cho ứng viên này!"
                                )
                _render_score_badge(c)

    st.divider()
    apps = db.get_applications_for_job(job_id)
    if not apps:
        st.info("Chưa có ứng viên nào cho job này.")
    else:
        st.markdown("### 💼 Danh sách ứng viên")
        for a in apps:
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(
                        f"**{a['fname']} {a['lname']}** ({a['email']}) "
                        f"— Trạng thái: `{a['stat']}` "
                        f"— Nộp: {a['appliedat'].strftime('%Y-%m-%d') if a['appliedat'] else 'N/A'}"
                    )
                with col2:
                    if st.button("Đánh giá CV", key=f"app_{a['jobappid']}"):
                        st.session_state.selected_app_id = a["jobappid"]
                        st.session_state.conversation_id = None
                        go("hr_app_detail")


def page_hr_app_detail():
    if st.button("← Quay lại danh sách Ứng viên", key="back_apps"):
        go("hr_applications")

    app_id = st.session_state.selected_app_id
    detail = db.get_application_detail(app_id)

    if not detail:
        st.error("Không tìm thấy dữ liệu ứng viên!")
        return

    st.title(f"🧑‍💼 Hồ sơ: {detail['fname']} {detail['lname']}")

    # --- Kiểm tra ingestion status ---
    index_job = db.get_ingestion_job_for_app(app_id)
    ingestion_ok = index_job and index_job["stat"] == "SUCCESS"
    ingestion_processing = index_job and index_job["stat"] in ("PENDING", "PROCESSING")
    ingestion_failed = index_job and index_job["stat"] == "FAILED"

    col1, col2 = st.columns([1, 1])

    # === Cột trái: Thông tin + CV ===
    with col1:
        st.subheader("Thông tin Ứng Viên")
        st.write(f"👤 **Họ tên:** {detail['fname']} {detail['lname']}")
        st.write(f"📧 **Email:** {detail['email']}")
        st.write(f"📌 **Trạng thái ATS:** `{detail['stat']}`")

        # Ingestion status badge
        if not index_job:
            st.warning("⚠️ CV chưa được xử lý bởi FANG.")
        elif ingestion_processing:
            st.info("⏳ CV đang được FANG xử lý...")
        elif ingestion_ok:
            st.success("✅ CV đã xử lý thành công — AI sẵn sàng phân tích.")
        elif ingestion_failed:
            err = index_job.get("errormsg", "Không rõ lỗi")
            st.error(f"❌ Xử lý thất bại: {err}")

        # CV viewer
        if detail.get("cvsnapurl"):
            st.write(f"📄 [Link CV (Cloudinary)]({detail['cvsnapurl']})")
            pdf_url = detail["cvsnapurl"]
            viewer_url = f"https://docs.google.com/viewer?url={pdf_url}&embedded=true"
            st.iframe(src=viewer_url, height=550)

    # === Cột phải: FANG HR Co-pilot ===
    with col2:
        st.subheader("🤖 FANG HR Co-pilot")

        if not ingestion_ok:
            st.warning(
                "Chat RAG chỉ khả dụng khi CV đã được FANG xử lý thành công. "
                "Vui lòng đợi hoặc yêu cầu ứng viên upload lại CV."
            )
            return

        # Chọn model mode
        mode_label = st.selectbox(
            "Chọn AI Model:",
            list(MODEL_MODES.keys()),
            key="hr_model_select",
        )
        model_mode = MODEL_MODES[mode_label]

        hr_id = st.session_state.hr_user["userid"]

        # --- Load/chọn conversation ---
        try:
            conversations = fang_client.list_conversations(hr_id, app_id)
        except Exception:
            conversations = []

        conv_options = {"[Tạo hội thoại mới]": None}
        for c in conversations:
            label = f"Hội thoại {c['conversationId'][:8]}... ({c['messageCount']} tin)"
            conv_options[label] = c["conversationId"]

        selected_label = st.selectbox(
            "Chọn hoặc tạo hội thoại:",
            list(conv_options.keys()),
            key="hr_conv_select",
        )
        chosen_conv_id = conv_options[selected_label]

        # Nếu chọn conversation cũ, load history
        if chosen_conv_id and chosen_conv_id != st.session_state.conversation_id:
            st.session_state.conversation_id = chosen_conv_id

        # Hiển thị context warning nếu có (lưu ở session)
        ctx_warning_key = f"ctx_warning_{app_id}"
        if ctx_warning_key in st.session_state and st.session_state[ctx_warning_key]:
            warning = st.session_state[ctx_warning_key]
            with st.warning(
                f"⚠️ Context đang sử dụng ~{warning.get('usedPercent', 0)}% ngân sách token. "
                "Bạn có muốn:"
            ):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📝 Tóm tắt & tiếp tục", key=f"summarize_{app_id}"):
                        try:
                            fang_client.summarize_conversation(
                                st.session_state.conversation_id
                            )
                            st.session_state[ctx_warning_key] = None
                            st.success("✅ Đã tóm tắt hội thoại!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi tóm tắt: {e}")
                with c2:
                    if st.button("🔀 Sang hội thoại mới", key=f"branch_{app_id}"):
                        try:
                            result = fang_client.branch_new_conversation(
                                st.session_state.conversation_id
                            )
                            st.session_state.conversation_id = result[
                                "newConversationId"
                            ]
                            st.session_state[ctx_warning_key] = None
                            st.success("✅ Đã tạo hội thoại mới với tóm tắt ngữ cảnh!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi tạo hội thoại mới: {e}")

        # --- Hiển thị lịch sử ---
        chat_box = st.container(height=450)
        if st.session_state.conversation_id:
            try:
                messages = fang_client.get_conversation_messages(
                    st.session_state.conversation_id
                )
                with chat_box:
                    for m in messages:
                        with st.chat_message(m["role"]):
                            st.markdown(m["content"])
                            if m["role"] == "assistant" and m.get("model"):
                                st.caption(f"🔧 Model: `{m['model']}`")
            except Exception as e:
                with chat_box:
                    st.warning(f"Không tải được lịch sử: {e}")
        else:
            with chat_box:
                st.info("Hội thoại mới — hãy đặt câu hỏi đầu tiên.")

        # --- Chat input ---
        if prompt := st.chat_input(
            "Hỏi về ứng viên này...", key=f"chat_input_{app_id}"
        ):
            with chat_box:
                with st.chat_message("user"):
                    st.markdown(prompt)

            with st.spinner("⚙️ FANG đang xử lý RAG pipeline..."):
                try:
                    result = fang_client.chat_query(
                        job_app_id=app_id,
                        hr_id=hr_id,
                        prompt=prompt,
                        model_mode=model_mode,
                        conversation_id=st.session_state.conversation_id,
                    )
                    st.session_state.conversation_id = str(result["conversationId"])

                    with chat_box:
                        with st.chat_message("assistant"):
                            st.markdown(result["response"])
                            st.caption(
                                f"🔧 Model: `{result.get('model', 'N/A')}` "
                                f"| ⏱ {result.get('latencyMs', 0)}ms "
                                f"| 📚 top-{result.get('topK', 0)} chunks"
                            )

                    # Lưu context warning để hiển thị lần sau
                    st.session_state[ctx_warning_key] = result.get("contextWarning")

                except Exception as e:
                    st.error(f"❌ Lỗi khi gọi FANG API: {e}")

            st.rerun()


# ===========================================================================
# CANDIDATE PAGES
# ===========================================================================


def page_login_candidate():
    st.title("🔐 Candidate Login")
    with st.form("login_cand_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Đăng nhập", use_container_width=True)

    if submit:
        user = db.get_candidate_user(username, password)
        if user:
            st.session_state.candidate_user = user
            go("candidate_jobs")
        else:
            st.error("Sai tài khoản hoặc mật khẩu!")

    if st.button("← Quay lại trang chủ", key="back_home_cand"):
        go("home")


def page_candidate_jobs():
    user = st.session_state.candidate_user
    st.title(f"👋 Xin chào, {user['fname']} {user['lname']}")
    st.subheader("📢 Công việc đang tuyển dụng")
    _ensure_master_data()

    st.divider()

    # Show/hide toggle for applied jobs (moved before AI recommendations)
    show_applied = st.checkbox(
        "✓ Hiển thị công việc đã ứng tuyển", value=True, key="show_applied_jobs"
    )

    st.divider()
    # Phase 3 — Section gợi ý việc làm AI (lên trước)
    _render_candidate_ai_jobs(user["userid"], show_applied)

    st.divider()

    # Get ALL jobs, then filter based on toggle
    all_jobs = db.get_all_job_postings()
    if show_applied:
        jobs = all_jobs
    else:
        jobs = [
            j for j in all_jobs if not db.has_applied(user["userid"], j["jobpostid"])
        ]

    if not jobs:
        if show_applied:
            st.info("Hiện tại chưa có vị trí tuyển dụng nào.")
        else:
            st.info("Bạn đã ứng tuyển hết tất cả các vị trí, hoặc chưa có vị trí mới.")
        return

    for j in jobs:
        already_applied = db.has_applied(user["userid"], j["jobpostid"])
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                title_badge = f"**{j['title']}**" + (" ✓" if already_applied else "")
                st.markdown(f"{title_badge} — 🏢 {j.get('compname', 'N/A')}")
                if j.get("description"):
                    st.caption(
                        j["description"][:200] + "..."
                        if len(j.get("description", "")) > 200
                        else j.get("description", "")
                    )
                st.caption(f"Hạn nộp: {j['expat']}")
            with col2:
                col2a, col2b = st.columns(2)
                with col2a:
                    if st.button(
                        "Xem", key=f"view_{j['jobpostid']}", use_container_width=True
                    ):
                        st.session_state.selected_job_id = j["jobpostid"]
                        go("candidate_job_detail")
                with col2b:
                    if not already_applied:
                        if st.button(
                            "Nộp CV",
                            key=f"apply_{j['jobpostid']}",
                            use_container_width=True,
                        ):
                            st.session_state.apply_job_id = j["jobpostid"]
                            st.session_state.apply_job_title = j["title"]
                            go("candidate_apply")
                    else:
                        st.caption("✓ Đã nộp")

    st.divider()
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("📄 Hồ sơ của tôi", use_container_width=True, key="goto_profile"):
            go("candidate_profile")
    with col_nav2:
        if st.button("🚪 Đăng xuất", use_container_width=True, key="logout_cand"):
            st.session_state.candidate_user = None
            go("home")


def _render_candidate_ai_jobs(candidate_id: int, show_applied: bool = True):
    """Phase 3 — Section gợi ý công việc phù hợp cho ứng viên (C→J ranking)."""
    master = _ensure_master_data()
    st.markdown("### 🎯 Việc làm phù hợp với bạn")
    st.caption("NMAIex phân tích hồ sơ của bạn và gợi ý các vị trí phù hợp nhất.")

    # Filters
    with st.expander("⚙️ Lọc gợi ý", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            provinces_data = master.get("provinces", [])
            region_map = {r["region_name"]: r for r in provinces_data}
            sel_region_c = st.selectbox(
                "Vùng", [""] + list(region_map.keys()), key="cj_region"
            )
            prov_list_c = region_map[sel_region_c]["provinces"] if sel_region_c else []
            prov_opts_c = {"(Tất cả)": None} | {
                p["province_name"]: p["province_id"] for p in prov_list_c
            }
            sel_prov_c = st.selectbox(
                "Tỉnh/Thành phố", list(prov_opts_c.keys()), key="cj_prov"
            )
            filter_prov_c = prov_opts_c[sel_prov_c]
        with col2:
            wm_opts_c = {
                "(Tất cả)": None,
                "ONSITE": "ONSITE",
                "HYBRID": "HYBRID",
                "REMOTE": "REMOTE",
            }
            sel_wm_c = st.selectbox("Hình thức", list(wm_opts_c.keys()), key="cj_wm")
            filter_wm_c = wm_opts_c[sel_wm_c]
        with col3:
            filter_limit_c = st.number_input(
                "Số gợi ý", min_value=5, max_value=50, value=10, step=5, key="cj_limit"
            )

    # Initialize session state for recommendation list
    if "cj_recommendations" not in st.session_state:
        st.session_state.cj_recommendations = None
    if "cj_recommendations_warning" not in st.session_state:
        st.session_state.cj_recommendations_warning = None
    if "cj_recommendations_error" not in st.session_state:
        st.session_state.cj_recommendations_error = None

    if st.button(
        "✨ Xem gợi ý AI", type="primary", use_container_width=True, key="run_cj_rank"
    ):
        st.session_state.cj_recommendations = None
        st.session_state.cj_recommendations_warning = None
        st.session_state.cj_recommendations_error = None
        params_c: dict = {"limit": filter_limit_c}
        if filter_prov_c:
            params_c["province_id"] = filter_prov_c
        if filter_wm_c:
            params_c["work_mode"] = filter_wm_c

        with st.spinner("⚙️ NMAIex đang tìm việc làm phù hợp..."):
            try:
                result_c = nmaiex_client.get_jobs_ranking(candidate_id, params=params_c)
                if isinstance(result_c, dict):
                    job_list = result_c.get("results", [])
                else:
                    job_list = result_c
                st.session_state.cj_recommendations = job_list
            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.session_state.cj_recommendations_warning = (
                        "⚠️ Hồ sơ của bạn chưa được NMAIex xử lý. "
                        "Hãy upload CV và đợi hệ thống phân tích xong."
                    )
                else:
                    st.session_state.cj_recommendations_error = f"❌ Lỗi gợi ý AI: {e}"

    # Render results
    if st.session_state.cj_recommendations_warning:
        st.warning(st.session_state.cj_recommendations_warning)
    if st.session_state.cj_recommendations_error:
        st.error(st.session_state.cj_recommendations_error)

    if st.session_state.cj_recommendations is not None:
        job_list = st.session_state.cj_recommendations
        if not job_list:
            st.info("Chưa tìm thấy việc làm phù hợp. Hãy cập nhật CV và hồ sơ của bạn!")
        else:
            st.success(f"✅ Tìm thấy **{len(job_list)}** việc làm phù hợp với bạn:")
            for idx, j in enumerate(job_list):
                score = j.get("match_score", 0)
                score_pct = f"{score * 100:.1f}%"
                title = j.get("job_title") or j.get("title", "?")
                company = j.get("company_name") or j.get("compname", "")
                job_id_rec = j.get("job_id") or j.get("jobpostid")
                already_applied = (
                    db.has_applied(candidate_id, job_id_rec) if job_id_rec else False
                )

                # Skip if job already applied and show_applied is False
                if already_applied and not show_applied:
                    continue

                with st.container(border=True):
                    c1, c2, c3 = st.columns([5, 1, 2])
                    with c1:
                        st.markdown(
                            f"**{title}**" + (f" — 🏢 {company}" if company else "")
                        )
                        if j.get("work_loc"):
                            st.caption(f"📍 {j['work_loc']}")
                    with c2:
                        st.metric("Match Score", score_pct)
                    with c3:
                        if already_applied:
                            st.caption("✓ Đã nộp")
                        else:
                            col3a, col3b = st.columns(2)
                            with col3a:
                                if st.button(
                                    "Xem",
                                    key=f"rec_view_{idx}_{job_id_rec}",
                                    use_container_width=True,
                                ):
                                    st.session_state.selected_job_id = job_id_rec
                                    go("candidate_job_detail")
                            with col3b:
                                if st.button(
                                    "Nộp CV",
                                    key=f"rec_apply_{idx}_{job_id_rec}",
                                    use_container_width=True,
                                ):
                                    st.session_state.apply_job_id = job_id_rec
                                    st.session_state.apply_job_title = title
                                    go("candidate_apply")
                _render_score_badge(j)


def page_candidate_job_detail():
    """Trang xem chi tiết job của ứng viên."""
    user = st.session_state.candidate_user

    if st.button("← Quay lại danh sách Job", key="back_cand_jobs_from_detail"):
        go("candidate_jobs")

    job_id = st.session_state.selected_job_id
    if not job_id:
        st.error("Không có job nào được chọn.")
        go("candidate_jobs")
        return

    # Load job detail từ DB
    job = db.get_job_posting_detail(job_id)
    if not job:
        st.error("Không tìm thấy job.")
        go("candidate_jobs")
        return

    st.title(f"📋 {job['title']}")
    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Thông tin Job")
        st.write(f"**Công ty:** {job.get('compname', 'N/A')}")
        st.write(f"**Hết hạn nộp:** {job['expat']}")
        if job.get("description"):
            st.markdown("**Mô tả công việc:**")
            st.markdown(job.get("description", ""))
        if job.get("minSalary") or job.get("maxSalary"):
            min_sal = job.get("minSalary", 0)
            max_sal = job.get("maxSalary", 0)
            st.markdown(f"**Mức lương:** {min_sal:,.0f} — {max_sal:,.0f} VNĐ")

    with col2:
        st.markdown("### Hành động")
        already_applied = db.has_applied(user["userid"], job_id)
        if not already_applied:
            if st.button(
                "🚀 Nộp CV",
                type="primary",
                use_container_width=True,
                key=f"apply_now_{job_id}",
            ):
                st.session_state.apply_job_id = job_id
                st.session_state.apply_job_title = job["title"]
                go("candidate_apply")
        else:
            st.success("✓ Bạn đã ứng tuyển\ncông việc này", icon="✅")


def page_candidate_profile():
    """Phase 1.5 — Trang hồ sơ của ứng viên: xem/sửa bio + upload CV mới."""
    user = st.session_state.candidate_user

    if st.button("← Quay lại danh sách Job", key="back_cand_jobs_from_profile"):
        go("candidate_jobs")

    st.title(f"📄 Hồ sơ của {user['fname']} {user['lname']}")
    st.divider()

    cand_id = user.get("userid")  # userid == candidateId (joined từ bảng user)
    if not cand_id:
        st.error("❌ Không xác định được candidate ID.")
        return

    # Lấy thông tin hiện tại
    profile = db.get_candidate_bio_and_cv(cand_id)
    current_bio = (profile or {}).get("bio") or ""
    current_cv_url = (profile or {}).get("cvurl") or ""

    col1, col2 = st.columns([1, 1])

    # === Cột trái: Bio ===
    with col1:
        st.subheader("📝 Giới thiệu bản thân (Bio)")
        new_bio = st.text_area(
            "Mô tả bản thân",
            value=current_bio,
            height=200,
            placeholder="VD: Fresher Backend Developer với 1 năm kinh nghiệm Java/Spring Boot...",
            key="cand_bio",
        )
        if st.button("💾 Lưu Bio", use_container_width=True, key="save_bio"):
            with st.spinner("Saving..."):
                try:
                    nmaiex_client.update_candidate(cand_id, bio=new_bio.strip())
                    st.success("✅ Bio đã được cập nhật!")
                except Exception as e:
                    err_str = str(e)
                    if "404" in err_str or "Not Found" in err_str:
                        st.warning(
                            "⚠️ Candidate chưa có bản ghi trong FANG NMAIex DB. "
                            "Bio sẽ được lưu sau khi dữ liệu được khởi tạo."
                        )
                    else:
                        st.error(f"❌ Lỗi cập nhật bio: {e}")

    # === Cột phải: CV ===
    with col2:
        st.subheader("📄 CV của bạn")
        if current_cv_url:
            st.success(f"✅ CV hiện tại: [Xem CV]({current_cv_url})")
            pdf_viewer_url = (
                f"https://docs.google.com/viewer?url={current_cv_url}&embedded=true"
            )
            st.iframe(src=pdf_viewer_url, height=350)
        else:
            st.info("⚠️ Bạn chưa có CV. Upload ngay để tiếp cận công việc phù hợp!")

        st.divider()
        st.write("⬆️ **Upload CV mới** (PDF, sẽ thay thế CV hiện tại):")
        uploaded_cv = st.file_uploader(
            "Chọn file PDF", type=["pdf"], key="profile_cv_upload"
        )

        if uploaded_cv and st.button(
            "⬆️ Cập nhật CV",
            type="primary",
            use_container_width=True,
            key="upload_profile_cv",
        ):
            with st.spinner("Đang upload lên Cloudinary..."):
                try:
                    new_cv_url = upload_cv_pdf(uploaded_cv.getvalue(), uploaded_cv.name)
                    # Lưu vào DB local
                    db.update_candidate_cv_url(cand_id, new_cv_url)
                    # Đồng bộ với FANG qua NMAIex API
                    nmaiex_client.update_candidate(cand_id, cv_url=new_cv_url)
                    st.success(f"✅ CV đã được cập nhật! [Xem CV mới]({new_cv_url})")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi upload CV: {e}")


def page_candidate_apply():
    user = st.session_state.candidate_user
    job_id = st.session_state.apply_job_id
    job_title = st.session_state.apply_job_title

    if st.button("← Quay lại danh sách Job", key="back_cand_jobs"):
        go("candidate_jobs")

    st.title(f"📝 Nộp CV cho: {job_title}")
    st.divider()

    # Kiểm tra CV cũ
    existing_cv_url = db.get_candidate_existing_cv(user["userid"])

    cv_to_use: str | None = None
    upload_new = True

    if existing_cv_url:
        st.info(f"📄 Bạn đã có CV trước đó: [Xem CV hiện tại]({existing_cv_url})")
        choice = st.radio(
            "Bạn muốn dùng CV nào?",
            ["✅ Giữ CV hiện tại", "⬆️ Upload CV mới"],
            key="cv_choice",
        )
        if "Giữ" in choice:
            cv_to_use = existing_cv_url
            upload_new = False

    if upload_new:
        uploaded_file = st.file_uploader(
            "Upload CV (PDF)", type=["pdf"], key="cv_upload"
        )

    st.divider()

    if st.button("🚀 Xác nhận nộp CV", use_container_width=True, key="confirm_apply"):
        # Validate
        if upload_new and not ("uploaded_file" in dir() and uploaded_file is not None):
            st.error("Vui lòng upload file CV PDF.")
            return

        with st.spinner("Đang xử lý..."):
            # 1. Upload nếu cần
            if upload_new and uploaded_file:
                try:
                    cv_to_use = upload_cv_pdf(
                        uploaded_file.getvalue(), uploaded_file.name
                    )
                    st.success(f"✅ Upload thành công: [Xem CV]({cv_to_use})")
                except Exception as e:
                    st.error(f"❌ Lỗi upload Cloudinary: {e}")
                    return

            # 2. Tạo JOBAPPLICATION
            try:
                job_app_id = db.create_application(user["userid"], job_id, cv_to_use)
            except Exception as e:
                st.error(f"❌ Lỗi tạo đơn ứng tuyển: {e}")
                return

            # 3. Trigger FANG ingestion
            try:
                ingest_result = fang_client.trigger_ingestion(job_app_id, cv_to_use)
                fang_job_id = ingest_result.get("indexJobId")
                st.info(f"⏳ FANG đang xử lý CV... (Job ID: `{fang_job_id}`)")
            except Exception as e:
                st.warning(
                    f"⚠️ Đơn đã nộp nhưng không thể kích hoạt FANG ingestion: {e}. "
                    "HR sẽ trigger lại sau."
                )
                go("candidate_jobs")
                return

            # 4. Polling
            st.write("🔄 Chờ FANG xử lý CV...")
            progress = st.progress(0, text="Đang xử lý...")
            try:
                import time

                for i in range(1, 31):  # max 60 giây (30 * 2s)
                    time.sleep(2)
                    status = fang_client.get_ingestion_status(fang_job_id)
                    pct = min(i * 3, 99)
                    progress.progress(
                        pct, text=f"Đang xử lý... ({status.get('status')})"
                    )
                    if status.get("status") == "SUCCESS":
                        progress.progress(100, text="Hoàn thành!")
                        st.success(
                            "🎉 CV của bạn đã được xử lý thành công! "
                            "HR sẽ liên hệ với bạn sớm."
                        )
                        go("candidate_jobs")
                        return
                    elif status.get("status") == "FAILED":
                        err = status.get("errorMsg", "Không rõ lỗi")
                        st.error(f"❌ Xử lý CV thất bại: {err}. Vui lòng thử lại sau.")
                        return
                # Timeout
                st.warning(
                    "⏰ Đơn đã được nộp. FANG đang xử lý CV ở nền "
                    "— bạn sẽ được thông báo khi hoàn tất."
                )
                go("candidate_jobs")
            except Exception as e:
                st.error(f"Lỗi polling: {e}")


# ===========================================================================
# C3: JOBPOSTING AGENT
# ===========================================================================

# Tool display name mapping (tiếng Việt)
_TOOL_DISPLAY_NAMES: dict[str, str] = {
    "get_job_posting_context": "Xem thông tin tin tuyển dụng",
    "get_job_candidate_ranking": "Xếp hạng ứng viên",
    "search_job_applications_text": "Tìm kiếm ứng viên",
    "get_job_application_summary": "Tóm tắt ứng viên",
    "get_job_application_full_cv": "Xem CV đã mask PII",
    "get_candidate_ats_history": "Lịch sử tuyển dụng",
    "count_job_applications": "Đếm ứng viên",
}

# HTTP status → Vietnamese message
_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Yêu cầu không hợp lệ. Vui lòng kiểm tra nội dung nhập.",
    403: "Bạn không có quyền truy cập tin tuyển dụng hoặc hội thoại này.",
    404: "Không tìm thấy tin tuyển dụng hoặc hội thoại.",
    410: "Hội thoại này đã được lưu trữ. Hãy tạo hội thoại mới.",
    429: "Hệ thống AI đang quá tải. Vui lòng thử lại sau.",
    500: "Lỗi hệ thống khi xử lý Job Agent. Vui lòng thử lại.",
    503: "Dịch vụ AI tạm thời không khả dụng. Vui lòng kiểm tra FANG backend.",
}


def _jobposting_agent_error_message(exc: Exception) -> str:
    """Map HTTPError status code sang Vietnamese UI message."""
    import requests as _req

    if isinstance(exc, _req.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        return _HTTP_ERROR_MESSAGES.get(code, f"Lỗi không xác định (HTTP {code}).")
    err_str = str(exc).lower()
    if "timeout" in err_str or "connection" in err_str or "connect" in err_str:
        return "Không kết nối được FANG hoặc yêu cầu quá thời gian chờ."
    return f"Lỗi không xác định: {exc}"


def _open_jobposting_agent(job_id: int, job_title: str | None = None) -> None:
    """Set session state và route sang hr_job_agent.

    Nếu mở với jobPostId khác thì reset conversation/messages/working_set/sources.
    """
    if st.session_state.jobposting_agent_job_id != job_id:
        st.session_state.jobposting_agent_conversation_id = None
        st.session_state.jobposting_agent_conversations = []
        st.session_state.jobposting_agent_messages = []
        st.session_state.jobposting_agent_working_set = None
        st.session_state.jobposting_agent_source_job_app_ids = []
        st.session_state.jobposting_agent_last_tool_calls = []
        st.session_state.jobposting_agent_warnings = []
        st.session_state.jobposting_agent_error = None
        st.session_state.jobposting_agent_rename_title = ""
    st.session_state.jobposting_agent_job_id = job_id
    if job_title:
        st.session_state.jobposting_agent_job_title = job_title
    go("hr_job_agent")


def _render_jobposting_agent_tool_message(tool_call: dict, step_idx: int) -> None:
    """Render 1 tool_call/tool_result dưới dạng collapsed expander."""
    import json as _json

    tool_name = tool_call.get("toolName") or tool_call.get("name", "unknown")
    display_name = _TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
    status = tool_call.get("status", "")
    latency = tool_call.get("latencyMs")
    result_summary = tool_call.get("resultSummary") or tool_call.get(
        "result_summary", ""
    )
    error_msg = tool_call.get("errorMsg") or tool_call.get("error_msg", "")

    label = f"Bước {step_idx}: {display_name}"
    if status:
        label += f" — {status}"

    with st.expander(label, expanded=False):
        if latency is not None:
            st.caption(f"⏱ {latency}ms")
        # Args
        args = tool_call.get("args") or tool_call.get("arguments")
        if args:
            try:
                if isinstance(args, str):
                    args = _json.loads(args)
                st.json(args)
            except Exception:
                st.code(str(args))

        # Result (nested expander, scrollable container)
        with st.expander("📤 Kết quả lệnh", expanded=False):
            with st.container(height=300):
                # Prefer sanitized backend preview. History rows may store it under
                # content.preview because tool_result messages persist JSON metadata.
                content = (
                    tool_call.get("resultPreview")
                    or tool_call.get("resultData")
                    or tool_call.get("content")
                    or result_summary
                )
                if content:
                    try:
                        if isinstance(content, str):
                            content = _json.loads(content)
                        if isinstance(content, dict) and content.get("preview"):
                            content = content["preview"]
                        st.json(content)
                    except Exception:
                        st.code(str(content))
                else:
                    st.caption("Không có kết quả chi tiết.")

        if error_msg:
            st.error(f"❌ {error_msg}")


def _render_jobposting_agent_messages(messages: list[dict]) -> None:
    """Render danh sách messages hoặc Welcome screen nếu chưa có tin nhắn."""
    is_loading = st.session_state.jobposting_agent_is_loading
    if not messages:
        # Render FANG Welcome Empty State
        st.markdown("### Xin chào, mình là FANG 👋")
        st.markdown(
            "Mình là trợ lý AI dành cho HR, được tích hợp để có thể hỗ trợ bạn sàng lọc, tìm kiếm và so sánh để tìm ra những ứng viên phù hợp nhất cho công việc này."
        )
        st.markdown("Bạn có thể thử hỏi mình một câu hỏi và mình sẽ hỗ trợ nhé:")

        # 3 suggested prompts
        prompts = [
            "Xếp hạng 10 ứng viên phù hợp nhất.",
            "Những ứng viên nào có chứng chỉ tiếng Anh TOEIC từ 600 trở lên?",
            "So sánh 3 ứng viên nổi bật nhất.",
        ]

        for idx, p in enumerate(prompts):
            if st.button(
                p,
                key=f"welcome_prompt_{idx}",
                disabled=is_loading,
                use_container_width=True,
            ):
                st.session_state.jobposting_agent_pending_prompt = p
                st.rerun()
        return

    tool_step = 0
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")

        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)

        elif role == "assistant":
            with st.chat_message("assistant"):
                st.markdown(content)
                model = m.get("model")
                latency = m.get("latencyMs")
                if model or latency:
                    parts = []
                    if model:
                        parts.append(f"🔧 `{model}`")
                    if latency:
                        parts.append(f"⏱ {latency}ms")
                    st.caption(" | ".join(parts))

        elif role in ("tool_call", "tool_result"):
            tool_step += 1
            _render_jobposting_agent_tool_message(m, tool_step)


def _render_jobposting_agent_working_set(
    working_set: dict | None,
    source_job_app_ids: list[int],
) -> None:
    """Render working set panel + source chips sau assistant response."""
    MAX_CHIPS = 25

    def _make_chip_label(jaid: int, summary_map: dict) -> str:
        s = summary_map.get(jaid)
        if s:
            name = f"{s.get('fname', '')} {s.get('lname', '')}".strip()
            stat = s.get("stat", "")
            return f"{name} [{stat}]" if stat else (name or f"#{jaid}")
        return f"#{jaid}"

    # Determine if working set and source are identical
    working_set_ids = working_set.get("jobAppIds") or [] if working_set else []
    show_source = bool(source_job_app_ids)
    if show_source and set(source_job_app_ids) == set(working_set_ids):
        show_source = False

    if working_set:
        label = working_set.get("label") or "Tập ứng viên hiện tại"
        job_app_ids: list[int] = working_set.get("jobAppIds") or []
        filters: dict = working_set.get("filters") or {}

        # Lookup names từ DB (defensive)
        visible_ids = job_app_ids[:MAX_CHIPS]
        summary_map: dict = {}
        if visible_ids:
            try:
                rows = db.get_application_summaries_by_ids(visible_ids)
                summary_map = {r["jobappid"]: r for r in rows}
            except Exception:
                pass  # fallback to raw IDs

        ws_expander_label = f"📋 {label} — {len(job_app_ids)} ứng viên"
        with st.expander(ws_expander_label, expanded=False):
            # Active filter chips
            if filters:
                filter_parts = [f"`{k}={v}`" for k, v in filters.items()]
                st.markdown(" ".join(filter_parts))

            # JobApp chips
            overflow = len(job_app_ids) - MAX_CHIPS
            if visible_ids:
                n_cols = min(len(visible_ids), 4)
                chip_cols = st.columns(n_cols)
                for idx, jaid in enumerate(visible_ids):
                    with chip_cols[idx % n_cols]:
                        chip_label = _make_chip_label(jaid, summary_map)
                        if st.button(
                            chip_label,
                            key=f"ws_chip_{jaid}",
                            use_container_width=True,
                            help=f"Mở hồ sơ jobAppId={jaid}",
                        ):
                            st.session_state.selected_app_id = jaid
                            st.session_state.conversation_id = None
                            go("hr_app_detail")
            if overflow > 0:
                st.caption(f"+{overflow} ứng viên khác")

    # Source chips — riêng biệt và chỉ hiển thị khi có sự khác biệt
    if show_source:
        src_visible = source_job_app_ids[:MAX_CHIPS]
        src_summary_map: dict = {}
        try:
            rows = db.get_application_summaries_by_ids(src_visible)
            src_summary_map = {r["jobappid"]: r for r in rows}
        except Exception:
            pass

        with st.expander("🔗 Nguồn được trích dẫn trong câu trả lời", expanded=False):
            src_overflow = len(source_job_app_ids) - MAX_CHIPS
            n_cols = min(len(src_visible), 4)
            src_cols = st.columns(n_cols)
            for idx, jaid in enumerate(src_visible):
                with src_cols[idx % n_cols]:
                    chip_label = _make_chip_label(jaid, src_summary_map)
                    if st.button(
                        chip_label,
                        key=f"src_chip_{jaid}",
                        use_container_width=True,
                        help=f"Xem hồ sơ jobAppId={jaid}",
                    ):
                        st.session_state.selected_app_id = jaid
                        st.session_state.conversation_id = None
                        go("hr_app_detail")
            if src_overflow > 0:
                st.caption(f"+{src_overflow} nguồn khác")


def _render_jobposting_agent_sidebar(
    job_id: int, hr_id: int, job_obj: dict | None = None
) -> None:
    """Render cột trái: conversation list, new/rename/archive, job posting details."""
    is_loading = st.session_state.jobposting_agent_is_loading

    # --- New conversation button ---
    if st.button(
        "➕ Hội thoại mới",
        use_container_width=True,
        disabled=is_loading,
        key="jp_new_conv",
    ):
        st.session_state.jobposting_agent_conversation_id = None
        st.session_state.jobposting_agent_messages = []
        st.session_state.jobposting_agent_working_set = None
        st.session_state.jobposting_agent_source_job_app_ids = []
        st.session_state.jobposting_agent_last_tool_calls = []
        st.session_state.jobposting_agent_warnings = []
        st.session_state.jobposting_agent_error = None
        # Refresh conversation list
        try:
            st.session_state.jobposting_agent_conversations = (
                fang_client.list_jobposting_agent_conversations(job_id, hr_id)
            )
        except Exception:
            pass
        st.rerun()

    st.divider()

    # --- Conversation list ---
    conversations = st.session_state.jobposting_agent_conversations
    if not conversations:
        st.caption("Chưa có hội thoại cho job này.")
    else:
        st.markdown("**Hội thoại**")
        current_conv_id = st.session_state.jobposting_agent_conversation_id
        for c in conversations:
            cid = c.get("conversationId", "")
            title = c.get("title") or f"Hội thoại {cid[:8]}..."
            msg_count = c.get("messageCount", 0)
            is_active = cid == current_conv_id

            btn_label = f"{'▶ ' if is_active else ''}{title}"
            if st.button(
                btn_label,
                key=f"jp_conv_{cid}",
                use_container_width=True,
                disabled=is_loading,
                type="primary" if is_active else "secondary",
            ):
                if cid != current_conv_id:
                    st.session_state.jobposting_agent_conversation_id = cid
                    st.session_state.jobposting_agent_rename_title = title
                    # Load messages
                    try:
                        st.session_state.jobposting_agent_messages = (
                            fang_client.get_jobposting_agent_messages(cid)
                        )
                    except Exception:
                        st.session_state.jobposting_agent_error = (
                            "Không tải được lịch sử hội thoại."
                        )
                    st.session_state.jobposting_agent_working_set = None
                    st.session_state.jobposting_agent_source_job_app_ids = []
                    st.rerun()
            st.caption(f"{msg_count} tin nhắn")

    st.divider()

    # --- Rename ---
    current_conv_id = st.session_state.jobposting_agent_conversation_id
    if current_conv_id:
        st.markdown("**Đổi tên hội thoại**")
        new_title = st.text_input(
            "Tên mới",
            value=st.session_state.jobposting_agent_rename_title,
            key="jp_rename_input",
            disabled=is_loading,
            label_visibility="collapsed",
        )
        if st.button(
            "💾 Lưu tên",
            use_container_width=True,
            disabled=is_loading or not new_title.strip(),
            key="jp_rename_btn",
        ):
            try:
                fang_client.rename_jobposting_agent_conversation(
                    current_conv_id, hr_id, new_title.strip()
                )
                st.session_state.jobposting_agent_rename_title = new_title.strip()
                st.session_state.jobposting_agent_conversations = (
                    fang_client.list_jobposting_agent_conversations(job_id, hr_id)
                )
                st.rerun()
            except Exception as e:
                st.error(_jobposting_agent_error_message(e))

        # --- Archive ---
        if st.button(
            "🗑️ Lưu trữ hội thoại này",
            use_container_width=True,
            disabled=is_loading,
            key="jp_archive_btn",
            type="secondary",
        ):
            try:
                fang_client.archive_jobposting_agent_conversation(
                    current_conv_id, hr_id
                )
                st.session_state.jobposting_agent_conversation_id = None
                st.session_state.jobposting_agent_messages = []
                st.session_state.jobposting_agent_working_set = None
                st.session_state.jobposting_agent_conversations = (
                    fang_client.list_jobposting_agent_conversations(job_id, hr_id)
                )
                st.rerun()
            except Exception as e:
                st.error(_jobposting_agent_error_message(e))

    # --- Job Posting Detail ---
    if job_obj:
        st.divider()
        with st.expander("📄 Job Posting", expanded=False):
            st.markdown(f"### {job_obj.get('title', '')}")
            if job_obj.get("compname"):
                st.write(f"🏢 **Công ty:** {job_obj['compname']}")

            # Format expiry date if exists
            expat = job_obj.get("expat")
            if expat:
                try:
                    expat_str = expat.strftime("%Y-%m-%d")
                except Exception:
                    expat_str = str(expat)
                st.write(f"📅 **Hết hạn:** {expat_str}")

            # App count
            try:
                apps = db.get_applications_for_job(job_id)
                st.write(f"👥 **Số ứng viên:** {len(apps)}")
            except Exception:
                pass

            if job_obj.get("location"):
                st.write(f"📍 **Địa điểm:** {job_obj['location']}")
            if job_obj.get("workMode"):
                st.write(f"💼 **Hình thức:** {job_obj['workMode']}")

            salary_min = job_obj.get("minSalary")
            salary_max = job_obj.get("maxSalary")
            if salary_min is not None or salary_max is not None:
                st.write(
                    f"💰 **Lương:** {salary_min or 0} - {salary_max or 'Thỏa thuận'}"
                )

            # Get detail from nmaiex if available
            try:
                from core import nmaiex

                job_detail = nmaiex.get_job_detail(job_id)
                if job_detail:
                    if job_detail.get("requiredLevel"):
                        st.write(f"🎓 **Yêu cầu level:** {job_detail['requiredLevel']}")
                    if job_detail.get("categories"):
                        st.write(
                            f"📁 **Ngành nghề:** {', '.join(job_detail['categories'])}"
                        )
                    if job_detail.get("skills"):
                        st.write(f"🛠️ **Kỹ năng:** {', '.join(job_detail['skills'])}")
            except Exception:
                pass

            # Actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "✏️ Sửa Job", key="side_edit_job", use_container_width=True
                ):
                    st.session_state.hr_edit_job_id = job_id
                    go("hr_job_edit")
            with col2:
                if st.button(
                    "👥 Xem ứng viên", key="side_view_apps", use_container_width=True
                ):
                    st.session_state.selected_job_id = job_id
                    go("hr_applications")

            # Description (scrollable)
            desc = job_obj.get("description", "")
            if desc:
                st.markdown("**Mô tả công việc:**")
                with st.container(height=350):
                    st.write(desc)


def page_hr_job_agent() -> None:
    """🤖 JobPosting Agent — HR hỏi về toàn bộ ứng viên của 1 job."""
    hr_id: int = st.session_state.hr_user["userid"]
    job_id: int | None = st.session_state.jobposting_agent_job_id

    # Guard: phải có job_id
    if not job_id:
        st.error("Không có job nào được chọn cho Job Agent.")
        if st.button("← Quay lại danh sách Job", key="jp_back_no_job"):
            go("hr_jobs")
        return

    # Load job detail để hiển thị context header
    job = db.get_job_posting_detail(job_id)
    job_title = st.session_state.jobposting_agent_job_title or (
        job["title"] if job else f"Job #{job_id}"
    )
    if job and not st.session_state.jobposting_agent_job_title:
        st.session_state.jobposting_agent_job_title = job["title"]

    # Load conversation list nếu chưa có
    if not st.session_state.jobposting_agent_conversations:
        try:
            st.session_state.jobposting_agent_conversations = (
                fang_client.list_jobposting_agent_conversations(job_id, hr_id)
            )
        except Exception:
            pass

    # --- Header ---
    col_back, col_title = st.columns([1, 6])
    with col_back:
        if st.button("← Quay lại", key="jp_back"):
            go("hr_jobs")
    with col_title:
        st.title(f"🤖 Job Agent: {job_title}")

    if job:
        meta_parts = []
        if job.get("compname"):
            meta_parts.append(f"🏢 {job['compname']}")
        if job.get("expat"):
            try:
                expat_str = job["expat"].strftime("%Y-%m-%d")
            except Exception:
                expat_str = str(job["expat"])
            meta_parts.append(f"📅 Hết hạn: {expat_str}")
        # Count applications
        apps = db.get_applications_for_job(job_id)
        meta_parts.append(f"👥 {len(apps)} ứng viên")
        st.caption("  |  ".join(meta_parts))

    st.divider()

    # --- 2-column layout ---
    col_left, col_right = st.columns([1, 3])

    # ── Cột trái: sidebar ──
    with col_left:
        _render_jobposting_agent_sidebar(job_id, hr_id, job)

    # ── Cột phải: chat ──
    with col_right:
        is_loading = st.session_state.jobposting_agent_is_loading

        # Error banner
        if st.session_state.jobposting_agent_error:
            st.error(st.session_state.jobposting_agent_error)

        # Warnings banner
        for w in st.session_state.jobposting_agent_warnings:
            msg = w.get("message", str(w))
            suggestion = w.get("suggestion", "")
            warn_text = f"⚠️ {msg}"
            if suggestion:
                warn_text += f"\nGợi ý: {suggestion}"
            st.warning(warn_text)

        # Chat history container
        chat_box = st.container(height=460)
        with chat_box:
            _render_jobposting_agent_messages(
                st.session_state.jobposting_agent_messages
            )

        # Working set + source chips
        _render_jobposting_agent_working_set(
            st.session_state.jobposting_agent_working_set,
            st.session_state.jobposting_agent_source_job_app_ids,
        )

        # Loading status hint
        if is_loading:
            st.caption("⏳ Có thể mất 10–60 giây tùy số ứng viên và công cụ được gọi.")

        # --- Chat input ---
        prompt_from_quick = st.session_state.jobposting_agent_pending_prompt
        if prompt_from_quick:
            st.session_state.jobposting_agent_pending_prompt = None
            prompt = prompt_from_quick
        else:
            prompt = st.chat_input(
                "Tìm nhanh ứng viên sáng giá cùng FANG.",
                key="jp_chat_input",
                disabled=is_loading,
            )

        if prompt:
            # Optimistic user message display
            with chat_box:
                with st.chat_message("user"):
                    st.markdown(prompt)

            st.session_state.jobposting_agent_is_loading = True
            st.session_state.jobposting_agent_error = None
            st.session_state.jobposting_agent_warnings = []

            with st.spinner("FANG Job Agent đang phân tích ứng viên và gọi công cụ..."):
                try:
                    result = fang_client.jobposting_agent_query(
                        job_post_id=job_id,
                        hr_id=hr_id,
                        prompt=prompt,
                        conversation_id=st.session_state.jobposting_agent_conversation_id,
                    )

                    # Update conversation state
                    new_conv_id = str(result.get("conversationId", ""))
                    if new_conv_id:
                        st.session_state.jobposting_agent_conversation_id = new_conv_id

                    # Store response data
                    st.session_state.jobposting_agent_last_tool_calls = (
                        result.get("toolCalls") or []
                    )
                    st.session_state.jobposting_agent_working_set = result.get(
                        "workingSet"
                    )
                    st.session_state.jobposting_agent_source_job_app_ids = (
                        result.get("sourceJobAppIds") or []
                    )
                    st.session_state.jobposting_agent_warnings = (
                        result.get("warnings") or []
                    )

                    # Build assistant message for display
                    assistant_msg = {
                        "role": "assistant",
                        "content": result.get("response", ""),
                        "model": result.get("model"),
                        "latencyMs": result.get("latencyMs"),
                    }

                    # Reload full message history (authoritative)
                    if new_conv_id:
                        try:
                            st.session_state.jobposting_agent_messages = (
                                fang_client.get_jobposting_agent_messages(new_conv_id)
                            )
                        except Exception:
                            # Fallback: append locally
                            st.session_state.jobposting_agent_messages.append(
                                {"role": "user", "content": prompt}
                            )
                            st.session_state.jobposting_agent_messages.append(
                                assistant_msg
                            )
                    else:
                        st.session_state.jobposting_agent_messages.append(
                            {"role": "user", "content": prompt}
                        )
                        st.session_state.jobposting_agent_messages.append(assistant_msg)

                    # Refresh conversation list
                    try:
                        st.session_state.jobposting_agent_conversations = (
                            fang_client.list_jobposting_agent_conversations(
                                job_id, hr_id
                            )
                        )
                    except Exception:
                        pass

                except Exception as e:
                    st.session_state.jobposting_agent_error = (
                        _jobposting_agent_error_message(e)
                    )
                finally:
                    st.session_state.jobposting_agent_is_loading = False

            st.rerun()


# ===========================================================================
# Router
# ===========================================================================

page = st.session_state.current_page

if page == "home":
    page_home()

# HR flow
elif page == "login_hr":
    page_login_hr()
elif page == "hr_jobs":
    if st.session_state.hr_user:
        page_hr_jobs()
    else:
        go("login_hr")
elif page == "hr_job_view":
    if st.session_state.hr_user:
        page_hr_job_view()
    else:
        go("login_hr")
elif page == "hr_job_edit":
    if st.session_state.hr_user:
        page_hr_job_edit()
    else:
        go("login_hr")
elif page == "hr_applications":
    if st.session_state.hr_user:
        page_hr_applications()
    else:
        go("login_hr")
elif page == "hr_app_detail":
    if st.session_state.hr_user:
        page_hr_app_detail()
    else:
        go("login_hr")
elif page == "hr_ai_ranking":
    if st.session_state.hr_user:
        page_hr_ai_ranking()
    else:
        go("login_hr")
elif page == "hr_job_agent":
    if st.session_state.hr_user:
        page_hr_job_agent()
    else:
        go("login_hr")

# Candidate flow
elif page == "login_candidate":
    page_login_candidate()
elif page == "candidate_jobs":
    if st.session_state.candidate_user:
        page_candidate_jobs()
    else:
        go("login_candidate")
elif page == "candidate_job_detail":
    if st.session_state.candidate_user:
        page_candidate_job_detail()
    else:
        go("login_candidate")
elif page == "candidate_profile":
    if st.session_state.candidate_user:
        page_candidate_profile()
    else:
        go("login_candidate")
elif page == "candidate_apply":
    if st.session_state.candidate_user:
        page_candidate_apply()
    else:
        go("login_candidate")

else:
    st.error(f"Trang không tồn tại: `{page}`")
    go("home")
