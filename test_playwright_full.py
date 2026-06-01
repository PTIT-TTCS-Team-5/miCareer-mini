"""miCareer-mini Full E2E E2E E2E Automated Integration Test Suite.

Prerequisites:
  - FANG Backend: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 (running)
  - miCareer Streamlit: python -m streamlit run app.py (running)
"""

import sys
import time

from playwright.sync_api import Page, expect, sync_playwright

FRONTEND_URL = "http://127.0.0.1:8501"
HR_USERNAME = "hr_microshop"
HR_PASSWORD = "1"
CANDIDATE_USERNAME = "nguyenhaihung"
CANDIDATE_PASSWORD = "1"
TARGET_JOB_TITLE = "Junior Frontend Developer (ReactJS)"
TARGET_COMPANY_NAME = "MicroShop Corp"
TARGET_CANDIDATE_TEXT = "Hải Hưng Nguyễn"

AGENT_TIMEOUT = 90000
DEFAULT_TIMEOUT = 15000
SLOW_MO = 500
JOB_AGENT_QUICK_PROMPTS = [
    "Xếp hạng 10 ứng viên phù hợp nhất.",
    "Những ứng viên nào có chứng chỉ tiếng Anh TOEIC từ 600 trở lên?",
    "So sánh 3 ứng viên nổi bật nhất.",
]


def wait_streamlit(page: Page, ms: int = 2000) -> None:
    page.wait_for_timeout(ms)


def target_job_block(page: Page):
    return (
        page.locator("[data-testid='stVerticalBlock']")
        .filter(has_text=TARGET_JOB_TITLE)
        .filter(has=page.locator("button:has-text('Agent')"))
        .last
    )


def target_candidate_block(page: Page):
    return (
        page.locator("[data-testid='stVerticalBlock']")
        .filter(has_text=TARGET_CANDIDATE_TEXT)
        .filter(has=page.locator("button:has-text('Đánh giá CV')"))
        .first
    )


def wait_for_message_count(
    page: Page, count: int, timeout: int = AGENT_TIMEOUT
) -> None:
    page.locator("div[data-testid='stChatMessage']").nth(count - 1).wait_for(
        state="visible", timeout=timeout
    )
    wait_streamlit(page, 1500)


def get_conversation_buttons(page: Page):
    """Helper to retrieve only the conversation buttons in the left sidebar column."""
    left_col = page.locator("[data-testid='stColumn']").filter(
        has=page.locator("button:has-text('➕ Hội thoại mới')")
    )
    all_buttons = left_col.locator("button")
    count = all_buttons.count()

    conv_buttons = []
    # Current JobPosting Agent empty-state quick prompts are the last 3 prompt buttons.
    limit = count - len(JOB_AGENT_QUICK_PROMPTS)
    for i in range(limit):
        btn = all_buttons.nth(i)
        txt = btn.inner_text().strip()
        if txt in [
            "➕ Hội thoại mới",
            "💾 Lưu tên",
            "🗑️ Lưu trữ hội thoại này",
            "← Quay lại",
            "",
        ]:
            continue
        conv_buttons.append(btn)
    return conv_buttons


def open_first_tool_output(page: Page) -> None:
    outer = page.locator("details summary:has-text('Bước')").last
    outer.click()
    wait_streamlit(page, 800)
    nested = page.locator("details summary:has-text('📤 Kết quả lệnh')").last
    nested.click()
    wait_streamlit(page, 800)
    expect(page.locator("body")).to_contain_text("data")


def run_test_suite():
    results = []

    def log_result(tc_id, tc_name, status, details=""):
        results.append((tc_id, tc_name, status, details))
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"[{status}] {tc_id}: {tc_name} {icon} {details}")

    with sync_playwright() as p:
        print("[INFO] Launching Chromium browser...")
        browser = p.chromium.launch(headless=True, slow_mo=SLOW_MO)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        # ---------------------------------------------------------------------------
        # TC01: Login HR
        # ---------------------------------------------------------------------------
        try:
            print(f"\n[STEP] TC01 — Login HR as {HR_USERNAME}...")
            page.goto(FRONTEND_URL)
            page.wait_for_selector(
                "button:has-text('Đăng nhập HR')", timeout=DEFAULT_TIMEOUT
            )
            page.get_by_role("button", name="Đăng nhập HR").click()

            page.get_by_label("Username").first.fill(HR_USERNAME)
            page.locator("input[type='password']").fill(HR_PASSWORD)
            page.get_by_role("button", name="Đăng nhập").click()

            page.wait_for_selector(
                f"text=Xin chào, {HR_USERNAME}", timeout=DEFAULT_TIMEOUT
            )
            log_result("TC01", "Login HR and verify welcome header", "PASS")
        except Exception as e:
            log_result("TC01", "Login HR and verify welcome header", "FAIL", str(e))
            browser.close()
            sys.exit(1)

        # ---------------------------------------------------------------------------
        # TC02: Job List Render
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC02 — Verify Job list has target job and buttons...")
            expect(page.locator("body")).to_contain_text("Danh sách tin tuyển dụng")
            expect(page.locator("body")).to_contain_text(TARGET_JOB_TITLE)

            job_block = target_job_block(page)
            xem_job_btns = job_block.locator("button:has-text('Xem job')")
            xem_uv_btns = job_block.locator("button:has-text('Xem ứng viên')")
            agent_btns = job_block.locator("button:has-text('Agent')")

            if (
                xem_job_btns.count() > 0
                and xem_uv_btns.count() > 0
                and agent_btns.count() > 0
            ):
                log_result(
                    "TC02",
                    "Verify Job list renders with details, applications and Agent buttons",
                    "PASS",
                )
            else:
                log_result(
                    "TC02",
                    "Verify Job list renders correctly",
                    "FAIL",
                    "Missing entry buttons",
                )
        except Exception as e:
            log_result("TC02", "Verify Job list renders correctly", "FAIL", str(e))

        # ---------------------------------------------------------------------------
        # TC03: Job Detail & Edit Smoke
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC03 — Navigate to job details & edit page...")
            target_job_block(page).locator("button:has-text('Xem job')").first.click()
            wait_streamlit(page, 2000)

            expect(page.locator("body")).to_contain_text("Thông tin Job")
            expect(page.locator("body")).to_contain_text(TARGET_JOB_TITLE)

            # Click Sửa Job
            page.locator("button:has-text('Sửa Job')").first.click()
            wait_streamlit(page, 3000)

            # Verify tabs
            expect(page.locator("body")).to_contain_text("📝 Nội dung")
            expect(page.locator("body")).to_contain_text("⚙️ Cài đặt & Kỹ năng")

            log_result("TC03", "Verify job metadata and edit tabs render", "PASS")

            # Go back to jobs list
            page.locator("button:has-text('← Quay lại danh sách Job')").first.click()
            wait_streamlit(page, 2000)
        except Exception as e:
            log_result(
                "TC03", "Verify job metadata and edit tabs render", "FAIL", str(e)
            )

        # ---------------------------------------------------------------------------
        # TC04: Single Application full-CV Chat
        # ---------------------------------------------------------------------------
        try:
            print(
                "\n[STEP] TC04 — Open applications list and run full-CV chat on Hưng's profile..."
            )
            target_job_block(page).locator(
                "button:has-text('Xem ứng viên')"
            ).first.click()
            wait_streamlit(page, 3000)

            expect(page.locator("body")).to_contain_text("Danh sách ứng viên")
            expect(page.locator("body")).to_contain_text(TARGET_CANDIDATE_TEXT)

            target_candidate_block(page).locator(
                "button:has-text('Đánh giá CV')"
            ).first.click()
            wait_streamlit(page, 4000)

            expect(page.locator("body")).to_contain_text(
                f"Hồ sơ: {TARGET_CANDIDATE_TEXT}"
            )
            expect(page.locator("body")).to_contain_text("🤖 FANG HR Co-pilot")

            # Write evaluation question
            chat_input = page.get_by_placeholder("Hỏi về ứng viên này...")
            chat_input.fill("Ứng viên này có kinh nghiệm làm việc với Next.js không?")
            chat_input.press("Enter")

            print("[INFO] Waiting for FANG Co-pilot response...")
            page.wait_for_selector("text=Model:", timeout=AGENT_TIMEOUT)

            # Verify the response is visible
            expect(page.locator("body")).to_contain_text("Next.js")
            log_result(
                "TC04",
                "Run single candidate full-CV chat & verify response metadata",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC04",
                "Run single candidate full-CV chat & verify response metadata",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC05: Full-CV Chat negative/edge UI check (SKIP)
        # ---------------------------------------------------------------------------
        print("\n[STEP] TC05 — Verify negative CVPARSED block...")
        log_result(
            "TC05",
            "Verify UI blocks chat if CV has no parsed text",
            "SKIP",
            "All applications in database have parsed CVs",
        )

        # ---------------------------------------------------------------------------
        # TC06: AI Ranking regression
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC06 — AI Ranking regression...")
            # Go back to applications page
            page.locator(
                "button:has-text('← Quay lại danh sách Ứng viên')"
            ).first.click()
            wait_streamlit(page, 2000)

            # Click "🚀 Chạy AI Ranking"
            page.locator("button:has-text('🚀 Chạy AI Ranking')").first.click()
            wait_streamlit(page, 4000)

            # Verify ranked list is rendered
            expect(page.locator("body")).to_contain_text("🥇")

            # Click "Xem" for the top candidate
            page.get_by_role("button", name="Xem", exact=True).first.click()
            wait_streamlit(page, 3000)

            expect(page.locator("body")).to_contain_text("Hồ sơ:")
            log_result(
                "TC06",
                "Verify AI Ranking calculates matches and navigates to profile detail",
                "PASS",
            )

            # Return to candidate list
            page.locator(
                "button:has-text('← Quay lại danh sách Ứng viên')"
            ).first.click()
            wait_streamlit(page, 2000)
        except Exception as e:
            log_result(
                "TC06",
                "Verify AI Ranking calculates matches and navigates to profile detail",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC07: JobPosting Agent full flow
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC07 — Open JobPosting Agent and verify flows...")
            # Click "🤖 Mở Job Agent"
            page.locator("button:has-text('🤖 Mở Job Agent')").first.click()
            wait_streamlit(page, 3000)

            # Click "➕ Hội thoại mới" to clear history for deterministic counts
            page.locator("button:has-text('➕ Hội thoại mới')").first.click()
            wait_streamlit(page, 2000)

            # Check suggested prompts
            for prompt in JOB_AGENT_QUICK_PROMPTS:
                expect(
                    page.locator(f"button:has-text('{prompt}')").first
                ).to_be_visible()

            # Send top candidates prompt
            chat_input = page.get_by_placeholder(
                "Tìm nhanh ứng viên sáng giá cùng FANG."
            )
            chat_input.fill(
                "Liệt kê top 10 ứng viên phù hợp nhất cho job này, nêu lý do ngắn gọn."
            )
            chat_input.press("Enter")

            print("[INFO] Waiting for agent analysis response...")
            wait_for_message_count(page, 2)

            expect(page.locator("body")).to_contain_text("ứng viên", timeout=15000)
            open_first_tool_output(page)
            expect(page.locator("body")).to_contain_text(
                "get_job_candidate_ranking", timeout=15000
            )

            # Send structured TOEIC certificate follow-up in same conversation
            chat_input = page.get_by_placeholder(
                "Tìm nhanh ứng viên sáng giá cùng FANG."
            )
            chat_input.fill(JOB_AGENT_QUICK_PROMPTS[1])
            chat_input.press("Enter")

            print("[INFO] Waiting for follow-up response...")
            wait_for_message_count(page, 4)

            expect(page.locator("body")).to_contain_text("TOEIC")
            open_first_tool_output(page)
            expect(page.locator("body")).to_contain_text(
                "find_candidates_by_language_certificate"
            )
            expect(page.locator("body")).to_contain_text("filters_used")

            # Send top-3 comparison prompt to exercise deterministic ranking explanation
            chat_input = page.get_by_placeholder(
                "Tìm nhanh ứng viên sáng giá cùng FANG."
            )
            chat_input.fill(JOB_AGENT_QUICK_PROMPTS[2])
            chat_input.press("Enter")
            wait_for_message_count(page, 6)
            expect(page.locator("body")).to_contain_text("So sánh")

            # Expand the working set expander in the right column
            print("[INFO] Expanding working set expander...")
            page.locator("details summary:has-text('📋')").first.click()
            wait_streamlit(page, 1000)

            # Click candidate chip in working set
            chip = page.locator("button:has-text('[')").first
            chip_name = chip.inner_text().split("[")[0].strip()
            print(f"[INFO] Clicking candidate chip: {chip_name}")
            chip.click()
            wait_streamlit(page, 3000)

            # Verify detail profile page
            expect(page.locator("body")).to_contain_text(f"Hồ sơ: {chip_name}")

            # Go back to Job Agent
            page.locator(
                "button:has-text('← Quay lại danh sách Ứng viên')"
            ).first.click()
            wait_streamlit(page, 2000)
            page.locator("button:has-text('🤖 Mở Job Agent')").first.click()
            wait_streamlit(page, 3000)

            # Rename conversation using unique timestamp
            unique_rename_title = f"Smoke Test {int(time.time())}"
            print(f"[INFO] Renaming conversation to: {unique_rename_title}")

            left_col = page.locator("[data-testid='stColumn']").filter(
                has=page.locator("button:has-text('➕ Hội thoại mới')")
            )
            try:
                rename_input = left_col.locator(
                    "input[aria-label='Tên mới'], [data-testid='stTextInput'] input"
                ).first
                rename_input.click()
                rename_input.press("Control+A")
                rename_input.press("Backspace")
                rename_input.fill(unique_rename_title)
                rename_input.press("Enter")

                save_btn = left_col.locator("button:has-text('💾 Lưu tên')").first
                if save_btn.is_enabled():
                    save_btn.click()
                wait_streamlit(page, 3000)

                expect(left_col).to_contain_text(unique_rename_title)

                # Create new conversation
                page.get_by_role("button", name="➕ Hội thoại mới").click()
                wait_streamlit(page, 2000)

                # Verify old working set is cleared
                expect(page.locator("body")).not_to_contain_text("Top 10 ứng viên")

                # Select the timestamped conversation again to archive it
                left_col.locator(f"button:has-text('{unique_rename_title}')").click()
                wait_streamlit(page, 3000)

                # Archive it
                left_col.locator(
                    "button:has-text('🗑️ Lưu trữ hội thoại này')"
                ).first.click()
                wait_streamlit(page, 3000)

                # Verify removed from sidebar
                expect(left_col).not_to_contain_text(unique_rename_title)

                log_result(
                    "TC07",
                    "Verify JobPosting Agent full workflow, rename, and archive",
                    "PASS",
                )
            except Exception as inner_e:
                # Diagnostics on failure
                screenshot_path = "C:/Users/os/.gemini/antigravity/brain/022a4434-4c18-4c77-9921-fd3295e6ffc6/tc07_failure.png"
                page.screenshot(path=screenshot_path)
                print(
                    f"[ERROR DIAGNOSTICS] Saved failure screenshot to {screenshot_path}"
                )
                try:
                    print("[ERROR DIAGNOSTICS] Left column HTML content:")
                    print(left_col.inner_html())
                except Exception as html_e:
                    print(f"[ERROR DIAGNOSTICS] Could not extract HTML: {html_e}")
                raise inner_e
        except Exception as e:
            log_result(
                "TC07",
                "Verify JobPosting Agent full workflow, rename, and archive",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC08: Candidate Flow Smoke
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC08 — Candidate Flow Smoke...")
            # Return to jobs list & logout
            page.locator("button:has-text('← Quay lại')").first.click()
            wait_streamlit(page, 2000)
            page.locator("button:has-text('🚪 Đăng xuất')").first.click()
            wait_streamlit(page, 2000)

            # Login Candidate
            page.get_by_role("button", name="Đăng nhập Ứng viên").click()
            page.get_by_label("Username").first.fill(CANDIDATE_USERNAME)
            page.locator("input[type='password']").fill(CANDIDATE_PASSWORD)
            page.get_by_role("button", name="Đăng nhập").click()

            page.wait_for_selector(
                "text=Xin chào, Hải Hưng Nguyễn", timeout=DEFAULT_TIMEOUT
            )
            expect(page.locator("body")).to_contain_text("Công việc đang tuyển dụng")

            # Click "Xem" for second job (which is unapplied)
            page.get_by_role("button", name="Xem", exact=True).nth(1).click()
            wait_streamlit(page, 2000)

            # Verify apply page layout & CV button
            expect(page.locator("body")).to_contain_text("Thông tin Job")
            expect(page.locator("button:has-text('🚀 Nộp CV')").first).to_be_visible()

            log_result(
                "TC08",
                "Verify candidate login, job list render, and job detail page",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC08",
                "Verify candidate login, job list render, and job detail page",
                "FAIL",
                str(e),
            )

        # Final cleanup
        context.close()
        browser.close()

    print("\n" + "=" * 80)
    print(f"{'TEST CASE SUMMARY':^80}")
    print("=" * 80)
    print(
        f"| {'ID':<6} | {'Test Case Name':<45} | {'Status':<6} | {'Details/Errors':<15} |"
    )
    print("-" * 80)

    passed_cnt = 0
    for tc_id, name, status, details in results:
        print(f"| {tc_id:<6} | {name:<45} | {status:<6} | {details[:15]:<15} |")
        if status in ["PASS", "WARN"]:
            passed_cnt += 1

    print("=" * 80)
    print(f"Result: {passed_cnt}/{len(results)} tests PASSED")
    print("=" * 80)

    if any(r[2] == "FAIL" for r in results):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_test_suite()
