# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Tests for Celery task wiring and invenio-jobs JobType."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from invenio_jobs.errors import TaskExecutionPartialError

from invenio_subjects_fast import tasks as tasks_mod
from invenio_subjects_fast.jobs import ProcessFastSubjectUpdatesJob
from invenio_subjects_fast.services.process_updates import ProcessUpdatesResult
from invenio_subjects_fast.tasks import process_fast_subject_updates


def test_build_task_arguments_includes_since():
    since = datetime(2026, 7, 1, tzinfo=timezone.utc)
    args = ProcessFastSubjectUpdatesJob.build_task_arguments(
        job_obj=SimpleNamespace(), since=since
    )
    assert args == {"since": since}


def test_build_task_arguments_omits_missing_since():
    args = ProcessFastSubjectUpdatesJob.build_task_arguments(
        job_obj=SimpleNamespace(), since=None
    )
    assert args == {}


def test_job_wires_task_and_id():
    assert ProcessFastSubjectUpdatesJob.id == "process_fast_subject_updates"
    assert ProcessFastSubjectUpdatesJob.task is process_fast_subject_updates


def test_task_delegates_to_process_fast_updates(appctx, monkeypatch):
    captured: dict = {}

    def fake_process(**kwargs):
        captured.update(kwargs)
        return ProcessUpdatesResult(downloaded=[], entry_errors=0)

    monkeypatch.setattr(tasks_mod, "process_fast_updates", fake_process)

    result = process_fast_subject_updates(since=date(2026, 7, 1))

    assert captured["since"] == date(2026, 7, 1)
    assert captured["ingest"] is True
    assert captured["log"] is not None
    assert result["entry_errors"] == 0


def test_task_raises_partial_error_on_entry_failures(appctx, monkeypatch):
    monkeypatch.setattr(
        tasks_mod,
        "process_fast_updates",
        lambda *a, **k: ProcessUpdatesResult(entry_errors=3),
    )

    with pytest.raises(TaskExecutionPartialError):
        process_fast_subject_updates(since=date(2026, 7, 1))
