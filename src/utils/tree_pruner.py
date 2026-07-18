"""
utils/tree_pruner.py — Accessibility Tree Pruning (no LLM)

Reduces the raw Playwright MCP snapshot tokens
by keeping only elements the Planner can act on + essential context nodes.

Kept:
  - Interactive roles : button, link, textbox, checkbox, combobox, …
  - Context roles     : dialog, alertdialog, heading
  - StaticText nodes  : only if they carry a meaningful label (len > 2)

Dropped:
  - Pure layout containers : group, region, list, listitem, none, generic, …
  - Decorative images / SVGs
  - Empty / whitespace-only nodes
"""

import re

#Roles the Planner can act on
INTERACTIVE_ROLES = frozenset({
    "button",
    "link",
    "textbox",
    "searchbox",
    "checkbox",
    "radio",
    "combobox",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "tab",
    "option",
    "switch",
    "slider",
    "spinbutton",
    "treeitem",
    "gridcell",
    "columnheader",
})

#Roles providing important structural context 
CONTEXT_ROLES = frozenset({
    "dialog",       # modal — agent must know it is blocked
    "alertdialog",  # confirmation / destructive — human-in-the-loop signal
    "heading",      # section label — helps the Planner orient itself
})

#Regex: matches the start of any accessibility-tree node line 
# Playwright MCP emits lines like:
#   - button "Create project" [ref=e601]
#   - textbox "Project name" [ref=e563]
#   - group [ref=e50]:
_ROLE_RE = re.compile(r"^\s*-\s+(\w+)(?:\s+['\"]([^'\"]*)['\"])?")


def prune_snapshot(raw_snapshot: str) -> str:
    """
    Level-1 pruning: keep only interactive elements and key context nodes.

    Args:
        raw_snapshot: Full accessibility tree string from browser_snapshot MCP tool.

    Returns:
        Pruned tree string — same format, greatly reduced size.
    """
    kept: list[str] = []

    for line in raw_snapshot.splitlines():
        m = _ROLE_RE.match(line)
        if not m:
            # Non-node lines (blank lines, YAML metadata, snapshot header) — skip
            continue

        role = m.group(1).lower()
        name = (m.group(2) or "").strip()

        if role in INTERACTIVE_ROLES:
            kept.append(line)

        elif role in CONTEXT_ROLES:
            kept.append(line)

        elif role in ("statictext", "text") and len(name) > 2:
            # Keep meaningful labels; drop single-char icons or empty text nodes
            kept.append(line)

        # Everything else (group, region, list, image, svg, …) is dropped

    pruned = "\n".join(kept)

    # Log reduction for debugging
    original_tokens = len(raw_snapshot.split())
    pruned_tokens   = len(pruned.split())
    print(f"[TreePruner] {original_tokens:,} → {pruned_tokens:,} tokens "
          f"({100 * pruned_tokens // original_tokens}% kept)")

    return pruned
