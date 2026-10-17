"""Teams transcript text → cues, and cues → speaker turns (M6).

Two formats come back from Graph's `/transcripts/{id}/content` (verified against Microsoft Learn,
2026-10-16):

* `text/vtt` — WebVTT, a cue per utterance with a `<v Speaker Name>` voice tag;
* `application/vnd.microsoft.graph.transcript+text` — the same timestamps without voice tags, when
  the organisation turned speaker attribution off (a blank line may sit between a timestamp and
  its text).

Timestamps are offsets from when transcription started; negative ones mean transcription began
while people were already talking. Cue identifiers (a line just before a timestamp, after a blank
line), `NOTE` blocks and styling tags are dropped. Nothing here is stored: it runs in memory on L0.
"""

from __future__ import annotations

import html
import re

from vanimo.sources.base import Cue

MAX_CUES = 5000
TURN_GAP_MS = 3000  # a pause longer than this starts a new turn, even for the same speaker
MAX_TURN_CHARS = 700

_TS = r"(-?)(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_TIMING = re.compile(rf"^\s*{_TS}\s*-->\s*{_TS}")
_VOICE = re.compile(r"<v(?:\.[\w.-]+)?\s+([^>]*)>(.*?)(?:</v>|$)", re.S)
_TAG = re.compile(r"</?[a-z][^>]*>|</[a-z]*>", re.I)


def _ms(sign: str, h: str | None, m: str, s: str, frac: str) -> int:
    value = ((int(h or 0) * 60 + int(m)) * 60 + int(s)) * 1000 + int(frac.ljust(3, "0")[:3])
    return -value if sign else value


def parse(content: str, *, attributed: bool) -> list[Cue]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "").split("\n")
    cues: list[Cue] = []
    timing: tuple[int, int] | None = None
    body: list[str] = []
    in_note = False

    def flush() -> None:
        if timing is None:
            return
        raw = "\n".join(body).strip()
        speaker = None
        if attributed and (v := _VOICE.search(raw)):
            speaker = " ".join(html.unescape(v.group(1)).split()) or None
            raw = _VOICE.sub(lambda x: x.group(2), raw)
        text = " ".join(html.unescape(_TAG.sub("", raw)).split())
        if text and len(cues) < MAX_CUES:
            cues.append(Cue(timing[0], max(timing[1], timing[0]), speaker, text))

    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped.upper().startswith("WEBVTT"):
            continue
        if (t := _TIMING.match(line)) is not None:
            flush()
            g = t.groups()
            timing, body, in_note = (_ms(*g[:5]), _ms(*g[5:])), [], False
            continue
        if not stripped:
            in_note = False
            continue
        if stripped.startswith(("NOTE", "STYLE", "REGION")) and (i == 0 or not lines[i - 1].strip()):
            in_note = True
            continue
        if in_note:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (i == 0 or not lines[i - 1].strip()) and _TIMING.match(nxt):
            continue  # a cue identifier
        if timing is not None:
            body.append(stripped)
    flush()
    return cues


def turns(cues: list[Cue]) -> list[Cue]:
    """Consecutive cues of one speaker, close in time, joined into one turn (Teams splits sentences
    across cues). Unattributed cues join on time alone, shorter."""
    out: list[Cue] = []
    for c in sorted(cues, key=lambda c: c.start_ms):
        last = out[-1] if out else None
        limit = MAX_TURN_CHARS if c.speaker else MAX_TURN_CHARS // 2
        if (
            last is not None
            and last.speaker == c.speaker
            and c.start_ms - last.end_ms <= TURN_GAP_MS
            and len(last.text) + len(c.text) < limit
        ):
            out[-1] = Cue(last.start_ms, max(last.end_ms, c.end_ms), last.speaker, f"{last.text} {c.text}")
        else:
            out.append(c)
    return out
