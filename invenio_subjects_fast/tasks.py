# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Celery tasks for FAST subject vocabulary updates (InvenioRDM).

Requires an Invenio application environment (Celery, Flask, invenio-jobs).
Registered via the `invenio_celery.tasks` entry point. Orchestration lives in
`process_updates`; this module only enables ingest and maps partial failures
to invenio-jobs errors.
"""

from celery import shared_task
from flask import current_app
from invenio_jobs.errors import TaskExecutionPartialError

from invenio_subjects_fast.services.process_updates import process_fast_updates


@shared_task(ignore_result=True)
def process_fast_subject_updates(since=None, **kwargs):
    """Run the FAST updates pipeline (same as CLI `process-updates --ingest`).

    Workdir comes from `resolve_updates_workdir` (`SUBJECTS_FAST_UPDATES_PATH`,
    else `<instance_path>/app_data/vocabularies/fast/`).

    Args:
        since: Optional ISO date/datetime or `date` (job bookmark).
        **kwargs: Ignored extra job arguments.

    Returns:
        Summary dict from `ProcessUpdatesResult.as_dict`.

    Raises:
        TaskExecutionPartialError: If any delta entries failed to write.
    """
    result = process_fast_updates(
        since=since,
        ingest=True,
        log=current_app.logger.info,
    )
    if result.entry_errors:
        raise TaskExecutionPartialError(
            message=(
                f"FAST subject updates succeeded with {result.entry_errors} "
                "entries with errors."
            )
        )
    return result.as_dict()
