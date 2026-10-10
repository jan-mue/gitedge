"""Markdown rendering service using markdown-it-py with GFM extensions."""

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

# Module-level singleton: GFM-like preset with task lists plugin.
# The "gfm-like" preset enables: tables, strikethrough, linkify, and autolink.
_md = MarkdownIt("gfm-like", {"html": False}).use(tasklists_plugin)


def render_markdown(content: str) -> str:
    """Render Markdown content to HTML using GFM extensions.

    Supports GitHub-Flavored Markdown features:
    - Tables
    - Strikethrough (~~text~~)
    - Task lists (- [x] / - [ ])
    - Autolinks / linkify
    - Fenced code blocks with language hints

    Args:
        content: Raw Markdown string.

    Returns:
        Rendered HTML string.
    """
    return str(_md.render(content))
