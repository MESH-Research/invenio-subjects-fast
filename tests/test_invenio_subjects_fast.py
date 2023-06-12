# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 MESH Research
#
# invenio-subjects-fast is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

"""Test subjects extension conforms to subjects extension interface."""

import yaml
from pathlib import Path

import pkg_resources

from invenio_subjects_fast import __version__


def test_version():
    """Test version import."""
    assert __version__


def test_vocabularies_yaml():
    """Test vocabularies.yaml structure."""
    extensions = [
        ep.load() for ep in
        pkg_resources.iter_entry_points('invenio_rdm_records.fixtures')
    ]

    assert len(extensions) == 1

    module = extensions[0]
    directory = Path(__file__).parent.parent
    filepath = directory / "invenio_subjects_fast" / "vocabularies" / "vocabularies.yaml"

    with open(filepath) as f:
        data = yaml.safe_load(f)
        assert len(data) == 1
        assert data["subjects"]
        assert data["subjects"]["pid-type"]
        assert data["subjects"]["schemes"]

        # don't care about values, but rather structure
        schemes = data["subjects"]["schemes"]
        assert len(schemes) == 9
        for s in schemes:
            assert "id" in s
            assert "data-file" in s
            assert "name" in s
            assert "uri" in s