import sqlite3
import pathlib

LOGGINGS_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH      = LOGGINGS_DIR / "database" / "piloteer_logs.db"
SCREENS_DIR  = LOGGINGS_DIR / "screenshots"   


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset: bool = False) -> None:
    try:
        conn = get_connection()
        if reset:
            conn.execute("DROP TABLE IF EXISTS events")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id               TEXT NOT NULL,
            user_task              TEXT,
            subgoal_id             TEXT,
            step_id                TEXT,
            
            node_name              TEXT NOT NULL,
            phase                  TEXT,
            status                 TEXT,
            
            timestamp_start        TEXT,
            timestamp_end          TEXT,
            duration_ms            INTEGER,
            
            gen_ai_model           TEXT,
            gen_ai_input_tokens    INTEGER,
            gen_ai_output_tokens   INTEGER,
            
            payload                TEXT,
            
            screenshot             TEXT
        )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger] DB init error: {e}")


def reset_logs() -> None:
    """Drops all previous logs and recreates a fresh events table."""
    init_db(reset=True)
    print("[Logger] Database reset successfully with clean schema.")
