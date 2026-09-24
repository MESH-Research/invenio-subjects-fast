# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Shared configuration for FAST download and convert."""

from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

# Package install root (`invenio_subjects_fast/`), not a nested subpackage.
PACKAGE_ROOT = Path(__file__).resolve().parent


class FastFacet(NamedTuple):
    """One FAST vocabulary facet.

    Attributes:
        slug: Filename stem after `FAST` (e.g. `FormGenre` →
            `FASTFormGenre.marcxml.zip`).
        scheme: Scheme suffix used in vocabulary rows (e.g. `formgenre` →
            `FAST-formgenre`).
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

# Incremental change files (ISO MARC .mrc), separate from full facet dumps.
# HTML listing of available FASTChanges*.mrc / FORMChanges*.mrc files.
FAST_UPDATES_INDEX_URL = "https://fast.oclc.org/fastChanges/"
FAST_UPDATES_REFERER = FAST_UPDATES_INDEX_URL

DEFAULT_DOWNLOAD_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2
# Pause between successive file downloads (full dumps and change files).
DEFAULT_INTER_REQUEST_DELAY_SECONDS = 10
# Cap on Retry-After waits so a runaway header cannot block forever.
DEFAULT_RETRY_AFTER_MAX_SECONDS = 300

# Flask / Invenio config key (set in invenio.cfg or env as
# INVENIO_SUBJECTS_FAST_UPDATES_PATH). When unset, the change-file workdir
# falls back to ``<instance_path>/app_data/vocabularies/fast/``.
SUBJECTS_FAST_UPDATES_PATH = None
"""Directory for FAST `.mrc` change files, `processed/`, and `deltas/`.

Override via Flask config `SUBJECTS_FAST_UPDATES_PATH`, or pass an explicit
path to the CLI / task. When both are unset, uses
`<instance_path>/app_data/vocabularies/fast/`.
"""
