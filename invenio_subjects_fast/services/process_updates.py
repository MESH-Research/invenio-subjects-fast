# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Orchestrate FAST change-file download, convert, and optional ingest.

Shared by the package CLI and the Invenio Celery task so both entry points
run the same pipeline.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class ProcessUpdatesResult:
    """Summary of one `process_fast_updates` run.

    Attributes:
        downloaded: Paths downloaded in this run.
        ingested_files: Pending `.mrc` files that were converted (and ingested
            when `ingest` was true).
        deltas: Delta JSONL paths written or ingested.
        schemes: Map of scheme id → row count from convert.
        entry_errors: Count of vocabulary writer entry errors (ingest only).
    """

    downloaded: list[str] = field(default_factory=list)
    ingested_files: list[str] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)
    schemes: dict[str, int] = field(default_factory=dict)
    entry_errors: int = 0

    def as_dict(self) -> dict:
        """Return a plain dict suitable for Celery / logging."""
        return asdict(self)


def resolve_updates_workdir(download_dir: Path | str | None = None) -> Path:
    """Resolve the working directory for change files.

    Precedence:

    1. Explicit `download_dir` argument
    2. Flask config `SUBJECTS_FAST_UPDATES_PATH` (when set)
    3. `<instance_path>/app_data/vocabularies/fast/`

    Ensures `processed/` and `deltas/` exist under the chosen root.

    Args:
        download_dir: Explicit override, or `None` to use config / fallback.

    Returns:
        Workdir with standard subdirs created.

    Raises:
        RuntimeError: If no explicit path is given and there is no Flask
            application context (needed for config and `instance_path`).
    """
    if download_dir is not None:
        return ensure_updates_workdir(Path(download_dir))

    try:
        from flask import current_app, has_app_context
    except ImportError as exc:
        raise RuntimeError(
            "Pass download_dir explicitly, or install Flask and run under "
            "an Invenio application context."
        ) from exc

    if not has_app_context():
        raise RuntimeError(
            "Pass download_dir explicitly, or run under an Invenio "
            "application context (e.g. `invenio subjects_fast …`)."
        )

    configured = current_app.config.get("SUBJECTS_FAST_UPDATES_PATH")
    if configured:
        return ensure_updates_workdir(Path(configured))

    return ensure_updates_workdir(
        Path(current_app.instance_path) / "app_data" / "vocabularies" / "fast"
    )


def ensure_updates_workdir(download_dir: Path) -> Path:
    """Create `download_dir` plus `processed/` and `deltas/` subdirs.

    Returns:
        The same `download_dir` path.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / "processed").mkdir(parents=True, exist_ok=True)
    (download_dir / "deltas").mkdir(parents=True, exist_ok=True)
    return download_dir


def ingest_delta_jsonl(
    delta_path: Path,
    *,
    log_error: Callable[[str], None] | None = None,
) -> int:
    """Upsert subject rows from one delta JSONL via the subjects service writer.

    Requires an Invenio application context (invenio-vocabularies).

    Args:
        delta_path: Path to a `*.updates.jsonl` file.
        log_error: Optional callback for per-entry error strings.

    Returns:
        Count of entries that reported errors during the datastream write.
    """
    from invenio_vocabularies.datastreams.factories import DataStreamFactory

    config = {
        "readers": [
            {"type": "jsonl", "args": {"origin": str(delta_path)}},
        ],
        "writers": [
            {
                "type": "subjects-service",
                "args": {"update": True},
            }
        ],
    }
    ds = DataStreamFactory.create(
        readers_config=config["readers"],
        writers_config=config["writers"],
        batch_size=config.get("batch_size", 1000),
        write_many=config.get("write_many", False),
    )
    entries_with_errors = 0
    for result in ds.process():
        if result.errors:
            for err in result.errors:
                if log_error is not None:
                    log_error(err)
                else:
                    print(err)
            entries_with_errors += 1
    return entries_with_errors


def process_fast_updates(
    download_dir: Path | str | None = None,
    *,
    since: date | datetime | str | None = None,
    force: bool = False,
    ingest: bool = False,
    log: Callable[[str], None] | None = None,
) -> ProcessUpdatesResult:
    """Download new FAST change files, convert to deltas, optionally ingest.

    Pipeline:

    1. `download_updates` (applies `resolve_default_since` when `since`
       is unset)
    2. Convert pending `.mrc` files to per-facet delta JSONL
    3. When `ingest` is true, upsert each delta via the subjects service
    4. Move converted `.mrc` files to `processed/` when not ingesting, or
       when ingest completes with zero entry errors (otherwise leave them
       for retry)

    Args:
        download_dir: Working directory for `.mrc` files, `processed/`, and
            `deltas/`. When omitted, uses `resolve_updates_workdir`
            (explicit → `SUBJECTS_FAST_UPDATES_PATH` →
            `<instance_path>/app_data/vocabularies/fast/`).
        since: Inclusive lower bound on change-file dates (see
            `download_updates`).
        force: Re-download even when a change file already exists locally.
        ingest: When true, upsert delta JSONL into the subjects vocabulary
            (requires Invenio). When false, only download and convert.
        log: Optional message logger (defaults to `print`).

    Returns:
        A `ProcessUpdatesResult` summary.
    """
    from invenio_subjects_fast.services.convert_updates import convert_updates
    from invenio_subjects_fast.services.download_updates import (
        download_updates,
        mark_update_files_processed,
    )

    def _log(message: str) -> None:
        if log is not None:
            log(message)
        else:
            print(message)

    workdir = resolve_updates_workdir(download_dir)
    _log(f"FAST subject updates: workdir={workdir} since={since}")

    newly_downloaded = download_updates(
        download_dir=workdir,
        since=since,
        force=force,
    )

    pending = sorted(
        p for p in workdir.glob("*.mrc") if p.is_file() and p.parent == workdir
    )
    if not pending:
        _log("FAST subject updates: nothing to convert.")
        return ProcessUpdatesResult(
            downloaded=[str(p) for p in newly_downloaded],
        )

    _log(f"FAST subject updates: converting {len(pending)} file(s)")
    delta_dir = workdir / "deltas"
    updates_by_scheme = convert_updates(
        pending,
        vocab_dir=workdir,
        delta_dir=delta_dir,
        merge=False,
        write_delta=True,
    )

    total_errors = 0
    ingested_deltas: list[str] = []
    for scheme, rows in updates_by_scheme.items():
        suffix = scheme.removeprefix("FAST-")
        delta_path = delta_dir / f"subjects_fast_{suffix}.updates.jsonl"
        if not delta_path.exists():
            _log(f"Expected delta missing for {scheme}: {delta_path}")
            continue
        if ingest:
            _log(
                f"FAST subject updates: ingesting {scheme} ({len(rows)} rows) "
                f"from {delta_path}"
            )
            total_errors += ingest_delta_jsonl(
                delta_path, log_error=_log
            )
        else:
            _log(
                f"FAST subject updates: wrote delta for {scheme} "
                f"({len(rows)} rows) at {delta_path}"
            )
        ingested_deltas.append(str(delta_path))

    # Only archive change files after a clean ingest (or when not ingesting).
    # Partial vocabulary write failures leave `.mrc` files in place so the
    # next run retries convert + upsert.
    if not ingest or total_errors == 0:
        mark_update_files_processed(pending, download_dir=workdir)
    else:
        _log(
            f"FAST subject updates: leaving {len(pending)} .mrc file(s) in "
            f"place after {total_errors} entry error(s) for retry."
        )

    result = ProcessUpdatesResult(
        downloaded=[str(p) for p in newly_downloaded],
        ingested_files=[str(p) for p in pending],
        deltas=ingested_deltas,
        schemes={
            scheme: len(rows) for scheme, rows in updates_by_scheme.items()
        },
        entry_errors=total_errors,
    )
    _log(f"FAST subject updates complete: {result.as_dict()}")
    return result
