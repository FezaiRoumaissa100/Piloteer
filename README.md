# Piloteer

Piloteer is an autonomous, AI-driven web navigation agent developed as part of a summer internship project. 

**Project Title:** Conception et développement d'un agent IA de navigation web autonome pour guider et exécuter des démonstrations produit en temps réel.

## Project Context & Objectives

The primary goal of Piloteer is to act as an intelligent commercial or support assistant. It is capable of understanding a user's natural language request, analyzing the web interface of a SaaS application, identifying the correct interactive elements (buttons, inputs, menus, tables), and autonomously guiding or executing actions to perform real-time product demonstrations.

Key objectives of the project include:
1. **Perception:** Building a web navigation agent based on the browser's **Accessibility Tree** rather than raw DOM or pure visual analysis, ensuring deterministic detection of interactive elements.
2. **Execution:** Generating an action plan from a user prompt and executing those actions reliably using Playwright.
3. **Safety & Auditing:** Adding a security layer to prevent destructive or unintended actions, and creating a logging/replay system to review exactly what the agent did.

## The Problematic: Building the "Motor AI"

To achieve these objectives, traditional web automation (Selenium, basic scripts) is insufficient as it breaks when a website's layout changes. 

### Why the Accessibility Tree? (Replacing Raw DOM & Screenshots)
Early versions of AI agents attempted to solve navigation using two flawed approaches:
- **Pure Vision (Screenshots):** Passing screenshots to multimodal models is expensive, introduces high latency, and creates a "grounding problem" (the model can see a button but cannot accurately click its exact X/Y coordinates without complex coordinate-mapping hacks).
- **Raw DOM Parsing:** Passing the full HTML of a modern SaaS application often exceeds 100,000 tokens. It is filled with noisy, non-interactive layout tags (`<div>`, `<span>`) that dilute the LLM's context window and trigger severe rate limits.

Piloteer abandons both in favor of the **Accessibility Tree (AXTree)**. The AXTree is a native browser structure that acts as a semantic distillatory of the page. It strips away presentational noise and exposes only what matters: interactive elements (buttons, links, inputs) and their accessible names. This allows the LLM to "read" the page exactly as a screen reader would, guaranteeing perfect alignment between the agent's intent and the physical element reference.

### The "Motor AI" Loop
Piloteer focuses on building a robust **"Motor AI"** — the underlying logic engine that drives the agent. Instead of planning long, fragile sequences of actions, Piloteer uses a strict **one-step-per-iteration hierarchical loop**. By combining the deterministic perception of the pruned Accessibility Tree with an LLM's reasoning, Piloteer can handle unexpected popups, modal overlays, and changing UIs on the fly. 

When Piloteer encounters a failure, it doesn't just guess; it feeds raw technical diagnostics back into its memory, allowing the Planner to self-correct its approach in real-time.

## Architecture

Piloteer is built around a continuous **Planner → Actor → Validator** loop orchestrated by LangGraph.

1. **Tree Pruning (Perception):**
   Before the Planner sees the page, the raw Accessibility Tree (~20,000 tokens) is passed through a deterministic Python Level-1 Pruner. This module strips out decorative elements and empty layout containers, keeping only interactive elements (buttons, inputs, links) and vital context (dialogs, headings). This reduces the payload to ~2,000 tokens, preventing LLM rate limits and hallucination.

2. **The Planner (Decision):**
   The Planner (LLM) receives the pruned tree, the user's target task, and the memory of previous attempts. It generates exactly **one** immediate action to take. It evaluates the current state of the page to decide if the task is already complete or what the next logical step is.

3. **The Actor (Execution):**
   The Actor receives the instruction and executes it via the Model Context Protocol (MCP) using Playwright. It captures the exact outcome of the action, including a hard boolean `isError` flag if the browser engine fails to execute the step.

4. **The Validator (Evaluation):**
   The Validator analyzes the Accessibility Tree **before** and **after** the action.
   - If a technical error occurred, it extracts the raw causal error.
   - If the action succeeded, it verifies if the target state (User Task) has been reached.
   This reasoning is appended to the agent's memory, and the loop restarts until the Validator confirms the task is done.

## Technologies Used

Based on the project specifications, Piloteer leverages the following stack:

- **AI Models:** Gemini / Gemini Live (used for dynamic reasoning, planning, and validation).
- **Automation Engine:** Playwright / Puppeteer (executing physical clicks and navigation).
- **Languages:** Python (Core Agent Logic) & JavaScript/TypeScript (Next.js for potential UI/Replay interfaces).
- **Orchestration:** LangGraph (for stateful, cyclic multi-agent loops).
- **Perception & Context:** DOM Parser (Accessibility Tree), Screenshot analysis, and RAG architectures.
- **Protocol:** Model Context Protocol (MCP) for standardizing browser control.
