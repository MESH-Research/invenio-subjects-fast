# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Shared HTTP helpers for FAST downloads."""

import requests

from invenio_subjects_fast.config import FAST_DOWNLOAD_USER_AGENT


def browser_download_session(
    referer: str,
    *,
    accept: str = "application/octet-stream,*/*;q=0.8",
) -> requests.Session:
    """Return a ``requests.Session`` with browser-like download headers.

    Args:
        referer: ``Referer`` header value for the remote site.
        accept: ``Accept`` header value (defaults to binary-friendly types).

    Returns:
        A configured session ready for ``get`` / streaming downloads.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": FAST_DOWNLOAD_USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
        }
    )
    return session
