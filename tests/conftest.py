"""
Pytest configuration and fixtures.
"""
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Create a shared test data directory."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def clean_environment(monkeypatch):
    """Provide a clean environment for tests."""
    # Clear relevant environment variables
    env_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "GITHUB_TOKEN",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
