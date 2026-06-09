import os
import sys
from unittest.mock import patch, MagicMock
import pytest

def test_main_cli_orchestration(tmp_path):
    output_dir = str(tmp_path)
    
    # Mock discover_repos, pytest.main and generate_html_report
    with patch("scan.discover_repos") as mock_discover, \
         patch("pytest.main") as mock_pytest, \
         patch("scan.generate_html_report") as mock_report, \
         patch("subprocess.run") as mock_run:
         
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
            
        mock_discover.assert_called_once_with("my-org")
        mock_pytest.assert_called_once()
        mock_report.assert_called_once_with(output_dir)

def test_main_cli_single_repo(tmp_path):
    output_dir = str(tmp_path)
    
    with patch("scan.discover_repo") as mock_discover_repo, \
         patch("pytest.main") as mock_pytest, \
         patch("scan.generate_html_report") as mock_report, \
         patch("subprocess.run") as mock_run:
         
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
            
        mock_discover_repo.assert_called_once_with("my-org", "repo1")
        mock_pytest.assert_called_once()
        mock_report.assert_called_once_with(output_dir)

