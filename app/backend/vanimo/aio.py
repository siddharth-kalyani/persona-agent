"""Small asyncio helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any


async def gather_strict(*coros: Coroutine[Any, Any, Any]) -> list[Any]:
    """Run concurrently; on the first failure cancel the rest and raise that error itself.

    (asyncio.gather leaves siblings running; a bare TaskGroup raises an ExceptionGroup, which
    the API's error handlers wouldn't recognise.)
    """
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c) for c in coros]
    except ExceptionGroup as group:
        first: BaseException = group
        while isinstance(first, BaseExceptionGroup):
            first = first.exceptions[0]
        raise first from None
    return [t.result() for t in tasks]
