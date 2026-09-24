# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Tests for FAST .mrc change-file conversion."""

from pathlib import Path

import jsonlines
from click.testing import CliRunner
from pymarc import Field, MARCWriter, Record, Subfield

from invenio_subjects_fast.cli import cli
from invenio_subjects_fast.services.convert_updates import (
    convert_updates,
    merge_subject_rows,
)
from invenio_subjects_fast.utils.marc_subjects import (
    DEPRECATED_SUFFIX,
    UNLISTED_TAG,
    extract_from_marc_record,
)


def _write_mrc(path: Path, records: list[Record]) -> None:
    with open(path, "wb") as handle:
        writer = MARCWriter(handle)
        for record in records:
            writer.write(record)


def _authority(
    *,
    uri: str,
    tag: str,
    subfields: list[tuple[str, str]],
    leader_status: str = "c",
    former_subfields: list[tuple[str, str]] | None = None,
    former_tag: str | None = None,
) -> Record:
    record = Record(force_utf8=True)
    # leader[5] is record status (n/c/d/…).
    record.leader = f"00000{leader_status}z  a2200037n  4500"
    record.add_field(Field(tag="001", data="fsttest"))
    record.add_field(
        Field(
            tag="024",
            indicators=["7", " "],
            subfields=[Subfield("a", uri), Subfield("2", "uri")],
        )
    )
    if subfields:
        record.add_field(
            Field(
                tag=tag,
                indicators=[" ", " "],
                subfields=[Subfield(code, value) for code, value in subfields],
            )
        )
    if former_subfields:
        ftag = former_tag or {"150": "450", "155": "455", "100": "400"}[tag]
        record.add_field(
            Field(
                tag=ftag,
                indicators=[" ", " "],
                subfields=[Subfield(code, value) for code, value in former_subfields],
            )
        )
    return record


def test_extract_active_and_deprecated_marc_records():
    active = _authority(
        uri="http://id.worldcat.org/fast/100",
        tag="150",
        subfields=[("a", "Dogs")],
    )
    deleted = _authority(
        uri="http://id.worldcat.org/fast/200",
        tag="150",
        subfields=[],
        leader_status="d",
        former_subfields=[("a", "Cats")],
        former_tag="450",
    )
    assert extract_from_marc_record(active) == {
        "id": "http://id.worldcat.org/fast/100",
        "scheme": "FAST-topical",
        "subject": "Dogs",
    }
    deprecated = extract_from_marc_record(deleted)
    assert deprecated == {
        "id": "http://id.worldcat.org/fast/200",
        "scheme": "FAST-topical",
        "subject": f"Cats{DEPRECATED_SUFFIX}",
        "tags": [UNLISTED_TAG],
    }


def test_merge_subject_rows_updates_and_appends():
    existing = [
        {"id": "a", "scheme": "FAST-topical", "subject": "Old"},
        {"id": "b", "scheme": "FAST-topical", "subject": "Keep"},
    ]
    updates = [
        {
            "id": "a",
            "scheme": "FAST-topical",
            "subject": f"Old{DEPRECATED_SUFFIX}",
            "tags": [UNLISTED_TAG],
        },
        {"id": "c", "scheme": "FAST-topical", "subject": "New"},
    ]
    merged = merge_subject_rows(existing, updates)
    assert [row["id"] for row in merged] == ["a", "b", "c"]
    assert merged[0]["tags"] == [UNLISTED_TAG]
    assert merged[2]["subject"] == "New"


def test_convert_updates_writes_delta_and_merges(tmp_path):
    mrc_path = tmp_path / "changes.mrc"
    _write_mrc(
        mrc_path,
        [
            _authority(
                uri="http://id.worldcat.org/fast/1",
                tag="100",
                subfields=[("a", "Mizner, Addison,"), ("d", "1872-1933")],
            ),
            _authority(
                uri="http://id.worldcat.org/fast/999",
                tag="155",
                subfields=[("a", "History (updated)")],
            ),
            _authority(
                uri="http://id.worldcat.org/fast/1411628",
                tag="155",
                subfields=[],
                leader_status="d",
                former_subfields=[("a", "History")],
                former_tag="455",
            ),
        ],
    )

    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    # Seed a minimal full facet file that should be updated in place.
    with jsonlines.open(vocab_dir / "subjects_fast_personal.jsonl", "w") as writer:
        writer.write(
            {
                "id": "http://id.worldcat.org/fast/1",
                "scheme": "FAST-personal",
                "subject": "Mizner, Addison, 1872-1933",
            }
        )
    with jsonlines.open(vocab_dir / "subjects_fast_formgenre.jsonl", "w") as writer:
        writer.write(
            {
                "id": "http://id.worldcat.org/fast/1411628",
                "scheme": "FAST-formgenre",
                "subject": "History",
            }
        )

    delta_dir = vocab_dir / "updates"
    result = convert_updates(
        [mrc_path],
        vocab_dir=vocab_dir,
        delta_dir=delta_dir,
    )

    assert set(result) == {"FAST-personal", "FAST-formgenre"}

    personal_delta = list(
        jsonlines.open(delta_dir / "subjects_fast_personal.updates.jsonl")
    )
    assert personal_delta == [
        {
            "id": "http://id.worldcat.org/fast/1",
            "scheme": "FAST-personal",
            "subject": "Mizner, Addison, 1872-1933",
        }
    ]

    formgenre_delta = list(
        jsonlines.open(delta_dir / "subjects_fast_formgenre.updates.jsonl")
    )
    assert formgenre_delta[0]["subject"] == "History (updated)"
    assert formgenre_delta[1] == {
        "id": "http://id.worldcat.org/fast/1411628",
        "scheme": "FAST-formgenre",
        "subject": f"History{DEPRECATED_SUFFIX}",
        "tags": [UNLISTED_TAG],
    }

    personal_full = list(jsonlines.open(vocab_dir / "subjects_fast_personal.jsonl"))
    assert personal_full[0]["subject"] == "Mizner, Addison, 1872-1933"

    formgenre_full = list(jsonlines.open(vocab_dir / "subjects_fast_formgenre.jsonl"))
    assert formgenre_full[0]["id"] == "http://id.worldcat.org/fast/1411628"
    assert formgenre_full[0]["tags"] == [UNLISTED_TAG]
    assert formgenre_full[1]["id"] == "http://id.worldcat.org/fast/999"
    assert formgenre_full[1]["subject"] == "History (updated)"


def test_cli_convert_updates(tmp_path):
    mrc_path = tmp_path / "changes.mrc"
    _write_mrc(
        mrc_path,
        [
            _authority(
                uri="http://id.worldcat.org/fast/50",
                tag="150",
                subfields=[("a", "Birds")],
            )
        ],
    )
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "convert-updates",
            str(mrc_path),
            "--vocab-dir",
            str(vocab_dir),
            "--no-merge",
        ],
    )
    assert result.exit_code == 0, result.output
    delta_path = vocab_dir / "updates" / "subjects_fast_topical.updates.jsonl"
    assert delta_path.exists()
    assert not (vocab_dir / "subjects_fast_topical.jsonl").exists()
    rows = list(jsonlines.open(delta_path))
    assert rows[0]["subject"] == "Birds"
