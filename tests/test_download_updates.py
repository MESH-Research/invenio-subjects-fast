# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Tests for FAST change-file downloads.

OCLC publishes two families of ISO MARC change files on the FAST Changes
page: `FASTChangesYYYY-MM-DD.mrc` (general facets) and
`FORMChangesYYYY-MM-DD.mrc` (form/genre only). Both are linked as
"FAST Change File"; the downloader must pick up both name patterns.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from invenio_subjects_fast.cli import cli
from invenio_subjects_fast.services.download_updates import (
    DEFAULT_UPDATES_LOOKBACK_DAYS,
    UpdateFileRef,
    _as_date,
    _parse_updates_index_html,
    download_updates,
    latest_full_dump_mtime_date,
    list_remote_update_files,
    mark_update_files_processed,
    resolve_default_since,
    update_file_date_from_name,
)

# Updates-index HTML mirrors OCLC naming: FASTChanges* (general) and
# FORMChanges* (form/genre). Spreadsheet reports (*.xlsx) must be ignored.
SAMPLE_UPDATES_INDEX = """
<html><body>
<a href="FASTChanges2026-07-24.mrc">FAST Change File</a>
<a href="/fastChanges/FORMChanges2026-07-24.mrc">FAST Change File</a>
<a href="FASTChanges2026-02-13.mrc">FAST Change File</a>
<a href="FASTChangeReport2026-07-24.xlsx">report</a>
</body></html>
"""


def test_parse_updates_index_html_extracts_mrc_links():
    refs = _parse_updates_index_html(
        SAMPLE_UPDATES_INDEX, "https://fast.oclc.org/fastChanges/"
    )
    names = [ref.filename for ref in refs]
    assert names == [
        "FASTChanges2026-07-24.mrc",
        "FORMChanges2026-07-24.mrc",
        "FASTChanges2026-02-13.mrc",
    ]
    assert refs[0].file_date == date(2026, 7, 24)
    assert refs[0].url.endswith("FASTChanges2026-07-24.mrc")


def test_update_file_date_from_name():
    assert update_file_date_from_name("FASTChanges2026-07-24.mrc") == date(
        2026, 7, 24
    )
    assert update_file_date_from_name("FORMChanges2025-12-18.mrc") == date(
        2025, 12, 18
    )
    assert update_file_date_from_name("not-a-change-file.mrc") is None
    assert update_file_date_from_name("FASTChangeReport2026-07-24.xlsx") is None


def test_as_date_normalizes_since_values():
    assert _as_date(None) is None
    assert _as_date("") is None
    assert _as_date("   ") is None
    assert _as_date(date(2026, 7, 1)) == date(2026, 7, 1)
    assert _as_date(datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)) == date(
        2026, 7, 1
    )
    assert _as_date("2026-07-01") == date(2026, 7, 1)
    assert _as_date("2026-07-01T15:30:00Z") == date(2026, 7, 1)


def test_latest_full_dump_mtime_date(tmp_path):
    assert latest_full_dump_mtime_date(tmp_path / "missing") is None
    assert latest_full_dump_mtime_date(tmp_path) is None

    dump = tmp_path / "FASTTopical.marcxml"
    dump.write_text("<xml/>")
    assert latest_full_dump_mtime_date(tmp_path) == date.today()


def test_list_remote_update_files(monkeypatch):
    response = MagicMock()
    response.text = SAMPLE_UPDATES_INDEX
    response.close = MagicMock()
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.get_with_retry",
        lambda *a, **k: response,
    )

    refs = list_remote_update_files(
        updates_index_url="https://fast.oclc.org/fastChanges/",
        session=MagicMock(),
    )
    assert [ref.filename for ref in refs] == [
        "FASTChanges2026-07-24.mrc",
        "FORMChanges2026-07-24.mrc",
        "FASTChanges2026-02-13.mrc",
    ]
    response.close.assert_called_once()


def test_list_remote_update_files_wraps_fetch_errors(monkeypatch):
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.get_with_retry",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="Failed to fetch FAST updates index"):
        list_remote_update_files(
            updates_index_url="https://fast.oclc.org/fastChanges/",
            session=MagicMock(),
        )


def test_download_updates_skips_existing_and_respects_since(
    tmp_path, monkeypatch
):
    existing = tmp_path / "FASTChanges2026-07-24.mrc"
    existing.write_bytes(b"old")

    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
        UpdateFileRef(
            "FASTChanges2026-02-13.mrc",
            "https://example.test/FASTChanges2026-02-13.mrc",
            date(2026, 2, 13),
        ),
        UpdateFileRef(
            "FORMChanges2025-12-18.mrc",
            "https://example.test/FORMChanges2025-12-18.mrc",
            date(2025, 12, 18),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )

    downloaded_urls: list[str] = []

    def fake_download(session, url, target_path, attempts=3):
        downloaded_urls.append(url)
        target_path.write_bytes(b"mrc")

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        fake_download,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.time.sleep",
        lambda *_args, **_kwargs: None,
    )

    paths = download_updates(
        download_dir=tmp_path,
        since="2026-01-01",
    )
    assert [p.name for p in paths] == ["FASTChanges2026-02-13.mrc"]
    assert downloaded_urls == [
        "https://example.test/FASTChanges2026-02-13.mrc"
    ]
    assert (tmp_path / "FASTChanges2026-02-13.mrc").exists()


def test_mark_update_files_processed(tmp_path):
    src = tmp_path / "FASTChanges2026-07-24.mrc"
    src.write_bytes(b"mrc")
    moved = mark_update_files_processed([src], download_dir=tmp_path)
    assert len(moved) == 1
    assert moved[0] == tmp_path / "processed" / src.name
    assert not src.exists()
    assert moved[0].exists()


def test_mark_update_files_processed_skips_missing_and_replaces_dest(tmp_path):
    missing = tmp_path / "gone.mrc"
    src = tmp_path / "FASTChanges2026-07-24.mrc"
    src.write_bytes(b"new")
    processed = tmp_path / "processed"
    processed.mkdir()
    existing_dest = processed / src.name
    existing_dest.write_bytes(b"old")

    moved = mark_update_files_processed(
        [missing, src], download_dir=tmp_path
    )
    assert moved == [existing_dest]
    assert existing_dest.read_bytes() == b"new"
    assert not src.exists()


def test_download_updates_force_redownloads(tmp_path, monkeypatch):
    existing = tmp_path / "FASTChanges2026-07-24.mrc"
    existing.write_bytes(b"old")
    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        lambda session, url, target_path, attempts=3: target_path.write_bytes(
            b"new"
        ),
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.time.sleep",
        lambda *_a, **_k: None,
    )

    paths = download_updates(
        download_dir=tmp_path, since="2026-01-01", force=True
    )
    assert [p.name for p in paths] == ["FASTChanges2026-07-24.mrc"]
    assert existing.read_bytes() == b"new"


def test_download_updates_filenames_filter(tmp_path, monkeypatch):
    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
        UpdateFileRef(
            "FORMChanges2026-07-24.mrc",
            "https://example.test/FORMChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )
    downloaded: list[str] = []

    def fake_download(session, url, target_path, attempts=3):
        downloaded.append(url.rsplit("/", 1)[-1])
        target_path.write_bytes(b"mrc")

    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        fake_download,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.time.sleep",
        lambda *_a, **_k: None,
    )

    paths = download_updates(
        download_dir=tmp_path,
        since="2026-01-01",
        filenames=["FORMChanges2026-07-24.mrc"],
    )
    assert [p.name for p in paths] == ["FORMChanges2026-07-24.mrc"]
    assert downloaded == ["FORMChanges2026-07-24.mrc"]


def test_download_updates_noop_when_nothing_new(tmp_path, monkeypatch):
    existing = tmp_path / "FASTChanges2026-07-24.mrc"
    existing.write_bytes(b"old")
    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )
    download = MagicMock()
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        download,
    )

    paths = download_updates(
        download_dir=tmp_path, since="2026-01-01", force=False
    )
    assert paths == []
    download.assert_not_called()


def test_download_updates_waits_between_multiple_downloads(
    tmp_path, monkeypatch
):
    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
        UpdateFileRef(
            "FORMChanges2026-07-24.mrc",
            "https://example.test/FORMChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        lambda session, url, target_path, attempts=3: target_path.write_bytes(
            b"mrc"
        ),
    )
    sleeps: list[float] = []
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    paths = download_updates(download_dir=tmp_path, since="2026-01-01")
    assert len(paths) == 2
    assert len(sleeps) == 1
    assert sleeps[0] > 0


def test_latest_local_update_file_date_scans_processed(tmp_path):
    from invenio_subjects_fast.services.download_updates import (
        latest_local_update_file_date,
    )

    (tmp_path / "processed").mkdir()
    (tmp_path / "FASTChanges2026-01-01.mrc").write_bytes(b"a")
    (tmp_path / "processed" / "FORMChanges2026-06-01.mrc").write_bytes(b"b")
    assert latest_local_update_file_date(tmp_path) == date(2026, 6, 1)


def test_resolve_default_since_from_local_update_files(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "FASTChanges2026-02-13.mrc").write_bytes(b"mrc")
    (processed / "FORMChanges2026-07-24.mrc").write_bytes(b"mrc")
    assert resolve_default_since(tmp_path) == date(2026, 7, 24)


def test_resolve_default_since_from_full_dump_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.latest_local_update_file_date",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.latest_full_dump_mtime_date",
        lambda *_a, **_k: date(2026, 3, 15),
    )
    assert resolve_default_since(tmp_path) == date(2026, 3, 15)


def test_resolve_default_since_lookback_when_no_local_anchor(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.latest_local_update_file_date",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.latest_full_dump_mtime_date",
        lambda *_a, **_k: None,
    )
    assert resolve_default_since(tmp_path) == (
        date.today() - timedelta(days=DEFAULT_UPDATES_LOOKBACK_DAYS)
    )


def test_download_updates_applies_default_since_when_omitted(
    tmp_path, monkeypatch
):
    remote = [
        UpdateFileRef(
            "FASTChanges2026-07-24.mrc",
            "https://example.test/FASTChanges2026-07-24.mrc",
            date(2026, 7, 24),
        ),
        UpdateFileRef(
            "FASTChanges2025-01-01.mrc",
            "https://example.test/FASTChanges2025-01-01.mrc",
            date(2025, 1, 1),
        ),
    ]
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.list_remote_update_files",
        lambda **kwargs: remote,
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.resolve_default_since",
        lambda *_a, **_k: date(2026, 6, 1),
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates._download_with_retry",
        lambda session, url, target_path, attempts=3: target_path.write_bytes(
            b"mrc"
        ),
    )
    monkeypatch.setattr(
        "invenio_subjects_fast.services.download_updates.time.sleep",
        lambda *_args, **_kwargs: None,
    )

    paths = download_updates(download_dir=tmp_path, since=None)
    assert [p.name for p in paths] == ["FASTChanges2026-07-24.mrc"]


def test_cli_download_updates(base_app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "invenio_subjects_fast.cli.download_updates",
        lambda **kwargs: [tmp_path / "a.mrc"],
    )
    runner = base_app.test_cli_runner()
    result = runner.invoke(
        cli,
        [
            "download-updates",
            "--since",
            "2026-01-01",
            "--download-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Downloaded 1 file(s)." in result.output
