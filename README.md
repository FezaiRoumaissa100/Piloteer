# Piloteer — Autonomous Web Agent

## 1. What is Piloteer?
Piloteer is an advanced, autonomous web navigation agent designed to interact seamlessly with complex SaaS platforms. 

**Missions:**
- **EXECUTE Mode**: Autonomously navigate web applications, fill out forms, and click buttons to achieve a user's target objective (e.g., "Add a new employee").
- **GUIDE Mode**: Act as an interactive, step-by-step instructor. Instead of silently executing the task, it narrates the process and spotlights UI elements to teach the user how to use the platform.
- **QUESTION Mode**: Act as a knowledgeable assistant, instantly answering factual questions about the software based on its internal knowledge base.

**Design Goal:**
To bridge the gap between complex software interfaces and natural language. Piloteer aims to make enterprise software instantly usable by anyone through text or voice, while maintaining strict enterprise-grade security and transparency.

---

## 2. Main Technologies Used and Why

| Technology | Role | Why we chose it |
|------------|------|-----------------|
| **Gemini (LLM)** | The core brain (Planner, Validator, TaskDirector) | Provides state-of-the-art reasoning, enabling the agent to adapt dynamically to unexpected pop-ups or layout changes without rigid scripts. |
| **Playwright & MCP** | Browser automation | **Playwright** captures clean Accessibility Trees (AOM) instead of raw HTML, drastically reducing token usage. **MCP** (Model Context Protocol) provides a standardized, decoupled bridge between the AI logic and the browser instance. |
| **RAG (ChromaDB)** | SaaS Knowledge Base | Prevents hallucination. By scraping official documentation and injecting relevant chunks into the prompt using semantic search, the agent "learns" the software dynamically rather than relying on pre-training. |
| **Semantic Guardrails** | Security | Uses vector embeddings to score the intent of every planned action against a blacklist of dangerous actions (e.g., mass deletions, leaving the domain). If a risk is detected, it enforces a **Human-in-the-Loop (HITL)** pause. |
| **LangGraph** | Orchestration | Creates a robust, stateful loop (Plan → Act → Validate). It enables advanced fallback strategies, like retrying a failed click 3 times before escalating back to the high-level planner for a new strategy. |
| **Gemini Live (Voice)** | Real-time STT / TTS | Powers a seamless, Siri-like voice interface over WebSockets, allowing hands-free operation and natural language HITL resolutions. |

---

## 3. Benchmarking 

To ensure reliability, Piloteer was evaluated against a standardized testing suite. 

- **Benchmark**: OrangeHRM-Benchmark v4.0
- **Test Platform**: OrangeHRM (opensource-demo.orangehrmlive.com)
- **Model Used**: `gemini-3.5-flash-lite` (fallback: `gemini-2.5-flash`)
- **Total Scenarios**: 33 rigorous tasks.
