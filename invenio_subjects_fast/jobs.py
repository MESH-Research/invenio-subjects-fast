# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""invenio-jobs JobTypes for FAST subject updates.

Registered under the `invenio_jobs.jobs` entry point. Operators schedule
them with `invenio kcworks-jobs upsert process_fast_subject_updates` (or
any invenio-jobs UI / CLI that creates Job rows).
"""

from invenio_i18n import lazy_gettext as _
from invenio_jobs.jobs import JobType, PredefinedArgsSchema

from invenio_subjects_fast.tasks import process_fast_subject_updates


class ProcessFastSubjectUpdatesJob(JobType):
    """Download FAST change files and upsert new/changed subject terms."""

    id = "process_fast_subject_updates"
    title = _("Update FAST subjects")
    description = _(
        "Download new OCLC FAST ISO MARC (.mrc) change files, convert them to "
        "subject JSONL deltas, and upsert into the subjects vocabulary."
    )
    task = process_fast_subject_updates
    arguments_schema = PredefinedArgsSchema

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Pass the job `since` bookmark into the FAST update task.

        When `since` is unset, `_build_task_arguments` fills it from the last
        successful run (if any). This override must return it in the kwargs
        dict or the Celery task never receives it (base class returns `{}`).

        Returns:
            Keyword arguments for `process_fast_subject_updates`.
        """
        args: dict = {}
        if since is not None:
            args["since"] = since
        return args
