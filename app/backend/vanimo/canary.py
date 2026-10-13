"""Canaries: planted markers that must never appear where they don't belong.

Release gate (docs/03 §5): seeded excluded chats/threads and never-send words show zero
hits in any store, prompt, draft, answer or log; seeded data of user A never appears to
user B. M0 provides the marker format and the scanners; M1 seeds exclusion and
never-send canaries through the real pipeline.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Iterable

import psycopg
from psycopg import sql

PREFIX = "VNMCANARY"
PATTERN = re.compile(rf"{PREFIX}-[a-z]+-[0-9a-f]{{12}}")


def new_canary(kind: str) -> str:
    if not re.fullmatch(r"[a-z]+", kind):
        raise ValueError("kind must be lowercase letters")
    return f"{PREFIX}-{kind}-{secrets.token_hex(6)}"


def scan_texts(texts: Iterable[str], canaries: Iterable[str] | None = None) -> list[str]:
    """Return every canary found. With `canaries=None`, any canary-shaped marker counts."""
    wanted = set(canaries) if canaries is not None else None
    hits: list[str] = []
    for text in texts:
        for found in PATTERN.findall(text or ""):
            if wanted is None or found in wanted:
                hits.append(found)
    return hits


def scan_database(owner_url: str, canaries: Iterable[str] | None = None) -> dict[str, list[str]]:
    """Scan every text-like column in the `vanimo` schema (as the owner, so RLS doesn't hide rows).

    Returns {"table.column": [hits]} for columns with hits. Used by the daily canary job
    and by tests; it never prints what it scans.
    """
    url = owner_url.replace("postgresql+psycopg://", "postgresql://")
    found: dict[str, list[str]] = {}
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = 'vanimo' and data_type in ('text', 'character varying', 'jsonb', 'json') "
            "and table_name <> 'alembic_version'"
        )
        for table, column in cur.fetchall():
            cur.execute(
                sql.SQL("select {}::text from vanimo.{} where {}::text like %s").format(
                    sql.Identifier(column), sql.Identifier(table), sql.Identifier(column)
                ),
                (f"%{PREFIX}-%",),
            )
            hits = scan_texts((r[0] for r in cur.fetchall()), canaries)
            if hits:
                found[f"{table}.{column}"] = hits
    return found
