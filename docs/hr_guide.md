# Hướng dẫn sử dụng nền tảng miCareer-mini dành cho HR

Chào mừng bạn đến với **miCareer-mini**, công cụ đánh giá ứng viên bằng AI mạnh mẽ được tối ưu hóa cho tốc độ.

## 1. Truy cập & Đăng nhập
1. Chạy lệnh cài đặt `pip install -r requirements.txt`.
2. Chạy ứng dụng bằng `streamlit run app.py`.
3. Mở URL do Streamlit cung cấp trên trình duyệt.
4. Đăng nhập bằng tên đăng nhập và mật khẩu (Dữ liệu mock trong Database).

## 2. Quản lý Tin Tuyển Dụng & CV
- **Danh sách Tin tuyển dụng**: Sau khi login, bạn sẽ thấy danh sách các vị trí tuyển dụng của công ty bạn. Bấm **"Xem ứng viên"** ở vị trí muốn xử lý.
- **Danh sách Ứng viên**: Hiển thị toàn bộ ứng viên đã apply. Bấm **"Xem / Đánh giá RAG"** để tiến vào màn hình phân tích.

## 3. Không gian Phân Tích bằng AI (RAG Workspace)
Màn hình chia làm 2 nửa chuyên nghiệp:
- **Trái**: Thông tin tóm tắt và Trình đọc CV Online (Tải trực tiếp bằng iFrame PDF từ ứng viên).
- **Phải (FANG Co-pilot)**: Không gian chat với AI.

### Cách sử dụng AI Chat:
1. **Chọn AI Model**: Dropdown có sẵn 3 mức (Tier 1: Gemini Flash, Tier 2: GPT-5.4 mini, Tier 3: Claude 4.5 Haiku). Chọn model tùy theo mức độ câu hỏi (Dễ -> Khó).
2. **Gửi Prompt**: Bạn có thể gửi các Prompt nghiệp vụ HR như:
   - *"Có kinh nghiệm nào liên quan tới ReactJS trên 2 năm không?"*
   - *"Đánh giá mức độ phù hợp của tính cách ứng viên so với công ty năng động"*
   - *"Phân tích các lỗ hổng (gap) trong thời gian làm việc của ứng viên này."*
3. **Kết quả**: AI sẽ phân tích dựa trên sự thấu hiểu CV và trả lời bạn. Toàn bộ lịch sử trao đổi của phiên làm việc đó sẽ được lưu ở cửa sổ chat để nối tiếp logic câu chuyện.
