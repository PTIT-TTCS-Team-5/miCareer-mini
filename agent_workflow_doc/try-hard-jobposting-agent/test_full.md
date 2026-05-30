# Báo cáo Chi tiết: Kiểm thử Tích hợp (Integration Testing) — C3 JobPosting Agent

Tài liệu này báo cáo chi tiết kết quả chạy test và các giải pháp kỹ thuật đã áp dụng để hoàn thành kiểm thử tích hợp (integration testing) end-to-end cho tính năng **C3 JobPosting Agent** (AI Co-pilot hỗ trợ tuyển dụng/ứng viên) trên cả frontend và backend.

---

## 1. Tổng quan Dự án & Mục tiêu Kiểm thử (Objectives)
Mục tiêu là xây dựng một kịch bản test tự động bằng **Playwright** (`test_playwright_job_agent.py`) để chạy toàn bộ luồng nghiệp vụ của JobPosting Agent trên giao diện Streamlit, kiểm tra kết nối với FANG Backend API, truy vấn cơ sở dữ liệu PostgreSQL và đảm bảo các chức năng không bị crash.

Kịch bản bao gồm **15 test cases (TC01 - TC15)** kiểm tra:
* Quy trình đăng nhập và điều hướng của HR.
* Khởi tạo, gửi truy vấn (query) và phản hồi từ AI Agent (bao gồm kiểm tra tool expanders và working set).
* Tương tác đa lượt (multi-turn follow-up) trong cùng một hội thoại.
* Điều hướng chi tiết ứng viên (app detail) từ working set chips.
* Đổi tên (rename) và lưu trữ (archive) hội thoại.
* Các bài kiểm tra hồi quy (regression tests) đối với tính năng RAG Chat và AI Ranking cũ.

---

## 2. Thách thức Kỹ thuật & Giải pháp Tối ưu (Technical Challenges & Solutions)

Trong quá trình phát triển kịch bản test tự động, nhóm đã phát hiện và xử lý thành công một số đặc thù của Streamlit UI và cơ chế persistent database:

### Thách thức 1: Định vị cột Sidebar trong Streamlit (`stColumn` vs `stSidebar`)
* **Vấn đề**: Giao diện frontend sử dụng layout 2 cột chia tỉ lệ (`st.columns([1, 3])`) để giả lập sidebar bên trái thay vì dùng sidebar mặc định của Streamlit (`st.sidebar`). Do đó, các bộ chọn (selectors) Playwright trỏ đến `[data-testid='stSidebar']` đều bị lỗi timeout hoặc không tìm thấy element.
* **Giải pháp**: Nhận diện cột sidebar bên trái bằng cách filter cột chứa nút bấm "Hội thoại mới" đặc trưng:
  ```python
  left_col = page.locator("[data-testid='stColumn']").filter(
      has=page.locator("button:has-text('➕ Hội thoại mới')")
  )
  ```
  Giải pháp này giúp định vị chính xác khu vực sidebar mà không bị ảnh hưởng bởi nút "Quay lại" (nằm trong một layout cột khác ở phía trên).

### Thách thức 2: Tránh xung đột dữ liệu cũ từ các lượt chạy trước (Persistent Database)
* **Vấn đề**: Cơ sở dữ liệu local lưu trữ lịch sử các hội thoại trước đó. Khi chạy lại test, các hội thoại cũ mang tên `"Liệt kê top 10..."` vẫn hiển thị ở sidebar, khiến việc đếm số hội thoại hoặc kiểm tra chức năng đổi tên (rename) và lưu trữ (archive) bị sai lệch kết quả.
* **Giải pháp**:
  * **TC07 (Multi-turn)**: Đo số lượng hội thoại trước và sau khi gửi follow-up query. Nếu số lượng bằng nhau, hệ thống chứng minh Agent hoạt động đúng cơ chế đa lượt trên cùng một hội thoại mà không tạo mới (branching).
  * **TC09 (Rename)** & **TC12 (Archive)**: Thay đổi tên hội thoại đang hoạt động thành một chuỗi duy nhất chứa timestamp (`Smoke Test Conv <timestamp>` và `Archive Test <timestamp>`). Sau đó kiểm tra sự xuất hiện hoặc biến mất của chuỗi duy nhất này trong sidebar, loại bỏ hoàn toàn khả năng trùng lặp dữ liệu.

### Thách thức 3: Click chính xác Quick Prompts
* **Vấn đề**: Tên của các quick prompt ở phía dưới sidebar có thể chứa các từ khóa trùng lặp với tên hội thoại cũ phía trên (ví dụ: `"Liệt kê top 10..."`).
* **Giải pháp**: Xác định vị trí nút quick prompt bằng cách chọn từ dưới lên (quick prompts luôn là 6 nút cuối cùng trong sidebar column):
  ```python
  all_buttons = left_col.locator("button")
  first_qp_btn = all_buttons.nth(all_buttons.count() - 6)  # Nút quick prompt đầu tiên
  ```

---

## 3. Bảng kết quả kiểm thử chi tiết (Test Case Summary)

Toàn bộ 15 test cases đã chạy thành công với kết quả **15/15 PASS**:

| ID | Test Case Name | Status | Details/Errors |
| :--- | :--- | :---: | :--- |
| **TC01** | Đăng nhập HR và kiểm tra welcome header | **PASS** | Đăng nhập thành công tài khoản `hr_helios` |
| **TC02** | Danh sách Job hiển thị nút 🤖 Agent | **PASS** | Tìm thấy 4 nút Agent tương ứng với danh sách job |
| **TC03** | Mở trang Job Agent và kiểm tra bố cục (layout) | **PASS** | Render đầy đủ metadata của Helios Software và các quick prompts |
| **TC04** | Gửi prompt tìm kiếm Top 10 ứng viên (timeout 90s) | **PASS** | Nhận được phản hồi phân tích ứng viên từ Agent thành công |
| **TC05** | Kiểm tra hiển thị và tương tác của Tool Expanders | **PASS** | Click mở expander "Bước" và đọc dữ liệu JSON nội bộ thành công |
| **TC06** | Xác minh hiển thị Working Set & Source Chips | **PASS** | Render đúng danh sách ứng viên đề xuất dưới dạng label chip |
| **TC07** | Thực hiện hội thoại đa lượt (multi-turn follow-up) | **PASS** | Gửi yêu cầu lọc tiếng Anh, không tạo hội thoại mới |
| **TC08** | Click chip ứng viên chuyển hướng đến trang hồ sơ | **PASS** | Click chip Vũ Đức Thành, chuyển hướng và quay lại thành công |
| **TC09** | Quay lại Job Agent và thực hiện đổi tên hội thoại | **PASS** | Đổi tên thành công sang chuỗi độc bản và xác nhận sidebar cập nhật |
| **TC10** | Tạo "Hội thoại mới" và xác minh xóa sạch trạng thái cũ | **PASS** | Clear panel chat và working set thành công |
| **TC11** | Kích hoạt hội thoại thông qua Quick Prompt | **PASS** | Click quick prompt và nhận phản hồi từ Agent thành công |
| **TC12** | Lưu trữ (archive) hội thoại | **PASS** | Lưu trữ thành công hội thoại và xác nhận biến mất khỏi sidebar |
| **TC13** | Regression: Vào Job Agent từ trang chi tiết Job (Xem job) | **PASS** | Nút "Hỏi Agent về job này" hoạt động ổn định |
| **TC14** | Regression: Đánh giá RAG và Co-pilot cũ hoạt động bình thường | **PASS** | Trang RAG Profile của ứng viên không bị ảnh hưởng bởi Job Agent |
| **TC15** | Regression: AI Ranking và Agent Entry trên trang ứng viên | **PASS** | Các nút "Chạy AI Ranking" và "Mở Job Agent" hiển thị đúng vị trí |

---

## 4. Kết luận (Conclusion)
* Tính năng **JobPosting Agent** đã được tích hợp hoàn chỉnh và hoạt động ổn định trên cả môi trường Frontend và Backend.
* Bộ kiểm thử Playwright đã khắc phục được toàn bộ các yếu tố bất định (flakiness) liên quan đến Streamlit render và persistent database, đảm bảo kết quả kiểm thử nhất quán và đáng tin cậy cho các chu kỳ phát triển (CI/CD) tiếp theo.
