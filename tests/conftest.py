import pytest
from pathlib import Path


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with test fixtures."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def workspace_dir(tmp_path):
    """Create a temporary workspace directory."""
    d = tmp_path / "workspace"
    d.mkdir()
    return d
