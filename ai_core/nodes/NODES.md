# Piloteer — Nodes

This directory contains the five execution nodes that make up the Piloteer agent pipeline. Each node is a pure async function (or factory) that receives the shared `SharedState` and returns a partial state update. Nodes are wired together by `orchestration/graph.py` using LangGraph conditional edges.

---

## Pipeline Overview

```
START
  └─► TaskDirector ──► Planner ──► OutputGuardrail ──► Actor ──► Validator ──► (loop or END)
                          │                │
                       ask_user        ask_user
                    (HITL / question)
```

---

## Nodes

### 1. `task_director.py` — Strategic Planner (High-Level)

**Role**: The brain that interprets the user's intent and orchestrates the mission at a high level. It is the **first node** called on every new task and the **last** when the task ends.

**Three operating modes:**

| Mode | Trigger | Action |
|------|---------|--------|
| **Understand** | First call — `subgoals` list is empty | Calls Gemini with `understand_task_prompt`. Decides if the task is `EXECUTE`, `GUIDE`, `QUESTION`, or `IMPOSSIBLE`. Breaks the task into ordered subgoals with `mini_planner_hints`. |
| **Revision** | Escalation from Validator — a subgoal `status == "failed"` after 3 attempts | Calls Gemini with `revise_subgoal_prompt`. Replaces the blocked subgoal with a new alternative strategy while keeping completed subgoals intact. |
| **Finalize** | `task_status` is `"completed"`, `"task_impossible"`, or `step_count >= 30` | Calls Gemini with `finalize_task_prompt`. Generates a natural-language summary message for the user and sets `task_status = "finalized"`. |

**Error & Fallback strategy:**
- If `QUESTION` or `IMPOSSIBLE` is detected during understanding, the task is immediately finalized without entering the agent loop.
- If revision returns no new subgoals (`new_subgoals = []`), the task is marked `"task_impossible"` and routed back to TaskDirector for finalization.
---

### 2. `planner.py` — Tactical Planner (Low-Level)

**Role**: The immediate decision-maker. Given the current subgoal and page state (accessibility tree snapshot), it decides **the next single atomic action** to execute.

**Inputs used:**
- Current subgoal description & `mini_planner_hints`
- Page accessibility snapshot
- Memory of past actions (OK / FAIL with summaries)
- `user_answer` (if the last step was an `ask_user` question)
- `execution_mode` (`EXECUTE` or `GUIDE`)

**Output:** A `current_step` dict: `{ "tool": "...", "arguments": {...}, "description": "..." }`.

**Error & Fallback strategy:**
- If Gemini returns an empty or invalid step, a safe fallback step is injected automatically:
  ```python
  { "tool": "browser_wait_for", "arguments": {"time": 3}, "description": "Wait for the page to load before retrying" }
  ```
- This prevents a `None` step from crashing the Actor and keeps the pipeline alive.

---

### 3. `actor.py` — Action Executor

**Role**: Executes the action decided by the Planner by dispatching it through the **Playwright MCP** session. It is the only node that physically interacts with the browser.

**Handles three action categories:**

| Category | How it works |
|----------|-------------|
| **Standard tools** (`browser_click`, `browser_type`, etc.) | Dispatched via `dispatch_action(session, tool, arguments)` over MCP. After navigation tools (`browser_click`, `browser_navigate`, `browser_press_key`), waits 3 seconds then takes a fresh accessibility snapshot. |
| **`browser_finish_subgoal`** | Does NOT interact with the browser. Signals to the Validator that the current subgoal is done or impossible, with a reason string. |
| **`ask_user`** | Does NOT interact with the browser. Sets `pending_question` and returns immediately, routing to `ask_user` node for human input. |

**Guide Mode spotlight:**
When `execution_mode == "GUIDE"`, the Actor injects a visual spotlight JS animation on the target element before executing the action. Cleanup JS runs after the action regardless of success.

**Error & Fallback strategy:**
- If `step` is `None`, the Actor returns immediately with `"error: no step"` without crashing.
- If the MCP call returns `isError=True`, `is_error` is set to `True` and forwarded to the Validator for evaluation.
- If Guide Mode spotlight injection fails (JS error), the failure is caught silently and the action is still executed normally.
- Screenshots are always taken **before** each action for audit logging.

---

### 4. `validator.py` — Result Evaluator

**Role**: Evaluates whether the last action succeeded and whether the current subgoal is complete. It is the **judge** that decides whether to loop, escalate, or finish.

**Inputs used:**
- Current accessibility snapshot (after the action)
- The step that was executed
- `last_action_result` text (MCP result or actor message)
- `last_action_is_error` flag
- Current subgoal description

**Outputs:** `step_success` (bool), `subgoal_done` (bool), `memory_entry` (text summary for future context).

**Routing logic:**

| Condition | Routing |
|-----------|---------|
| `subgoal_done = True` | Advance `current_subgoal_index`. If last subgoal → `task_status = "completed"` → finalize. |
| `step_success = False` | Increment `attempts` counter. If `attempts >= 3` → `status = "failed"` → escalate to TaskDirector. |
| `step_success = True, subgoal_done = False` | Stay in current subgoal → return to Planner for next step. |
| `needs_revision` from Actor | Skip LLM call entirely. Update subgoal status to `"impossible"` and advance index. |
| `step_count >= MAX_STEPS (30)` | Force finalize via router in `graph.py`. |

**Error & Fallback strategy:**
- If Gemini returns an empty or invalid response, the Validator defaults to `step_success=False`, preventing silent forward progress on a broken response.
- For `browser_finish_subgoal` with `status="impossible"`, the Validator bypasses its LLM call and processes the result directly from the Actor message, avoiding wasted LLM tokens.

---

### 5. `ask_user.py` — Human-in-the-Loop Gate

**Role**: Pauses the pipeline and requests input from the human operator. Handles both **standard questions** from the Planner and **HITL security confirmations** from the Output Guardrail.

**Two entry paths:**

| Source | Question format | What happens |
|--------|----------------|--------------|
| **Planner** (`ask_user` tool) | Plain natural language question | Sends via `channel.ask()`. Stores answer in `user_answer` for the Planner to use on its next step. |
| **Security Guardrail** | `HITL:<natural language message>` | The chat UI strips the prefix to show Allow/Deny buttons. The voice layer strips it for TTS playback and appends *"Please answer allow or deny."* |

**HITL decision logic:**
- If `"allow"` is contained anywhere in the user's answer (case-insensitive substring match) → the action is authorized → routed to Actor.
- Otherwise (deny, no, refuse, etc.) → a fatal security denial entry is written to memory → `task_status = "task_impossible"` → routed to TaskDirector for finalization.

**Fallback (no channel / CLI mode):**
- If no WebSocket channel is present (e.g. running in a test script), falls back to a blocking `input()` prompt in the terminal.

---

## Security Node (adjacent, called before Actor)

### `security/output_guardrail.py` — Risk Interceptor

**Role**: Intercepts every Planner step **before** it reaches the Actor. Embeds the action description and queries a ChromaDB blacklist to detect semantically dangerous actions.

**Monitored tools:** `browser_click`, `browser_navigate`

**Scoring:**
- Converts action description to a vector via `embed_text()` (Gemini Embedding model).
- Queries the `security` ChromaDB collection for the nearest blacklisted action.
- Computes `risk_score = 1.0 - cosine_distance`.

**Thresholds:**

| Score | Verdict | Action |
|-------|---------|--------|
| `< 0.75` | `PASS` | Pipeline continues directly to Actor. |
| `>= 0.75` | `HITL` | Pipeline pauses at `ask_user` for human approval. |


---
