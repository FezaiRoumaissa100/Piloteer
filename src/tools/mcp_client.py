"""
mcp_client.py — Piloteer
Complete wrapper around the Playwright MCP server (@playwright/mcp@latest).

Each function maps to ONE MCP tool exposed by the server.
All functions are async and require an active ClientSession.

Organization:
  - Connection / debug
  - Perception       : snapshot, screenshot, console, network
  - Navigation       : navigate, back, tabs
  - Interaction      : click, type, press_key, hover, select, drag, drop, fill_form, upload
  - Utilities        : wait_for, resize, handle_dialog
  - Advanced/Unsafe  : evaluate (blocked in guardrails.py)
  - Close            : close_browser
"""

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Optional

# ─────────────────────────────────────────────
#  Server connection
# ─────────────────────────────────────────────

SERVER_PARAMS = StdioServerParameters(
    command="npx",
    args=[
        "@playwright/mcp@latest",
        "--caps=devtools",
        "--timeout-action=20000",   # default is 5000ms — increased for slow SaaS navigation
    ]
)


# ─────────────────────────────────────────────
#  Debug — list available tools
# ─────────────────────────────────────────────

async def list_tools(session: ClientSession) -> None:
    """List all tools exposed by the MCP server (useful for debugging)."""
    result = await session.list_tools()
    for tool in result.tools:
        print(f"  🔧 {tool.name}")
        print(f"     {tool.inputSchema}\n")


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
                  Useful when crossing with a screenshot.
        filename: Save snapshot to a .md file instead of returning text.
                  Useful for very large pages that would overflow the context window.
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
    """
    Takes a screenshot of the current page or a specific element.
    Used by Gemini Vision as a fallback for Shadow DOM or non-ARIA elements.

    Args:
        image_type : Image format — 'png' or 'jpeg'. (REQUIRED)
        scale      : 'css' = CSS pixels (lightweight, recommended for Gemini Vision).
                     'device' = high-res physical pixels (heavier). (REQUIRED)
        target     : If provided, captures ONE specific element only.
                     Cannot be combined with full_page=True.
        full_page  : If True, captures the full page including non-visible parts.
        filename   : Save image to file instead of returning bytes.
    """
    args: dict = {"type": image_type, "scale": scale}
    if target:
        args["target"] = target
    if full_page:
        args["fullPage"] = True
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_take_screenshot", arguments=args)
    return result.content[0].text


async def get_console_messages(
    session: ClientSession,
    level: str = "error",
    all_messages: bool = False,
    filename: Optional[str] = None
) -> str:
    """
    Retrieves JavaScript console messages from the browser.
    Used by the Validator to detect silent errors that don't appear in the UI.

    Args:
        level        : Minimum severity — 'error', 'warning', 'info', 'debug'. (REQUIRED)
                       Each level includes messages from more severe levels.
        all_messages : True = from the beginning of the session.
                       False = since the last navigation only.
        filename     : Save to file instead of returning text.
    """
    args: dict = {"level": level}
    if all_messages:
        args["all"] = True
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_console_messages", arguments=args)
    return result.content[0].text


async def get_network_requests(
    session: ClientSession,
    static: bool = False,
    filter_pattern: Optional[str] = None,
    filename: Optional[str] = None
) -> str:
    """
    Lists all network requests made by the page.
    Used by the Validator to verify API calls succeeded (e.g. POST returned 200).

    Args:
        static         : REQUIRED. True = include static resources (images, CSS, JS).
        filter_pattern : Regex to filter request URLs (e.g. '/api/.*tasks').
        filename       : Save to file instead of returning text.
    """
    args: dict = {"static": static}
    if filter_pattern:
        args["filter"] = filter_pattern
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_network_requests", arguments=args)
    return result.content[0].text


async def get_network_request_detail(
    session: ClientSession,
    index: int,
    part: Optional[str] = None,
    filename: Optional[str] = None
) -> str:
    """
    Retrieves full details of a specific network request (1-based index).

    Args:
        index    : Request number (1-based) as returned by get_network_requests. (REQUIRED)
        part     : Part to retrieve — 'request-headers', 'request-body',
                   'response-headers', 'response-body'. If None, returns everything.
        filename : Save to file instead of returning text.
    """
    args: dict = {"index": index}
    if part:
        args["part"] = part
    if filename:
        args["filename"] = filename

    result = await session.call_tool("browser_network_request", arguments=args)
    return result.content[0].text


# ─────────────────────────────────────────────
#  NAVIGATION
# ─────────────────────────────────────────────

async def navigate(session: ClientSession, url: str) -> str:
    """
    Navigates to the given URL.

    Args:
        url : Full address to load (e.g. 'https://app.cal.com'). (REQUIRED)
    """
    result = await session.call_tool("browser_navigate", arguments={"url": url})
    return result.content[0].text


async def navigate_back(session: ClientSession) -> str:
    """
    Equivalent to the browser's Back button.
    No parameters.
    """
    result = await session.call_tool("browser_navigate_back", arguments={})
    return result.content[0].text


async def manage_tabs(
    session: ClientSession,
    action: str,
    index: Optional[int] = None,
    url: Optional[str] = None
) -> str:
    """
    Manages browser tabs.

    Args:
        action : 'list' | 'new' | 'close' | 'select'. (REQUIRED)
        index  : Tab number for 'close' or 'select'.
                 If omitted for 'close', closes the current tab.
        url    : URL to open in the new tab (only used with action='new').
    """
    args: dict = {"action": action}
    if index is not None:
        args["index"] = index
    if url:
        args["url"] = url

    result = await session.call_tool("browser_tabs", arguments=args)
    return result.content[0].text


# ─────────────────────────────────────────────
#  INTERACTION
# ─────────────────────────────────────────────

async def click(
    session: ClientSession,
    ref: str,
    label: Optional[str] = None,
    double_click: bool = False,
    button: str = "left",
    modifiers: Optional[list] = None
) -> str:
    """
    Clicks on an element identified by its accessibility tree reference.

    Args:
        ref         : Element reference (e.g. 'e5') returned by get_snapshot. (REQUIRED)
        label       : Human-readable description (e.g. 'Login button').
                      Optional but recommended to enrich logs and HITL traces.
        double_click: True to simulate a double-click.
        button      : 'left' (default) | 'right' | 'middle'.
        modifiers   : Keys to hold during click — ['Control'], ['Shift'], ['Alt'], ['Meta'].
    """
    args: dict = {"target": ref}
    if label:
        args["element"] = label
    if double_click:
        args["doubleClick"] = True
    if button != "left":
        args["button"] = button
    if modifiers:
        args["modifiers"] = modifiers

    result = await session.call_tool("browser_click", arguments=args)
    return result.content[0].text


async def type_text(
    session: ClientSession,
    ref: str,
    text: str,
    label: Optional[str] = None,
    submit: bool = False,
    slowly: bool = False
) -> str:
    """
    Types text into an input field.

    Args:
        ref    : Element reference (e.g. 'e12'). (REQUIRED)
        text   : Text to insert. (REQUIRED)
        label  : Human-readable description of the field. Optional, for logs.
        submit : True = automatically press Enter after typing.
                 Avoids a separate press_key call.
        slowly : True = type character by character.
                 Useful to trigger JS keystroke event handlers (autocomplete, live validation).
                 Default is instant fill, which is faster but may skip those handlers.
    """
    args: dict = {"target": ref, "text": text}
    if label:
        args["element"] = label
    if submit:
        args["submit"] = True
    if slowly:
        args["slowly"] = True

    result = await session.call_tool("browser_type", arguments=args)
    return result.content[0].text


async def press_key(session: ClientSession, key: str) -> str:
    """
    Presses a keyboard key at the page level (not targeted at a specific element).
    Equivalent to page.keyboard.press() in raw Playwright.

    Args:
        key : Key name (e.g. 'Enter', 'Escape', 'Tab', 'ArrowDown')
              or single character (e.g. 'a'). (REQUIRED)
    """
    result = await session.call_tool("browser_press_key", arguments={"key": key})
    return result.content[0].text


async def hover(
    session: ClientSession,
    ref: str,
    label: Optional[str] = None
) -> str:
    """
    Hovers over an element without clicking.
    Useful to trigger CSS :hover dropdown menus in navigation bars.

    Args:
        ref   : Element reference. (REQUIRED)
        label : Human-readable description. Optional, for logs.
    """
    args: dict = {"target": ref}
    if label:
        args["element"] = label

    result = await session.call_tool("browser_hover", arguments=args)
    return result.content[0].text


async def select_option(
    session: ClientSession,
    ref: str,
    values: list,
    label: Optional[str] = None
) -> str:
    """
    Selects one or more options in a <select> dropdown.

    Args:
        ref    : Reference of the <select> element. (REQUIRED)
        values : List of values to select (e.g. ['Option A']).
                 Always a list, even for a single value.
                 Natively supports multi-select. (REQUIRED)
        label  : Human-readable description. Optional, for logs.
    """
    args: dict = {"target": ref, "values": values}
    if label:
        args["element"] = label

    result = await session.call_tool("browser_select_option", arguments=args)
    return result.content[0].text


async def drag(
    session: ClientSession,
    start_ref: str,
    end_ref: str,
    start_label: Optional[str] = None,
    end_label: Optional[str] = None
) -> str:
    """
    Drags one element and drops it onto another (in-page drag & drop).
    Useful for moving Kanban cards between columns (e.g. Plane).

    Args:
        start_ref   : Reference of the element to drag. (REQUIRED)
        end_ref     : Reference of the drop target. (REQUIRED)
        start_label : Human-readable description of the source. Optional, for logs.
        end_label   : Human-readable description of the target. Optional, for logs.
    """
    args: dict = {"startTarget": start_ref, "endTarget": end_ref}
    if start_label:
        args["startElement"] = start_label
    if end_label:
        args["endElement"] = end_label

    result = await session.call_tool("browser_drag", arguments=args)
    return result.content[0].text


async def drop_data(
    session: ClientSession,
    ref: str,
    paths: Optional[list] = None,
    data: Optional[dict] = None,
    label: Optional[str] = None
) -> str:
    """
    Drops an external file or data onto a page element (OS-level drag).
    Different from drag() which moves elements within the page.

    Args:
        ref   : Reference of the target element. (REQUIRED)
        paths : List of file paths to drop (e.g. ['C:/docs/report.pdf']).
        data  : MIME-typed data to drop (e.g. {'text/plain': 'hello'}).
        label : Human-readable description. Optional, for logs.
    """
    args: dict = {"target": ref}
    if paths:
        args["paths"] = paths
    if data:
        args["data"] = data
    if label:
        args["element"] = label

    result = await session.call_tool("browser_drop", arguments=args)
    return result.content[0].text


async def upload_file(
    session: ClientSession,
    paths: Optional[list] = None
) -> str:
    """
    Responds to an OS file upload dialog.
    Call this immediately after clicking a 'Choose File' button.

    Args:
        paths : List of file paths to upload.
                If None, cancels the file chooser dialog.
    """
    args: dict = {}
    if paths:
        args["paths"] = paths

    result = await session.call_tool("browser_file_upload", arguments=args)
    return result.content[0].text


async def fill_form(session: ClientSession, fields: list) -> str:
    """
    Fills multiple form fields in a single MCP call.
    More efficient than multiple successive type_text calls.

    Args:
        fields : List of field dicts, each describing one field:
            {
              'target' : str,   # element ref from get_snapshot (REQUIRED)
              'name'   : str,   # field name (REQUIRED)
              'type'   : str,   # 'textbox' | 'checkbox' | 'radio' |
                                #  'combobox' | 'slider' (REQUIRED)
              'value'  : str,   # value to fill (REQUIRED)
                                #   checkbox: 'true' or 'false' (string, not bool)
                                #   combobox: displayed option text
              'element': str    # human-readable label (optional)
            }

    Example:
        await fill_form(session, [
            {'target': 'e5', 'name': 'email',    'type': 'textbox',  'value': 'a@b.com'},
            {'target': 'e6', 'name': 'password', 'type': 'textbox',  'value': 'pass123'},
            {'target': 'e7', 'name': 'remember', 'type': 'checkbox', 'value': 'true'},
        ])
    """
    result = await session.call_tool("browser_fill_form", arguments={"fields": fields})
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
    Prefer 'text' or 'text_gone' over 'time' when possible —
    condition-based waits are more reliable than fixed delays.

    Args:
        time      : Fixed wait in seconds (e.g. 2.0). Use as a last resort.
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


async def resize_window(session: ClientSession, width: int, height: int) -> str:
    """
    Resizes the browser window.
    Useful to standardize screenshot dimensions across sessions.

    Args:
        width  : Width in pixels. (REQUIRED)
        height : Height in pixels. (REQUIRED)
    """
    result = await session.call_tool(
        "browser_resize",
        arguments={"width": width, "height": height}
    )
    return result.content[0].text


async def handle_dialog(
    session: ClientSession,
    accept: bool,
    prompt_text: Optional[str] = None
) -> str:
    """
    Responds to a native JavaScript dialog (alert, confirm, prompt).
     Deletion confirm() dialogs must be intercepted by guardrails.py
    before reaching this function — never auto-accept destructive dialogs.

    Args:
        accept      : True = click OK. False = click Cancel. (REQUIRED)
        prompt_text : Text to type if the dialog is a prompt() asking for input.
    """
    args: dict = {"accept": accept}
    if prompt_text:
        args["promptText"] = prompt_text

    result = await session.call_tool("browser_handle_dialog", arguments=args)
    return result.content[0].text


# ─────────────────────────────────────────────
#  ADVANCED / UNSAFE
#  hese tools MUST be blocked in guardrails.py
#  Never expose them in the Planner's action_type vocabulary
# ─────────────────────────────────────────────

async def evaluate_js(
    session: ClientSession,
    function: str,
    target: Optional[str] = None,
    filename: Optional[str] = None
) -> str:
    """
    UNSAFE — Executes arbitrary JavaScript in the page.
    Reserved for internal debugging only. Never exposed to the Planner.

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


# browser_run_code_unsafe is intentionally NOT implemented.
# It executes raw Playwright code with full page access —
# the highest-risk entry point in the MCP system.
# Blocked at the guardrails level.


# ─────────────────────────────────────────────
#  CLOSE
# ─────────────────────────────────────────────

async def close_browser(session: ClientSession) -> str:
    """
    Closes the browser and releases all resources.
    No parameters.
    """
    result = await session.call_tool("browser_close", arguments={})
    return result.content[0].text