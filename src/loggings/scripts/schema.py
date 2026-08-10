import sqlite3
import pathlib

LOGGINGS_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH      = LOGGINGS_DIR / "database" / "piloteer_logs.db"
SCREENS_DIR  = LOGGINGS_DIR / "screenshots"   


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    try:
        conn = get_connection()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id               TEXT NOT NULL,
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
