# Hướng dẫn Phân hệ Đánh Giá AI Co-pilot (`app.py` & `core/ai.py`)

Tài liệu này giải thích chi tiết cách hoạt động thực tiễn của công cụ Frontend `miCareer-mini` và quy trình kỹ thuật luân chuyển luồng tương tác với kho Vector Core FANG.

`rag_strategy.md` mang tính định hướng lý thuyết kiến trúc, tài liệu này tập trung vào cách User Experience (UX) được triển khai qua Streamlit và quy trình mã nguồn thực thi.

## 1. Luồng Hoạt Động (Workflow)
Hệ thống dẫn dắt HR qua 4 màn hình chính hoạt động theo mô hình rẽ nhánh tương tự Single Page Application (SPA):
1. **Xác thực Identity:** Lớp Middleware `app.py` đối chiếu User và Pass trực tiếp bằng Plaintext/Hash tại bảng "user" kết nối chèn bảng "HR".
2. **Khai thác Job Posting:** Dựa vào `compId` của HR để list ra danh sách tin đang được theo dõi trên hệ thống.
3. **Sàng lọc Ứng Viên:** Xem xét danh sách ứng viên (Job Applications), hiện ứng viên và trạng thái Resume tương ứng.
4. **Phân tích Workspace (Module RAG cốt lõi):** Màn hình chia đôi UI trực quan - Bản PDF gốc (Nguồn tải tĩnh) đặt cạnh Co-pilot RAG Model.

## 2. Quản Lý Trạng Thái Cục Bộ (Session State)
Streamlit bản chất render lại giao diện mỗi khi có tương tác nhỏ nhất, để giải quyết bài toán chống Reset biến cục bộ, hệ thống dùng `st.session_state`:
* **Định tuyến (Router):** Lưu lại trang hiện tại `current_page` để luồng hiển thị không bị giật hoặc đứt quãng.
* **Ghim Lịch Sử Trò Chuyện (Chat Context):**
    * Tận dụng hàm logic `init_chat_history(job_app_id)` để đóng dấu tên khóa duy nhất cho lịch sử Chat.
    * Khi HR chuyển giao qua lại giữa các ứng viên khác nhau, dữ liệu LLM Chat hoàn toàn cô lập, ngăn chặn hoàn toàn "Data Leaking Context" giữa hồ sơ Hưng và hồ sơ An.

## 3. Mã Nguồn AI Chat RAG (Module `core/ai.py`)
Tại màn hình RAG Workspace, toàn bộ tác vụ tính toán được xử lý ở Layer bên dưới qua các cơ chế sau:

1. Thiết lập biến môi trường và nạp khóa thông qua thư viện Langchain API tích hợp (`ChatGoogleGenerativeAI`, `ChatOpenAI`, `ChatAnthropic`).
2. Mã nguồn triển khai phương thức `ask_rag(job_app_id, hr_id, model_tier, chat_history, new_prompt)`:
    * Nhúng Vector: Bắn thẳng bằng `embeddings.embed_query`.
    * V-Search SQL: Kết nối tới `database/db.py` thực thi lệnh `ORDER BY embedding <=> %s` và trả về `fetchall()`.
    * Build Context: Tổng dãy chuỗi Chunk thành format nhồi cho System Prompt (`Dưới đây là thông tin ứng viên...`).
    * Trả kết quả: Quét mô hình tuỳ biến qua biến `model_tier`, nhận kết quả chuỗi String của AI, trả về UI và Call ngầm DB `log_ai_query()` ghi lịch sử `latency`, `top_k`.

## 4. Xử lý Cơ chế Ngoại lệ (Edge Cases)
* **API Timeout/Key Rotation:** Cơ chế gọi model không lock main thread quá lâu. Do thiết kế LLM linh hoạt 3 tầng, nếu quá giới hạn hạn mức (Rate limit) API của OpenAPI (Tier 2), HR có thể xoay sang Gemini (Tier 1) hay Claude (Tier 3) để Bypass.
* **Rendering IFrame CV:** Hệ thống khai thác cấu trúc HTML tĩnh `<iframe src="...">` nhúng trực tiếp file PDF Cloudinary lưu trên cơ sở dữ liệu. Tránh việc dùng CPU server convert ảnh nội suy. Tăng sức trải nghiệm Native PDF.
