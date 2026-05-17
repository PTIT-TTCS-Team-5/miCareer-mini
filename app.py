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
    # Phase 3: Ranking
    "hr_ranking_job_id": None,  # job HR đang xem AI ranking
    "hr_ranking_job_title": None,
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
                if st.button("Xem ứng viên", key=f"hr_job_{j['jobpostid']}"):
                    st.session_state.selected_job_id = j["jobpostid"]
                    go("hr_applications")
            with col3:
                if st.button("✅ AI Ranking", key=f"hr_rank_{j['jobpostid']}"):
                    st.session_state.hr_ranking_job_id = j["jobpostid"]
                    st.session_state.hr_ranking_job_title = j["title"]
                    go("hr_ai_ranking")
            with col4:
                if st.button("✏️ Sửa Job", key=f"hr_edit_{j['jobpostid']}"):
                    st.session_state.hr_edit_job_id = j["jobpostid"]
                    go("hr_job_edit")

    st.divider()
    if st.button("🚪 Đăng xuất", key="logout_hr"):
        st.session_state.hr_user = None
        go("home")


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

    if st.button(
        "🚀 Chạy AI Ranking",
        type="primary",
        use_container_width=True,
        key=f"run_rank_{job_id}",
    ):
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

                st.success(
                    f"✅ Tìm thấy **{returned}** ứng viên phù hợp (pool: {total})"
                )

                if not candidates:
                    st.info("Không có ứng viên phù hợp với bộ lọc hiện tại.")
                    return

                for i, c in enumerate(candidates, 1):
                    score = c.get("match_score", 0)
                    score_pct = f"{score * 100:.1f}%"
                    name = c.get(
                        "candidate_name", f"Candidate #{c.get('candidate_id', '?')}"
                    )

                    with st.container(border=True):
                        col_rank, col_info, col_score = st.columns([1, 6, 2])
                        with col_rank:
                            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
                            st.markdown(f"## {medal}")
                        with col_info:
                            st.markdown(f"**{name}**")
                            if c.get("candidate_id"):
                                st.caption(f"Candidate ID: {c['candidate_id']}")
                        with col_score:
                            st.metric("Match Score", score_pct)
                        _render_score_badge(c)

            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.warning(
                        "⚠️ Job này chưa có dữ liệu NMAIex (chưa được seed structured data). "
                        "Hãy vào **Sửa Job** → **Cài đặt** để cấu hình trước khi ranking."
                    )
                else:
                    st.error(f"❌ Lỗi khi gọi AI Ranking: {e}")


def page_hr_ai_ranking():
    """Phase 3 — Trang AI Ranking riêng (truy cập từ nút trong danh sách Job)."""
    if st.button("← Quay lại danh sách Job", key="back_from_ai_ranking"):
        go("hr_jobs")

    job_id = st.session_state.hr_ranking_job_id
    job_title = st.session_state.hr_ranking_job_title or f"Job #{job_id}"

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

    # Tab: Danh sách thường và AI Ranking
    tab_list, tab_rank = st.tabs(["💼 Danh sách ứng viên", "🤖 AI Ranking"])

    with tab_list:
        apps = db.get_applications_for_job(job_id)
        if not apps:
            st.info("Chưa có ứng viên nào cho job này.")
        else:
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
                        if st.button("Đánh giá RAG", key=f"app_{a['jobappid']}"):
                            st.session_state.selected_app_id = a["jobappid"]
                            st.session_state.conversation_id = None
                            go("hr_app_detail")

    with tab_rank:
        _render_hr_ranking_tab(job_id)


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
    st.subheader("📢 Các vị trí đang tuyển dụng")

    master = _ensure_master_data()

    with st.expander("🔍 Lọc kết quả tìm kiếm (Bộ lọc AI)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            # Province
            provinces_data = master.get("provinces", [])
            region_map = {r["region_name"]: r for r in provinces_data}
            sel_region = st.selectbox(
                "Vùng", [""] + list(region_map.keys()), key="cand_sel_region"
            )
            prov_list = region_map[sel_region]["provinces"] if sel_region else []
            prov_options = {p["province_name"]: p["province_id"] for p in prov_list}
            st.selectbox(
                "Tỉnh/Thành phố", [""] + list(prov_options.keys()), key="cand_sel_prov"
            )

            # Level
            levels_data = master.get("levels", [])
            level_name_to_id = {
                lvl["level_name"]: lvl["level_id"] for lvl in levels_data
            }
            st.selectbox(
                "Cấp bậc", [""] + list(level_name_to_id.keys()), key="cand_sel_level"
            )

        with col2:
            # Category
            cats_data = master.get("categories", [])
            cat_name_to_id = {c["category_name"]: c["category_id"] for c in cats_data}
            st.multiselect("Danh mục", list(cat_name_to_id.keys()), key="cand_sel_cats")

            # Skills
            skills_data = master.get("skills", [])
            skill_name_to_id = {s["skill_name"]: s["skill_id"] for s in skills_data}
            st.multiselect(
                "Kỹ năng", list(skill_name_to_id.keys()), key="cand_sel_skills"
            )

        st.button(
            "Áp dụng bộ lọc (Sắp ra mắt)", disabled=True, use_container_width=True
        )

    jobs = db.get_all_job_postings()
    if not jobs:
        st.info("Hiện tại chưa có vị trí tuyển dụng nào.")
        return

    for j in jobs:
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{j['title']}** — 🏢 {j.get('compname', 'N/A')}")
                if j.get("description"):
                    st.caption(
                        j["description"][:200] + "..."
                        if len(j.get("description", "")) > 200
                        else j.get("description", "")
                    )
                st.caption(f"Hạn nộp: {j['expat']}")
            with col2:
                already_applied = db.has_applied(user["userid"], j["jobpostid"])
                if already_applied:
                    st.success("✅ Đã nộp")
                else:
                    if st.button("Nộp CV", key=f"apply_{j['jobpostid']}"):
                        st.session_state.apply_job_id = j["jobpostid"]
                        st.session_state.apply_job_title = j["title"]
                        go("candidate_apply")

    st.divider()
    # Phase 3 — Section gợi ý việc làm AI
    _render_candidate_ai_jobs(user["userid"])

    st.divider()
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("📄 Hồ sơ của tôi", use_container_width=True, key="goto_profile"):
            go("candidate_profile")
    with col_nav2:
        if st.button("🚪 Đăng xuất", use_container_width=True, key="logout_cand"):
            st.session_state.candidate_user = None
            go("home")


def _render_candidate_ai_jobs(candidate_id: int):
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

    if st.button(
        "✨ Xem gợi ý AI", type="primary", use_container_width=True, key="run_cj_rank"
    ):
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

                if not job_list:
                    st.info(
                        "Chưa tìm thấy việc làm phù hợp. Hãy cập nhật CV và hồ sơ của bạn!"
                    )
                    return

                st.success(f"✅ Tìm thấy **{len(job_list)}** việc làm phù hợp với bạn:")
                for j in job_list:
                    score = j.get("match_score", 0)
                    score_pct = f"{score * 100:.1f}%"
                    title = j.get("job_title") or j.get("title", "?")
                    company = j.get("company_name") or j.get("compname", "")
                    with st.container(border=True):
                        c1, c2 = st.columns([6, 2])
                        with c1:
                            st.markdown(
                                f"**{title}**" + (f" — 🏢 {company}" if company else "")
                            )
                            if j.get("work_loc"):
                                st.caption(f"📍 {j['work_loc']}")
                        with c2:
                            st.metric("Match Score", score_pct)
                        _render_score_badge(j)

            except Exception as e:
                err = str(e)
                if "404" in err:
                    st.warning(
                        "⚠️ Hồ sơ của bạn chưa được NMAIex xử lý. "
                        "Hãy upload CV và đợi hệ thống phân tích xong."
                    )
                else:
                    st.error(f"❌ Lỗi gợi ý AI: {e}")


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


# Candidate flow
elif page == "login_candidate":
    page_login_candidate()
elif page == "candidate_jobs":
    if st.session_state.candidate_user:
        page_candidate_jobs()
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
