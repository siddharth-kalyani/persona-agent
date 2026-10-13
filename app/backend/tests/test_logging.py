from __future__ import annotations

import logging

import pytest

from tests.conftest import log_lines
from vanimo.logs import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _logging(capsys: pytest.CaptureFixture) -> None:
    # Configure after capsys starts so the stdlib handler writes into the captured stdout.
    configure_logging("INFO", json=True)


def test_unknown_keys_and_free_text_are_dropped(capsys: pytest.CaptureFixture) -> None:
    log = get_logger()
    log.info("graph.call", graph_status=200, subject="Quarterly results for Acme", body="hello", count=3)
    log.info("Sent mail to priya@example.com")  # free-text event
    log.info("graph.call", route="/api/me?q=priya@example.com")  # unsafe value in an allowed key
    lines = log_lines(capsys.readouterr().out)
    assert lines[0]["graph_status"] == 200 and lines[0]["count"] == 3
    assert "subject" not in lines[0] and "body" not in lines[0] and lines[0]["dropped_fields"] == 2
    assert lines[1]["event"] == "invalid_event"
    assert "route" not in lines[2]
    text = str(lines)
    assert "Acme" not in text and "priya" not in text


def test_stdlib_library_logs_lose_their_message(capsys: pytest.CaptureFixture) -> None:
    logging.getLogger("some.lib").warning("GET https://graph.microsoft.com/v1.0/users/priya@example.com")
    logging.getLogger("httpx").info("HTTP Request: GET ...?$filter=priya")  # below WARNING: silenced
    out = capsys.readouterr().out
    assert "priya" not in out
    lines = log_lines(out)
    assert lines == [{"event": "lib.log", "logger": "some.lib", "level": "warning", "timestamp": lines[0]["timestamp"]}]


def test_exception_messages_are_not_logged(capsys: pytest.CaptureFixture) -> None:
    try:
        raise ValueError("contains client name Acme")
    except ValueError:
        logging.getLogger("uvicorn.error").exception("boom with Acme")
    assert "Acme" not in capsys.readouterr().out
