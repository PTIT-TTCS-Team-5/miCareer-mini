# miCareer-mini

Giao diện Web Frontend (Streamlit) dành cho nhân sự (HR) và ứng viên, đóng vai trò **thin client** tích hợp với **FANG v2 AI Core**. Mọi logic AI (embedding, RAG, fallback) được xử lý tại FANG; miCareer-mini chỉ gọi JSON API và hiển thị kết quả.

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
- Kết nối CSDL PostgreSQL (`DATABASE_URL`).
- API Keys của FANG không cần thiết nữa (FANG tự quản lý).
- URL của FANG: `FANG_API_URL=http://localhost:8000`
- Cloudinary (cho upload CV): `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

**Bước 3: Khởi chạy Giao diện UI**
```bash
# Lệnh chạy server Streamlit
python -m streamlit run app.py
```
*Giao diện web sẽ tự động bật lên qua địa chỉ `http://localhost:8501`.*

## 2. Kịch Bản Test Mẫu Hiện Tại (HR Demo)
Do nền tảng này sử dụng chung nguồn Data với hệ thống `micareer_lite_db` rẽ nhánh từ FANG, có thể thực hiện kiểm thử RAG theo kịch bản chuẩn nhất hiện có:

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

**Tài liệu hiện hành:**
- Chiến lược luồng ứng viên và upload CV: [candidate_apply_strategy.md](./docs/candidate_apply_strategy.md)
- **API contract của FANG v2** (tham chiếu): [FANG/docs/integration_strategy.md](../FANG/docs/integration_strategy.md)
- **Chiến lược RAG query** (tham chiếu): [FANG/docs/rag_query_strategy.md](../FANG/docs/rag_query_strategy.md)

**Lưu trữ (archive — phác hiện cũ):**
- [docs/archive/rag_strategy_v1.md](./docs/archive/rag_strategy_v1.md) — Kiến trúc RAG cũ (Direct-DB, 3-tier)
- [docs/archive/hr_guide_v1.md](./docs/archive/hr_guide_v1.md) — Hướng dẫn UI cũ
