import os
import json
import pytest
from report import generate_html_report

def test_generate_html_report_creates_file(tmp_path) -> None:
    """Verifies that generate_html_report creates summary.html and includes expected repo contents and light theme defaults."""
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    # Mock some repo scan results
    repo1_data = {
        "repo_name": "org/repo1",
        "is_private": True,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    repo2_data = {
        "repo_name": "org/repo2",
        "is_private": False,
        "scan_status": "compromised",
        "findings": [{
            "detector": "AWS",
            "file": "config.json",
            "line": 10,
            "commit": "abc",
            "redacted": "AKIA..."
        }],
        "error": ""
    }
    
    with open(os.path.join(repos_dir, "org_repo1.json"), "w") as f:
        json.dump(repo1_data, f)
    with open(os.path.join(repos_dir, "org_repo2.json"), "w") as f:
        json.dump(repo2_data, f)
        
    html_path = generate_html_report(output_dir)
    assert os.path.exists(html_path)
    with open(html_path, "r") as f:
        html_content = f.read()
        assert "org/repo1" in html_content
        assert "org/repo2" in html_content
        # Verify Light Mode Default is implemented (e.g. body data-theme="light")
        assert 'body data-theme="light"' in html_content

def test_generate_html_report_sorting(tmp_path) -> None:
    """Verifies that compromised repositories are sorted to the top, and clean ones are alphabetically sorted after."""
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    clean_b_data = {
        "repo_name": "org/clean-b",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    compromised_data = {
        "repo_name": "org/compromised-a",
        "is_private": False,
        "scan_status": "compromised",
        "findings": [{"detector": "AWS", "file": "key.json", "line": 1, "commit": "123", "redacted": "xxx"}],
        "error": ""
    }
    clean_a_data = {
        "repo_name": "org/clean-a",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    
    with open(os.path.join(repos_dir, "clean_b.json"), "w") as f:
        json.dump(clean_b_data, f)
    with open(os.path.join(repos_dir, "compromised_a.json"), "w") as f:
        json.dump(compromised_data, f)
    with open(os.path.join(repos_dir, "clean_a.json"), "w") as f:
        json.dump(clean_a_data, f)
        
    generate_html_report(output_dir)
    
    # Read output summary.json to verify sort order on data structure
    summary_json_path = os.path.join(output_dir, "summary.json")
    assert os.path.exists(summary_json_path)
    
    with open(summary_json_path, "r") as f:
        sorted_results = json.load(f)
        
    assert len(sorted_results) == 3
    # First: compromised
    assert sorted_results[0]["repo_name"] == "org/compromised-a"
    # Second: clean-a (alphabetical clean sort)
    assert sorted_results[1]["repo_name"] == "org/clean-a"
    # Third: clean-b
    assert sorted_results[2]["repo_name"] == "org/clean-b"

def test_generate_html_report_resilience_to_malformed_json(tmp_path) -> None:
    """Verifies that the report generator is resilient to malformed/corrupted files and skips them gracefully."""
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    # Correct file
    valid_data = {
        "repo_name": "org/valid",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    with open(os.path.join(repos_dir, "valid.json"), "w") as f:
        json.dump(valid_data, f)
        
    # Completely corrupted JSON file
    with open(os.path.join(repos_dir, "corrupted.json"), "w") as f:
        f.write("{ invalid json: [ corrupted ")
        
    # File with missing schema keys
    incomplete_data = {
        "wrong_schema_keys": "some value"
    }
    with open(os.path.join(repos_dir, "incomplete.json"), "w") as f:
        json.dump(incomplete_data, f)
        
    # Ensure it compiles summary.html without throwing exceptions
    html_path = generate_html_report(output_dir)
    assert os.path.exists(html_path)
    
    # Only the valid repo should be present in summary.json
    summary_json_path = os.path.join(output_dir, "summary.json")
    with open(summary_json_path, "r") as f:
        results = json.load(f)
    assert len(results) == 1
    assert results[0]["repo_name"] == "org/valid"


def test_generate_html_report_organization_segmenting(tmp_path) -> None:
    """Verifies that generate_html_report handles organization parsing, sorting, and metadata inclusion correctly."""
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    # 1. Repo with explicit 'org'
    repo_explicit = {
        "repo_name": "project-a",
        "org": "explicit-org",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    
    # 2. Repo with implicit 'org' in repo_name (e.g. "implicit-org/project-b")
    repo_implicit_name = {
        "repo_name": "implicit-org/project-b",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    
    # 3. Repo with implicit 'org' in filename only (e.g. filename "filename-org_project-c.json")
    repo_implicit_file = {
        "repo_name": "project-c",
        "is_private": False,
        "scan_status": "clean",
        "findings": [],
        "error": ""
    }
    
    with open(os.path.join(repos_dir, "explicit-org_project-a.json"), "w") as f:
        json.dump(repo_explicit, f)
    with open(os.path.join(repos_dir, "implicit-org_project-b.json"), "w") as f:
        json.dump(repo_implicit_name, f)
    with open(os.path.join(repos_dir, "filename-org_project-c.json"), "w") as f:
        json.dump(repo_implicit_file, f)
        
    generate_html_report(output_dir)
    
    # Verify summary.json
    summary_json_path = os.path.join(output_dir, "summary.json")
    assert os.path.exists(summary_json_path)
    
    with open(summary_json_path, "r") as f:
        results = json.load(f)
        
    assert len(results) == 3
    
    # Check that organizations were parsed correctly
    # Sorted order of org names: "explicit-org", "filename-org", "implicit-org"
    
    assert results[0]["org"] == "explicit-org"
    assert results[0]["repo_name"] == "project-a"
    
    assert results[1]["org"] == "filename-org"
    assert results[1]["repo_name"] == "project-c"
    
    assert results[2]["org"] == "implicit-org"
    assert results[2]["repo_name"] == "implicit-org/project-b"

