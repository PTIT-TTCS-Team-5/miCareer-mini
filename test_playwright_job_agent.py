"""FE-3 Playwright Integration Test Suite — C3 JobPosting Agent.

Prerequisites:
  - FANG Backend: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 (running)
  - miCareer Streamlit: python -m streamlit run app.py (running)
"""

import sys
import time

from playwright.sync_api import Page, expect, sync_playwright

FRONTEND_URL = "http://localhost:8501"
HR_USERNAME = "hr_helios"
HR_PASSWORD = "1"
AGENT_TIMEOUT = 90000
DEFAULT_TIMEOUT = 15000
SLOW_MO = 500

_QUICK_PROMPTS = [
    "Liệt kê top 10 ứng viên phù hợp nhất cho job này, nêu lý do ngắn gọn.",
    "Trong nhóm này, lọc ứng viên có tiếng Anh Advanced trở lên.",
    "So sánh 3 ứng viên nổi bật nhất trong nhóm hiện tại.",
    "Ứng viên nào có kinh nghiệm backend + AI tốt nhất?",
    "Đếm số ứng viên theo trạng thái tuyển dụng hiện tại.",
    "Gợi ý shortlist 5 ứng viên nên phỏng vấn trước.",
]


def wait_streamlit(page: Page, ms: int = 1500) -> None:
    page.wait_for_timeout(ms)


def get_conversation_buttons(page: Page):
    """Helper to retrieve only the conversation buttons in the left sidebar column."""
    left_col = page.locator("[data-testid='stColumn']").filter(
        has=page.locator("button:has-text('➕ Hội thoại mới')")
    )
    all_buttons = left_col.locator("button")
    count = all_buttons.count()
    print(f"[DEBUG] get_conversation_buttons: count={count}")
    for i in range(count):
        print(f"[DEBUG]   Button {i}: '{all_buttons.nth(i).inner_text().strip()}'")

    conv_buttons = []
    # The last 6 buttons are quick prompts
    limit = count - 6
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
    print(f"[DEBUG] get_conversation_buttons: returned {len(conv_buttons)} buttons")
    return conv_buttons


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
        # Set default timeout for fast UI failure feedback
        page.set_default_timeout(DEFAULT_TIMEOUT)

        # ---------------------------------------------------------------------------
        # TC01: Login HR
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC01 — Login HR...")
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
            return

        # ---------------------------------------------------------------------------
        # TC02: Job List contains Agent buttons
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC02 — Verify Job list has Agent button...")
            expect(page.locator("body")).to_contain_text("Danh sách tin tuyển dụng")
            agent_buttons = page.locator("button:has-text('Agent')")
            count = agent_buttons.count()
            if count > 0:
                log_result(
                    "TC02", f"Verify Job list displays {count} Agent button(s)", "PASS"
                )
            else:
                log_result(
                    "TC02",
                    "Verify Job list displays Agent button",
                    "FAIL",
                    "No Agent button found",
                )
        except Exception as e:
            log_result("TC02", "Verify Job list displays Agent button", "FAIL", str(e))

        # ---------------------------------------------------------------------------
        # TC03: Open Job Agent Page
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC03 — Navigate to Job Agent...")
            page.locator("button:has-text('Agent')").first.click()
            wait_streamlit(page, 2500)

            expect(page.locator("body")).to_contain_text("Job Agent:")

            # Verify context metadata & layout
            expect(page.locator("body")).to_contain_text("Helios Software")
            expect(page.locator("body")).to_contain_text("Hết hạn:")

            # Verify basic elements
            expect(
                page.locator("button:has-text('Hội thoại mới')").first
            ).to_be_visible()
            expect(
                page.locator("button:has-text('Liệt kê top 10')").first
            ).to_be_visible()
            expect(page.locator("text=Hội thoại mới").first).to_be_visible()

            log_result("TC03", "Verify Job Agent page layout & quick prompts", "PASS")
        except Exception as e:
            log_result(
                "TC03", "Verify Job Agent page layout & quick prompts", "FAIL", str(e)
            )

        # ---------------------------------------------------------------------------
        # TC04: Gửi prompt top 10
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC04 — Send top 10 candidates query...")
            chat_input = page.get_by_placeholder("Hỏi về ứng viên của job này...")
            chat_input.fill(
                "Liệt kê top 10 ứng viên phù hợp nhất cho job này, nêu lý do ngắn gọn."
            )
            chat_input.press("Enter")

            print("[INFO] Waiting for agent analysis response (up to 90s)...")
            # Wait for second stChatMessage locator to load using Playwright wait_for
            page.locator("div[data-testid='stChatMessage']").nth(1).wait_for(
                state="visible", timeout=AGENT_TIMEOUT
            )

            # Check response contains key words
            expect(
                page.locator("div[data-testid='stChatMessage']").nth(1)
            ).to_contain_text("ứng viên")
            log_result(
                "TC04", "Send query for top 10 candidates & verify response", "PASS"
            )
        except Exception as e:
            log_result(
                "TC04",
                "Send query for top 10 candidates & verify response",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC05: Tool expanders
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC05 — Verify tool expanders...")
            expanders = page.locator("details summary:has-text('Bước')")
            if expanders.count() > 0:
                expanders.first.click()
                wait_streamlit(page, 1000)
                # Verify internal json details loaded
                expect(page.locator("details").first).to_contain_text("{")
                log_result("TC05", "Verify tool expander exists and can open", "PASS")
            else:
                log_result(
                    "TC05",
                    "Verify tool expander exists and can open",
                    "WARN",
                    "No expanders generated by model",
                )
        except Exception as e:
            log_result(
                "TC05", "Verify tool expander exists and can open", "FAIL", str(e)
            )

        # ---------------------------------------------------------------------------
        # TC06: Working Set & Source chips
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC06 — Verify working set or source chips...")
            has_working_set = page.locator("text=Tập ứng viên hiện tại").is_visible()
            has_sources = page.locator("text=Nguồn được trích dẫn").is_visible()

            if has_working_set or has_sources:
                log_result(
                    "TC06", "Verify working set or cited sources display chips", "PASS"
                )
            else:
                log_result(
                    "TC06",
                    "Verify working set or cited sources display chips",
                    "WARN",
                    "Neither working set nor cited sources are visible",
                )
        except Exception as e:
            log_result(
                "TC06",
                "Verify working set or cited sources display chips",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC07: Multi-turn follow-up
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC07 — Send follow-up prompt in same conversation...")

            # Count conversations before sending follow-up
            initial_convs = get_conversation_buttons(page)
            initial_count = len(initial_convs)
            print(f"[INFO] Initial conversation count: {initial_count}")

            chat_input = page.get_by_placeholder("Hỏi về ứng viên của job này...")
            chat_input.fill(
                "Trong nhóm này, lọc ứng viên có tiếng Anh Advanced trở lên."
            )
            chat_input.press("Enter")

            print("[INFO] Waiting for follow-up response...")
            page.locator("div[data-testid='stChatMessage']").nth(3).wait_for(
                state="visible", timeout=AGENT_TIMEOUT
            )

            # Count conversations after response
            wait_streamlit(page, 2000)
            final_convs = get_conversation_buttons(page)
            final_count = len(final_convs)
            print(f"[INFO] Final conversation count: {final_count}")

            if final_count == initial_count:
                log_result(
                    "TC07",
                    "Verify multi-turn follow-up within same conversation",
                    "PASS",
                )
            else:
                log_result(
                    "TC07",
                    "Verify multi-turn follow-up within same conversation",
                    "FAIL",
                    f"New conversation was created (initial={initial_count}, final={final_count})",
                )
        except Exception as e:
            log_result(
                "TC07",
                "Verify multi-turn follow-up within same conversation",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC08: Click chip to navigate to app detail
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC08 — Click candidate chip and verify navigation...")
            # Target any applicant chip containing status brackets e.g. [PENDING], [NEW], etc.
            candidate_chip = page.locator("button:has-text('[')").first
            candidate_name = candidate_chip.inner_text().split("[")[0].strip()
            print(f"[INFO] Clicking chip for candidate: {candidate_name}")
            candidate_chip.click()
            wait_streamlit(page, 3000)

            # Verify detail page
            expect(page.locator("body")).to_contain_text(f"Hồ sơ: {candidate_name}")
            expect(page.locator("body")).to_contain_text("FANG HR Co-pilot")
            log_result(
                "TC08",
                "Verify applicant chip click navigates to candidate profile details",
                "PASS",
            )

            # Navigate back to candidate list
            page.get_by_role("button", name="← Quay lại danh sách Ứng viên").click()
            wait_streamlit(page, 2000)
        except Exception as e:
            log_result(
                "TC08",
                "Verify applicant chip click navigates to candidate profile details",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC09: Return to Job Agent and Rename Conversation
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC09 — Return to Job Agent and Rename conversation...")

            # If on candidate applications list page, go back to jobs dashboard first
            back_to_jobs = page.locator(
                "button:has-text('← Quay lại danh sách Job')"
            ).first
            if back_to_jobs.is_visible():
                back_to_jobs.click()
                wait_streamlit(page, 2000)
            elif page.locator("button:has-text('← Quay lại')").first.is_visible():
                page.locator("button:has-text('← Quay lại')").first.click()
                wait_streamlit(page, 2000)

            # Click Agent again to open Job Agent
            page.locator("button:has-text('Agent')").first.click()
            wait_streamlit(page, 2500)

            # Select the active conversation to rename (first conversation button)
            conv_buttons = get_conversation_buttons(page)
            if conv_buttons:
                print(
                    f"[INFO] Selecting active conversation: {conv_buttons[0].inner_text()}"
                )
                conv_buttons[0].click()
                wait_streamlit(page, 2500)
            else:
                raise Exception("No conversation buttons found in sidebar to rename")

            # Generate a unique rename title to avoid collision with previous test runs
            unique_rename_title = f"Smoke Test Conv {int(time.time())}"
            print(f"[INFO] Renaming conversation to: {unique_rename_title}")

            # Target rename input using multiple selector fallback
            left_col = page.locator("[data-testid='stColumn']").filter(
                has=page.locator("button:has-text('➕ Hội thoại mới')")
            )
            rename_input = left_col.locator(
                "input[aria-label='Tên mới'], [data-testid='stTextInput'] input"
            ).first
            rename_input.click()
            rename_input.press("Control+A")
            rename_input.press("Backspace")
            rename_input.fill(unique_rename_title)
            rename_input.press("Enter")

            # Also click the button just in case
            save_btn = left_col.locator("button:has-text('💾 Lưu tên')").first
            if save_btn.is_visible():
                save_btn.click()

            wait_streamlit(page, 3000)

            # Verify the updated conversation title in left sidebar column
            expect(left_col).to_contain_text(unique_rename_title)
            log_result(
                "TC09", "Rename conversation and verify updated sidebar item", "PASS"
            )
        except Exception as e:
            log_result(
                "TC09",
                "Rename conversation and verify updated sidebar item",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC10: New conversation clears state
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC10 — Click 'Hội thoại mới' and verify cleared state...")
            page.get_by_role("button", name="➕ Hội thoại mới").click()
            wait_streamlit(page, 2000)

            # Verify empty state text
            expect(page.locator("body")).to_contain_text(
                "Hội thoại mới — hãy hỏi về ứng viên"
            )
            expect(page.locator("body")).not_to_contain_text("Tập ứng viên hiện tại")
            log_result(
                "TC10",
                "Verify New Conversation clears active chat and working set panels",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC10",
                "Verify New Conversation clears active chat and working set panels",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC11: Quick prompt trigger
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC11 — Trigger quick prompt...")
            # Click quick prompt from the sidebar column (the 6th button from the end of all buttons in left_col)
            left_col = page.locator("[data-testid='stColumn']").filter(
                has=page.locator("button:has-text('➕ Hội thoại mới')")
            )
            all_buttons = left_col.locator("button")
            btn_count = all_buttons.count()
            first_qp_btn = all_buttons.nth(btn_count - 6)
            print(f"[INFO] Clicking quick prompt: {first_qp_btn.inner_text()}")
            first_qp_btn.click()

            print("[INFO] Waiting for quick prompt agent response...")
            page.locator("div[data-testid='stChatMessage']").nth(1).wait_for(
                state="visible", timeout=AGENT_TIMEOUT
            )
            log_result(
                "TC11",
                "Trigger quick prompt buttons and receive agent response",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC11",
                "Trigger quick prompt buttons and receive agent response",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC12: Archive conversation
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC12 — Archive conversation...")
            # Rename active conversation to a unique name before archiving to make assertion robust
            unique_archive_title = f"Archive Test {int(time.time())}"
            print(
                f"[INFO] Renaming active conversation to: {unique_archive_title} before archiving"
            )

            left_col = page.locator("[data-testid='stColumn']").filter(
                has=page.locator("button:has-text('➕ Hội thoại mới')")
            )
            rename_input = left_col.locator(
                "input[aria-label='Tên mới'], [data-testid='stTextInput'] input"
            ).first
            rename_input.click()
            rename_input.press("Control+A")
            rename_input.press("Backspace")
            rename_input.fill(unique_archive_title)
            rename_input.press("Enter")

            save_btn = left_col.locator("button:has-text('💾 Lưu tên')").first
            if save_btn.is_visible():
                save_btn.click()
            wait_streamlit(page, 3000)

            # Verify the unique title is in the sidebar first
            expect(left_col).to_contain_text(unique_archive_title)

            # Click archive on the loaded quick prompt conversation
            left_col.locator("button:has-text('🗑️ Lưu trữ hội thoại này')").first.click()
            wait_streamlit(page, 3000)

            # Ensure it is gone from sidebar listing
            expect(left_col).not_to_contain_text(unique_archive_title)
            log_result(
                "TC12", "Archive conversation and verify removal from sidebar", "PASS"
            )
        except Exception as e:
            log_result(
                "TC12",
                "Archive conversation and verify removal from sidebar",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC13: Regression - Entry from Job View
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC13 — Regression: Entry from job details view...")
            page.get_by_role("button", name="← Quay lại").click()
            wait_streamlit(page, 2000)

            page.locator("button:has-text('Xem job')").first.click()
            wait_streamlit(page, 2000)

            ask_agent = page.locator("button:has-text('Hỏi Agent về job này')").first
            expect(ask_agent).to_be_visible()
            ask_agent.click()
            wait_streamlit(page, 2000)

            expect(page.locator("body")).to_contain_text("Job Agent:")
            log_result(
                "TC13",
                "Verify Agent entry button in job view details page navigates correctly",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC13",
                "Verify Agent entry button in job view details page navigates correctly",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC14: Regression - RAG Chat still works
        # ---------------------------------------------------------------------------
        try:
            print("\n[STEP] TC14 — Regression: RAG chat still functions correctly...")
            page.get_by_role("button", name="← Quay lại").click()
            wait_streamlit(page, 2000)

            page.locator("button:has-text('Xem ứng viên')").first.click()
            wait_streamlit(page, 5000)  # Give extra time to load 500 apps list

            # Open RAG details for first candidate
            page.locator("button:has-text('Đánh giá RAG')").first.click()
            wait_streamlit(page, 3000)

            expect(page.locator("body")).to_contain_text("FANG HR Co-pilot")
            # Verify RAG chat input is available but does not have Job Agent specific UI details
            expect(page.get_by_placeholder("Hỏi về ứng viên này...")).to_be_visible()
            log_result(
                "TC14",
                "Verify RAG evaluation profile view renders RAG Co-pilot correctly",
                "PASS",
            )

            page.get_by_role("button", name="← Quay lại danh sách Ứng viên").click()
            wait_streamlit(page, 2000)
        except Exception as e:
            log_result(
                "TC14",
                "Verify RAG evaluation profile view renders RAG Co-pilot correctly",
                "FAIL",
                str(e),
            )

        # ---------------------------------------------------------------------------
        # TC15: Regression - AI Ranking still works
        # ---------------------------------------------------------------------------
        try:
            print(
                "\n[STEP] TC15 — Regression: AI Ranking buttons are visible on candidates page..."
            )
            expect(
                page.locator("button:has-text('Mở Job Agent')").first
            ).to_be_visible()
            expect(
                page.locator("button:has-text('Chạy AI Ranking')").first
            ).to_be_visible()
            log_result(
                "TC15",
                "Verify AI Ranking and Job Agent buttons exist on applicants view",
                "PASS",
            )
        except Exception as e:
            log_result(
                "TC15",
                "Verify AI Ranking and Job Agent buttons exist on applicants view",
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
    print(f"Result: {passed_cnt}/{len(results)} tests PASSED (including warnings)")
    print("=" * 80)

    if any(r[2] == "FAIL" for r in results):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_test_suite()
