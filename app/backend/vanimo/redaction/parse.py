"""S2 Parse (architecture §7.2): HTML → text, quoted history and signatures split off, hidden
content detected. Works on L0 text in memory only."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "table"}
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|color\s*:\s*(#fff\b|#ffffff|white)", re.I
)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0
        self.hidden_seen = False
        self._stack: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        style = dict(attrs).get("style") or ""
        hidden = bool(_HIDDEN_STYLE.search(style)) or tag in ("script", "style", "head", "title")
        if tag not in ("br", "img", "hr", "meta", "link", "input"):
            self._stack.append(hidden)
            if hidden:
                self.hidden_depth += 1
                self.hidden_seen = self.hidden_seen or tag not in ("style", "head", "title")
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            if self._stack.pop():
                self.hidden_depth -= 1
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        # Hidden text (white-on-white, display:none) is a prompt-injection vector: dropped.
        if self.hidden_depth == 0:
            self.parts.append(data)


def html_to_text(value: str) -> tuple[str, bool]:
    """Visible text of an HTML body, and whether hidden content was found and dropped."""
    if "<" not in value:
        return html.unescape(value), False
    parser = _Text()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub("[ \t\u00a0\u202f]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip(), parser.hidden_seen


# Tag characters (U+E0000-E007F) can smuggle invisible instructions to a model.
_TAGS = re.compile("[\U000e0000-\U000e007f]")

_QUOTE_STARTS = re.compile(r"^(on .{3,80} wrote:|-{2,}\s*original message\s*-{2,}|from:\s.+|_{5,})\s*$", re.I | re.M)
_SIGNATURE = re.compile(r"^(--\s*$|sent from my (iphone|android|mobile)|get outlook for)", re.I | re.M)


def strip_quotes(text: str) -> tuple[str, str]:
    """Fallback quote stripper when Graph's `uniqueBody` isn't available: (own words, quoted)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(">") or _QUOTE_STARTS.match(line.strip()):
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
    return text.strip(), ""


def strip_signature_noise(text: str) -> str:
    m = _SIGNATURE.search(text)
    return text[: m.start()].rstrip() if m else text


def clean(text: str) -> tuple[str, bool]:
    """Remove invisible tag characters; report if any were present (a suspicious-input signal)."""
    cleaned = _TAGS.sub("", text)
    return cleaned, cleaned != text
