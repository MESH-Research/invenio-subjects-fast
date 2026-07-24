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
from pprint import pprint
from typing import Optional

import jsonlines
from halo import Halo
from tqdm import trange

from invenio_subjects_fast.facets import (
    MARC_TAG_TO_SCHEME,
    marcxml_filename,
    resolve_facets,
)


def convert_to_jsonl(
    source_dir: Optional[str] = None, target_dir: Optional[str] = None, facets=None
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
    mx = "{http://www.loc.gov/MARC21/slim}"
    selected = resolve_facets(facets)

    source_folder = (
        Path(__file__).parent / "downloads" if not source_dir else source_dir
    )
    target_folder = (
        Path(__file__).parent / "vocabularies" if not target_dir else target_dir
    )
    for facet in selected:
        source_path = str(Path(source_folder) / marcxml_filename(facet))
        print(f"\nConverting {facet.slug} vocabulary to Invenio jsonl format")
        with jsonlines.open(
            f"{target_folder}/subjects_fast_{facet.scheme}.jsonl", "w"
        ) as target_file:
            with open(source_path, "rb") as source_file:
                spinner = Halo(
                    text="    parsing FAST marcxml file (This may take a while!)",
                    spinner="dots",
                )
                spinner.start()
                parsed = ET.parse(source_file)
                spinner.stop()
                print(f"  done parsing {source_path.split('/')[-1]}")

                print("  converting contents to jsonl")
                root = parsed.getroot()

                records = root.findall(f"./{mx}record")

                for r in trange(len(records)):
                    record = records[r]

                    uri_field_parent = record.find(f'./{mx}datafield[@tag="024"]')
                    uri_field = uri_field_parent.find(f'./{mx}subfield[@code="a"]')
                    uri = uri_field.text

                    label_parent = [
                        field
                        for field in record
                        if "tag" in field.attrib.keys()
                        and field.attrib["tag"] in MARC_TAG_TO_SCHEME
                    ][0]

                    facet_num = label_parent.attrib["tag"]
                    label_fields = [
                        field
                        for field in label_parent
                        if "code" in field.attrib.keys()
                        and field.attrib["code"] in ["a", "b", "c", "d", "p", "x", "z"]
                    ]
                    if len(label_fields) > 1:
                        code_letters = [field.get("code") for field in label_fields]
                        if any(c for c in code_letters if c in ["b", "c", "d", "p"]):
                            label = " ".join([field.text for field in label_fields])
                        elif any(c for c in code_letters if c in ["x", "z"]):
                            label = "--".join([field.text for field in label_fields])
                        else:
                            pprint("BAD CODE COMBINATION")
                            pprint(MARC_TAG_TO_SCHEME[facet_num])
                            pprint(uri)
                            pprint([field.get("code") for field in label_fields])
                    else:
                        label = label_fields[0].text
                    myline = {
                        "id": uri,
                        "scheme": f"FAST-{MARC_TAG_TO_SCHEME[facet_num]}",
                        "subject": f"{label}",
                    }
                    target_file.write(myline)
                print(
                    f"finished writing this facet to its jsonl file: "
                    f"subjects_fast_{facet.scheme}.jsonl"
                )
    print("All done! All FAST facets have been converted")
    return True
