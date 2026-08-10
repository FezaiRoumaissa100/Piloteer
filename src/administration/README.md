# Administration

This directory contains the admin-facing observability tools for Piloteer. Its purpose is to give the operator a clear view of what the agent did, how it performed, and where it succeeded or failed.

The tools in this directory are read-only. They consume data produced by the loggings layer but never write to it.

---

## Directory Structure

```
administration/
    replay/
        replay.py           Streamlit app — step-by-step session replay viewer
        app.py              Legacy combined app (superseded by the two separate apps)
    performance/
        performance.py      Streamlit app — token usage and timing analytics dashboard
```

---

## Tools

### Session Replay

**File:** `replay/replay.py`

**Purpose:** Allows the operator to step through any recorded agent session frame by frame. For each step, it shows:

- The screenshot of the browser page as the agent saw it before acting
- The node that executed (Actor, Planner, Validator, TaskDirector)
- The step result (success or error)
- The agent's reasoning payload (the JSON the LLM returned)
- Token counts and execution duration for that step

**How to run:**

```bash
python -m streamlit run src/administration/replay/replay.py
```

**Design decisions:**

- Navigation uses explicit buttons (First, Previous, Next, Last) rather than a slider, so the operator can step precisely without accidentally jumping steps.
- Screenshots are the single "before" capture taken by the Actor node — this is what the agent actually saw before deciding to click or type.
- Nodes that do not interact with the browser (Planner, Validator, TaskDirector) have no screenshot. An informational message is shown instead of an error.

---

### Performance Dashboard

**File:** `performance/performance.py`

**Purpose:** Provides quantitative analysis of agent runs. It answers questions such as:

- How many tokens did this mission consume, split by node?
- Which node is the slowest on average?
- What is the overall success rate across all missions?
- How does mission duration compare across runs?

It exposes three levels of granularity:

1. **Global summary** — total tokens, total duration, success rate across the selected scope
2. **Breakdown by node** — calls, input tokens, output tokens, average and total duration per node
3. **Summary by mission** — one row per trace ID with aggregated metrics (only when "All missions" is selected)

**How to run:**

```bash
python -m streamlit run src/administration/performance/performance.py --server.port 8502
```

---

## Technology Choice: Streamlit

Streamlit was chosen for the following reasons:

- **Single-file apps** — each tool is a self-contained Python script with no frontend build step, no Node.js, no API layer.
- **Admin-only audience** — these tools are used exclusively by the operator, not by end users. A polished React frontend is not justified for internal tooling at this stage.
- **Direct database access** — Streamlit reads from SQLite directly in Python. No API, no serialization, no extra moving parts.
- **Fast iteration** — changes to the UI are visible immediately on file save with auto-reload.

The tradeoff is that Streamlit does not support real-time streaming updates (it polls on a timer). For the current use case — replaying completed sessions and analyzing historical metrics — this is not a limitation. If real-time monitoring of a live agent run becomes a requirement, the appropriate replacement would be a Next.js frontend connected to Piloteer's existing WebSocket server.

---

## Audience

These tools are designed for the **operator** (researcher, developer, or administrator) who needs to:

- Diagnose why a specific step failed
- Measure token consumption and latency per node
- Compare performance across multiple missions
- Verify that the agent completed its task correctly

They are not designed for end users. End users interact with the agent through the chat interface at `src/interface/static/index.html`.
