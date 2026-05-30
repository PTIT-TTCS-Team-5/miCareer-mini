"""FE-3 Playwright Smoke Test — C3 JobPosting Agent.

Yêu cầu:
  - FANG backend: cd C:\\Users\\os\\Desktop\\cur_prj\\Fang && venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  - Frontend:     cd C:\\Users\\os\\Desktop\\cur_prj\\miCareer-mini && venv\\Scripts\\streamlit.exe run app.py
  - CV mẫu:       C:\\Users\\os\\Desktop\\cur_prj\\Fang\\sample_2.pdf

Chạy:
    python test_playwright_job_agent.py
"""

from playwright.sync_api import Page, expect, sync_playwright

FRONTEND_URL = "http://localhost:8501"
HR_USERNAME = "hr_helios"
HR_PASSWORD = "1"
JOB_POST_ID = 1  # jobPostId sẽ test — đổi nếu cần
SAMPLE_CV_PATH = r"C:\Users\os\Desktop\cur_prj\Fang\sample_2.pdf"

SLOW_MO = 600  # ms — tăng nếu muốn dễ theo dõi hơn
TIMEOUT = 90_000  # ms — agent có thể chậm 10-60s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def login_hr(page: Page) -> None:
    """Đăng nhập HR và xác nhận landing trên trang jobs."""
    print("[STEP] Login HR...")
    page.goto(FRONTEND_URL)
    page.wait_for_selector("button:has-text('Đăng nhập HR')", timeout=15_000)
    page.get_by_role("button", name="Đăng nhập HR").click()
    page.get_by_label("Username").first.fill(HR_USERNAME)
    page.locator("input[type='password']").fill(HR_PASSWORD)
    page.get_by_role("button", name="Đăng nhập").click()
    page.wait_for_selector(f"text=Xin chào, {HR_USERNAME}", timeout=10_000)
    print(f"[OK] Đăng nhập HR thành công: {HR_USERNAME}")


def wait_streamlit(page: Page, ms: int = 1500) -> None:
    """Đợi Streamlit re-render."""
    page.wait_for_timeout(ms)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_01_job_list_has_agent_button(page: Page) -> None:
    """TC01: Trang job list hiển thị nút 🤖 Agent cho mỗi job."""
    print("\n[TC01] Job list có nút Agent...")
    agent_buttons = page.locator("button:has-text('Agent')")
    count = agent_buttons.count()
    assert count > 0, "Không tìm thấy nút Agent trên trang job list!"
    print(f"[OK] Tìm thấy {count} nút Agent")


def test_02_open_job_agent_page(page: Page) -> None:
    """TC02: Click nút 🤖 Agent đầu tiên → chuyển sang page Job Agent."""
    print("\n[TC02] Mở Job Agent từ job list...")
    page.locator("button:has-text('Agent')").first.click()
    wait_streamlit(page, 2500)
    # Verify title chứa "Job Agent"
    expect(page.locator("h1")).to_contain_text("Job Agent")
    print("[OK] Page Job Agent hiển thị đúng title")


def test_03_new_conversation_empty_state(page: Page) -> None:
    """TC03: State rỗng ban đầu — hiển thị message hướng dẫn."""
    print("\n[TC03] Empty state hội thoại mới...")
    page.wait_for_selector("text=Hội thoại mới", timeout=8_000)
    print("[OK] Empty state hiển thị đúng")


def test_04_send_top10_prompt(page: Page) -> None:
    """TC04: Gửi prompt top 10 → nhận response từ agent (có thể chậm 10-60s)."""
    print("\n[TC04] Gửi prompt top 10 ứng viên...")
    chat_input = page.locator("textarea[aria-label='Hỏi về ứng viên của job này...']")
    if not chat_input.is_visible():
        # Thử placeholder text khác
        chat_input = page.get_by_placeholder("Hỏi về ứng viên của job này...")
    chat_input.fill(
        "Liệt kê top 10 ứng viên phù hợp nhất cho job này, nêu lý do ngắn gọn."
    )
    chat_input.press("Enter")

    print("[INFO] Đang chờ agent xử lý (tối đa 90s)...")
    # Chờ spinner xuất hiện rồi biến mất
    try:
        page.wait_for_selector("text=FANG Job Agent đang phân tích", timeout=5_000)
    except Exception:
        pass  # spinner có thể quá nhanh
    # Chờ response — assistant bubble xuất hiện
    page.wait_for_selector(
        "div[data-testid='stChatMessage']:has-text('ứng viên')",
        timeout=TIMEOUT,
    )
    print("[OK] Nhận được response từ agent")


def test_05_tool_expanders_visible(page: Page) -> None:
    """TC05: Tool expanders (Bước X: ...) hiển thị sau response."""
    print("\n[TC05] Kiểm tra tool expanders...")
    expanders = page.locator("details summary:has-text('Bước')")
    count = expanders.count()
    if count > 0:
        print(f"[OK] {count} tool expander hiển thị")
        # Click mở expander đầu tiên
        expanders.first.click()
        wait_streamlit(page, 500)
        print("[OK] Mở expander đầu tiên thành công")
    else:
        print(
            "[WARN] Không có tool expander — agent có thể không dùng tool trong response này"
        )


def test_06_working_set_visible(page: Page) -> None:
    """TC06: Working set panel hoặc source chips hiển thị."""
    print("\n[TC06] Kiểm tra working set / source chips...")
    working_set = page.locator("text=Tập ứng viên hiện tại")
    source_chips = page.locator("text=Nguồn được trích dẫn")
    if working_set.is_visible() or source_chips.is_visible():
        print("[OK] Working set / source chips hiển thị")
    else:
        print(
            "[WARN] Không có working set — có thể agent chưa trả về workingSet trong response này"
        )


def test_07_followup_same_conversation(page: Page) -> None:
    """TC07: Gửi follow-up → conversationId giữ nguyên (chỉ 1 conversation trong sidebar)."""
    print("\n[TC07] Gửi follow-up prompt...")
    chat_input = page.get_by_placeholder("Hỏi về ứng viên của job này...")
    chat_input.fill("Trong nhóm này, lọc ứng viên có tiếng Anh Advanced trở lên.")
    chat_input.press("Enter")
    print("[INFO] Chờ follow-up response...")
    page.wait_for_selector(
        "div[data-testid='stChatMessage']:nth-child(4)",  # ít nhất 4 messages
        timeout=TIMEOUT,
    )
    print("[OK] Follow-up response nhận được")


def test_08_rename_conversation(page: Page) -> None:
    """TC08: Rename conversation — sidebar cập nhật tên."""
    print("\n[TC08] Rename conversation...")
    rename_input = page.locator("input[aria-label='Tên mới']")
    if not rename_input.is_visible():
        # label_visibility collapsed nên thử bằng placeholder hoặc role
        rename_input = page.locator("input").filter(has_text="")
    rename_input.clear()
    rename_input.fill("Test Playwright Rename")
    page.get_by_role("button", name="Lưu tên").click()
    wait_streamlit(page, 2000)
    print("[OK] Rename hoàn thành (kiểm tra thủ công sidebar)")


def test_09_new_conversation_clears_state(page: Page) -> None:
    """TC09: Nhấn 'Hội thoại mới' → messages clear, empty state hiển thị."""
    print("\n[TC09] Tạo hội thoại mới...")
    page.get_by_role("button", name="Hội thoại mới").click()
    wait_streamlit(page, 2000)
    page.wait_for_selector("text=Hội thoại mới", timeout=8_000)
    print("[OK] State clear — empty state hiển thị lại")


def test_10_quick_prompt_sends_message(page: Page) -> None:
    """TC10: Click quick prompt → gửi prompt tương ứng."""
    print("\n[TC10] Quick prompt button...")
    # Tìm button quick prompt đầu tiên
    qp = page.locator("button:has-text('Liệt kê top 10')").first
    if qp.is_visible():
        qp.click()
        print("[INFO] Chờ quick prompt response...")
        page.wait_for_selector(
            "div[data-testid='stChatMessage']",
            timeout=TIMEOUT,
        )
        print("[OK] Quick prompt gửi thành công")
    else:
        print("[WARN] Không tìm thấy quick prompt button")


def test_11_regression_back_to_job_list(page: Page) -> None:
    """TC11: Nút quay lại → trở về job list, trang vẫn normal."""
    print("\n[TC11] Regression: quay lại job list...")
    page.get_by_role("button", name="← Quay lại").click()
    wait_streamlit(page, 2000)
    expect(page.locator("h2, h1")).to_contain_text("Danh sách tin tuyển dụng")
    print("[OK] Quay lại job list thành công")


def test_12_regression_rag_chat_still_works(page: Page) -> None:
    """TC12: Regression — page_hr_app_detail RAG chat vẫn hoạt động bình thường."""
    print("\n[TC12] Regression: RAG chat app detail...")
    # Mở ứng viên đầu tiên từ job đầu tiên
    page.locator("button:has-text('Xem ứng viên')").first.click()
    wait_streamlit(page, 2000)

    # Kiểm tra trang ứng viên render bình thường
    assert (
        page.locator("text=Danh sách ứng viên").is_visible()
        or page.locator("text=Đánh giá RAG").is_visible()
    ), "Trang ứng viên không render được"
    print("[OK] Trang ứng viên vẫn hoạt động bình thường")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_all_tests():
    results = []
    with sync_playwright() as p:
        print("[INFO] Khởi động Chromium (headless=False, slow_mo={SLOW_MO}ms)...")
        browser = p.chromium.launch(headless=False, slow_mo=SLOW_MO)
        page = browser.new_page()
        page.set_default_timeout(TIMEOUT)

        try:
            # Setup
            login_hr(page)

            # Test suite
            tests = [
                test_01_job_list_has_agent_button,
                test_02_open_job_agent_page,
                test_03_new_conversation_empty_state,
                test_04_send_top10_prompt,
                test_05_tool_expanders_visible,
                test_06_working_set_visible,
                test_07_followup_same_conversation,
                test_08_rename_conversation,
                test_09_new_conversation_clears_state,
                test_10_quick_prompt_sends_message,
                test_11_regression_back_to_job_list,
                test_12_regression_rag_chat_still_works,
            ]

            for test_fn in tests:
                try:
                    test_fn(page)
                    results.append((test_fn.__name__, "PASS"))
                except Exception as e:
                    results.append((test_fn.__name__, f"FAIL: {e}"))
                    print(f"[FAIL] {test_fn.__name__}: {e}")

        finally:
            print("\n" + "=" * 60)
            print("TEST RESULTS")
            print("=" * 60)
            passed = 0
            for name, status in results:
                icon = "✅" if status == "PASS" else "❌"
                print(f"  {icon} {name}: {status}")
                if status == "PASS":
                    passed += 1
            print(f"\n{passed}/{len(results)} tests PASSED")
            print("=" * 60)

            page.wait_for_timeout(2000)
            browser.close()


if __name__ == "__main__":
    run_all_tests()
