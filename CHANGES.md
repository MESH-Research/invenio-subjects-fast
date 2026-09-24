# Changes

Version 2026.09.23

- Incremental FAST updates: download ISO MARC (`.mrc`) change files from
  OCLC (`download-updates`), convert them to delta JSONL and merge into the
  full facet vocabularies (`convert-updates`), and run the full
  download → convert → subjects upsert pipeline (`process-updates`).
  On ingest entry errors, `.mrc` files stay in the workdir for the next run
  instead of moving to `processed/`.
- Shared change-file workdir for CLI and Celery (explicit path, else
  `SUBJECTS_FAST_UPDATES_PATH`, else
  `<instance_path>/app_data/vocabularies/fast/`).
- Register `invenio subjects_fast` (Flask CLI), Celery task
  `process_fast_subject_updates`, and invenio-jobs
  `ProcessFastSubjectUpdatesJob` for scheduled runs in InvenioRDM.
- Polite downloads: 10s spacing between requests; honour HTTP 429
  `Retry-After` (integer or HTTP-date, capped) for full dumps and change
  files.
- Shared MARC / MARCXML term extraction (`pymarc` + `marc_subjects.py`), including
  deprecated-term handling (` (deprecated)` label, `tags: ["unlisted"]`).
- Ship `subjects_datastream.yaml` for jsonl ingest and document
  `invenio vocabularies update` / `--filepath` usage in the README.
- Test and CI hardening: pytest-invenio, coverage, `ty`, GitHub Actions,
  `requests-mock`, Python `>=3.12`.
- Reorganize package layout: service logic under `services/`, facet helpers
  under `utils/`.
- Align incremental-pipeline naming on `updates` (modules, config
  `SUBJECTS_FAST_UPDATES_PATH`, APIs); OCLC’s “change file” wording remains
  in docs where referring to upstream `FASTChanges*` / `FORMChanges*` files.

Version 2026.07.23

- Switch packaging and local development from Pipenv to uv (`.venv`, `uv.lock`,
  consolidated `pyproject.toml`; remove `Pipfile` / `setup.py` / `setup.cfg`).
- Add Ruff for lint and format (`ruff>=0.3`), with settings aligned to
  kcworks-next where appropriate (rule set `B`/`D`/`DOC`/`E`/`F`/`I`/`UP`,
  Google pydocstyle, double quotes, line length 88).
- Add `pytest-ruff` and run Ruff via pytest (`--ruff`); keep package-local
  excludes for vocabulary/download test data.
- Add repeatable `-f` / `--facet` to `download` and `convert` so a single facet
  (or subset) can be refreshed without reprocessing all nine.
- Align the form/genre converter scheme with the registered scheme id
  (`FAST-formgenre` instead of `FAST-form`). Regenerate
  `subjects_fast_formgenre.jsonl` before release if shipping corrected terms.
- Document refreshing existing InvenioRDM subject terms via
  `invenio vocabularies update`, and update README/INSTALL for uv workflows.
- Replace deprecated `pkg_resources` usage in tests with `importlib.metadata`.
- Update file copyright headers to `Copyright (C) 2023-2026 MESH Research` with
  `SPDX-License-Identifier: MIT` (and year span on `LICENSE`).
- Move CLI runtime dependencies (`halo`, `jsonlines`, `requests`, `tqdm`) into
  main package dependencies.
- Centralize FAST facet metadata in `config.py` and share helpers via
  `facets.py` across download and convert.
- Retry failed FAST downloads with backoff; skip unzip until a download
  succeeds; raise if download or unzip ultimately fails.

Version 2023.06.07

- Initial public release.
