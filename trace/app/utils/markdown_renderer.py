# TESTING THIS MODULE:
# Run from Flask shell: flask shell
# Then:
# from app.utils.markdown_renderer import convert_markdown, is_markdown
# print(convert_markdown("# Hello\n\nThis is **bold** and *italic*."))
# print(is_markdown("# This is markdown"))  # True
# print(is_markdown("This is plain text"))  # False
# 
# To test code highlighting:
# md = "```python\ndef hello():\n    return 'world'\n```"
# print(convert_markdown(md))  # Should show <div class="highlight">...</div>
#
# To test TOC:
# from app.utils.markdown_renderer import convert_markdown_with_toc
# content, toc = convert_markdown_with_toc("# H1\n## H2\n### H3\nContent here")
# print(toc)  # Should show TOC HTML
"""
Core Markdown rendering utilities.
"""
from __future__ import annotations

import logging
import re
from html import escape
from typing import Optional, Tuple

import markdown
from markdown import Markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

LOGGER = logging.getLogger(__name__)


def _build_markdown_instance() -> Markdown:
    return Markdown(
        extensions=[
            "markdown.extensions.extra",
            CodeHiliteExtension(guess_lang=False, css_class="highlight", use_pygments=True),
            TocExtension(permalink=True, permalink_class="heading-anchor", toc_depth="2-4"),
            "markdown.extensions.nl2br",
            "markdown.extensions.sane_lists",
            "markdown.extensions.attr_list",
            "markdown.extensions.def_list",
            "markdown.extensions.footnotes",
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
        ]
    )


md = _build_markdown_instance()


def convert_markdown(text: Optional[str]) -> str:
    """Convert markdown text to HTML using the module-level Markdown instance."""
    if text is None:
        return ""
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="ignore")
    text = str(text).strip()
    if text == "":
        return ""
    try:
        md.reset()
        return md.convert(text)
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("Markdown conversion failed")
        return f"<p>{escape(text)}</p>"


def convert_markdown_with_toc(text: Optional[str]) -> Tuple[str, str]:
    """Convert markdown and also return generated TOC HTML."""
    if text is None:
        return "", ""
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="ignore")
    text = str(text).strip()
    if text == "":
        return "", ""
    try:
        md.reset()
        html_content = md.convert(text)
        toc_html = getattr(md, "toc", "") or ""
        return html_content, toc_html
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("Markdown conversion with TOC failed")
        return f"<p>{escape(text)}</p>", ""


def markdown_to_safe_html(text: Optional[str]) -> str:
    """Convert markdown to HTML and strip script tags for basic safety."""
    html_content = convert_markdown(text)
    if not html_content:
        return ""
    return re.sub(r"<script.*?>.*?</script>", "", html_content, flags=re.IGNORECASE | re.DOTALL)


def is_markdown(text: Optional[str]) -> bool:
    """Heuristically determine if text appears to contain markdown."""
    if not text:
        return False
    sample = text if isinstance(text, str) else str(text)
    return any(
        (
            sample.lstrip().startswith("#"),
            "**" in sample,
            "__" in sample,
            "`" in sample,
            "[" in sample and "]" in sample,
            "![" in sample,
            "---" in sample,
            "\n|" in sample or sample.strip().startswith("|"),
            re.search(r"(?m)^\s*[-*]\s+", sample) is not None,
            re.search(r"(?m)^>\s+", sample) is not None,
        )
    )


def highlight_code(code: str, language: str = "") -> str:
    """Highlight code using Pygments, falling back to plain text."""
    if code is None:
        return ""
    lexer = None
    if language:
        try:
            lexer = get_lexer_by_name(language)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        lexer = TextLexer()
    formatter = HtmlFormatter(cssclass="highlight")
    return highlight(code, lexer, formatter)


def get_markdown_instance() -> Markdown:
    """Return a freshly configured Markdown instance."""
    return _build_markdown_instance()
