"""Render the add-in manifest for a host:  py render_manifest.py https://dxxxx.cloudfront.net > manifest.xml"""

import sys
import xml.dom.minidom
from pathlib import Path
from urllib.parse import urlparse


def render(host: str) -> str:
    parsed = urlparse(host)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise SystemExit("host must be an https origin, e.g. https://dxxxx.cloudfront.net (Outlook requires HTTPS)")
    origin = f"https://{parsed.netloc}"
    text = (Path(__file__).parent / "manifest.template.xml").read_text(encoding="utf-8").replace("{{HOST}}", origin)
    xml.dom.minidom.parseString(text.encode("utf-8"))  # must stay well-formed
    return text


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.write(render(sys.argv[1]))
