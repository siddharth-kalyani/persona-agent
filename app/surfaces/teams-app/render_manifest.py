"""Build the Teams app package (manifest.json + icons, zipped) for a host:

    py render_manifest.py https://dxxxx.cloudfront.net <bot-id> <entra-client-id> vanimo-teams.zip

Upload the zip in Teams: Apps → Manage your apps → Upload an app → Upload a custom app (your
organisation must allow custom apps), or have a Teams admin add it for the people who use Vanimo.
The API needs VANIMO_TEAMS_APP_ID set to the manifest's `id` (printed) and VANIMO_TEAMS_BOT_ID to
the bot's ID. The icons are drawn here (no image files to keep in sync).
"""

from __future__ import annotations

import io
import json
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse

GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
ACCENT = (0x2F, 0x5B, 0xA8)


def _png(width: int, height: int, pixel) -> bytes:  # pixel(x, y) -> (r, g, b, a)
    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def _in_v(x: float, y: float, size: int) -> bool:
    """A "V": two strokes from the top corners to the bottom middle."""
    u, v = x / size, y / size
    if not 0.22 <= v <= 0.78:
        return False
    t = (v - 0.22) / 0.56  # 0 at the top, 1 at the bottom
    left = 0.22 + t * 0.28
    right = 0.78 - t * 0.28
    w = 0.09
    return abs(u - left) < w / 2 + 0.01 or abs(u - right) < w / 2 + 0.01


def color_icon() -> bytes:
    return _png(192, 192, lambda x, y: (255, 255, 255, 255) if _in_v(x, y, 192) else (*ACCENT, 255))


def outline_icon() -> bytes:
    return _png(32, 32, lambda x, y: (255, 255, 255, 255) if _in_v(x, y, 32) else (0, 0, 0, 0))


def render(host: str, bot_id: str, client_id: str) -> dict:
    parsed = urlparse(host)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise SystemExit("host must be an https origin, e.g. https://dxxxx.cloudfront.net (Teams requires HTTPS)")
    for name, value in (("bot id", bot_id), ("Entra client id", client_id)):
        if not GUID.match(value):
            raise SystemExit(f"{name} must be a GUID")
    text = (Path(__file__).parent / "manifest.template.json").read_text(encoding="utf-8")
    text = (
        text.replace("{{HOST}}", f"https://{parsed.netloc}")
        .replace("{{DOMAIN}}", parsed.netloc)
        .replace("{{BOT_ID}}", bot_id.lower())
        .replace("{{CLIENT_ID}}", client_id.lower())
    )
    manifest = json.loads(text)  # must stay valid JSON
    if "{{" in text:
        raise SystemExit("unfilled placeholder in the manifest template")
    return manifest


def package(host: str, bot_id: str, client_id: str) -> tuple[bytes, str]:
    manifest = render(host, bot_id, client_id)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("color.png", color_icon())
        z.writestr("outline.png", outline_icon())
    return out.getvalue(), manifest["id"]


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    data, app_id = package(sys.argv[1], sys.argv[2], sys.argv[3])
    Path(sys.argv[4]).write_bytes(data)
    print(f"wrote {sys.argv[4]}; set VANIMO_TEAMS_APP_ID={app_id} and VANIMO_TEAMS_BOT_ID={sys.argv[2].lower()}")
