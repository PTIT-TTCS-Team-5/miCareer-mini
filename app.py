import streamlit as st

from core import ai, db

st.set_page_config(page_title="miCareer-mini HR Portal", layout="wide")

if "hr_user" not in st.session_state:
    st.session_state.hr_user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"
if "selected_job_id" not in st.session_state:
    st.session_state.selected_job_id = None
if "selected_app_id" not in st.session_state:
    st.session_state.selected_app_id = None


# Logic tạo session để lưu lịch sử chat cho từng bộ hồ sơ cụ thể
def init_chat_history(job_app_id):
    chat_key = f"chat_history_{job_app_id}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    return chat_key


def navigate_to(page):
    st.session_state.current_page = page


# --- Pages ---
def page_login():
    st.title("HR Login - miCareer Core")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            user = db.get_hr_user(username, password)
            if user:
                st.session_state.hr_user = user
                navigate_to("jobs")
                st.rerun()
            else:
                st.error("Sai tài khoản hoặc mật khẩu HR!")


def page_jobs():
    user = st.session_state.hr_user
    st.title(f"Welcome, {user['username']}")
    st.subheader("Your Company's Job Postings")

    jobs = db.get_job_postings_by_company(user["compid"])
    if not jobs:
        st.info("Không có tin tuyển dụng nào.")
        return

    for j in jobs:
        with st.container():
            st.write(f"### {j['title']}")
            st.write(f"Hết hạn: {j['expat']}")
            if st.button(
                f"Xem ứng viên ({j['jobpostid']})", key=f"job_{j['jobpostid']}"
            ):
                st.session_state.selected_job_id = j["jobpostid"]
                navigate_to("applications")
                st.rerun()
            st.divider()


def page_applications():
    if st.button("⬅ Quay lại danh sách Job"):
        navigate_to("jobs")
        st.rerun()

    st.title("Danh sách ứng viên")

    apps = db.get_applications_for_job(st.session_state.selected_job_id)
    if not apps:
        st.info("Chưa có ứng viên nào cho job này.")
        return

    # Tạo bảng hiển thị cho đẹp
    for a in apps:
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(
                    f"**{a['fname']} {a['lname']}** ({a['email']}) - Trạng thái: `{a['stat']}` - Ngày nộp: {a['appliedat'].strftime('%Y-%m-%d') if a['appliedat'] else 'N/A'}"
                )
            with col2:
                if st.button("Xem / Đánh giá RAG", key=f"app_{a['jobappid']}"):
                    st.session_state.selected_app_id = a["jobappid"]
                    navigate_to("app_detail")
                    st.rerun()
            st.divider()


def page_app_detail():
    if st.button("⬅ Quay lại danh sách Ứng viên"):
        navigate_to("applications")
        st.rerun()

    st.title("Workspace Đánh Giá Bằng RAG")
    app_id = st.session_state.selected_app_id
    detail = db.get_application_detail(app_id)

    if not detail:
        st.error("Không tìm thấy dữ liệu ứng viên!")
        return

    col1, col2 = st.columns([1, 1])

    # Cột 1: Thông tin và CV
    with col1:
        st.subheader("Thông tin Ứng Viên")
        st.write(f"👤 **Họ tên:** {detail['fname']} {detail['lname']}")
        st.write(f"📧 **Email:** {detail['email']}")
        st.write(f"📌 **Trạng thái:** {detail['stat']}")
        st.write(f"📄 **CV URL:** [Link Cloudinary]({detail['cvsnapurl']})")
        if detail["cvsnapurl"]:
            # Dùng Google Docs Viewer bọc URL để lách X-Frame-Options bị block bởi Edge/Chrome
            pdf_url = detail["cvsnapurl"]
            viewer_url = f"https://docs.google.com/viewer?url={pdf_url}&embedded=true"
            st.iframe(src=viewer_url, height=600)

    # Cột 2: Giao diện Chat RAG
    with col2:
        st.subheader("🤖 FANG HR Co-pilot")

        # Chọn model Tier
        model_tier = st.selectbox(
            "Chọn AI Model phân tích:",
            (
                "Tier 1: Gemini Flash",
                "Tier 2: GPT-5.4 mini",
                "Tier 3: Claude 4.5 Haiku",
            ),
        )

        chat_key = init_chat_history(app_id)

        # Vùng hiển thị Lịch sử
        chat_box = st.container(height=500)
        with chat_box:
            for message in st.session_state[chat_key]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Vùng nhập liệu mới
        if prompt := st.chat_input(
            "Hãy phân tích ứng viên này so với Job Description?"
        ):
            # Hiển thị luôn prompt của HR
            with chat_box:
                with st.chat_message("user"):
                    st.markdown(prompt)

            # Tương tác AI
            with st.spinner("AI RAG đang tổng hợp tri thức..."):
                response_text = ai.ask_rag(
                    job_app_id=app_id,
                    hr_id=st.session_state.hr_user["userid"],
                    model_tier=model_tier,
                    chat_history=st.session_state[chat_key],
                    new_prompt=prompt,
                )

                with chat_box:
                    with st.chat_message("assistant"):
                        st.markdown(response_text)

            # Lưu lại lịch sử vào state
            st.session_state[chat_key].append({"role": "user", "content": prompt})
            st.session_state[chat_key].append(
                {"role": "assistant", "content": response_text}
            )


# --- Router ---
if st.session_state.current_page == "login":
    page_login()
elif st.session_state.current_page == "jobs":
    page_jobs()
elif st.session_state.current_page == "applications":
    page_applications()
elif st.session_state.current_page == "app_detail":
    page_app_detail()
