# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Download FAST marcxml vocabulary files.

FAST (Faceted Application of Subject Terminology) data files are made
available by OCLC under the Open Data Commons Attribution License
(ODC-By): http://www.oclc.org/research/activities/fast/odcby.htm
"""

import time
from pathlib import Path
from typing import Optional
from zipfile import BadZipFile, ZipFile

import requests

from invenio_subjects_fast.config import (
    DEFAULT_DOWNLOAD_ATTEMPTS,
    DEFAULT_INTER_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    FAST_DOWNLOAD_REFERER,
    FAST_DOWNLOAD_URL_BASE,
    FAST_DOWNLOAD_USER_AGENT,
)
from invenio_subjects_fast.facets import (
    marcxml_filename,
    resolve_facets,
    zip_filename,
)


def _download_session() -> requests.Session:
    """Return a session that sends browser-like download headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": FAST_DOWNLOAD_USER_AGENT,
            "Accept": "application/zip,application/octet-stream,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": FAST_DOWNLOAD_REFERER,
        }
    )
    return session


def _download_with_retry(
    session: requests.Session,
    url: str,
    target_path: Path,
    attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS,
) -> None:
    """Download a URL to ``target_path``, retrying transient failures.

    Args:
        session: Requests session with browser-like headers.
        url: Absolute download URL.
        target_path: Local path for the zip archive.
        attempts: Maximum number of download attempts.

    Raises:
        RuntimeError: If every attempt fails.
    """
    last_error: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        try:
            with session.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(target_path, "wb") as outfile:
                    print("saving to", target_path)
                    for chunk in response.iter_content(chunk_size=1024 * 8):
                        if chunk:
                            outfile.write(chunk)
            return
        except (requests.RequestException, OSError) as exc:
            last_error = exc
            if target_path.exists():
                target_path.unlink()
            if attempt < attempts:
                delay = DEFAULT_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(f"  download attempt {attempt}/{attempts} failed: {exc}")
                print(f"  retrying in {delay}s...")
                time.sleep(delay)

    raise RuntimeError(
        f"Failed to download {url} after {attempts} attempts"
    ) from last_error


def download_marcxml_files(
    download_dir: Optional[str] = None, facets=None
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
        Path(__file__).parent / "downloads" if not download_dir else download_dir
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
