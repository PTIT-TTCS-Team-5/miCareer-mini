# miCareer-mini

Giao diện Web Frontend nhẹ dành cho nhân sự (HR), tích hợp trực tiếp với thuật toán Vector Retrieval-Augmented Generation (RAG) của dự án lõi FANG. Hệ thống sử dụng **Streamlit** để tối ưu hóa tốc độ triển khai UI và đảm bảo tương tác AI thời gian thực.

## 1. Cài Đặt và Chạy Ứng Dụng

**Bước 1: Thiết lập môi trường**
```bash
# Tạo môi trường ảo (Khuyến nghị)
python -m venv venv

# Kích hoạt môi trường (Terminal Windows)
venv\Scripts\activate   

# Cài đặt bộ thư viện
pip install -r requirements.txt

# Cài đặt thêm Hooks kiểm soát chất lượng code
pre-commit install
```

**Bước 2: Cài đặt Biến Môi Trường**
Hãy đổi tên (hoặc Copy) file `.env.example` thành `.env` ngay tại thư mục gốc và điền thông tin:
- Mật khẩu kết nối CSDL PostgreSQL (`DATABASE_URL`).
- Cấu hình các API Keys cho mô hình (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `CLAUDE_API_KEY`).

**Bước 3: Khởi chạy Giao diện UI**
```bash
# Lệnh chạy server Streamlit
python -m streamlit run app.py
```
*Giao diện web sẽ tự động bật lên qua địa chỉ `http://localhost:8501`.*

## 2. Kịch Bản Test Mẫu Hiện Tại (HR Demo)
Do nền tảng này sử dụng chung nguồn Data với hệ thống `micareer_lite_db` rẽ nhánh từ FANG, bạn có thể thực hiện kiểm thử RAG theo kịch bản chuẩn nhất hiện có:

*   **Tài khoản HR Công Ty VNG Demo:**
    *   **Tên đăng nhập:** `hr_vng`
    *   **Mật khẩu:** `123456`

### 👉 Cách thực thi luồng Check CV:
1. Đăng nhập hệ thống bằng tài khoản `hr_vng` ở trên.
2. Tại màn hình Dashboard Công ty, tìm và bấm nút **"Xem ứng viên"** tại vị trí **AI Engineer (Python/NLP)**.
3. Trong danh sách đổ về, cuốn xuống tìm ứng viên có tên **Nguyễn Hải Hưng**, nhấn **"Xem / Đánh giá RAG"**.
4. Màn hình Workspace chia làm 2 hiện lên. Một bên tự động load CV thực tế bằng iFrame. Một bên là Chatbot kết nối vào khối Vector DB chứa Chunking của FANG.
5. Hãy chọn Tier 2 hoặc Tier 3, sau đó nhập Prompt: *"Dựa vào CV, Hưng có kinh nghiệm sử dụng thư viện Langchain và hệ cơ sở dữ liệu Vector Database không?"* để lấy kết quả.

## 3. Kho Tài Liệu Vận Hành
- Khái quát kiến trúc AI truy xuất DB: [Chiến lược RAG (rag_strategy.md)](./docs/rag_strategy.md)
- Hướng dẫn thiết kế UX và Quản trị State: [Hướng dẫn Luồng UI System](./docs/hr_guide.md)
