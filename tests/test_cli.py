# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Test FAST download and convert CLI helpers."""

import os
from pathlib import Path

import jsonlines
import responses
from click.testing import CliRunner

from invenio_subjects_fast.cli import cli
from invenio_subjects_fast.converter import convert_to_jsonl
from invenio_subjects_fast.downloader import download_marcxml_files


def assert_includes(dicts, dict_cores):
    """Checks that each dict in dicts has the corresponding dict_core."""
    for d, dc in zip(dicts, dict_cores):
        for key, value in dc.items():
            assert value == d[key]


@responses.activate
def test_downloader(monkeypatch):
    monkeypatch.setattr("invenio_subjects_fast.downloader.time.sleep", lambda _: None)
    downloads_dir = Path(__file__).parent / "downloads"
    data_dir = Path(__file__).parent / "data"

    names = {
        "FASTPersonal": None,
        "FASTCorporate": None,
        "FASTEvent": None,
        "FASTTitle": None,
        "FASTChronological": None,
        "FASTTopical": None,
        "FASTGeographic": None,
        "FASTFormGenre": None,
        "FASTMeeting": None,
    }
    for n in names.keys():
        names[n] = open(f"{data_dir}/mock_{n}.marcxml.zip", "rb")
        responses.add(
            responses.Response(
                method="GET",
                url=(
                    f"https://researchworks.oclc.org/researchdata/fast/{n}.marcxml.zip"
                ),
                status=200,
                body=names[n],
                content_type="application/octet-stream",
            )
        )

    files = download_marcxml_files(download_dir=downloads_dir)

    for n in names.keys():
        assert os.path.exists(downloads_dir / f"{n}.marcxml.zip")
        assert os.path.exists(f"{downloads_dir}/{n}.marcxml")
    assert files == [downloads_dir / f"{f}.marcxml.zip" for f in names]
    assert "Mozilla/5.0" in responses.calls[0].request.headers["User-Agent"]

    for n in names:
        names[n].close()


@responses.activate
def test_downloader_single_facet():
    downloads_dir = Path(__file__).parent / "downloads"
    data_dir = Path(__file__).parent / "data"
    name = "FASTFormGenre"

    with open(f"{data_dir}/mock_{name}.marcxml.zip", "rb") as body:
        responses.add(
            responses.Response(
                method="GET",
                url=(
                    "https://researchworks.oclc.org/researchdata/fast/"
                    f"{name}.marcxml.zip"
                ),
                status=200,
                body=body.read(),
                content_type="application/octet-stream",
            )
        )

    files = download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
    assert files == [downloads_dir / f"{name}.marcxml.zip"]
    assert len(responses.calls) == 1


@responses.activate
def test_downloader_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("invenio_subjects_fast.downloader.time.sleep", lambda _: None)
    downloads_dir = Path(__file__).parent / "downloads"
    data_dir = Path(__file__).parent / "data"
    name = "FASTFormGenre"
    url = f"https://researchworks.oclc.org/researchdata/fast/{name}.marcxml.zip"
    body = (data_dir / f"mock_{name}.marcxml.zip").read_bytes()

    responses.add(responses.GET, url, status=500, body="temporary error")
    responses.add(
        responses.GET,
        url,
        status=200,
        body=body,
        content_type="application/octet-stream",
    )

    files = download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
    assert files == [downloads_dir / f"{name}.marcxml.zip"]
    assert len(responses.calls) == 2


@responses.activate
def test_downloader_raises_after_retries(monkeypatch):
    monkeypatch.setattr("invenio_subjects_fast.downloader.time.sleep", lambda _: None)
    downloads_dir = Path(__file__).parent / "downloads"
    name = "FASTFormGenre"
    url = f"https://researchworks.oclc.org/researchdata/fast/{name}.marcxml.zip"

    responses.add(responses.GET, url, status=503, body="unavailable")
    responses.add(responses.GET, url, status=503, body="unavailable")
    responses.add(responses.GET, url, status=503, body="unavailable")

    try:
        download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "Failed to download" in str(exc)
    assert raised
    assert len(responses.calls) == 3


def test_converter():
    source_dir = Path(__file__).parent / "downloads"
    target_dir = Path(__file__).parent / "vocabularies"
    assert convert_to_jsonl(source_dir=source_dir, target_dir=target_dir)

    names = [
        "personal",
        "corporate",
        "event",
        "title",
        "chronological",
        "topical",
        "geographic",
        "formgenre",
        "meeting",
    ]
    for n in names:
        assert os.path.exists(f"{target_dir}/subjects_fast_{n}.jsonl")
    with jsonlines.open(f"{target_dir}/subjects_fast_personal.jsonl", "r") as p:
        expected_lines = [
            {
                "id": "http://id.worldcat.org/fast/1",
                "scheme": "FAST-personal",
                "subject": "Mizner, Addison, 1872-1933",
            },
            {
                "id": "http://id.worldcat.org/fast/2",
                "scheme": "FAST-personal",
                "subject": "Thatcher, Margaret",
            },
        ]
        for idx, line in enumerate(p):
            assert line == expected_lines[idx]


def test_converter_single_facet(tmp_path):
    source_dir = Path(__file__).parent / "downloads"
    target_dir = tmp_path / "vocabularies"
    target_dir.mkdir()
    assert convert_to_jsonl(
        source_dir=source_dir,
        target_dir=target_dir,
        facets=["personal"],
    )
    assert (target_dir / "subjects_fast_personal.jsonl").exists()
    assert not (target_dir / "subjects_fast_formgenre.jsonl").exists()


def test_cli_facet_option_validation():
    runner = CliRunner()
    result = runner.invoke(cli, ["convert", "-f", "nope"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "Unknown FAST facet" in str(result.exception)

    result = runner.invoke(cli, ["download", "--help"])
    assert result.exit_code == 0
    assert "--facet" in result.output
