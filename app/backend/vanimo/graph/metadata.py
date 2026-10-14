"""Metadata-only Graph reads (headers, rosters, org chart).

Exclusions are applied before any message text is read (architecture §6.5), so these
helpers must never select a content field. `assert_metadata_only` enforces that for
every `$select` built here, and tests pin the exact field lists.
"""

from __future__ import annotations

from typing import Any

from vanimo.graph.client import GraphClient, GraphError

CONTENT_FIELDS = frozenset({"body", "uniqueBody", "bodyPreview", "attachments", "hasAttachments"})

SENT_HEADER_FIELDS = (
    "id",
    "conversationId",
    "subject",
    "sentDateTime",
    "toRecipients",
    "ccRecipients",
    "bccRecipients",
    "internetMessageId",
)
# mail/userPrincipalName are used in memory only, to leave the user out of their own Sources index.
ME_FIELDS = ("id", "displayName", "jobTitle", "department", "mail", "userPrincipalName")
# The manager's address is used in memory only, to label messages to them ("writing to: your manager").
MANAGER_FIELDS = ("id", "displayName", "jobTitle", "mail", "userPrincipalName")
# Received mail for the drafting thread picker (M3): headers only.
INBOX_HEADER_FIELDS = ("id", "conversationId", "subject", "receivedDateTime", "from", "toRecipients", "ccRecipients")


def assert_metadata_only(fields: tuple[str, ...] | list[str]) -> str:
    bad = CONTENT_FIELDS.intersection(fields)
    if bad:
        raise ValueError(f"content fields are not allowed in metadata reads: {sorted(bad)}")
    return ",".join(fields)


async def me(graph: GraphClient) -> dict[str, Any]:
    return await graph.get("me", {"$select": assert_metadata_only(ME_FIELDS)})


async def manager(graph: GraphClient) -> dict[str, Any] | None:
    try:
        return await graph.get("me/manager", {"$select": assert_metadata_only(MANAGER_FIELDS)})
    except GraphError as exc:
        if exc.status == 404:
            return None
        raise


async def recent_sent_headers(graph: GraphClient, top: int = 5) -> list[dict[str, Any]]:
    page = await graph.get(
        "me/mailFolders/sentitems/messages",
        {
            "$select": assert_metadata_only(SENT_HEADER_FIELDS),
            "$orderby": "sentDateTime desc",
            "$top": str(top),
        },
    )
    return list(page.get("value", []))


async def recent_inbox_headers(graph: GraphClient, top: int = 50) -> list[dict[str, Any]]:
    page = await graph.get(
        "me/mailFolders/inbox/messages",
        {
            "$select": assert_metadata_only(INBOX_HEADER_FIELDS),
            "$orderby": "receivedDateTime desc",
            "$top": str(top),
        },
        headers={"Prefer": 'IdType="ImmutableId"'},
    )
    return list(page.get("value", []))
