# Piloteer — Prompts

This directory contains the three prompt modules that define every instruction, rule, and example given to Gemini across the entire agent pipeline. Each module pairs a **system prompt** (static, defines the agent's identity and rules) with a **content prompt** (dynamic, built fresh each call from live state).

---


## Prompting Techniques Used

### 1. Role Assignment (System Prompt Identity)
Every system prompt opens with a clear role declaration. This anchors the model's behaviour and prevents generic, unfocused outputs.

```
"You are the Planner agent of Piloteer, an autonomous web navigation system.
Your job is to analyze the current page accessibility tree to decide
the SINGLE NEXT ACTION needed to make progress toward the current subgoal."
```

**Why it works**: LLMs perform significantly better when given a precise persona and a narrow scope. The role constrains the solution space from the very first token.

---

### 2. Structured Chain-of-Thought (CoT) Reasoning
All three prompts enforce a **mandatory numbered reasoning chain** before the final decision. The model cannot skip to the answer without passing through each analytical step.

**Planner — 5-step chain:**
```
1_analyze_subgoal      → What is the target end-state and exact values?
2_analyze_hints_memory → What did the past actions tell us? Any repeated failures?
3_analyze_tree         → Which page am I on? What refs exist? Is the subgoal already done?
4_make_decision        → What is the logical next step?
5_select_tool          → Which exact tool and arguments?
```

**Validator — 4-step chain:**
```
1_analyze_subgoal      → What must be TRUE/VISIBLE for the subgoal to be complete?
2_analyze_step_result  → What did Playwright return? Success or error type?
3_analyze_current_state → What does the URL and page structure imply?
4_verification         → Final combined verdict.
```

**TaskDirector (Understand) — 4-step chain:**
```
1_analyze_platform     → What platform is this? What are its capabilities?
2_analyze_task         → Is this a question, an action, or an impossible request?
3_analyze_context      → What does the RAG context provide for this specific task?
4_decision             → Choose mode (QUESTION / EXECUTE / GUIDE / IMPOSSIBLE) and justify.
```

**Why it works**: CoT forces the model to build intermediate conclusions before the final answer, dramatically reducing hallucinations and wrong tool choices. Making the chain **mandatory JSON fields** means the reasoning is always present and auditable in the logs.

---

### 3. Few-Shot Examples
Every system prompt includes **fully worked examples** in the target JSON format. Examples cover both success paths and failure paths.

**Planner examples cover:**
- Standard progress action (Guide mode narration)
- Missing required data → `ask_user`
- Subgoal already achieved → `browser_finish_subgoal`
- Loop prevention (same action failed twice → pivot strategy)
- Navigation without explicit hints (relying on SaaS UX conventions)

**Validator examples cover:**
- Playwright selector format error (`ref=f2e26` vs `f2e26`)
- Action succeeded but subgoal not yet done
- Action succeeded and subgoal confirmed by URL change

**TaskDirector examples cover:**
- QUESTION mode (informational query)
- EXECUTE mode (real browser actions)
- GUIDE mode (step-by-step walkthrough)
- IMPOSSIBLE mode (incompatible task)

**Why it works**: Few-shot examples define the exact output schema implicitly. The model learns the reasoning style, the vocabulary, and the expected JSON structure without needing additional instructions. Examples with failure cases teach the model to reason about errors, not just happy paths.

---

### 4. Strict Rules with Numbered Constraints
Each prompt contains an explicit `=== STRICT RULES ===` section with numbered, imperative constraints. This prevents the most common failure modes.

---

### 5. Conditional Prompt Injection (Dynamic System Prompt)
The Planner system prompt is built dynamically at runtime using a factory function. Sections are included or excluded based on the current execution mode.

```python
def planner_system_prompt(execution_mode: str = "EXECUTE") -> str:
    narration_rule = GUIDE_NARRATION_RULE if execution_mode == "GUIDE" else ""
    return f"""
{PLANNER_ROLE}
{tool_section}
{PLANNER_RULES}
{narration_rule}       # ← only injected in GUIDE mode
{PLANNER_OUTPUT_FORMAT}
"""
```

**Why it works**: The system prompt stays lean in EXECUTE mode and gets the narration rules only when the agent is in tutorial mode. This avoids confusing the model with irrelevant instructions.

---

### 6. Guide Mode Narration Rules (Pedagogical Prompting)
When `execution_mode == "GUIDE"`, a special narration block is injected into the Planner system prompt. It instructs the model to generate the `description` field as a live, human-style tutorial narration that adapts to the memory of past actions.



**Why it works**: The description field doubles as both an audit log and a real-time explanation for the user. Asking the model to adopt a "knowledgeable instructor" persona produces natural language instead of robotic summaries.

---



**Why it works**: End-state subgoals give the Planner and Validator a shared objective. The Planner decides HOW to get there. The Validator checks IF the screen matches. This separation of concerns prevents goal-drift and makes validation unambiguous.

---

### 7. Dynamic Content Prompts (Stateful Context Injection)
Each content prompt is rebuilt every single call from the live state. This gives the model full situational awareness without relying on conversation history.

**Planner content prompt injects:**
- Current subgoal description
- RAG-retrieved SaaS context (`saas_info`)
- Full accessibility tree snapshot (the live page state)
- `mini_planner_hints` (navigation hints from TaskDirector, only when available)
- User answer from previous `ask_user` call (with re-interpretation guidance)
- Memory of last N actions with OK/FAIL labels

**Validator content prompt injects:**
- Current subgoal
- The step that was executed (tool + arguments + description)
- Playwright result text — with conditional framing: labelled as `PLAYWRIGHT ERROR` or `EXPLICIT PLANNER MESSAGE` or omitted entirely
- Current page URL
- Full accessibility tree snapshot

**Why it works**: Each call is self-contained. The model never needs to remember prior turns. Memory is managed explicitly by the system, not left to the model's context window.

---

### 9. Language-Adaptive Responses
The TaskDirector is instructed to detect the user's language and respond in the same language. It also passes this information as a hint to the Planner for Guide Mode narration.

```
"You must detect the language of the user and respond in that language.
If the mode is GUIDE, include a hint for the Planner to generate descriptions in that language."
```

**Why it works**: Users interacting in French, Arabic, or any other language receive a fully localized experience without any hardcoded language logic in the code.

---

### 10. Failure-Aware Prompting (Revision Mode)
The TaskDirector's revision system prompt (`REVISE_SYSTEM_PROMPT`) is specifically designed to reason about failure. It forces the model to go beyond the surface error message and diagnose the underlying root cause.

```
"Do not just accept the failure reason at face value — reason about the underlying cause.
What would a human expert do differently in this situation?"
```

**The revision chain:**
```
1_analyze_subgoal_and_progress → What was the goal? Where exactly is the agent stuck?
2_diagnose_failure             → WHY is it failing? Root cause, not just the error message.
3_decision                     → Revised plan: correct approach, add intermediate steps, or declare impossible.
```

If revision is impossible (e.g. the data simply does not exist), the model returns `"new_subgoals": []` which triggers the TaskDirector to mark the task as `task_impossible` and generate a graceful final message.

---

### 11. Tone-Adaptive Finalization
The finalize prompt instructs the model to adapt its tone to the outcome and the execution mode.

| Outcome | Tone |
|---------|------|
| All subgoals completed (EXECUTE) | Warm, positive, confirms the objective achieved |
| All subgoals completed (GUIDE) | Friendly, tells the user where they now are and what to do next |
| Some subgoals failed | Honest about what worked and what did not |
| Task was impossible | Clear and factual, avoids excessive apology |

---
