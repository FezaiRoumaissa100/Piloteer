"""
Piloteer unified launcher.

Lance uniquement :
1. FastAPI / Piloteer sur le port 8000.
2. Le frontend Next.js qui contient le widget Siri sur le port 3000.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

processes: list[tuple[str, subprocess.Popen]] = []


def launch(
    name: str,
    command: list[str],
    cwd: Path,
    color: str = RESET,
) -> subprocess.Popen:
    """Lance une commande depuis un dossier existant."""
    cwd = cwd.resolve()

    if not cwd.exists():
        raise FileNotFoundError(f"Dossier introuvable pour {name}: {cwd}")
    if not cwd.is_dir():
        raise NotADirectoryError(f"Le cwd n'est pas un dossier pour {name}: {cwd}")

    print(f"{color}▶ Lancement de {name} depuis {cwd}{RESET}")

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=False,
    )
    processes.append((name, process))
    return process


def stream_output(name: str, process: subprocess.Popen, color: str) -> None:
    """Affiche la sortie d'un processus dans un thread séparé."""
    if process.stdout is None:
        return

    def read_output() -> None:
        for line in iter(process.stdout.readline, ""):
            print(f"{color}[{name}]{RESET} {line}", end="")

    threading.Thread(target=read_output, daemon=True).start()


def cleanup(*_signals: object) -> None:
    print(f"\n{YELLOW}⏹ Arrêt de Piloteer...{RESET}")
    for name, process in processes:
        if process.poll() is None:
            print(f"   Arrêt de {name}...")
            process.terminate()
    raise SystemExit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)
os.environ["PYTHONUNBUFFERED"] = "1"


if __name__ == "__main__":
    print(f"""
{CYAN}╔════════════════════════════════════════╗
║         PILOTEER  —  Launcher          ║
╚════════════════════════════════════════╝{RESET}
""")

    if not (FRONTEND_DIR / "package.json").is_file():
        raise FileNotFoundError(
            "Frontend Next.js introuvable : "
            f"{FRONTEND_DIR / 'package.json'}"
        )

    server_process = launch(
        "Server  ",
        [sys.executable, "-u", "-m", "ai_server.server"],
        cwd=ROOT,
        color=GREEN,
    )
    stream_output("Server  ", server_process, GREEN)
    time.sleep(3)

    frontend_process = launch(
        "Frontend",
        ["npm.cmd", "run", "dev"],
        cwd=FRONTEND_DIR,
        color=YELLOW,
    )
    stream_output("Frontend", frontend_process, YELLOW)
    time.sleep(3)

    print(f"""
{GREEN} FastAPI et Next.js sont démarrés.{RESET}

  {CYAN}Widget Siri / application Next.js{RESET} → http://localhost:3000
  {GREEN}Backend Piloteer{RESET}                 → http://localhost:8000

  Ctrl+C pour tout arrêter.
""")

    try:
        webbrowser.open("http://localhost:3000/voice")
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
            if server_process.poll() is not None:
                print(f"{GREEN}[Server]{RESET} Le processus s'est arrêté.")
                break
            if frontend_process.poll() is not None:
                print(f"{YELLOW}[Frontend]{RESET} Le processus s'est arrêté.")
                break
    except KeyboardInterrupt:
    
        cleanup()
