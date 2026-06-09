import json
import os
import pytest

def pytest_addoption(parser: pytest.Parser) -> None:
    """Registers command-line options for specifying the repository JSON list and the output scans directory."""
    parser.addoption("--repo-list-file", action="store", default="", help="Path to temporary JSON repository list file")
    parser.addoption("--output-dir", action="store", default="scans", help="Output directory for individual repo scans")

def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parameterizes the `repo_info` test fixture based on the listed repositories in the JSON file."""
    if "repo_info" in metafunc.fixturenames:
        list_file = metafunc.config.getoption("--repo-list-file")
        if list_file and os.path.exists(list_file):
            with open(list_file, "r") as f:
                repos = json.load(f)
            # Parameterize based on repos
            metafunc.parametrize("repo_info", repos, ids=lambda r: r["name"])
        else:
            # Fallback for manual/empty runs
            metafunc.parametrize("repo_info", [])
