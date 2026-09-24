# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Shared JSONL read/write helpers for FAST vocabulary files."""

from collections.abc import Iterable
from pathlib import Path

import jsonlines


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts (empty if missing).

    Args:
        path: Path to a ``.jsonl`` file.

    Returns:
        Parsed rows, or an empty list when ``path`` does not exist.
    """
    if not path.exists():
        return []
    with jsonlines.open(path, "r") as reader:
        return list(reader)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    """Write ``rows`` to ``path`` as JSONL, creating parent dirs as needed.

    Args:
        path: Destination ``.jsonl`` path.
        rows: Iterable of dict rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with jsonlines.open(path, "w") as writer:
        for row in rows:
            writer.write(row)
