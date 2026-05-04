# miCareer-mini

Giao diện Web Frontend để test FANG sử dụng **Streamlit**.

Mọi logic AI phức tạp (embedding, RAG query, 5-tier LLM fallback, quản lý lịch sử chat) đều được xử lý tập trung tại FANG. `miCareer-mini` chỉ gọi REST API và hiển thị kết quả.

## 1. Tính Năng Chính (v2)

Dự án hiện tại hỗ trợ 2 luồng người dùng riêng biệt:

**Luồng Ứng Viên (Candidate):**

- Đăng nhập và xem danh sách công việc.
- Nộp đơn (Apply) và tải lên CV PDF (lưu trữ tại Cloudinary).
- Tự động kích hoạt FANG Ingestion Pipeline (Parse -> Chunk -> Embed).
- Theo dõi trạng thái AI xử lý CV theo thời gian thực (Polling).

**Luồng Tuyển Dụng (HR):**

- Đăng nhập và xem danh sách ứng viên đã nộp đơn.
- Kiểm tra trạng thái xử lý CV của FANG (Chỉ khi `SUCCESS` mới được phép dùng AI).
- Giao diện chat RAG 2 cột: Xem CV gốc (iFrame) và Chat với FANG Co-pilot.
- Tùy chọn 7 Model Modes (từ Lite đến Pro, tự động Fallback).
- Cảnh báo Context Window (ngân sách Token) kèm tính năng "Tóm tắt & Tiếp tục" hoặc "Nhánh hội thoại mới".

## 2. Cài Đặt và Chạy Ứng Dụng

**Bước 1: Thiết lập môi trường**

```bash
# Tạo môi trường ảo (Khuyến nghị)
python -m venv venv

# Kích hoạt môi trường (Terminal Windows)
venv\Scripts\activate   

# Cài đặt bộ thư viện
pip install -r requirements.txt

# Kich hoat pre_commit
python -m pre_commit install
```

**Bước 2: Cài đặt Biến Môi Trường**
Copy file `.env.example` thành `.env` tại thư mục gốc và điền thông tin:

- Kết nối CSDL PostgreSQL (`DATABASE_URL`).
- URL của FANG: `FANG_API_URL=http://localhost:8000/v2` *(Lưu ý: FANG phải được bật song song)*
- Cloudinary (dùng để upload CV): `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

**Bước 3: Khởi chạy Giao diện UI**

```bash
# Lệnh chạy server Streamlit
python -m streamlit run app.py
```

*Giao diện web sẽ tự động bật lên qua địa chỉ `http://localhost:8501`.*

## 3. Kho Tài Liệu Vận Hành

**Tài liệu hiện hành:**

- 📖 [Hướng dẫn Kỹ thuật: Luồng Ứng Viên](./docs/candidate_apply_guide.md)
- 📖 [Chiến lược luồng ứng viên và upload CV](./docs/candidate_apply_strategy.md)
- 🔗 **API contract của FANG v2**: [FANG/docs/strategy/integration_strategy.md](../Fang/docs/strategy/integration_strategy.md)
- 🔗 **Chiến lược RAG query**: [FANG/docs/strategy/rag_query_strategy.md](../Fang/docs/strategy/rag_query_strategy.md)

**Lưu trữ (Archive — phiên bản cũ):**

- [docs/archive/rag_strategy_v1.md](./docs/archive/rag_strategy_v1.md) — Kiến trúc RAG cũ (Direct-DB, 3-tier)
- [docs/archive/hr_guide_v1.md](./docs/archive/hr_guide_v1.md) — Hướng dẫn UI cũ
