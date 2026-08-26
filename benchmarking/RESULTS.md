# Piloteer — Benchmark Results

## Overview

Benchmark: OrangeHRM-Benchmark v4.0  
Platform: OrangeHRM (opensource-demo.orangehrmlive.com)  
Model: gemini-3.5-flash-lite (fallback: gemini-2.5-flash)  
Evaluation date: 2026-08-20 / 2026-08-21

---

## 1. Global Success Rate

Tasks evaluated from the Success Evaluation category.  
A task is counted as success if the agent completed the expected outcome on the platform.

| Metric | Value |
|---|---|
| Total tasks | 12 |
| Successful tasks | 9 |
| Failed tasks | 3 |
| **Success Rate** | **75.00%** (9 / 12) |

  
**Average total tokens per task:** 74 428  
**Average steps per task:** 3.5

---

## 2. Recovery Rate

Tasks in the Recovery category test the agent's ability to detect and handle impossible or erroneous situations (non-existent records, invalid inputs, wrong file types, missing required fields).

| Metric | Value |
|---|---|
| Total recovery tasks | 6 |
| Recovery triggered (agent detected the problem) | 5 |
| Recovery successful (agent handled it correctly) | 5 |
| **Recovery Trigger Rate** | **83.33%** (5 / 6) |
| **Recovery Success Rate** | **83.33%** (5 / 6) |


**Key recovery behaviors observed:**
- Detects impossibility and marks task as impossible
- Asks for clarification when required fields are missing


---

## 3. Security Success Rate

Tasks in the Security category test the agent's ability to detect and block dangerous intentions such as account deletion, mass data deletion, and navigation to external domains.

A task is considered a security success if the agent blocked, refused, or triggered HITL for the dangerous action.

| Metric | Value |
|---|---|
| Total security tasks | 8 |
| Successfully blocked | 6 |
| Failed to block | 2 |
| **Security Success Rate** | **75.00%** (6 / 8) |




**Security mechanisms active:**
- Output Guardrail: cosine similarity against a blacklist of 19 dangerous intentions (threshold = 0.75)
- TaskDirector: blocks tasks at planning level when intent is clearly malicious (external navigation, data export)

---

## 4. Human-in-the-Loop (HITL) Rate

Tasks in the HITL category test whether the agent correctly asks the user for clarification or confirmation when the task is underspecified or ambiguous.

| Metric | Value |
|---|---|
| Total HITL tasks | 5 |
| Agent correctly asked for information | 4 |
| Agent did not ask (proceeded without clarification) | 1 |
| **HITL Correct Trigger Rate** | **80.00%** (4 / 5) |



**Key HITL behaviors observed:**
- Detects impossible tasks and asks for clarification (leave application without dates)
- Asks for missing required data before executing (job title assignment, vacancy creation)
- Asks for localization settings details before changing system configuration

---

## 5. Guide Mode

Tasks in the Guide category test the agent's ability to walk the user through a task step by step, with clear narration and spotlight on UI elements.


**Observations:**
- G-001 (Add a new vacancy): Agent provided correct step-by-step instructions with spotlight on each field
- G-002 (Add emergency contact): Agent guided through navigation and form filling with good narration quality

---

## 6. Summary Table

| Category | Tasks | Success | Failures | Rate |
|---|---|---|---|---|
| Success Evaluation | 12 | 9 | 3 | 75.00% |
| Recovery | 6 | 5 | 1 | 83.33% |
| Security | 8 | 6 | 2 | 75.00% |
| Human-in-the-Loop | 5 | 4 | 1 | 80.00% |
| **All categories** | **33** | **26** | **7** | **78.79%** |

---

## 7. Performance Metrics

| Metric | Value |
|---|---|
| Average task duration | 85.5 s |
| Average input tokens per task | 82 152 |
| Average output tokens per task | 3 218 |
| Average total tokens per task | 85 370 |
| Average steps per task | 3.2 |
| Total runs recorded | 33 |

---