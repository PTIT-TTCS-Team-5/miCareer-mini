# PROMPT: Tự động test C3 JobPosting Agent Frontend + Viết Playwright Script

## Vai trò của bạn

Bạn là một QA agent tự động. Nhiệm vụ là **test toàn diện tính năng C3 JobPosting Agent** vừa được implement trong miCareer-mini, sử dụng Chrome DevTools MCP, Postman MCP, và xác minh dữ liệu qua PostgreSQL MCP.

Sau khi test xong, **viết file Playwright script** `test_playwright_job_agent.py` hoàn chỉnh (ghi đè file đã có tại `C:\Users\os\Desktop\cur_prj\miCareer-mini\test_playwright_job_agent.py`) dựa trên những gì bạn quan sát thực tế từ UI.

---

## Thông tin hệ thống

| Thành phần | URL / Path |
|---|---|
| FANG Backend | Tự chạy để đọc log, dùng venv của FANG lệnh "python -m uvicorn app.main:app --reload |
| FANG API base | `http://localhost:8000/v2` |
| Frontend Streamlit | Tự chạy để đọc log, dùng venv của miCareer-mini lệnh "python -m streamlit run app.py" |
| CV mẫu | `C:\Users\os\Desktop\cur_prj\Fang\sample_2.pdf` |
| Frontend source | `C:\Users\os\Desktop\cur_prj\miCareer-mini\app.py` |

## Thông tin đăng nhập

| Role | Username | Password |
|---|---|---|
| HR | `hr_dndh` | `1` |
| nguyenhaihung | 1 |

- Nếu cần thêm tài khoản HR -> tự query thêm. Đặc biệt tài khoản hr_helios (pass 1) có JobPosting "Senior Backend Engineer (Go/Python)" có 500 JobApplication

## Database

```
DATABASE_URL=postgresql://postgres:hungklv123@localhost:5432/micareer_lite_db
```

Useful queries:
```sql
-- Lấy danh sách HR users
SELECT u.userid, u.username, h.compid FROM "user" u JOIN hr h ON u.userid = h.userid WHERE u.role = 'HR';

-- Lấy jobs của công ty hr_helios (compid)
SELECT jobpostid, title, expat FROM jobposting WHERE compid = (SELECT compid FROM hr WHERE userid = (SELECT userid FROM "user" WHERE username = 'hr_helios'));

-- Đếm ứng viên theo job
SELECT jobpostid, COUNT(*) as cnt FROM jobapplication GROUP BY jobpostid ORDER BY cnt DESC;

-- Lấy conversation IDs của JobPosting Agent (nếu bảng tồn tại trong FANG DB)
-- Kiểm tra bằng GET API: http://localhost:8000/v2/agent/job-posting/conversations?jobPostId=1&hrId=2
```

## Postman

- **Workspace ID**: `da90bd2c-d4f1-46f6-8066-dc77fc81deba`
- **Collection**: `FANG v2 API Test Suite` — ID: `77454b9d-7104-488c-9895-15f3b4a887b4`
- **Collection UID**: `54551854-77454b9d-7104-488c-9895-15f3b4a887b4`

### Collection variables mặc định
| Variable | Value | Ghi chú |
|---|---|---|
| `base_url` | `http://localhost:8000` | |
| `job_post_id` | `1` | jobPostId=1, có 500 ứng viên |
| `hr_id` | `2` | HR thuộc companyId=1 |
| `conversation_id` | (rỗng, tự điền sau Case 2) | |
| `job_app_id` | `2` | |
| `candidate_id` | `19` | |

### Folder "JobPosting Agent API" (6 cases có sẵn)
| Request ID | Tên |
|---|---|
| `54551854-7e0927ea-368d-4d03-ad91-fa4b72570d93` | Case 2: POST query — Top Candidates |
| `54551854-d8369834-71a8-48d8-9629-37149d274a02` | Case 3: POST query — Language Filter (multi-turn) |
| `54551854-f6712a1e-5be7-4669-8add-042303ca19db` | Case 4: POST query — CV Drill-down |
| `54551854-ab72f509-e533-461c-9c3c-463ffee868be` | Case 5a: GET conversations |
| `54551854-81b86ba2-8304-4f58-bb2e-078290c20d15` | Case 5b: GET messages |
| `54551854-49db5ca9-e2ba-4984-ad1e-65cf811d8c0d` | Case 6: Negative 403 scope |

---

## Quy trình thực hiện

### PHASE 1 — API Smoke (Postman MCP)

Chạy từng request trong folder **JobPosting Agent API** theo thứ tự Case 2 → 3 → 4 → 5a → 5b → 6:

1. Dùng `runCollection` hoặc `getCollections` → `getCollection` để lấy request details.
2. Với **Case 2** (POST query top candidates):
   - Gọi `POST http://localhost:8000/v2/agent/job-posting/query` body `{"jobPostId":1,"hrId":2,"prompt":"Liệt kê top 10 ứng viên phù hợp nhất","conversationId":null}`
   - Ghi lại `conversationId` từ response.
   - Xác nhận: response có `response`, `toolCalls`, `sourceJobAppIds`, `workingSet`, `latencyMs`.
3. Với **Case 3** (Language filter, multi-turn):
   - Dùng `conversationId` từ Case 2.
   - Prompt: `"Trong nhóm này, lọc ứng viên có tiếng Anh Advanced trở lên."`
   - Xác nhận: cùng `conversationId`, `workingSet.filters` có giá trị.
4. Với **Case 5a**: GET conversations — xác nhận list có conversation vừa tạo.
5. Với **Case 5b**: GET messages — xác nhận có `user` và `assistant` messages.
6. Với **Case 6**: POST với `hrId` sai → xác nhận HTTP `403`.

**Ghi lại kết quả**: PASS/FAIL và response body tóm tắt cho từng case.

---

### PHASE 2 — DB Verification (PostgreSQL MCP)

Sau khi chạy API, dùng PostgreSQL MCP query DB để:

1. Xác nhận `jobpostid=1` tồn tại và thuộc `compid` của `hr_helios`.
2. Đếm số `jobapplication` của `jobpostid=1` → confirm agent có data để làm việc.
3. Query thông tin 3 ứng viên đầu (jobappid, fname, lname, stat) để chuẩn bị assertions cho UI test.
4. Kiểm tra bảng conversation/message nếu tồn tại trong schema (optional — FANG có thể dùng PostgreSQL riêng).

---

### PHASE 3 — UI Test (Chrome DevTools MCP)

Mở tab mới trỏ đến `http://localhost:8501`. Thực hiện từng step, chụp screenshot sau mỗi bước quan trọng.

#### TC01 — Trang chủ và đăng nhập HR
```
1. navigate_page → http://localhost:8501
2. Chờ button "Đăng nhập HR" xuất hiện
3. click "Đăng nhập HR"
4. fill Username = "hr_helios"
5. fill Password = "1"
6. click "Đăng nhập"
7. Xác nhận: h1/h2 chứa "Xin chào, hr_helios"
8. take_screenshot → lưu kết quả TC01
```

#### TC02 — Job list có nút 🤖 Agent
```
1. Xác nhận page đang ở trang job list ("Danh sách tin tuyển dụng")
2. Xác nhận ít nhất 1 button có text chứa "Agent"
3. take_screenshot → TC02
```

#### TC03 — Mở Job Agent từ job list
```
1. click button "🤖 Agent" đầu tiên
2. wait_for: h1 chứa "Job Agent"
3. Xác nhận: có thông tin context (tên công ty, hết hạn, số ứng viên)
4. Xác nhận: có cột trái (sidebar) và cột phải (chat area)
5. Xác nhận: có button "➕ Hội thoại mới"
6. Xác nhận: có 6 quick prompt buttons
7. Xác nhận: chat area hiển thị "Hội thoại mới"
8. take_screenshot → TC03_job_agent_page
```

#### TC04 — Gửi prompt top 10 (timeout 90s)
```
1. fill chat input = "Liệt kê top 10 ứng viên phù hợp nhất cho job này, nêu lý do ngắn gọn."
2. press Enter
3. Xác nhận: spinner "FANG Job Agent đang phân tích" xuất hiện
4. wait_for (timeout=90000): assistant message bubble xuất hiện
5. take_screenshot → TC04_response
6. Ghi lại: response text, có tool expanders không, có working set không
```

#### TC05 — Tool expanders
```
1. Tìm elements có text "Bước" (tool expanders)
2. Nếu có: click expander đầu tiên → xác nhận nội dung mở ra (latencyMs, args, resultSummary)
3. take_screenshot → TC05_tool_expander
```

#### TC06 — Working set và source chips
```
1. Tìm "Tập ứng viên hiện tại" hoặc "Nguồn được trích dẫn"
2. Nếu có: xác nhận hiển thị số ứng viên, filter chips, name chips (Tên [STATUS])
3. take_screenshot → TC06_working_set
```

#### TC07 — Multi-turn follow-up (cùng conversationId)
```
1. fill chat input = "Trong nhóm này, lọc ứng viên có tiếng Anh Advanced trở lên."
2. press Enter
3. wait_for (timeout=90000): assistant bubble thứ 2 xuất hiện
4. Xác nhận: sidebar vẫn chỉ có 1 conversation (không tạo mới)
5. take_screenshot → TC07_followup
```

#### TC08 — Click chip → navigate sang app detail
```
1. Tìm button chip (working set hoặc source) đầu tiên
2. Ghi lại label của chip (tên ứng viên)
3. click chip
4. wait_for: page chứa "Hồ sơ:" hoặc "FANG HR Co-pilot"
5. Xác nhận: page_hr_app_detail render đúng (không crash)
6. take_screenshot → TC08_app_detail_chip_click
7. Nhấn "← Quay lại danh sách Ứng viên" để quay về
```

#### TC09 — Quay lại Job Agent và rename conversation
```
1. Điều hướng về hr_jobs → click "🤖 Agent" lại
2. Sidebar: click conversation vừa tạo
3. Điền rename input = "Smoke Test Conversation"
4. click "💾 Lưu tên"
5. wait_for: sidebar cập nhật tên mới
6. take_screenshot → TC09_rename
```

#### TC10 — New conversation clears state
```
1. click "➕ Hội thoại mới"
2. wait_for: chat area hiển thị "Hội thoại mới" (empty state)
3. Xác nhận: working set panel không còn hiển thị
4. take_screenshot → TC10_new_conv
```

#### TC11 — Quick prompt
```
1. click quick prompt đầu tiên (text cắt ở 55 ký tự, full text: "Liệt kê top 10...")
2. wait_for (timeout=90000): assistant response
3. take_screenshot → TC11_quick_prompt
```

#### TC12 — Archive conversation
```
1. Đảm bảo đang có conversation được chọn (click conversation trong sidebar nếu cần)
2. click "🗑️ Lưu trữ hội thoại này"
3. wait_for: conversation biến mất khỏi sidebar
4. take_screenshot → TC12_archive
```

#### TC13 — Regression: entry point từ page_hr_job_view
```
1. click "← Quay lại" để về hr_jobs
2. click "Xem job" cho job đầu tiên
3. Xác nhận: có button "🤖 Hỏi Agent về job này" trong cột hành động
4. click button đó
5. wait_for: h1 "Job Agent:"
6. take_screenshot → TC13_entry_from_job_view
```

#### TC14 — Regression: RAG chat vẫn hoạt động
```
1. click "← Quay lại" về hr_jobs
2. click "Xem ứng viên" cho job đầu tiên
3. click "Đánh giá RAG" cho ứng viên đầu tiên
4. Xác nhận: page_hr_app_detail render bình thường
5. Xác nhận: có "🤖 FANG HR Co-pilot" section
6. Xác nhận: KHÔNG có model selector của JobPosting Agent (tức là trang RAG không bị ảnh hưởng)
7. take_screenshot → TC14_regression_rag
```

#### TC15 — Regression: AI Ranking vẫn hoạt động
```
1. Điều hướng về hr_jobs
2. Tìm job có nút "AI Ranking" (nếu có) hoặc vào page_hr_applications
3. Xác nhận: có button "🤖 Mở Job Agent" ở đầu trang
4. Xác nhận: button "🚀 Chạy AI Ranking" vẫn còn nguyên
5. take_screenshot → TC15_regression_ranking
```

---

### PHASE 4 — Tổng hợp và viết Playwright script

Sau khi hoàn thành Phase 1-3:

1. **Tổng hợp kết quả** vào bảng PASS/FAIL/WARN.
2. **Ghi nhận các selector thực tế** bạn đã dùng trong Chrome MCP (aria-label, text, data-testid...) vì Streamlit có thể render khác so với selector ban đầu.
3. **Ghi đè** file `C:\Users\os\Desktop\cur_prj\miCareer-mini\test_playwright_job_agent.py` với script hoàn chỉnh dựa trên:
   - Selector thực tế từ quan sát UI.
   - 12+ test cases theo thứ tự trên.
   - `slow_mo=500`, `timeout=90000` cho agent calls.
   - Mỗi test case in `[STEP]`, `[OK]`, `[FAIL]`, `[WARN]`.
   - Kết quả cuối in bảng PASS/FAIL tổng hợp.
   - Sử dụng `sample_2.pdf` (`C:\Users\os\Desktop\cur_prj\Fang\sample_2.pdf`) nếu cần test CV upload trong candidate apply flow (optional regression).

---

## Điều kiện thành công

| Tiêu chí | Mức độ |
|---|---|
| FANG backend health check OK | **BẮT BUỘC** |
| POST /agent/job-posting/query trả về response có `toolCalls` | **BẮT BUỘC** |
| UI Job Agent page render không crash | **BẮT BUỘC** |
| Chat input gửi và nhận assistant response | **BẮT BUỘC** |
| Sidebar conversation list cập nhật sau query | **BẮT BUỘC** |
| Rename + Archive conversation hoạt động | BẮT BUỘC |
| Working set hoặc source chips hiển thị | Khuyến nghị |
| Chip click → app detail navigate | Khuyến nghị |
| Regression RAG chat không bị break | **BẮT BUỘC** |
| Tool expanders hiển thị | Khuyến nghị (phụ thuộc agent config) |
| Playwright script cuối cùng chạy được | **BẮT BUỘC** |

---

## Lưu ý kỹ thuật

- **Streamlit re-render**: sau mỗi action cần `wait_for_timeout(1500)` hoặc `wait_for_selector`.
- **Agent latency**: prompt agent có thể mất 10–60s. Dùng `timeout=90000` cho tất cả agent-related waits.
- **Session state**: nếu refresh browser, Streamlit reset session — không refresh trang giữa chừng.
- **Selector Streamlit**: buttons thường dùng `button:has-text(...)`, inputs dùng `textarea` hoặc `input[type='text']`. Chat input của Streamlit là `textarea` với aria-label.
- **Tool expanders**: Streamlit render `<details>/<summary>` — dùng `locator("details summary:has-text('Bước')")`.
- **Quick prompts**: text bị cắt ở 55 ký tự trong button label — dùng `button:has-text('Liệt kê top')` thay vì full text.
- **Postman MCP**: nếu cần tạo request mới trong collection, dùng `createCollectionRequest`. Nếu chỉ cần test API trực tiếp, dùng `evaluate_script` hoặc `fetch` trong Chrome devtools.
