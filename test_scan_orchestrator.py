import os
import sys
import json
from unittest.mock import patch, MagicMock
import pytest

def test_main_cli_orchestration(tmp_path):
    output_dir = str(tmp_path)
    
    # Mock discover_repos, pytest.main, generate_html_report, subprocess.run and verify_tools
    with patch("scan.discover_repos") as mock_discover, \
         patch("pytest.main") as mock_pytest, \
         patch("scan.generate_html_report") as mock_report, \
         patch("subprocess.run") as mock_run, \
         patch("scan.verify_tools") as mock_verify:
         
        # Import main inside the test to allow patching scan module before import
        from scan import main
        
        mock_discover.return_value = [
            {"name": "org/repo1", "ssh_url": "git@github.com:org/repo1.git", "is_private": True, "pushed_at": "123"}
        ]
        mock_pytest.return_value = 0
        mock_report.return_value = os.path.join(output_dir, "summary.html")
        mock_run.return_value = MagicMock(returncode=0)
        
        # Invoke main with argparse overrides
        test_args = ["scan.py", "--org", "my-org", "--output-dir", output_dir]
        with patch.object(sys, 'argv', test_args):
            main()
            
        mock_discover.assert_called_once_with("my-org", "github")
        mock_pytest.assert_called_once()
        mock_report.assert_called_once_with(output_dir)
        mock_verify.assert_called_once_with("github")

def test_main_cli_orchestration_gitlab(tmp_path):
    output_dir = str(tmp_path)

    with patch("scan.discover_repos") as mock_discover, \
         patch("pytest.main") as mock_pytest, \
         patch("scan.generate_html_report") as mock_report, \
         patch("subprocess.run") as mock_run, \
         patch("scan.verify_tools") as mock_verify:

        from scan import main

        mock_discover.return_value = [
            {"name": "org/repo1", "ssh_url": "git@gitlab.com:org/repo1.git", "is_private": True, "pushed_at": "123"}
        ]
        mock_pytest.return_value = 0
        mock_report.return_value = os.path.join(output_dir, "summary.html")
        mock_run.return_value = MagicMock(returncode=0)

        test_args = ["scan.py", "--org", "my-org", "--provider", "gitlab", "--output-dir", output_dir]
        with patch.object(sys, 'argv', test_args):
            main()

        mock_discover.assert_called_once_with("my-org", "gitlab")
        mock_pytest.assert_called_once()
        mock_report.assert_called_once_with(output_dir)
        mock_verify.assert_called_once_with("gitlab")


def test_main_cli_single_repo(tmp_path):
    output_dir = str(tmp_path)
    
    with patch("scan.discover_repo") as mock_discover_repo, \
         patch("pytest.main") as mock_pytest, \
         patch("scan.generate_html_report") as mock_report, \
         patch("subprocess.run") as mock_run, \
         patch("scan.verify_tools") as mock_verify:
         
        mock_discover_repo.return_value = {
            "name": "repo1", "ssh_url": "git@github.com:org/repo1.git", "is_private": True, "pushed_at": "123"
        }
        mock_pytest.return_value = 0
        mock_report.return_value = os.path.join(output_dir, "summary.html")
        mock_run.return_value = MagicMock(returncode=0)
        
        from scan import main
        
        test_args = ["scan.py", "--org", "my-org", "--repo", "repo1", "--output-dir", output_dir]
        with patch.object(sys, 'argv', test_args):
            main()
            
        mock_discover_repo.assert_called_once_with("my-org", "repo1", "github")
        mock_pytest.assert_called_once()
        mock_report.assert_called_once_with(output_dir)
        mock_verify.assert_called_once_with("github")


def test_main_cli_removal_org(tmp_path):
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    # Write a test scan JSON file
    scan_file = os.path.join(repos_dir, "my-org_repo1.json")
    with open(scan_file, "w") as f:
        json.dump({
            "repo_name": "repo1",
            "org": "my-org",
            "scan_status": "clean",
            "findings": [],
            "error": ""
        }, f)
        
    with patch("scan.generate_html_report") as mock_report:
        mock_report.return_value = os.path.join(output_dir, "summary.html")
        
        from scan import main
        test_args = ["scan.py", "--remove-org", "my-org", "--output-dir", output_dir]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
                
            assert exc_info.value.code == 0
            
        # File should have been removed
        assert not os.path.exists(scan_file)
        mock_report.assert_called_once_with(output_dir)


def test_main_cli_removal_repo(tmp_path):
    output_dir = str(tmp_path)
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    # Write a test scan JSON file
    scan_file = os.path.join(repos_dir, "my-org_repo1.json")
    with open(scan_file, "w") as f:
        json.dump({
            "repo_name": "my-org/repo1",
            "org": "my-org",
            "scan_status": "clean",
            "findings": [],
            "error": ""
        }, f)
        
    with patch("scan.generate_html_report") as mock_report:
        mock_report.return_value = os.path.join(output_dir, "summary.html")
        
        from scan import main
        test_args = ["scan.py", "--remove-repo", "my-org/repo1", "--output-dir", output_dir]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
                
            assert exc_info.value.code == 0
            
        # File should have been removed
        assert not os.path.exists(scan_file)
        mock_report.assert_called_once_with(output_dir)


