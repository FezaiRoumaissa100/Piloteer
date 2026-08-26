# Loggings

This directory contains the full observability stack for Piloteer. Its purpose is to record every decision, action, and outcome produced by the autonomous agent during a session, so that any run can be replayed, inspected, and measured after the fact.

---

## What is Logged

Every time a node in the LangGraph pipeline finishes executing, it writes one row to the `events` table. A node is any component in the agent pipeline: TaskDirector, Planner, Actor, or Validator.

Each row captures:

- **Identity** — trace ID (session), subgoal ID, step ID, node name
- **Timing** — start timestamp, end timestamp, duration in milliseconds
- **LLM Usage** — model name, input token count, output token count
- **Payload** — the node's reasoning or result as a JSON blob
- **Screenshot** — absolute path to the PNG file captured before the action (Actor node only)

---

## Why This Methodology

### Raw Events, Not Aggregates

Each row represents one atomic event — one node execution — rather than a summary. This is the same approach used by distributed tracing systems (OpenTelemetry spans, LangSmith traces). Raw events can always be aggregated upward into summaries. Aggregates cannot be decomposed back into individual events.

This gives full flexibility: you can query total tokens per mission, average duration per node, or drill down into the exact reasoning payload of a single failed step.

### One Screenshot Per Actor Step

Screenshots are only taken by the Actor node, once per step, immediately before the browser action is executed. Screenshots are stored as files on disk rather than as BLOBs in the database, and only the file path is stored in the events table. This keeps the database small and fast.

### Asynchronous Writes

`log_event()` is always called with `asyncio.create_task()` or `loop.run_in_executor()`, meaning the agent never waits for the database write to complete before moving to the next node. The write happens in the background. This avoids any latency penalty on the agent pipeline from the logging layer.

---

## Technology Choice: SQLite

SQLite was chosen for the following reasons:

- **Zero infrastructure** — no server, no configuration, no network. The database is a single file on disk.
- **Sufficient throughput** — SQLite handles thousands of writes per second, so it is never a bottleneck.
- **Direct inspection** — the database file can be opened with any SQLite browser (DB Browser for SQLite, DBeaver) or queried directly with Python for ad hoc analysis.
- **Portability** — the file can be copied, shared, or archived with no dependencies.



---