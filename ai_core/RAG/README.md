# Piloteer — RAG Module

This directory contains the Retrieval-Augmented Generation (RAG) module used to inject dynamic SaaS documentation and knowledge into the agent's context.

---

## Technologies Used

- **Vector Database**: [ChromaDB](https://www.trychroma.com/) (Persistent local storage in `rag_db`)
- **Embedding Model**: Google Gemini (`gemini-embedding-001`) via `google-genai`
- **Web Scraping**: Playwright (Headless Chromium)
- **Text Splitting**: Langchain (`RecursiveCharacterTextSplitter`)

---

##  How It Works (Strategy)

The RAG strategy in Piloteer is split into two distinct phases: **Ingestion** (offline/prep) and **Retrieval** (real-time).

### 1. Ingestion (`ingest.py`)
This script is responsible for populating the knowledge base with SaaS documentation.

1. **Scraping**: It uses Playwright to open the documentation URL, wait for network idle (useful for SPAs), and extract the main content using semantic selectors (`article`, `[role='main']`, `.prose`, etc.).
2. **Noise Filtering**: It runs a custom heuristic (`_filter_navigation_text`) that drops short lines (menus, footers, breadcrumbs) to ensure only meaningful paragraphs are embedded.
3. **Chunking**: The cleaned text is split into overlapping chunks of 400 characters (with 50 characters overlap) using Langchain's RecursiveCharacterTextSplitter. This ensures context isn't lost across paragraph breaks.
4. **Embedding & Storage**: Each chunk is embedded using Gemini and stored in ChromaDB. If the URL was previously ingested, old chunks are automatically deleted before inserting the new ones to prevent duplication.

### 2. Retrieval (`retrieve.py`)
This script runs in real-time when the user submits a new task.

1. **Smart Routing**: The `_detect_collection` function looks at the user's current URL (e.g., `orangehrmlive.com`) and automatically routes the query to the corresponding knowledge collection (e.g., `orangehrm_docs`). If unknown, it falls back to a default collection.
2. **Semantic Search**: The user's natural language task is embedded into a vector, and ChromaDB is queried for the top 3 most similar documentation chunks.
3. **Context Formatting**: The retrieved chunks are formatted into a single markdown string, with their exact source URLs prepended (e.g., `[Source: https://...]`).
4. **Injection**: This context is passed into the `SharedState` and injected directly into the `planner_prompt.py` and `task_director_prompt.py` so the LLM knows how the platform operates before planning actions.

---

