# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Tests for polite download retries and Retry-After handling."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import MagicMock

import requests

from invenio_subjects_fast.config import DEFAULT_INTER_REQUEST_DELAY_SECONDS
from invenio_subjects_fast.services.downloader import (
    _download_with_retry,
    download_marcxml_files,
    retry_after_seconds,
)


def test_retry_after_seconds_parses_integer_header():
    response = MagicMock()
    response.headers = {"Retry-After": "45"}
    assert retry_after_seconds(response, fallback=2) == 45


def test_retry_after_seconds_caps_large_values():
    response = MagicMock()
    response.headers = {"Retry-After": "9999"}
    assert retry_after_seconds(response, fallback=2, max_seconds=300) == 300


def test_retry_after_seconds_parses_http_date():
    when = datetime.now(timezone.utc) + timedelta(seconds=30)
    response = MagicMock()
    response.headers = {"Retry-After": format_datetime(when)}
    delay = retry_after_seconds(response, fallback=2)
    assert 20 <= delay <= 35


def test_retry_after_seconds_falls_back_on_garbage():
    response = MagicMock()
    response.headers = {"Retry-After": "not-a-date"}
    assert retry_after_seconds(response, fallback=7) == 7


def test_download_with_retry_honours_429_retry_after(
    requests_mock, tmp_path, monkeypatch
):
    sleeps: list[float] = []
    monkeypatch.setattr(
        "invenio_subjects_fast.services.downloader.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    url = "https://example.test/file.mrc"
    target = tmp_path / "file.mrc"
    requests_mock.get(
        url,
        [
            {
                "status_code": 429,
                "headers": {"Retry-After": "12"},
            },
            {
                "status_code": 200,
                "content": b"ok",
                "headers": {"Content-Type": "application/octet-stream"},
            },
        ],
    )

    session = requests.Session()
    _download_with_retry(session, url, target, attempts=3)

    assert target.read_bytes() == b"ok"
    assert sleeps == [12.0]


def test_downloader_waits_between_files(requests_mock, tmp_path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(
        "invenio_subjects_fast.services.downloader.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    downloads_dir = tmp_path / "downloads"
    data_dir = Path(__file__).parent / "data"
    for name in ("FASTFormGenre", "FASTMeeting"):
        requests_mock.get(
            (
                "https://researchworks.oclc.org/researchdata/fast/"
                f"{name}.marcxml.zip"
            ),
            content=(data_dir / f"mock_{name}.marcxml.zip").read_bytes(),
            headers={"Content-Type": "application/octet-stream"},
        )

    download_marcxml_files(
        download_dir=downloads_dir, facets=["formgenre", "meeting"]
    )

    assert DEFAULT_INTER_REQUEST_DELAY_SECONDS == 10
    assert sleeps == [10]
