# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Download FAST marcxml vocabulary files.

FAST (Faceted Application of Subject Terminology) data files are made
available by OCLC under the Open Data Commons Attribution License
(ODC-By): http://www.oclc.org/research/activities/fast/odcby.htm
"""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import requests

from invenio_subjects_fast.config import (
    DEFAULT_DOWNLOAD_ATTEMPTS,
    DEFAULT_INTER_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_AFTER_MAX_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    FAST_DOWNLOAD_REFERER,
    FAST_DOWNLOAD_URL_BASE,
    PACKAGE_ROOT,
)
from invenio_subjects_fast.utils.facets import (
    marcxml_filename,
    resolve_facets,
    zip_filename,
)
from invenio_subjects_fast.utils.http import browser_download_session


def _download_session() -> requests.Session:
    """Return a session that sends browser-like download headers."""
    return browser_download_session(
        FAST_DOWNLOAD_REFERER,
        accept="application/zip,application/octet-stream,*/*;q=0.8",
    )


def retry_after_seconds(
    response: requests.Response,
    fallback: float,
    *,
    max_seconds: float = DEFAULT_RETRY_AFTER_MAX_SECONDS,
) -> float:
    """Return how long to sleep after a rate-limit or transient failure.

    Prefers the `Retry-After` header (delay-seconds or HTTP-date). Falls back
    to `fallback` when the header is missing or unparsable. The result is
    clamped to `[0, max_seconds]`.

    Args:
        response: HTTP response that may carry `Retry-After`.
        fallback: Seconds to use when the header is absent/invalid.
        max_seconds: Upper bound on the wait.

    Returns:
        Seconds to sleep before the next attempt.
    """
    raw = response.headers.get("Retry-After")
    delay = fallback
    if raw is not None:
        try:
            delay = float(raw)
        except ValueError:
            try:
                when = parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                delay = (when - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, IndexError, OverflowError):
                delay = fallback
    return max(0.0, min(float(delay), max_seconds))


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS,
    timeout: float = 120,
    stream: bool = False,
    label: str = "request",
) -> requests.Response:
    """GET `url`, retrying transient failures and honouring 429 Retry-After.

    On HTTP errors (including 429), `raise_for_status` raises `HTTPError`;
    `Retry-After` is preferred when present, otherwise exponential backoff.
    The caller owns the returned response and must close it.

    Args:
        session: Requests session.
        url: Absolute request URL.
        attempts: Maximum number of GET attempts.
        timeout: Request timeout in seconds.
        stream: Passed through to `session.get`.
        label: Short name used in retry log lines (e.g. `download`,
            `fetch updates index`).

    Returns:
        A successful response (status 2xx).

    Raises:
        RuntimeError: If every attempt fails.
    """
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        response: requests.Response | None = None
        try:
            response = session.get(url, stream=stream, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if response is not None:
                response.close()
            if attempt < attempts:
                delay = DEFAULT_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    delay = retry_after_seconds(exc.response, delay)
                print(f"  {label} attempt {attempt}/{attempts} failed: {exc}")
                print(f"  retrying in {delay:.0f}s...")
                time.sleep(delay)

    raise RuntimeError(
        f"Failed to {label} {url} after {attempts} attempts"
    ) from last_error


def _download_with_retry(
    session: requests.Session,
    url: str,
    target_path: Path,
    attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS,
) -> None:
    """Download a URL to `target_path`, retrying transient failures.

    Network retries (including 429 / `Retry-After`) are handled by
    `get_with_retry`. Local write failures remove a partial file and
    raise.

    Args:
        session: Requests session with browser-like headers.
        url: Absolute download URL.
        target_path: Local path for the zip archive.
        attempts: Maximum number of download attempts.

    Raises:
        RuntimeError: If the GET fails after retries, or the file cannot be
            written.
    """
    response = get_with_retry(
        session,
        url,
        attempts=attempts,
        timeout=120,
        stream=True,
        label="download",
    )
    try:
        with open(target_path, "wb") as outfile:
            print("saving to", target_path)
            for chunk in response.iter_content(chunk_size=1024 * 8):
                if chunk:
                    outfile.write(chunk)
    except OSError as exc:
        if target_path.exists():
            target_path.unlink()
        raise RuntimeError(f"Failed to write download to {target_path}") from exc
    finally:
        response.close()


def download_marcxml_files(
    download_dir: Path | str | None = None, facets=None
) -> list:
    """Download the raw marcxml files from the FAST repository.

    Args:
        download_dir: Directory for downloaded zip/marcxml files. Defaults to
            this package's `downloads` folder when omitted.
        facets: Optional iterable of facet names (e.g. `formgenre`).
            Matching is case-insensitive. Omit or pass empty to download all.

    Returns:
        Paths to the downloaded zip files (as `pathlib.Path` values).

    Raises:
        RuntimeError: If a download or unzip fails after retries.
    """
    print("Downloading FAST marcxml files...")
    selected = resolve_facets(facets)
    target_folder = Path(
        PACKAGE_ROOT / "downloads" if not download_dir else download_dir
    )
    target_folder.mkdir(parents=True, exist_ok=True)
    session = _download_session()

    output_list = []
    for index, facet in enumerate(selected):
        if index > 0:
            print(
                f"waiting {DEFAULT_INTER_REQUEST_DELAY_SECONDS}s "
                "before next download..."
            )
            time.sleep(DEFAULT_INTER_REQUEST_DELAY_SECONDS)

        archive_name = zip_filename(facet)
        bare_filename = marcxml_filename(facet)
        print(f"getting {bare_filename}...")
        download_url = f"{FAST_DOWNLOAD_URL_BASE}{archive_name}"
        target_path = target_folder / archive_name

        _download_with_retry(session, download_url, target_path)

        print("unzipping download into downloads folder...")
        try:
            with ZipFile(target_path, "r") as zip_file:
                zip_file.extractall(path=target_folder)
        except (BadZipFile, OSError) as exc:
            raise RuntimeError(f"Failed to unzip {target_path}") from exc

        print(f"successfully downloaded {bare_filename}")
        output_list.append(target_path)

    print("All Done!")
    return output_list
