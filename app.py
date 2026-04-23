"""miCareer-mini — thin Streamlit UI.

Kiến trúc:
- miCareer-mini CHỈ hiển thị UI và gọi FANG API.
- Mọi logic AI (embed, vector search, LLM call) đều nằm ở FANG.

Các trang:
  HR:        login_hr → jobs → applications → app_detail (RAG chat)
  Candidate: login_candidate → candidate_jobs → candidate_apply
"""

import streamlit as st

from core import db, fang_client
from core.cloudinary_upload import upload_cv_pdf

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
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


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
    "🤖 Auto-Pro (Gemini Pro → GPT-5.4)": "auto-pro",
    "💚 Gemini Flash Lite": "gemini-flash",
    "💚 GPT-5.4 mini": "gpt-mini",
    "💚 Claude 4.5 Haiku": "claude-haiku",
    "🔶 Gemini 3.1 Pro": "gemini-pro",
    "🔶 GPT-5.4 (Flagship)": "gpt-full",
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
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{j['title']}**")
                st.caption(f"Hết hạn: {j['expat']}")
            with col2:
                if st.button("Xem ứng viên", key=f"hr_job_{j['jobpostid']}"):
                    st.session_state.selected_job_id = j["jobpostid"]
                    go("hr_applications")

    st.divider()
    if st.button("🚪 Đăng xuất", key="logout_hr"):
        st.session_state.hr_user = None
        go("home")


def page_hr_applications():
    if st.button("← Quay lại danh sách Job", key="back_jobs"):
        go("hr_jobs")

    st.title("📋 Danh sách ứng viên")

    apps = db.get_applications_for_job(st.session_state.selected_job_id)
    if not apps:
        st.info("Chưa có ứng viên nào cho job này.")
        return

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
                    st.session_state.conversation_id = None  # reset conversation
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
            st.components.v1.iframe(src=viewer_url, height=550, scrolling=True)

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
    if st.button("🚪 Đăng xuất", key="logout_cand"):
        st.session_state.candidate_user = None
        go("home")


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

# Candidate flow
elif page == "login_candidate":
    page_login_candidate()
elif page == "candidate_jobs":
    if st.session_state.candidate_user:
        page_candidate_jobs()
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
