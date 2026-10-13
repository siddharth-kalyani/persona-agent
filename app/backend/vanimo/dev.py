"""Local dev server:  uv run python -m vanimo.dev

Same as `uvicorn vanimo.main:app --reload`, but on Windows it runs a selector event
loop, which psycopg's async mode needs (the default Proactor loop is unsupported).
"""

from __future__ import annotations

import asyncio
import os
import sys

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    config = uvicorn.Config("vanimo.main:app", host="127.0.0.1", port=port, log_config=None)
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
