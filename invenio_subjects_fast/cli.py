# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 MESH Research
#
# invenio-subjects-fast is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

import click
from invenio_subjects_fast.downloader import download_marcxml_files
from invenio_subjects_fast.converter import convert_to_jsonl
from pathlib import Path

"""
A Script and command line interface for producing an InvenioRDM vocabulary file from the FAST subject vocabulary marcxml files.

Setup

This script

"""

@click.group()
def cli():
    pass


@cli.command("download")
def download_marcxml():
    """
    Download the FAST vocabulary marcxml files.
    """
    download_marcxml_files()


@cli.command("convert")
def convert_marcxml():
    """
    Convert the downloaded FAST marcxml files to a jsonl vocabulary file
    """
    convert_to_jsonl(source_dir=Path(__file__).parent / "downloads",
                    target_dir=Path(__file__).parent / "vocabularies")



if __name__ == "__main__":
    cli()