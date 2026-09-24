# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Convert FAST ISO MARC (.mrc) change files into JSONL vocabulary updates."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from pymarc import MARCReader

from invenio_subjects_fast.config import PACKAGE_ROOT, FastFacet
from invenio_subjects_fast.utils.facets import resolve_facets
from invenio_subjects_fast.utils.jsonl import read_jsonl, write_jsonl
from invenio_subjects_fast.utils.marc_subjects import extract_from_marc_record


def full_jsonl_filename(facet: FastFacet) -> str:
    """Return the full-facet vocabulary filename for `facet`."""
    return f"subjects_fast_{facet.scheme}.jsonl"


def updates_jsonl_filename(facet: FastFacet) -> str:
    """Return the incremental updates vocabulary filename for `facet`."""
    return f"subjects_fast_{facet.scheme}.updates.jsonl"


def _scheme_to_facet(facets: Sequence[FastFacet]) -> dict[str, FastFacet]:
    """Map `FAST-<scheme>` strings to facet metadata.

    Returns:
        Dict keyed by full scheme id (e.g. `FAST-topical`).
    """
    return {f"FAST-{facet.scheme}": facet for facet in facets}


def merge_subject_rows(
    existing_rows: list[dict], updates: list[dict]
) -> list[dict]:
    """Merge update rows into an existing full-facet row list.

    Existing order is preserved for ids already present; new ids are appended.
    Each update replaces the prior row for that `id` entirely (so an active
    update clears a previous `tags: ["unlisted"]` entry).

    Args:
        existing_rows: Current full-facet vocabulary rows.
        updates: Rows extracted from a change file.

    Returns:
        Merged row list.
    """
    by_id = {row["id"]: row for row in existing_rows}
    order = [row["id"] for row in existing_rows]
    for row in updates:
        row_id = row["id"]
        if row_id not in by_id:
            order.append(row_id)
        by_id[row_id] = row
    return [by_id[row_id] for row_id in order]


def iter_update_rows_from_mrc(
    mrc_paths: Sequence[Path],
    facets: Iterable[str] | None = None,
) -> dict[str, list[dict]]:
    """Parse ISO MARC change files into subject rows grouped by scheme.

    Args:
        mrc_paths: Paths to `.mrc` change files (concatenated records).
        facets: Optional facet name filter (same as `convert` / `download`).

    Returns:
        Mapping of scheme string (e.g. `FAST-topical`) to ordered update rows.
        Later records for the same id within the batch overwrite earlier ones.
    """
    selected = resolve_facets(facets)
    allowed_schemes = {f"FAST-{facet.scheme}" for facet in selected}
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    order: dict[str, list[str]] = defaultdict(list)

    for mrc_path in mrc_paths:
        with open(mrc_path, "rb") as handle:
            reader = MARCReader(handle, to_unicode=True, force_utf8=True)
            for record in reader:
                if record is None:
                    continue
                row = extract_from_marc_record(record)
                if row is None:
                    continue
                scheme = row["scheme"]
                if scheme not in allowed_schemes:
                    continue
                row_id = row["id"]
                if row_id not in grouped[scheme]:
                    order[scheme].append(row_id)
                grouped[scheme][row_id] = row

    return {
        scheme: [grouped[scheme][row_id] for row_id in order[scheme]]
        for scheme in order
    }


def convert_updates(
    mrc_paths: Sequence[str | Path],
    *,
    vocab_dir: str | Path | None = None,
    delta_dir: str | Path | None = None,
    facets: Iterable[str] | None = None,
    merge: bool = True,
    write_delta: bool = True,
) -> dict[str, list[dict]]:
    """Convert FAST `.mrc` change files into delta and/or merged JSONL.

    Args:
        mrc_paths: One or more ISO MARC change files from OCLC FAST Changes.
        vocab_dir: Directory of full `subjects_fast_*.jsonl` files. Defaults
            to this package's `vocabularies` folder.
        delta_dir: Directory for `*.updates.jsonl` delta files. Defaults to
            `vocab_dir / "updates"`.
        facets: Optional facet filter; omit to accept all facets in the file.
        merge: When true, upsert updates into the full facet JSONL files.
        write_delta: When true, write per-facet delta JSONL under `delta_dir`.

    Returns:
        Mapping of scheme → update rows that were applied.

    Raises:
        ValueError: If neither `merge` nor `write_delta` is enabled, or if
            no `mrc_paths` are given.
    """
    paths = [Path(p) for p in mrc_paths]
    if not paths:
        raise ValueError("At least one .mrc path is required")
    if not merge and not write_delta:
        raise ValueError("Enable merge and/or write_delta")

    package_vocab = PACKAGE_ROOT / "vocabularies"
    vocab_folder = package_vocab if vocab_dir is None else Path(vocab_dir)
    updates_folder = (
        vocab_folder / "updates" if delta_dir is None else Path(delta_dir)
    )

    selected = resolve_facets(facets)
    scheme_facets = _scheme_to_facet(selected)
    updates_by_scheme = iter_update_rows_from_mrc(paths, facets=facets)

    if not updates_by_scheme:
        print("No convertible FAST records found in the change file(s).")
        return {}

    for scheme, rows in updates_by_scheme.items():
        facet = scheme_facets[scheme]
        print(f"\n{scheme}: {len(rows)} update(s)")

        if write_delta:
            delta_path = updates_folder / updates_jsonl_filename(facet)
            write_jsonl(delta_path, rows)
            print(f"  wrote delta {delta_path}")

        if merge:
            full_path = vocab_folder / full_jsonl_filename(facet)
            existing = read_jsonl(full_path)
            merged = merge_subject_rows(existing, rows)
            write_jsonl(full_path, merged)
            print(f"  merged into {full_path} ({len(merged)} total terms)")

    print("\nDone converting FAST updates.")
    return updates_by_scheme


__all__ = [
    "convert_updates",
    "full_jsonl_filename",
    "iter_update_rows_from_mrc",
    "merge_subject_rows",
    "updates_jsonl_filename",
]
