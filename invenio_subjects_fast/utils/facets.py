# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Shared helpers for FAST facet selection and filenames."""

from collections.abc import Iterable
from typing import Optional

from invenio_subjects_fast.config import FAST_FACETS, FastFacet

MARC_TAG_TO_SCHEME = {facet.marc_tag: facet.scheme for facet in FAST_FACETS}


def zip_filename(facet: FastFacet) -> str:
    """Return the OCLC zip archive name for a facet."""
    return f"FAST{facet.slug}.marcxml.zip"


def marcxml_filename(facet: FastFacet) -> str:
    """Return the extracted marcxml filename for a facet."""
    return f"FAST{facet.slug}.marcxml"


def resolve_facets(facets: Optional[Iterable[str]] = None) -> list[FastFacet]:
    """Return facets to process, optionally filtered by name.

    Names are matched case-insensitively against each facet's `slug` (e.g.
    `formgenre` or `FormGenre`).

    Args:
        facets: Optional iterable of facet names. Omit or empty to use all.

    Returns:
        Ordered list of `FastFacet` entries.

    Raises:
        ValueError: If any requested name is not a known FAST facet.
    """
    if not facets:
        return list(FAST_FACETS)

    wanted = {name.lower() for name in facets}
    selected = [facet for facet in FAST_FACETS if facet.slug.lower() in wanted]
    matched = {facet.slug.lower() for facet in selected}
    unknown = wanted - matched
    if unknown:
        raise ValueError(f"Unknown FAST facet(s): {', '.join(sorted(unknown))}")
    return selected
