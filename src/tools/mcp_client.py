"""
mcp_client.py — Piloteer
Wrapper around the Playwright MCP server (@playwright/mcp@latest).

Organization:
  - Connection         : SERVER_PARAMS
  - Perception         : get_snapshot, take_screenshot
  - Navigation         : navigate
  - Utilities          : wait_for, evaluate_js
  - Pipeline gateway   : dispatch_action
  - Planner interface  : get_tool_descriptions, TOOL_DESCRIPTIONS
"""

from mcp import ClientSession, StdioServerParameters
from typing import Optional


# ─────────────────────────────────────────────
#  Server connection
# ─────────────────────────────────────────────

import os

SERVER_PARAMS = StdioServerParameters(
    command="npx",
    args=[
        "@playwright/mcp@latest",
        "--caps=devtools",
        "--timeout-action=20000", 
    ],
    env={**os.environ, "HEADLESS": "false"}
)


# ─────────────────────────────────────────────
#  PERCEPTION
# ─────────────────────────────────────────────

async def get_snapshot(
    session: ClientSession,
    target: Optional[str] = None,
    depth: Optional[int] = None,
    boxes: bool = False,
    filename: Optional[str] = None
) -> str:
    """
    Returns the accessibility tree of the current page (YAML format).
    This is the primary perception tool for the agent — refs returned here
    are used by all interaction tools.

    Args:
        target  : Limit snapshot to ONE element and its children (ref e.g. 'e5').
                  If None, captures the entire page.
        depth   : Limit tree depth to reduce token count on deeply nested pages.
        boxes   : If True, adds [x, y, width, height] coordinates per element.
        filename: Save snapshot to a .md file instead of returning text.
    """
    args: dict = {}
    if target:
        args["target"] = target
    if depth is not None:
        args["depth"] = depth
    if boxes:
        args["boxes"] = True
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_snapshot", arguments=args)
    return result.content[0].text


async def take_screenshot(
    session: ClientSession,
    image_type: str = "png",
    scale: str = "css",
    target: Optional[str] = None,
    full_page: bool = False,
    filename: Optional[str] = None
) -> str:
    args: dict = {"type": image_type, "scale": scale}
    if target:
        args["target"] = target
    if full_page:
        args["fullPage"] = True
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_take_screenshot", arguments=args)
    content = result.content[0]
    if hasattr(content, "data") and content.data:
        return content.data
    return getattr(content, "text", "") or ""


# ─────────────────────────────────────────────
#  NAVIGATION
# ─────────────────────────────────────────────

async def navigate(session: ClientSession, url: str) -> str:
    """
    Navigates to the given URL.
    Used by test scripts and internal setup — the Planner never calls this directly.

    Args:
        url : Full address to load (e.g. 'https://app.orangehrm.com'). (REQUIRED)
    """
    result = await session.call_tool("browser_navigate", arguments={"url": url})
    return result.content[0].text


# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────

async def wait_for(
    session: ClientSession,
    time: Optional[float] = None,
    text: Optional[str] = None,
    text_gone: Optional[str] = None
) -> str:
    """
    Waits for a condition before continuing.
    Used by the Actor after navigation actions to let the page stabilize.

    Args:
        time      : Fixed wait in seconds (e.g. 3.0). Use as a last resort.
        text      : Wait until this text APPEARS on the page.
        text_gone : Wait until this text DISAPPEARS (e.g. 'Loading...').
    """
    args: dict = {}
    if time is not None:
        args["time"] = time
    if text:
        args["text"] = text
    if text_gone:
        args["textGone"] = text_gone

    result = await session.call_tool("browser_wait_for", arguments=args)
    return result.content[0].text


async def evaluate_js(
    session: ClientSession,
    function: str,
    target: Optional[str] = None,
    filename: Optional[str] = None
) -> str:
    """
    Executes arbitrary JavaScript in the page.
    Used internally by the Actor for Guide Mode spotlight animations.
    Never exposed to the Planner.

    Args:
        function : JS function code to execute. (REQUIRED)
        target   : If provided, executes the function on this specific element.
        filename : Save output to a file.
    """
    args: dict = {"function": function}
    if target:
        args["target"] = target
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_evaluate", arguments=args)
    return result.content[0].text


# ─────────────────────────────────────────────
#  PIPELINE GATEWAY
#  Single entry-point for the Actor to execute
#  any action chosen by the Planner.
# ─────────────────────────────────────────────

async def dispatch_action(
    session: ClientSession,
    tool_name: str,
    arguments: dict
) -> tuple[str, bool]:
    """
    Executes any Planner-selected action tool via MCP.
    Returns (result_text, is_error).

    Args:
        session   : Active MCP ClientSession.
        tool_name : Tool name chosen by the Planner (e.g. 'browser_click').
        arguments : Arguments dict from the Planner step.
    """
    result   = await session.call_tool(name=tool_name, arguments=arguments)
    text     = result.content[0].text if result.content else "Command executed with no text output."
    is_error = getattr(result, "isError", False)
    return text, is_error


# ─────────────────────────────────────────────
#  PLANNER INTERFACE
#  Single source of truth for action tool
#  descriptions injected into the Planner prompt.
# ─────────────────────────────────────────────

TOOL_DESCRIPTIONS = """
=== TOOLS (always available) ===

- browser_click: Use to click a SINGLE interactive element (button, link, checkbox, radio).
  Do NOT use for typing text (see browser_type) or for revealing hover-only menus (see browser_hover).
  Use the optional "force": true ONLY as a last resort if a previous click failed with
  "intercepts pointer events" on a checkbox/toggle. Do NOT use it to bypass popups.
  Arguments: {"target": "<ref>", "element": "<human_description>", "force": false}

- browser_type: Use to type text into ONE input field.
  For 2+ fields visible in the same form, prefer browser_fill_form — more reliable and token-efficient.
  Set "submit": true to press Enter automatically after typing (avoids a separate press_key call).
  Set "slowly": true to type character by character (for live autocomplete / JS keystroke handlers).
  Arguments: {"target": "<ref>", "text": "<text_to_type>", "element": "<human_description>", "submit": false, "slowly": false}

- browser_fill_form: Use ONLY when 2+ fields are visible in the same form on the current page.
  Do NOT use for a single field — use browser_type instead.
  Supports types: textbox, checkbox (value: "true"/"false" as string), radio, combobox (value: displayed option text).
  Arguments: {"fields": [{"target": "<ref>", "name": "<field_name>", "type": "<textbox|checkbox|radio|combobox>", "value": "<value>", "element": "<human_description>"}]}

- browser_press_key: Use for special keys (Enter, Escape, Tab, ArrowDown) or combinations ("Shift+P", "Control+A").
  ALWAYS use Enter after typing in a search bar instead of clicking a search/submit icon — more reliable.
  Arguments: {"key": "<Enter|Escape|Tab|Shift+P|...>"}

- browser_wait_for: Use to pause when the page is transitioning or an action is still executing
  (e.g. button says "Loading...", "Saving..."). Use condition-based waits over fixed delays.
  Arguments: {"text": "<text_to_wait_for>"} OR {"textGone": "<text_that_should_disappear>"}

- browser_select_option: Use ONLY for native HTML <select> dropdowns.
  Do NOT use for custom JS-based dropdowns (styled divs) — use browser_click on the option instead.
  Arguments: {"target": "<ref>", "values": ["<option_value>"], "element": "<human_description>"}

- browser_hover: Use ONLY to reveal a CSS :hover-triggered menu (e.g. navigation bar submenu)
  BEFORE clicking an item inside it. Never use as a substitute for browser_click.
  Arguments: {"target": "<ref>", "element": "<human_description>"}

- browser_drag: Use ONLY to move an item between positions on the SAME page
  (e.g. Kanban card between columns, list reordering). Not for external file uploads.
  Arguments: {"startTarget": "<ref>", "endTarget": "<ref>", "startElement": "<desc>", "endElement": "<desc>"}

- browser_file_upload: Use immediately AFTER clicking a "Choose file" / "Upload" button that
  opened an OS file dialog. Do NOT call this speculatively before that click.
  Arguments: {"paths": ["<file_path>"]}

- browser_drop: Use ONLY for dropping external OS-level files or data onto a page element
  (distinct from browser_drag which moves elements WITHIN the page).
  Arguments: {"target": "<ref>", "paths": ["<file_path>"]}

- browser_resize: Use ONLY if the task explicitly requires a specific viewport size
  (e.g. "check the mobile view"). Rare — do not use for normal navigation tasks.
  Arguments: {"width": <int>, "height": <int>}

- browser_finish_subgoal: Use when the current SUBGOAL is clearly resolved — either
  100% done on screen, OR confirmed impossible (e.g. search returned 0 results).
  MUST provide both fields:
  - status: "success" if achieved, "impossible" if data does not exist.
  - reason: Short sentence explaining what you observed on screen.
  Arguments: {"status": "<success|impossible>", "reason": "<what you observed>"}

- ask_user: Use ONLY when a REQUIRED form field value is NOT mentioned in the subgoal or task.
  NEVER use for optional fields — leave those as default.
  NEVER use if the value is already stated in the subgoal.
  Arguments: {"question": "<clear, specific question for the user>", "field": "<field name>"}
"""


def get_tool_descriptions() -> str:
    """Returns the action tool descriptions to inject into the Planner system prompt."""
    return TOOL_DESCRIPTIONS