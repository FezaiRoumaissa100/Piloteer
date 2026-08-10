import base64
import pathlib
from loggings.scripts.schema import SCREENS_DIR


def get_screenshot_path(trace_id: str, subgoal_id: str, step_id: str, moment: str) -> str:
    """Creates the directory and returns the absolute path where the screenshot should be saved."""
    run_dir = SCREENS_DIR / trace_id
    run_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{subgoal_id}_{step_id}_{moment}.png"
    filepath = run_dir / filename
    return str(filepath.resolve())