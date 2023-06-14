# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 MESH Research
#
# invenio-subjects-fast is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

import jsonlines
from halo import Halo
from pathlib import Path
from pprint import pprint
import re
from tqdm import trange
from typing import Optional
import xml.etree.ElementTree as ET
"""

File format

Although the current InvenioRDM documentation recommends yaml format for vocabulary files, this module produces jsonl files instead. These are much
faster for InvenioRDM to read than are yaml files.

Escaping

In the converted jsonl file double quotes (") are escaped with a backslash (\"). Single backslashes followed by a letter are also escaped (\\) so that the Invenio importer does not try to interpret the slash and following letter as a control character. (This escaping is done by the jsonlines writer.)
"""

def convert_to_jsonl(source_dir:Optional[str], target_dir:Optional[str]) -> bool:
    """
    Parse a FAST marcxml file and write to an Invenio jsonl vocabulary file

    :param str source_folder: A string representing the path (absolute
                              or relative to this script file) for the
                              folder holding the marcxml files.
    :param str target_folder: A string representing the path (absolute
                              or relative to this script file) for the
                              folder where the subjects_fast.jsonl file
                              exists (or will be created if it does not
                              exist).
    """
    mx = "{http://www.loc.gov/MARC21/slim}"
    slugs = ["Corporate",
             "Topical",
             "Chronological",
             "Event",
             "FormGenre",
             "Geographic",
             "Meeting",
             "Personal",
             "Title"]

    source_folder = Path(__file__).parent / 'downloads' \
        if not source_dir else source_dir
    source_paths = [f"{source_folder}/FAST{s}.marcxml" for s in slugs]
    target_folder = Path(__file__).parent / 'vocabularies' \
        if not target_dir else target_dir
    for idx, source_path in enumerate(source_paths):
        print(f'\nConverting {slugs[idx]} vocabulary to Invenio jsonl format')
        with jsonlines.open(f'{target_folder}/subjects_fast_'
                            f'{slugs[idx].lower()}.jsonl',
                            "w") as target_file:
            with open(source_path, "rb") as source_file:
                # print('\nParsing FAST marcxml file (This may take a while!)')
                spinner = Halo(text='    parsing FAST marcxml file (This may take a while!)', spinner='dots')
                spinner.start()
                parsed = ET.parse(source_file)
                spinner.stop()
                print(f'  done parsing {source_path.split("/")[-1]}')

                print(f'  converting contents to jsonl')
                root = parsed.getroot()

                records = root.findall(f'./{mx}record')

                for r in trange(len(records)):
                    record = records[r]
                    # pprint([r for r in record])
                    # id_num = record.find(f"./{mx}controlfield[@tag='001']")
                    # id_num = id_num.text
                    # id_num = re.sub(r'fst[0]*', '', id_num)

                    uri_field_parent = record.find(
                        f'./{mx}datafield[@tag="024"]'
                        )
                    # pprint(uri_field_parent)
                    # pprint([u for u in uri_field_parent])
                    uri_field = uri_field_parent.find(f'./{mx}subfield[@code="a"]')
                    # pprint(uri_field.text)
                    uri = uri_field.text

                    label_parent = [r for r in record
                                    if 'tag' in r.attrib.keys()
                                    and r.attrib['tag'] in ["148", "150", "110", "147", "155", "151", "111", "100", "130"]][0]

                    facets = {"110": "corporate",
                            "150": "topical",
                            "148": "chronological",
                            "147": "event",
                            "155": "form",
                            "151": "geographic",
                            "111": "meeting",
                            "100": "personal",
                            "130": "title"
                            }
                    facet_num = label_parent.attrib['tag']
                    label_fields = [l for l in label_parent
                                    if 'code' in l.attrib.keys()
                                    and l.attrib['code'] in ["a", "b", "c", "d", "p", "x", "z"]]
                    if len(label_fields) > 1:
                        code_letters = [f.get('code') for f in label_fields]
                        if any(c for c in code_letters if c in ["b", "c", "d", "p"]):
                            label = ' '.join([f.text for f in label_fields])
                        elif any(c for c in code_letters if c in ["x", "z"]):
                            label = '--'.join([f.text for f in label_fields])
                        else:
                            pprint('BAD CODE COMBINATION')
                            pprint(facets[facet_num])
                            pprint(uri)
                            pprint([f.get('code') for f in label_fields])
                    else:
                        label = label_fields[0].text
                    # escape quotation marks and slashes (now done by jsonlines)
                    # label = label.replace('"', '\\"')
                    # label = re.sub(r'\\([a-z A-Z])', r'\\\\1', label)
                    myline = {'id': uri,
                              'scheme': f'FAST-{facets[facet_num]}',
                              'subject': f'{label}'
                    }
                    target_file.write(myline)
                print(f'finished writing this facet to its jsonl file: '
                      f'subjects_fast_{slugs[idx].lower()}.jsonl')
    print(f'All done! All FAST facets have been converted')
    return(True)