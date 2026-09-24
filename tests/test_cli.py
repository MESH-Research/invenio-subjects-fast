# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Test FAST download and convert CLI helpers."""

from pathlib import Path
from zipfile import ZipFile

import jsonlines
from click.testing import CliRunner

from invenio_subjects_fast.cli import cli
from invenio_subjects_fast.services.converter import convert_to_jsonl
from invenio_subjects_fast.services.downloader import download_marcxml_files

DATA_DIR = Path(__file__).parent / "data"

FAST_ARCHIVE_NAMES = [
    "FASTPersonal",
    "FASTCorporate",
    "FASTEvent",
    "FASTTitle",
    "FASTChronological",
    "FASTTopical",
    "FASTGeographic",
    "FASTFormGenre",
    "FASTMeeting",
]


def _mock_zip_bytes(name: str) -> bytes:
    return (DATA_DIR / f"mock_{name}.marcxml.zip").read_bytes()


def _extract_mock_marcxml(target_dir: Path, names: list[str]) -> Path:
    """Unpack fixture zips into ``target_dir`` (pytest ``tmp_path``)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        with ZipFile(DATA_DIR / f"mock_{name}.marcxml.zip") as archive:
            archive.extractall(path=target_dir)
    return target_dir


def _register_facet_downloads(requests_mock, names: list[str]) -> None:
    for name in names:
        requests_mock.get(
            f"https://researchworks.oclc.org/researchdata/fast/{name}.marcxml.zip",
            content=_mock_zip_bytes(name),
            headers={"Content-Type": "application/octet-stream"},
        )


_DOWNLOADER_SLEEP = "invenio_subjects_fast.services.downloader.time.sleep"


def test_downloader(requests_mock, tmp_path, monkeypatch):
    monkeypatch.setattr(_DOWNLOADER_SLEEP, lambda _: None)
    downloads_dir = tmp_path / "downloads"
    _register_facet_downloads(requests_mock, FAST_ARCHIVE_NAMES)

    files = download_marcxml_files(download_dir=downloads_dir)

    for name in FAST_ARCHIVE_NAMES:
        assert (downloads_dir / f"{name}.marcxml.zip").exists()
        assert (downloads_dir / f"{name}.marcxml").exists()
    assert files == [
        downloads_dir / f"{name}.marcxml.zip" for name in FAST_ARCHIVE_NAMES
    ]
    assert "Mozilla/5.0" in requests_mock.request_history[0].headers["User-Agent"]


def test_downloader_single_facet(requests_mock, tmp_path):
    downloads_dir = tmp_path / "downloads"
    name = "FASTFormGenre"
    _register_facet_downloads(requests_mock, [name])

    files = download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
    assert files == [downloads_dir / f"{name}.marcxml.zip"]
    assert requests_mock.call_count == 1


def test_downloader_retries_then_succeeds(requests_mock, tmp_path, monkeypatch):
    monkeypatch.setattr(_DOWNLOADER_SLEEP, lambda _: None)
    downloads_dir = tmp_path / "downloads"
    name = "FASTFormGenre"
    url = f"https://researchworks.oclc.org/researchdata/fast/{name}.marcxml.zip"

    requests_mock.get(
        url,
        [
            {"status_code": 500, "text": "temporary error"},
            {
                "status_code": 200,
                "content": _mock_zip_bytes(name),
                "headers": {"Content-Type": "application/octet-stream"},
            },
        ],
    )

    files = download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
    assert files == [downloads_dir / f"{name}.marcxml.zip"]
    assert requests_mock.call_count == 2


def test_downloader_raises_after_retries(requests_mock, tmp_path, monkeypatch):
    monkeypatch.setattr(_DOWNLOADER_SLEEP, lambda _: None)
    downloads_dir = tmp_path / "downloads"
    name = "FASTFormGenre"
    url = f"https://researchworks.oclc.org/researchdata/fast/{name}.marcxml.zip"

    requests_mock.get(
        url,
        [
            {"status_code": 503, "text": "unavailable"},
            {"status_code": 503, "text": "unavailable"},
            {"status_code": 503, "text": "unavailable"},
        ],
    )

    try:
        download_marcxml_files(download_dir=downloads_dir, facets=["formgenre"])
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "Failed to download" in str(exc)
    assert raised
    assert requests_mock.call_count == 3


def test_converter(tmp_path):
    source_dir = _extract_mock_marcxml(tmp_path / "downloads", FAST_ARCHIVE_NAMES)
    target_dir = tmp_path / "vocabularies"
    target_dir.mkdir()
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
    for name in names:
        assert (target_dir / f"subjects_fast_{name}.jsonl").exists()
    with jsonlines.open(target_dir / "subjects_fast_personal.jsonl", "r") as reader:
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
        for idx, line in enumerate(reader):
            assert line == expected_lines[idx]


def test_converter_single_facet(tmp_path):
    source_dir = _extract_mock_marcxml(tmp_path / "downloads", ["FASTPersonal"])
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
