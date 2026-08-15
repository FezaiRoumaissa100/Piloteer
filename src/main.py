"""
Piloteer — Unified Entry Point.
Run: python src/main.py
"""
import sys
import os

# ── Load .env FIRST — must happen before any LangGraph/LangSmith import ──
from pathlib import Path
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
    print(f"[Piloteer] .env loaded from {_env_path}")

import subprocess
import time
import webbrowser
import threading
import uvicorn

# Add src to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from loggings.scripts.schema import init_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def run_fastapi():
    """Runs the FastAPI server."""
    print("[Piloteer] Starting FastAPI Backend on http://localhost:8000 ...")
    uvicorn.run(
        "interface.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )


def start_nextjs_frontend():
    """Starts the Next.js development server in the background."""
    print("[Piloteer] Launching Next.js Frontend on http://localhost:3000 ...")
    subprocess.Popen("npm run dev", cwd=str(FRONTEND_DIR), shell=True)


def main():
    print("\n[Piloteer] Initializing database...")
    init_db()

    # 1. Start FastAPI Backend first in a daemon thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Wait 2 seconds for FastAPI to bind port 8000
    time.sleep(2)

    # 2. Start Next.js Frontend
    start_nextjs_frontend()

    # 3. Wait 3 seconds for Next.js to start, then open browser
    time.sleep(3)
    print("[Piloteer] Opening chat interface in your browser: http://localhost:3000 ...\n")
    webbrowser.open("http://localhost:3000")

    # Keep main script alive
    try:
        fastapi_thread.join()
    except KeyboardInterrupt:
        print("\n[Piloteer] Shutting down...")


if __name__ == "__main__":
    main()
