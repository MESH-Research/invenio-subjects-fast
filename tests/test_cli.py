# -*- coding: utf-8 -*-
#
# Copyright (C) 2023
#
# invenio-subjects-mesh is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

"""Test MeSH extractor."""

import jsonlines
import os
from pathlib import Path
import responses

from invenio_subjects_fast.converter import convert_to_jsonl
from invenio_subjects_fast.downloader import download_marcxml_files

# Helpers

def assert_includes(dicts, dict_cores):
    """Checks that each dict in dicts has the corresponding dict_core."""
    for d, dc in zip(dicts, dict_cores):
        for key, value in dc.items():
            assert value == d[key]


# Tests


@responses.activate
def test_downloader():
    # patch requests.get to return files
    # patched_get.side_effect = fake_request_context
    downloads_dir = Path(__file__).parent / "downloads"
    data_dir = Path(__file__).parent / "data"

    names = {
        'FASTPersonal': None,
        'FASTCorporate': None,
        'FASTEvent': None,
        'FASTTitle': None,
        'FASTChronological': None,
        'FASTTopical': None,
        'FASTGeographic': None,
        'FASTFormGenre': None,
        'FASTMeeting': None
    }
    for n in names.keys():
        names[n] = open(f'{data_dir}/mock_{n}.marcxml.zip', 'rb')
        rsp1 = responses.Response(
            method='GET',
            url=f'https://researchworks.oclc.org/researchdata/fast/{n}.marcxml.zip',
            status=200,
            body=names[n],
            content_type="application/octet-stream",
            stream=True,
        )
        responses.add(rsp1)

    files = download_marcxml_files(download_dir=downloads_dir)

    for n in names.keys():
        assert os.path.exists(downloads_dir / f'{n}.marcxml.zip')
        assert os.path.exists(f'{downloads_dir}/{n}.marcxml')
    assert files == [downloads_dir / f'{f}.marcxml.zip' for f in names]

    for n in names:
        names[n].close()


def test_converter():
    source_dir = Path(__file__).parent / "downloads"
    target_dir = Path(__file__).parent / "vocabularies"
    assert convert_to_jsonl(source_dir=source_dir, target_dir=target_dir)

    names = [
        'personal',
        'corporate',
        'event',
        'title',
        'chronological',
        'topical',
        'geographic',
        'formgenre',
        'meeting'
    ]
    for n in names:
        assert os.path.exists(f'{target_dir}/subjects_fast_{n}.jsonl')
    with jsonlines.open(f'{target_dir}/subjects_fast_personal.jsonl', 'r') as p:
        expected_lines = [{'id': "http://id.worldcat.org/fast/1",
                           'scheme': "FAST-personal",
                           'subject': "Mizner, Addison, 1872-1933"
                           },
                          {'id': "http://id.worldcat.org/fast/2",
                           'scheme': "FAST-personal",
                           'subject': "Thatcher, Margaret"
                           }
                          ]
        for idx, l in enumerate(p):
            assert l == expected_lines[idx]
