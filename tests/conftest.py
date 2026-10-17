"""Keep ordinary tests offline; learned serving behavior uses injected encoders."""

import os
import sys

import pytest

os.environ["SRA_MINILM_SUGGESTIONS"] = "false"


@pytest.fixture(autouse=True)
def isolated_community_storage(tmp_path, monkeypatch):
    """Never write reports/usage into the running app's database from tests."""
    api = sys.modules.get("smart_recycling.api")
    if api:
        monkeypatch.setattr(api.community_store, "path", tmp_path / "community.sqlite3")
