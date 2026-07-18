CORE_TOOLS = """
=== CORE TOOLS (always available) ===

- browser_click: Use to click a SINGLE interactive element (button, link, checkbox, radio).
  Do NOT use for typing text (see browser_type) or for revealing hover-only menus (see browser_hover).
  {"target": "<ref>", "element": "<human_description>"}

- browser_type: Use to type text into ONE input field.
  For 2+ fields visible in the same form, prefer browser_fill_form instead — more reliable and token-efficient.
  {"target": "<ref>", "text": "<text_to_type>", "element": "<human_description>"}

- browser_fill_form: Use ONLY when 2+ fields are visible in the same form on the current page.
  Do NOT use for a single field — use browser_type instead.
  {"fields": [{"target": "<ref>", "name": "<field_name>", "type": "<textbox|checkbox|radio|combobox>", "value": "<value>", "element": "<human_description>"}]}

- browser_press_key: Use for special keys only (Enter, Escape, Tab, ArrowDown, etc.), not for typing text.
  ALWAYS use with "Enter" after typing in a search bar instead of clicking a submit/search icon button — more reliable.
  {"key": "<Enter|Escape|Tab|ArrowDown|...>"}

- browser_wait_for: Use to pause and wait when the page is transitioning or processing a previous action.
  Crucial: If the page clearly shows an action is still executing (e.g., a button is disabled and says "Loading", "Saving", "Creating..."), DO NOT give up and return null. Use this tool to wait for that temporary state to finish.
  {"text": "<text_to_wait_for>"} OR {"text_gone": "<text_that_should_disappear>"}

- finish_task: Use this ONLY when you see that the user's overall task is already 100% completed on the current screen and absolutely no more actions are needed. This triggers a final double-check by the Validator.
  {}
"""

OPTIONAL_TOOLS = {
    "select_option": {
        "description": """
- browser_select_option: Use ONLY for native HTML <select> dropdowns.
  Do NOT use for custom JS-based dropdowns (styled divs mimicking a select) — use browser_click on the option instead.
  {"target": "<ref>", "values": ["<option_value>"], "element": "<human_description>"}
""",
        "triggers": ["combobox", "listbox", "<select"],
    },
    "hover": {
        "description": """
- browser_hover: Use ONLY to reveal a CSS :hover-triggered menu (e.g. navigation bar submenu)
  BEFORE clicking an item inside it. Never use as a substitute for browser_click.
  {"target": "<ref>", "element": "<human_description>"}
""",
        "triggers": ["menu", "submenu", "dropdown-trigger"],
    },
    "drag": {
        "description": """
- browser_drag: Use ONLY to move an item between positions on the SAME page (e.g. Kanban card
  between columns, list reordering). Not for external file uploads — see browser_upload.
  {"startTarget": "<ref>", "endTarget": "<ref>", "startElement": "<desc>", "endElement": "<desc>"}
""",
        "triggers": ["kanban", "draggable", "sortable"],
    },
    "upload_file": {
        "description": """
- browser_file_upload: Use immediately AFTER clicking a "Choose file" / "Upload" button that
  opened an OS file dialog. Do NOT call this speculatively without that click happening first.
  {"paths": ["<file_path>"]}
""",
        "triggers": ["file", "upload", "choose file", "browse"],
    },
    "drop_data": {
        "description": """
- browser_drop: Use ONLY for dropping external OS-level files or data onto a page element
  (distinct from browser_drag which moves elements WITHIN the page).
  {"target": "<ref>", "paths": ["<file_path>"]}
""",
        "triggers": ["dropzone", "drag and drop", "drop here"],
    },
    "resize_window": {
        "description": """
- browser_resize: Use ONLY if the task explicitly requires testing a specific viewport size
  (e.g. "check the mobile view"). Rare — do not use for normal navigation tasks.
  {"width": <int>, "height": <int>}
""",
        "triggers": ["responsive", "mobile view", "viewport"],
    },
}


def build_tool_section(snapshot: str, task: str = "") -> str:
    sections = [CORE_TOOLS]
    search_context = (snapshot + " " + task).lower()

    for tool_name, tool_data in OPTIONAL_TOOLS.items():
        if any(trigger in search_context for trigger in tool_data["triggers"]):
            sections.append(tool_data["description"])

    return "\n".join(sections)