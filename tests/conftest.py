# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Pytest configuration.

See https://pytest-invenio.readthedocs.io/ for documentation on which test
fixtures are available.

Prefer ``base_app`` / ``appctx`` for tests that only need a Flask application
context (no database or OpenSearch). The heavier ``app`` fixture also starts
those services.
"""

import pytest
from invenio_app.factory import create_app as _create_app


@pytest.fixture(scope="module")
def celery_config():
    """Override pytest-invenio Celery config (no broker required here)."""
    return {}


@pytest.fixture(scope="module")
def app_config(app_config):
    """Application config for pytest-invenio ``base_app``."""
    app_config["JSONSCHEMAS_HOST"] = "not-used"
    # Avoid Redis; flask-caching 2.x module path is simplecache (not "simple").
    app_config["CACHE_TYPE"] = (
        "flask_caching.backends.simplecache.SimpleCache"
    )
    app_config["SUBJECTS_FAST_UPDATES_PATH"] = None
    return app_config


@pytest.fixture(scope="module")
def create_app(instance_path):
    """Application factory for pytest-invenio (``base_app`` / ``app``)."""
    return _create_app
