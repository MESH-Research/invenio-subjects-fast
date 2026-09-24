# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Tests for the shared FAST updates orchestrator."""

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from invenio_subjects_fast.services import process_updates as process_mod
from invenio_subjects_fast.services.process_updates import (
    ProcessUpdatesResult,
    process_fast_updates,
)


def test_process_fast_updates_noop_when_no_pending_mrc(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.download_updates",
        lambda **kwargs: [],
    )
    convert = MagicMock()
    monkeypatch.setattr(
        "invenio_subjects_fast.services.convert_updates.convert_updates", convert
    )

    result = process_fast_updates(tmp_path, since=date(2026, 7, 1))

    assert result.ingested_files == []
    assert result.schemes == {}
    convert.assert_not_called()


def test_process_fast_updates_converts_and_marks_without_ingest(
    tmp_path, monkeypatch
):
    workdir = tmp_path
    (workdir / "processed").mkdir()
    (workdir / "deltas").mkdir()
    mrc = workdir / "FASTChanges2026-07-24.mrc"
    mrc.write_bytes(b"mrc")
    delta_path = workdir / "deltas" / "subjects_fast_topical.updates.jsonl"
    delta_path.write_text("{}\n")

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.download_updates",
        lambda **kwargs: [mrc],
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.convert_updates.convert_updates",
        lambda *args, **kwargs: {
            "FAST-topical": [
                {
                    "id": "http://id.worldcat.org/fast/1",
                    "scheme": "FAST-topical",
                    "subject": "Dogs",
                }
            ]
        },
    )
    moved: list = []

    def fake_mark(paths, download_dir=None):
        moved.extend(list(paths))
        return []

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.mark_update_files_processed",
        fake_mark,
    )
    ingest = MagicMock()
    monkeypatch.setattr(process_mod, "ingest_delta_jsonl", ingest)

    result = process_fast_updates(workdir, since="2026-07-01", ingest=False)

    ingest.assert_not_called()
    assert moved == [mrc]
    assert result.schemes == {"FAST-topical": 1}
    assert result.entry_errors == 0
    assert str(delta_path) in result.deltas


def test_process_fast_updates_ingests_when_requested(tmp_path, monkeypatch):
    workdir = tmp_path
    (workdir / "processed").mkdir()
    (workdir / "deltas").mkdir()
    mrc = workdir / "FASTChanges2026-07-24.mrc"
    mrc.write_bytes(b"mrc")
    delta_path = workdir / "deltas" / "subjects_fast_topical.updates.jsonl"
    delta_path.write_text("{}\n")

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.download_updates",
        lambda **kwargs: [mrc],
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.convert_updates.convert_updates",
        lambda *args, **kwargs: {"FAST-topical": [{"id": "x"}]},
    )
    moved: list = []

    def fake_mark(paths, download_dir=None):
        moved.extend(list(paths))
        return []

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.mark_update_files_processed",
        fake_mark,
    )
    ingest = MagicMock(return_value=0)
    monkeypatch.setattr(process_mod, "ingest_delta_jsonl", ingest)

    result = process_fast_updates(workdir, since=date(2026, 7, 1), ingest=True)

    assert ingest.call_args.args[0] == delta_path
    assert result.entry_errors == 0
    assert moved == [mrc]


def test_process_fast_updates_skips_mark_processed_on_ingest_errors(
    tmp_path, monkeypatch
):
    workdir = tmp_path
    (workdir / "processed").mkdir()
    (workdir / "deltas").mkdir()
    mrc = workdir / "FASTChanges2026-07-24.mrc"
    mrc.write_bytes(b"mrc")
    delta_path = workdir / "deltas" / "subjects_fast_topical.updates.jsonl"
    delta_path.write_text("{}\n")

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.download_updates",
        lambda **kwargs: [mrc],
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.convert_updates.convert_updates",
        lambda *args, **kwargs: {"FAST-topical": [{"id": "x"}]},
    )
    moved: list = []

    def fake_mark(paths, download_dir=None):
        moved.extend(list(paths))
        return []

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.mark_update_files_processed",
        fake_mark,
    )
    ingest = MagicMock(return_value=2)
    monkeypatch.setattr(process_mod, "ingest_delta_jsonl", ingest)

    result = process_fast_updates(workdir, since=date(2026, 7, 1), ingest=True)

    assert ingest.call_args.args[0] == delta_path
    assert result.entry_errors == 2
    assert moved == []
    assert mrc.exists()


def test_ingest_delta_jsonl_counts_errors(monkeypatch):
    stream = MagicMock()
    ok = SimpleNamespace(errors=[])
    bad = SimpleNamespace(errors=["boom"])
    stream.process.return_value = [ok, bad]
    factory = MagicMock()
    factory.create.return_value = stream
    monkeypatch.setitem(sys.modules, "invenio_vocabularies", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "invenio_vocabularies.datastreams", SimpleNamespace()
    )
    monkeypatch.setitem(
        sys.modules,
        "invenio_vocabularies.datastreams.factories",
        SimpleNamespace(DataStreamFactory=factory),
    )

    logged: list[str] = []
    errors = process_mod.ingest_delta_jsonl(
        MagicMock(), log_error=logged.append
    )
    assert errors == 1
    assert logged == ["boom"]


def test_result_as_dict():
    result = ProcessUpdatesResult(
        downloaded=["a"],
        ingested_files=["b"],
        deltas=["c"],
        schemes={"FAST-topical": 1},
        entry_errors=0,
    )
    assert result.as_dict()["schemes"] == {"FAST-topical": 1}


def test_resolve_updates_workdir_explicit(tmp_path):
    from invenio_subjects_fast.services.process_updates import resolve_updates_workdir

    root = resolve_updates_workdir(tmp_path / "changes")
    assert root == tmp_path / "changes"
    assert (root / "processed").is_dir()
    assert (root / "deltas").is_dir()


def test_resolve_updates_workdir_uses_config(base_app, tmp_path):
    from invenio_subjects_fast.services.process_updates import resolve_updates_workdir

    configured = tmp_path / "configured"
    base_app.config["SUBJECTS_FAST_UPDATES_PATH"] = str(configured)

    with base_app.app_context():
        root = resolve_updates_workdir(None)

    assert root == configured
    assert (root / "processed").is_dir()


def test_resolve_updates_workdir_falls_back_to_app_data(base_app):
    from invenio_subjects_fast.services.process_updates import resolve_updates_workdir

    base_app.config["SUBJECTS_FAST_UPDATES_PATH"] = None

    with base_app.app_context():
        root = resolve_updates_workdir(None)

    assert root == (
        Path(base_app.instance_path) / "app_data" / "vocabularies" / "fast"
    )
    assert (root / "processed").is_dir()


def test_resolve_updates_workdir_requires_app_without_explicit_path(base_app):
    from invenio_subjects_fast.services.process_updates import resolve_updates_workdir

    # Outside an application context (base_app alone does not push one).
    with pytest.raises(RuntimeError, match="download_dir"):
        resolve_updates_workdir(None)
