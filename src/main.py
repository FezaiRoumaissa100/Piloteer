"""
Piloteer — Entry point.
Run: python main.py
"""
import sys
import os
import asyncio
import webbrowser
import threading
import time

import uvicorn


sys.path.insert(0, os.path.dirname(__file__))


def _open_browser():
    """Wait a bit for the server to start, then open the UI."""
    time.sleep(2)
    print("[Piloteer] Ouverture du navigateur sur l'interface...")
    webbrowser.open("http://localhost:8000")


def main():
    print("\n[Piloteer] Starting server on http://localhost:8000 ...")
    print("[Piloteer] Opening chat interface in your browser...\n")
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(
        "interface.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning" 
    )


if __name__ == "__main__":
    main()
