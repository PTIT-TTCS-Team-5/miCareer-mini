# miCareer-mini RAG Strategy

## Tổng quan Kiến trúc

`miCareer-mini` hoạt động như một hệ thống frontend cho FANG, đồng thời chứa logic trực tiếp xử lý quy trình Retrieval-Augmented Generation (RAG).

## 1. Cơ chế Chunking và Embedding (Nguồn từ FANG)
- CV của ứng viên sẽ được FANG chia nhỏ (Chunking) theo Semantic.
- Các Chunk này được FANG dùng `text-embedding-3-small` để chuyển đổi thành vector (1024 chiều).
- Toàn bộ được lưu tại bảng `AIDOCUMENTCHUNK` trên PostgreSQL bằng extension `pgvector`.

## 2. Chiến lược Truy xuất (Retrieval)
Thay vì dùng database vector cồng kềnh, `miCareer-mini` trực tiếp kết nối DB và sử dụng phép toán `<=>` (Khoảng cách Cosine) của pgvector:

1. **User Prompt Embedding**: Khi HR gõ prompt (VD: "Đánh giá ứng viên"), hệ thống sẽ dùng chính `text-embedding-3-small` để nhúng câu prompt.
2. **K-Nearest Neighbors (KNN)**: Truy vấn SQL sẽ tìm Top `K` (Mặc định: 3) chunks chứa nội dung liên đới nhất đến câu prompt.
3. **Lọc theo Applicant**: Quá trình tìm kiếm được scope chặt trong ngữ cảnh `jobAppId` hiện tại, đảm bảo context luôn nạp đúng CV.

## 3. Tạo sinh nội dung (Generation & Model Tiers)
`miCareer-mini` áp dụng chuẩn 3 Tier từ hệ thống FANG để điều phối chất lượng và chi phí:
- **Tier 1 (Gemini Flash)**: Phù hợp hỏi nhanh, phân tích tổng quan CV.
- **Tier 2 (GPT-5.4 mini)**: Cân bằng thời gian/chất lượng cho đánh giá kỹ năng.
- **Tier 3 (Claude 4.5 Haiku)**: Suy luận logic chậm nhưng chính xác nhất.

LLM được cấp context (các chunks) và lịch sử chat từ Memory (quản lý bởi Streamlit Session State). Lịch sử chat được lưu trữ tạm thời nhưng mỗi prompt đều được ghi log vào `AIQUERYLOG` cho mục đích kiểm soát lượng truy vấn.
