# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

r"""Convert FAST marcxml files to jsonl for InvenioRDM import.

## File format

Although the current InvenioRDM documentation recommends yaml format for
vocabulary files, this module produces jsonl files instead. These are much
faster for InvenioRDM to read than are yaml files.

## Escaping

In the converted jsonl file double quotes (") are escaped with a backslash
(\"). Single backslashes followed by a letter are also escaped (\\) so that
the Invenio importer does not try to interpret the slash and following letter
as a control character. (This escaping is done by the jsonlines writer.)
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import jsonlines
from halo import Halo
from tqdm import trange

from invenio_subjects_fast.config import PACKAGE_ROOT
from invenio_subjects_fast.utils.facets import marcxml_filename, resolve_facets
from invenio_subjects_fast.utils.marc_subjects import (
    MARCXML_NS,
    extract_from_xml_record,
)


def convert_to_jsonl(
    source_dir: Path | str | None = None,
    target_dir: Path | str | None = None,
    facets=None,
) -> bool:
    """Parse a FAST marcxml file and write to an Invenio jsonl vocabulary file.

    Args:
        source_dir: Path (absolute or relative) to the folder holding the
            marcxml files. Defaults to this package's `downloads` folder.
        target_dir: Path (absolute or relative) to the folder where
            `subjects_fast_*.jsonl` files are written. Defaults to this
            package's `vocabularies` folder.
        facets: Optional iterable of facet names (e.g. `formgenre`).
            Matching is case-insensitive. Omit or pass empty to convert all.

    Returns:
        `True` when conversion of the selected facets completes.
    """
    selected = resolve_facets(facets)

    source_folder = (
        PACKAGE_ROOT / "downloads" if not source_dir else Path(source_dir)
    )
    target_folder = (
        PACKAGE_ROOT / "vocabularies" if not target_dir else Path(target_dir)
    )
    for facet in selected:
        source_path = source_folder / marcxml_filename(facet)
        print(f"\nConverting {facet.slug} vocabulary to Invenio jsonl format")
        with jsonlines.open(
            target_folder / f"subjects_fast_{facet.scheme}.jsonl", "w"
        ) as target_file:
            with open(source_path, "rb") as source_file:
                spinner = Halo(
                    text="    parsing FAST marcxml file (This may take a while!)",
                    spinner="dots",
                )
                spinner.start()
                parsed = ET.parse(source_file)
                spinner.stop()
                print(f"  done parsing {source_path.name}")

                print("  converting contents to jsonl")
                root = parsed.getroot()
                records = root.findall(f"./{MARCXML_NS}record")

                for r in trange(len(records)):
                    row = extract_from_xml_record(records[r])
                    if row is None:
                        continue
                    target_file.write(row)
                print(
                    f"finished writing this facet to its jsonl file: "
                    f"subjects_fast_{facet.scheme}.jsonl"
                )
    print("All done! All FAST facets have been converted")
    return True
