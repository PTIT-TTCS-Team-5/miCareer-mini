# C3 Prompt — JobPosting Agent Frontend Design for miCareer-mini

You are working in the `miCareer-mini` repository at:

`C:\Users\os\Desktop\cur_prj\miCareer-mini`

Your task is **design-first only**: produce a frontend implementation design for integrating the completed FANG C3 JobPosting Agent into the Streamlit HR experience. Do not implement code in this task unless the user explicitly asks for implementation later.

## Current Backend Status

The FANG backend JobPosting Agent C3 is complete and smoke-tested against real local data.

Known backend results:

- Risk A backfill is acceptable:
  - `501/501` candidate users have `provId`.
  - `463/501` candidates have language rows.
  - The remaining 38 candidates have `parsedJson.languages = []`, so they are not backfill failures.
- Postman/API smoke test passed 6/6 scenarios:
  - top candidates
  - language filter multi-turn
  - full CV drill-down with PII masking
  - conversation list/messages
  - cross-tenant authorization negative case
- Backend phase has no known blocker for frontend work.

Relevant FANG backend docs and files:

1. `..\Fang\agent_workflow_doc\try_hard_jobposting\FANG_NEXT_PHASE_JOBPOSTING_C3_OFFICIAL_IMPLEMENTATION_PLAN.md`
2. `..\Fang\agent_workflow_doc\try_hard_jobposting\FANG_NEXT_PHASE_JOBPOSTING_C3_WSD_API_UI_CONTRACT.md`
3. `..\Fang\agent_workflow_doc\try_hard_jobposting\FANG_NEXT_PHASE_JOBPOSTING_C3_POSTMAN_API_SMOKE_REPORT.md`
4. `..\Fang\app\models\jobposting_agent.py`
5. `..\Fang\app\api\routes_jobposting_agent.py`
6. `..\Fang\postman\collections\FANG v2 API Test Suite\JobPosting Agent API\`

## Mandatory Knowledge Graph Use

This repo has an Understand Anything knowledge graph:

`C:\Users\os\Desktop\cur_prj\miCareer-mini\.understand-anything\knowledge-graph.json`

Use it before reading too much code:

1. Read only the `"project"` metadata first.
2. Search the graph for:
   - `JobPosting`
   - `jobPost`
   - `HR`
   - `chat`
   - `ranking`
   - `fang_client`
   - `nmaiex_client`
   - `page_hr_job_view`
   - `page_hr_applications`
   - `page_hr_ai_ranking`
3. Use the matched nodes and one-hop edges to orient yourself.
4. Then read only the directly relevant source files.

Relevant known graph findings:

- `app.py` is the Streamlit entrypoint and page router.
- `core/fang_client.py` is the thin FANG API client for chat/ingestion/health.
- `core/nmaiex_client.py` is the thin FANG/NMAIex client for ranking/master/job APIs.
- `core/db.py` owns relational reads for HR jobs, applications, and candidate/job details.
- Existing HR flow includes:
  - `page_hr_jobs`
  - `page_hr_job_view`
  - `page_hr_applications`
  - `page_hr_ai_ranking`
  - `page_hr_app_detail`
- Existing single-application chat lives in `page_hr_app_detail` and calls `fang_client.chat_query()`.

## Backend API Contract to Design Against

`FANG_API_URL` already includes `/v2`, for example:

```env
FANG_API_URL=http://localhost:8000/v2
```

Therefore frontend client paths should be:

### Query

`POST /agent/job-posting/query`

Request:

```json
{
  "jobPostId": 1,
  "hrId": 2,
  "prompt": "Liệt kê top 10 ứng viên phù hợp nhất cho job này",
  "conversationId": null
}
```

Response shape:

```json
{
  "conversationId": "uuid",
  "messageId": 123,
  "response": "...",
  "model": "gemini-3.1-flash-lite",
  "stepsUsed": 1,
  "toolCalls": [
    {
      "step": 1,
      "toolName": "get_job_candidate_ranking",
      "args": {"limit": 10},
      "resultSummary": "...",
      "status": "success",
      "latencyMs": 1234,
      "errorMsg": null,
      "toolCallId": "..."
    }
  ],
  "sourceJobAppIds": [57, 274],
  "workingSet": {
    "jobAppIds": [57, 274],
    "label": "Top candidates",
    "activeFilters": {}
  },
  "latencyMs": 12345,
  "warnings": []
}
```

### Conversation List

`GET /agent/job-posting/conversations?jobPostId=<id>&hrId=<id>`

Returns:

```json
[
  {
    "conversationId": "uuid",
    "jobPostId": 1,
    "hrId": 2,
    "title": "Liệt kê top 10...",
    "createdAt": "...",
    "lastMessageAt": "...",
    "messageCount": 12,
    "isArchived": false
  }
]
```

### Messages

`GET /agent/job-posting/conversations/<conversationId>/messages?includeToolMessages=true&includeSystem=false`

Returns message rows with:

```json
{
  "messageId": 1,
  "role": "user|assistant|tool_call|tool_result",
  "content": "...",
  "toolName": "...",
  "toolCallId": "...",
  "model": "...",
  "latencyMs": 123,
  "createdAt": "..."
}
```

### Rename

`PATCH /agent/job-posting/conversations/<conversationId>?hrId=<id>`

Body:

```json
{"title": "Tên hội thoại mới"}
```

### Archive

`DELETE /agent/job-posting/conversations/<conversationId>?hrId=<id>`

Returns `204`.

## Product Goal

Design a practical HR-facing JobPosting Agent UI inside `miCareer-mini`.

The user should be able to stand on a JobPosting context and ask questions across all applications for that job:

- "Liệt kê top 10 ứng viên phù hợp nhất"
- "Trong nhóm này lọc người có tiếng Anh Advanced trở lên"
- "So sánh 3 ứng viên này"
- "Xem chi tiết CV đã mask PII của jobAppId=..."
- "Ứng viên nào có kinh nghiệm backend + AI tốt nhất?"

This is **not** the existing single-application RAG chat. Keep the UX and state separate from `jobAppId` chat.

## Design Requirements

Your design should cover:

1. **Placement in current Streamlit UI**
   - Decide whether to place the agent in `page_hr_job_view`, `page_hr_applications`, a new `page_hr_job_agent`, or a tab/section shared by job detail/applications.
   - Explain the tradeoff and recommend one primary placement.
2. **Navigation**
   - How HR enters the agent from job list/job detail/application list/ranking.
   - How selected `jobPostId` and `hrId` flow through `st.session_state`.
3. **API client changes**
   - Add thin wrappers in `core/fang_client.py`.
   - Do not put business logic in the client.
   - Suggested functions:
     - `jobposting_agent_query(job_post_id, hr_id, prompt, conversation_id=None)`
     - `list_jobposting_agent_conversations(job_post_id, hr_id)`
     - `get_jobposting_agent_messages(conversation_id, include_tool_messages=True)`
     - `rename_jobposting_agent_conversation(conversation_id, hr_id, title)`
     - `archive_jobposting_agent_conversation(conversation_id, hr_id)`
4. **Session state design**
   - Define exact keys and lifecycle.
   - Avoid colliding with existing app-level chat/ranking/session keys.
5. **Message rendering**
   - User and assistant messages as chat bubbles.
   - `tool_call` and `tool_result` as collapsed expanders by default.
   - Vietnamese display names for tool names.
   - Tool calls should be visible enough for debugging but not overwhelm HR.
6. **Working set UI**
   - Show `workingSet.jobAppIds`, label, active filters.
   - Make jobAppId chips actionable where feasible: click/view candidate detail should route to existing `page_hr_app_detail` if mapping is available.
7. **Source job applications**
   - Show `sourceJobAppIds` in a compact way.
   - Include a clear plan for linking `jobAppId` to existing application detail.
8. **Warnings and errors**
   - Render `warnings[]`.
   - Handle 400/403/404/410/429/500/503 in Vietnamese.
   - 403 must be clearly treated as access/scope denial, not generic failure.
9. **Loading/no streaming**
   - Backend is request-response only in phase 1.
   - Design a robust loading state for long LLM/tool calls.
10. **No modelMode selector**
   - Do not expose agent model selection in frontend phase 1.
11. **Conversation management**
   - Conversation list for the current job.
   - Start new conversation.
   - Rename conversation.
   - Archive conversation.
   - Load history with tool messages.
12. **Quick prompts**
   - Suggest a small set of action buttons for common HR workflows.
   - Keep them practical and job-scoped.
13. **Visual density**
   - This is an operational HR tool, not a marketing page.
   - Keep layout dense, scan-friendly, and consistent with current Streamlit UI.
14. **Regression boundaries**
   - Do not break existing candidate flow.
   - Do not break existing single-application RAG chat.
   - Do not remove existing ranking pages.

## Suggested UI Direction

Start from this recommendation unless your code reading shows a better fit:

- Add a JobPosting Agent entry point from `page_hr_jobs`, `page_hr_job_view`, and `page_hr_applications`.
- Use a dedicated page or dedicated tab for the job-scoped agent.
- Use a two-column layout:
  - Left/narrow: conversation list, new chat, rename/archive, quick prompts.
  - Right/wide: current conversation messages, tool expanders, working set, prompt input.
- Do not embed this inside the single-application CV iframe/RAG page. That page is `jobAppId` scoped, while this feature is `jobPostId` scoped.

## Required Output

Create a design report in:

`agent_workflow_doc/C3_JOBPOSTING_AGENT_FRONTEND_DESIGN_REPORT.md`

The report must include:

1. Executive recommendation.
2. Current frontend architecture summary based on the knowledge graph.
3. Backend API contract summary.
4. Recommended UX placement and navigation flow.
5. Streamlit layout wireframe in text or Mermaid.
6. Required changes by file/function.
7. Proposed `core/fang_client.py` function signatures.
8. Proposed `st.session_state` keys.
9. Message/tool/working-set rendering rules.
10. Error/loading/empty-state behavior.
11. Test plan:
    - manual smoke
    - Streamlit run command
    - Playwright/manual browser checks if useful
    - backend prerequisites
12. Implementation phases:
    - Phase FE-0: design acceptance
    - Phase FE-1: API client + minimal page
    - Phase FE-2: conversation management + tool expanders
    - Phase FE-3: polish + browser smoke
13. Explicit non-goals.
14. Risks/open questions.
15. Final recommendation on whether a tier 2 implementation agent can start.

## Verification for This Design Task

Since this is a design-only task:

- Do not run full frontend implementation.
- Do not edit `app.py` or client code.
- You may run read-only inspection commands.
- You may create only the design report.
- At the end, report:
  - files read
  - graph nodes considered
  - design report path
  - whether implementation is ready to assign

## Constraints

- Do not commit secrets.
- Do not edit `.env`.
- Do not modify `.understand-anything` generated graph files.
- Do not modify backend FANG files.
- Keep all AI-heavy logic in FANG; `miCareer-mini` remains a thin frontend.
- Keep the frontend compatible with `FANG_API_URL=http://localhost:8000/v2`.
