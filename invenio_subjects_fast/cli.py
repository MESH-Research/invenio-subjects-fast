# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""CLI to convert FAST marcxml / mrc files to InvenioRDM vocabulary files.

Registered as a Flask/Invenio command group (`subjects_fast`) and as the
console script `invenio-subjects-fast`. Commands that resolve the change-file
workdir use `@with_appcontext` so config and `instance_path` are available.
"""

from pathlib import Path

import click

try:
    from flask.cli import with_appcontext
except ImportError:  # pragma: no cover - Flask always present under Invenio

    def with_appcontext(f):
        """No-op stand-in when Flask is not installed.

        Returns:
            The undecorated callable.
        """
        return f


from invenio_subjects_fast.config import PACKAGE_ROOT
from invenio_subjects_fast.services.convert_updates import convert_updates
from invenio_subjects_fast.services.converter import convert_to_jsonl
from invenio_subjects_fast.services.download_updates import download_updates
from invenio_subjects_fast.services.downloader import download_marcxml_files
from invenio_subjects_fast.services.process_updates import (
    process_fast_updates,
    resolve_updates_workdir,
)

_WORKDIR_HELP = (
    "Working directory for .mrc files, processed/, and deltas/ "
    "(default: SUBJECTS_FAST_UPDATES_PATH, else "
    "<instance_path>/app_data/vocabularies/fast/)."
)


@click.group()
def cli():
    """Parent command group for the invenio_subjects_fast CLI."""
    pass


@cli.command("download")
@click.option(
    "-f",
    "--facet",
    multiple=True,
    help="FAST facet to download (repeatable). Omit to download all.",
)
def download_marcxml(facet):
    """Download the FAST vocabulary marcxml files."""
    download_marcxml_files(
        download_dir=PACKAGE_ROOT / "downloads",
        facets=facet or None,
    )


@cli.command("convert")
@click.option(
    "-f",
    "--facet",
    multiple=True,
    help="FAST facet to convert (repeatable). Omit to convert all.",
)
def convert_marcxml(facet):
    """Convert the downloaded FAST marcxml files to a jsonl vocabulary file."""
    convert_to_jsonl(
        source_dir=PACKAGE_ROOT / "downloads",
        target_dir=PACKAGE_ROOT / "vocabularies",
        facets=facet or None,
    )


@cli.command("download-updates")
@click.option(
    "--download-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=_WORKDIR_HELP,
)
@click.option(
    "--since",
    type=click.STRING,
    default=None,
    help=(
        "Only download change files on or after this ISO date (YYYY-MM-DD). "
        "When omitted, uses local change-file dates, then full-dump mtime, "
        "then a 180-day lookback."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-download even when the file already exists locally.",
)
@with_appcontext
def download_updates_cmd(download_dir, since, force):
    """Download new FAST ISO MARC (.mrc) change files from OCLC.

    Lists https://fast.oclc.org/fastChanges/, skips files already present in
    the download directory or its `processed/` subdirectory, and saves new
    `FASTChanges*.mrc` / `FORMChanges*.mrc` files.
    """
    workdir = resolve_updates_workdir(download_dir)
    paths = download_updates(
        download_dir=workdir,
        since=since,
        force=force,
    )
    if paths:
        click.echo(f"Downloaded {len(paths)} file(s).")
    else:
        click.echo("No new change files.")


@cli.command("process-updates")
@click.option(
    "--download-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=_WORKDIR_HELP,
)
@click.option(
    "--since",
    type=click.STRING,
    default=None,
    help=(
        "Only download change files on or after this ISO date (YYYY-MM-DD). "
        "When omitted, uses local change-file dates, then full-dump mtime, "
        "then a 180-day lookback."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-download even when the file already exists locally.",
)
@click.option(
    "--ingest/--no-ingest",
    default=False,
    help=(
        "Upsert delta JSONL into the Invenio subjects vocabulary "
        "(requires an application context; default: no ingest)."
    ),
)
@with_appcontext
def process_updates_cmd(download_dir, since, force, ingest):
    """Download, convert, and optionally ingest FAST change files.

    Same pipeline as the scheduled Invenio job (`process_fast_subject_updates`),
    sharing `process_fast_updates`. Without `--ingest`, writes delta JSONL under
    `<download-dir>/deltas/` and moves `.mrc` files to `processed/`.
    """
    result = process_fast_updates(
        download_dir,
        since=since,
        force=force,
        ingest=ingest,
    )
    click.echo(
        f"Downloaded {len(result.downloaded)}; "
        f"converted {len(result.ingested_files)}; "
        f"deltas {len(result.deltas)}; "
        f"entry_errors {result.entry_errors}."
    )


@cli.command("convert-updates")
@click.argument(
    "mrc_paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--vocab-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Directory of full subjects_fast_*.jsonl files "
        "(default: package vocabularies/)."
    ),
)
@click.option(
    "--delta-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Directory for *.updates.jsonl delta files "
        "(default: <vocab-dir>/updates/)."
    ),
)
@click.option(
    "--merge/--no-merge",
    default=True,
    help="Upsert updates into the full facet JSONL files (default: merge).",
)
@click.option(
    "--delta/--no-delta",
    "write_delta",
    default=True,
    help="Write per-facet delta JSONL under --delta-dir (default: delta).",
)
@click.option(
    "-f",
    "--facet",
    multiple=True,
    help="Limit to FAST facet(s) (repeatable). Omit to process all in the file.",
)
def convert_updates_cmd(mrc_paths, vocab_dir, delta_dir, merge, write_delta, facet):
    """Convert FAST ISO MARC (.mrc) change files to JSONL updates.

    Writes delta files as subjects_fast_<scheme>.updates.jsonl and, by default,
    merges the same rows into the full subjects_fast_<scheme>.jsonl files.

    Deprecated / deleted authority records keep their id, append
    ` (deprecated)` to the label, and set tags to `["unlisted"]` so deposit
    suggestions hide them while existing record metadata can still resolve them.
    """
    convert_updates(
        mrc_paths,
        vocab_dir=vocab_dir,
        delta_dir=delta_dir,
        facets=facet or None,
        merge=merge,
        write_delta=write_delta,
    )


if __name__ == "__main__":
    cli()
