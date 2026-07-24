# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""CLI to convert FAST marcxml files to InvenioRDM vocabulary files."""

from pathlib import Path

import click

from invenio_subjects_fast.converter import convert_to_jsonl
from invenio_subjects_fast.downloader import download_marcxml_files


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
        download_dir=Path(__file__).parent / "downloads",
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
        source_dir=Path(__file__).parent / "downloads",
        target_dir=Path(__file__).parent / "vocabularies",
        facets=facet or None,
    )


if __name__ == "__main__":
    cli()
