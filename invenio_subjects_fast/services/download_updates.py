# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Download OCLC FAST ISO MARC (.mrc) change files.

Change files are listed on https://fast.oclc.org/fastChanges/ as
`FASTChangesYYYY-MM-DD.mrc` (general) and `FORMChangesYYYY-MM-DD.mrc`
(form/genre). Full-facet MARCXML dumps remain under `downloader.py`.
"""

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from invenio_subjects_fast.config import (
    DEFAULT_INTER_REQUEST_DELAY_SECONDS,
    FAST_UPDATES_INDEX_URL,
    FAST_UPDATES_REFERER,
    PACKAGE_ROOT,
)
from invenio_subjects_fast.services.downloader import (
    _download_with_retry,
    get_with_retry,
)
from invenio_subjects_fast.utils.http import browser_download_session

# Last-resort window when there is no explicit `since`, no local change files,
# and no full-facet dump mtime to anchor from.
DEFAULT_UPDATES_LOOKBACK_DAYS = 180

# Matches hrefs such as FASTChanges2026-07-24.mrc / FORMChanges2026-07-24.mrc
_MRC_HREF_RE = re.compile(
    r"""href=["']([^"']*?(?:FAST|FORM)Changes(\d{4}-\d{2}-\d{2})\.mrc)["']""",
    re.IGNORECASE,
)
_MRC_NAME_RE = re.compile(
    r"^(?:FAST|FORM)Changes(\d{4}-\d{2}-\d{2})\.mrc$",
    re.IGNORECASE,
)


def update_file_date_from_name(filename: str) -> date | None:
    """Parse the YYYY-MM-DD stamp from a change-file basename.

    Args:
        filename: e.g. `FASTChanges2026-07-24.mrc`.

    Returns:
        The embedded date, or `None` if the name does not match.
    """
    match = _MRC_NAME_RE.match(Path(filename).name)
    if not match:
        return None
    return date.fromisoformat(match.group(1))


def latest_local_update_file_date(download_dir: str | Path) -> date | None:
    """Return the newest filename date among local change `.mrc` files.

    Scans `download_dir` and `download_dir/processed/` for
    `FASTChanges*` / `FORMChanges*` names.

    Args:
        download_dir: Changes directory (pending + optional `processed/`).

    Returns:
        Max parsed date, or `None` if no matching files exist.
    """
    root = Path(download_dir)
    dates: list[date] = []
    for folder in (root, root / "processed"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.mrc"):
            parsed = update_file_date_from_name(path.name)
            if parsed is not None:
                dates.append(parsed)
    return max(dates) if dates else None


def latest_full_dump_mtime_date(
    downloads_dir: str | Path | None = None,
) -> date | None:
    """Return the newest mtime date among full-facet dump files.

    Looks at `*.marcxml` and `*.marcxml.zip` (and `FASTAll*.zip`) under
    the package `downloads/` directory by default — the artifacts produced
    by `download` / a manual full-vocab drop.

    Args:
        downloads_dir: Override for the full-dump directory.

    Returns:
        Calendar date of the newest matching file mtime, or `None`.
    """
    folder = Path(
        PACKAGE_ROOT / "downloads"
        if downloads_dir is None
        else downloads_dir
    )
    if not folder.is_dir():
        return None
    candidates: list[Path] = []
    candidates.extend(folder.glob("*.marcxml"))
    candidates.extend(folder.glob("*.marcxml.zip"))
    candidates.extend(folder.glob("FASTAll*.zip"))
    mtimes = [path.stat().st_mtime for path in candidates if path.is_file()]
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes)).date()


@dataclass(frozen=True)
class UpdateFileRef:
    """One remote FAST change file.

    Attributes:
        filename: Basename (e.g. `FASTChanges2026-07-24.mrc`).
        url: Absolute download URL.
        file_date: Date parsed from the filename.
    """

    filename: str
    url: str
    file_date: date


def _updates_session() -> requests.Session:
    """Return a session with browser-like headers for the changes site."""
    return browser_download_session(
        FAST_UPDATES_REFERER,
        accept="text/html,application/octet-stream,*/*;q=0.8",
    )


def _parse_updates_index_html(
    html: str, updates_index_url: str
) -> list[UpdateFileRef]:
    """Extract `.mrc` change-file links from the FAST updates index page.

    Args:
        html: Raw HTML of the updates index page.
        updates_index_url: Base URL used to resolve relative hrefs.

    Returns:
        Deduplicated change-file refs, newest date first.
    """
    found: dict[str, UpdateFileRef] = {}
    for match in _MRC_HREF_RE.finditer(html):
        href, date_str = match.group(1), match.group(2)
        filename = Path(urlparse(href).path).name
        if not _MRC_NAME_RE.match(filename):
            continue
        url = urljoin(updates_index_url, href)
        file_date = date.fromisoformat(date_str)
        found[filename] = UpdateFileRef(
            filename=filename, url=url, file_date=file_date
        )
    return sorted(found.values(), key=lambda ref: ref.file_date, reverse=True)


def list_remote_update_files(
    *,
    updates_index_url: str = FAST_UPDATES_INDEX_URL,
    session: requests.Session | None = None,
) -> list[UpdateFileRef]:
    """Fetch and parse the FAST updates index for `.mrc` links.

    Network retries (including HTTP 429 / `Retry-After`) use `get_with_retry`.

    Args:
        updates_index_url: FAST updates index page URL (HTML listing of
            change files).
        session: Optional requests session.

    Returns:
        Change-file refs, newest first.

    Raises:
        RuntimeError: If the updates index cannot be fetched.
    """
    own_session = session is None
    session = session or _updates_session()
    try:
        try:
            response = get_with_retry(
                session,
                updates_index_url,
                timeout=60,
                label="fetch updates index",
            )
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to fetch FAST updates index {updates_index_url}"
            ) from exc
        try:
            return _parse_updates_index_html(response.text, updates_index_url)
        finally:
            response.close()
    finally:
        if own_session:
            session.close()


def _as_date(value: date | datetime | str | None) -> date | None:
    """Normalize `since` filters to a `date` (or `None`).

    Returns:
        A `date`, or `None` when `value` is empty/unset.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Accept ISO date or datetime.
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text[:10])


def resolve_default_since(download_dir: str | Path) -> date:
    """Choose a `since` date when none is supplied.

    Precedence:

    1. Newest date embedded in local `FASTChanges*` / `FORMChanges*`
       filenames under `download_dir` or `download_dir/processed/`.
    2. Newest mtime date among package `downloads/` full-facet dump files.
    3. Today minus `DEFAULT_UPDATES_LOOKBACK_DAYS`.

    Args:
        download_dir: Change-file directory (pending + optional `processed/`).

    Returns:
        Inclusive lower bound for remote change-file dates.
    """
    local = latest_local_update_file_date(download_dir)
    if local is not None:
        print(f"default since from local change file(s): {local}")
        return local

    dump = latest_full_dump_mtime_date()
    if dump is not None:
        print(f"default since from full-dump mtime: {dump}")
        return dump

    fallback = date.today() - timedelta(days=DEFAULT_UPDATES_LOOKBACK_DAYS)
    print(
        f"no local change files or full dump; defaulting to "
        f"{DEFAULT_UPDATES_LOOKBACK_DAYS}-day lookback ({fallback})"
    )
    return fallback


def _already_have(filename: str, download_dir: Path) -> bool:
    """Return whether `filename` exists in download or processed dirs."""
    return (download_dir / filename).exists() or (
        download_dir / "processed" / filename
    ).exists()


def download_updates(
    download_dir: str | Path | None = None,
    *,
    since: date | datetime | str | None = None,
    updates_index_url: str = FAST_UPDATES_INDEX_URL,
    force: bool = False,
    filenames: Iterable[str] | None = None,
) -> list[Path]:
    """Download new FAST `.mrc` change files into `download_dir`.

    Skips files already present in `download_dir` or
    `download_dir/processed/` unless `force` is true. When `since` is
    omitted, uses `resolve_default_since`. Optional `filenames` limits to an
    explicit set of basenames.

    Args:
        download_dir: Destination directory. Defaults to this package's
            `downloads/updates` folder.
        since: Inclusive lower bound on the change-file date. When unset,
            resolved via `resolve_default_since`.
        updates_index_url: FAST updates index URL (HTML listing of change
            files).
        force: Re-download even when the file already exists locally.
        filenames: If set, only download these basenames (still subject to
            `since` / skip logic).

    Returns:
        Paths to files downloaded in this call (not previously present).
    """
    target = Path(
        PACKAGE_ROOT / "downloads" / "updates"
        if download_dir is None
        else download_dir
    )
    target.mkdir(parents=True, exist_ok=True)
    since_date = _as_date(since)
    if since_date is None:
        since_date = resolve_default_since(target)
    allow = {name for name in filenames} if filenames is not None else None

    session = _updates_session()
    try:
        remote = list_remote_update_files(
            updates_index_url=updates_index_url, session=session
        )
        to_fetch: list[UpdateFileRef] = []
        for ref in remote:
            if allow is not None and ref.filename not in allow:
                continue
            if ref.file_date < since_date:
                continue
            if not force and _already_have(ref.filename, target):
                continue
            to_fetch.append(ref)

        if not to_fetch:
            print("No new FAST change files to download.")
            return []

        print(f"Downloading {len(to_fetch)} FAST change file(s) to {target}...")
        downloaded: list[Path] = []
        for index, ref in enumerate(to_fetch):
            if index > 0:
                print(
                    f"waiting {DEFAULT_INTER_REQUEST_DELAY_SECONDS}s "
                    "before next download..."
                )
                time.sleep(DEFAULT_INTER_REQUEST_DELAY_SECONDS)

            dest = target / ref.filename
            print(f"getting {ref.filename}...")
            _download_with_retry(session, ref.url, dest)
            downloaded.append(dest)
            print(f"successfully downloaded {ref.filename}")

        print("Done downloading FAST change files.")
        return downloaded
    finally:
        session.close()


def mark_update_files_processed(
    paths: Iterable[Path | str],
    download_dir: str | Path | None = None,
) -> list[Path]:
    """Move ingested `.mrc` files into `download_dir/processed/`.

    Args:
        paths: Files that were successfully converted/ingested.
        download_dir: Parent changes directory (default: package
            `downloads/updates`).

    Returns:
        Destinations under `processed/`.
    """
    target = Path(
        PACKAGE_ROOT / "downloads" / "updates"
        if download_dir is None
        else download_dir
    )
    processed_dir = target / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for path in paths:
        src = Path(path)
        if not src.exists():
            continue
        dest = processed_dir / src.name
        if dest.exists():
            dest.unlink()
        src.replace(dest)
        moved.append(dest)
    return moved


__all__ = [
    "UpdateFileRef",
    "DEFAULT_UPDATES_LOOKBACK_DAYS",
    "update_file_date_from_name",
    "download_updates",
    "latest_full_dump_mtime_date",
    "latest_local_update_file_date",
    "list_remote_update_files",
    "mark_update_files_processed",
    "resolve_default_since",
]
