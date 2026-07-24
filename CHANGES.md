# Changes

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
