from playwright.sync_api import sync_playwright


def run_test():
    # Khởi động trình duyệt Chromium ở chế độ có giao diện (headless=False)
    # Thêm slow_mo=1000 để làm chậm các bước 1 giây, giúp bạn dễ dàng theo dõi trực quan
    with sync_playwright() as p:
        print("[INFO] Khoi dong trinh duyet Chromium...")
        browser = p.chromium.launch(headless=False, slow_mo=1000)

        # Tạo một trang tab mới
        page = browser.new_page()

        # 1. Truy cập vào trang web miCareer-mini (Streamlit)
        print("[INFO] Dang truy cap miCareer-mini (Streamlit)...")
        page.goto("http://localhost:8501")

        # Đợi trang web tải xong và hiển thị nút
        page.wait_for_selector("button:has-text('Đăng nhập HR')")

        # Kiểm tra tiêu đề trang
        assert "miCareer-mini" in page.title()
        print("[SUCCESS] Trang chu miCareer-mini da hien thi chinh xac!")

        # 2. Click nút "Đăng nhập HR" ở trang chủ
        print("[INFO] Dang Click chon 'Dang nhap HR'...")
        page.get_by_role("button", name="Đăng nhập HR").click()

        # 3. Đợi form đăng nhập xuất hiện và điền tài khoản HR
        # Tài khoản 'hr_helios' / '123456' lấy từ dữ liệu hạt giống (seed) trong CSDL
        print("[INFO] Dien Username va Password cua HR...")
        page.get_by_label("Username").first.fill("hr_helios")
        page.locator("input[type='password']").fill("1")

        # 4. Click nút "Đăng nhập" trong form
        print("[INFO] Bam nut 'Dang nhap'...")
        page.get_by_role("button", name="Đăng nhập").click()

        # 5. Xác nhận đăng nhập thành công
        # Sau khi đăng nhập, hệ thống sẽ chuyển trang và hiển thị câu chào "Xin chào, Nguyễn Thu Hà"
        print("[INFO] Doi he thong xu ly dang nhap...")
        page.wait_for_timeout(2000)  # Đợi 2 giây cho Streamlit re-render trang mới

        welcome_locator = page.locator("text=Xin chào, hr_helios")
        if welcome_locator.is_visible():
            print("[SUCCESS] Dang nhap HR thanh cong! Giao dien hien thi dung ten HR.")
        else:
            print(
                "[FAILED] Khong tim thay cau chao HR. Hay kiem tra xem server FANG va DB da chay chua."
            )

        # Đóng trình duyệt
        browser.close()
        print("[INFO] Da dong trinh duyet. Ket thuc test!")


if __name__ == "__main__":
    run_test()
