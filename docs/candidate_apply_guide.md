# Hướng dẫn Kỹ thuật: Luồng Ứng Viên (Candidate Apply)

Tài liệu này hướng dẫn chi tiết về cách thiết lập, vận hành, và gỡ lỗi (debug) luồng ứng viên trên ứng dụng `miCareer-mini`.

## 1. Yêu cầu Hệ thống & Môi trường

Để luồng ứng viên hoạt động hoàn chỉnh, bạn cần cấu hình các biến môi trường sau trong file `.env` của `miCareer-mini`:

```env
# URL của hệ thống FANG AI Core (bắt buộc phải chạy song song)
FANG_API_URL=http://localhost:8000/v2

# Cấu hình Cloudinary (Dùng để upload và lưu trữ CV PDF)
# Lấy từ: https://console.cloudinary.com/settings/api-keys
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

> [!IMPORTANT]
> FANG Server phải đang chạy. Nếu FANG không phản hồi, luồng upload CV sẽ báo lỗi khi trigger ingestion pipeline.

## 2. Kiến trúc Luồng Hoạt Động (Code Flow)

Luồng ứng viên bắt đầu từ UI (`app.py`), tương tác với CSDL (`core/db.py`), upload file lên Cloudinary (`core/cloudinary_upload.py`), và gọi API của FANG (`core/fang_client.py`).

1. **Đăng nhập & Xem Job:**
   - Ứng viên đăng nhập bằng thông tin trong bảng `CANDIDATE` và `user` (role='CANDIDATE').
   - Hệ thống hiển thị danh sách `JOBPOSTING` công khai (chưa hết hạn).
2. **Nộp CV (Apply):**
   - Ứng viên chọn nộp hồ sơ.
   - Hàm `get_candidate_existing_cv` trong `db.py` kiểm tra xem ứng viên đã có CV trên hệ thống chưa. Nếu có, cho phép chọn dùng lại CV cũ.
   - Nếu chọn upload CV mới (file PDF), `upload_cv_pdf` sẽ đẩy file lên thư mục `Home/miCareer-mini` trên Cloudinary và lấy về `secure_url`.
3. **Lưu Trữ & Kích hoạt FANG:**
   - Tạo bản ghi trong `JOBAPPLICATION` với `cvSnapUrl` là link Cloudinary vừa nhận được.
   - Gọi `fang_client.trigger_ingestion(job_app_id, cv_snap_url)` để gửi yêu cầu xử lý CV sang FANG qua API `POST /v2/ingestion/jobs`.
4. **Theo Dõi Trạng Thái (Polling):**
   - Giao diện người dùng sử dụng polling (vòng lặp gọi `fang_client.get_ingestion_status`) để cập nhật thanh tiến trình (Progress Bar).
   - FANG sẽ xử lý (Parse -> Chunk -> Embed -> Lưu Vector).
   - Khi trạng thái chuyển thành `SUCCESS`, ứng viên nhận được thông báo hoàn tất.

## 3. Kịch Bản Kiểm Thử (Test Scenario)

Dưới đây là các bước để kiểm tra E2E luồng ứng viên:

1. **Chuẩn bị dữ liệu:** Đảm bảo trong database đã có ít nhất 1 tài khoản Candidate (VD: candidate1 / 123456) và 1 Job Posting đang mở.
2. **Đăng nhập:** Mở `miCareer-mini` UI, chọn phần "Ứng viên" và đăng nhập.
3. **Nộp CV mới:**
   - Chọn một công việc và nhấn "Nộp CV".
   - Upload một file PDF hợp lệ (VD: CV mẫu).
   - Nhấn "Xác nhận nộp CV".
4. **Quan sát Polling:** Theo dõi thanh tiến trình. Nó sẽ hiển thị trạng thái `PENDING` -> `PROCESSING` -> `SUCCESS`.
5. **Kiểm tra bên HR:**
   - Đăng xuất và đăng nhập vào tài khoản HR.
   - Chọn cùng một công việc và xem danh sách ứng viên.
   - Mở chi tiết ứng viên vừa nộp. Bạn sẽ thấy thông báo "✅ CV đã xử lý thành công — AI sẵn sàng phân tích" và có thể bắt đầu chat với FANG Co-pilot.

## 4. Gỡ Lỗi (Troubleshooting)

| Vấn đề | Nguyên nhân phổ biến | Cách khắc phục |
| :--- | :--- | :--- |
| **Lỗi Upload Cloudinary** | Sai cấu hình credentials trong `.env` hoặc file upload không hợp lệ. | Kiểm tra lại `CLOUDINARY_*` trong `.env`. Đảm bảo file upload là PDF nhỏ hơn 10MB. |
| **Lỗi `ConnectionError`** | FANG API không hoạt động. | Kiểm tra terminal chạy FANG. Đảm bảo cổng 8000 đang mở và `FANG_API_URL` cấu hình đúng. |
| **Polling bị Timeout** | FANG xử lý CV quá lâu (vượt quá 60s) hoặc bị kẹt. | Kiểm tra log của FANG để xem quá trình Parse/Embed có bị treo hay không. Có thể do LLM provider phản hồi chậm. |
| **Ingestion FAILED** | FANG không thể phân tích nội dung PDF. | Xem chi tiết thông báo lỗi trong UI hoặc kiểm tra log FANG. Có thể CV là dạng hình ảnh không có text layer. |

> [!WARNING]
> Không chia sẻ file `.env` chứa các API Key thật (đặc biệt là Cloudinary Secret) lên bất kỳ kho lưu trữ mã nguồn công khai nào.
