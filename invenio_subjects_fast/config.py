# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Shared configuration for FAST download and convert."""

from collections.abc import Sequence
from typing import NamedTuple


class FastFacet(NamedTuple):
    """One FAST vocabulary facet.

    Attributes:
        slug: Filename stem after ``FAST`` (e.g. ``FormGenre`` →
            ``FASTFormGenre.marcxml.zip``).
        scheme: Scheme suffix used in vocabulary rows (e.g. ``formgenre`` →
            ``FAST-formgenre``).
        marc_tag: MARC datafield tag that carries the preferred label.
    """

    slug: str
    scheme: str
    marc_tag: str


# Canonical facet catalog (download/convert order).
FAST_FACETS: Sequence[FastFacet] = (
    FastFacet("Personal", "personal", "100"),
    FastFacet("Corporate", "corporate", "110"),
    FastFacet("Event", "event", "147"),
    FastFacet("Title", "title", "130"),
    FastFacet("Chronological", "chronological", "148"),
    FastFacet("Topical", "topical", "150"),
    FastFacet("Geographic", "geographic", "151"),
    FastFacet("FormGenre", "formgenre", "155"),
    FastFacet("Meeting", "meeting", "111"),
)

FAST_DOWNLOAD_URL_BASE = "https://researchworks.oclc.org/researchdata/fast/"
FAST_DOWNLOAD_REFERER = (
    "https://www.oclc.org/research/areas/data-science/fast/download.html"
)
FAST_DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_DOWNLOAD_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2
DEFAULT_INTER_REQUEST_DELAY_SECONDS = 3
