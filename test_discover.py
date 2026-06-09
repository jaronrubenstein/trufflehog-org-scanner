import pytest
from unittest.mock import patch, MagicMock
import subprocess
from discover import discover_repos, discover_repo

def test_discover_repos_success():
    mock_json_output = '[{"name": "repo1", "sshUrl": "git@github.com:org/repo1.git", "isPrivate": true, "pushedAt": "2026-06-05T00:00:00Z"}]'
    
    with patch("subprocess.run") as mock_run:
        # Mock gh repo list execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_json_output
        mock_run.return_value = mock_proc
        
        repos = discover_repos("my-org")
        assert len(repos) == 1
        assert repos[0]["name"] == "repo1"
        assert repos[0]["is_private"] is True

def test_discover_repos_failure():
    with patch("subprocess.run") as mock_run:
        # Mock gh repo list execution failure
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="gh repo list my-org --json name,sshUrl,isPrivate,pushedAt --limit 1000",
            stderr="Could not find organization"
        )
        
        repos = discover_repos("my-org")
        assert repos == []

def test_discover_repos_os_error():
    with patch("subprocess.run") as mock_run:
        # Mock OSError (e.g. gh binary not found)
        mock_run.side_effect = OSError("No such file or directory")
        
        repos = discover_repos("my-org")
        assert repos == []

def test_discover_repo_success():
    mock_json_output = '{"name": "repo1", "sshUrl": "git@github.com:org/repo1.git", "isPrivate": true, "pushedAt": "2026-06-05T00:00:00Z"}'
    
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_json_output
        mock_run.return_value = mock_proc
        
        repo = discover_repo("my-org", "repo1")
        assert repo is not None
        assert repo["name"] == "repo1"
        assert repo["is_private"] is True

def test_discover_repo_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="gh repo view my-org/repo1 --json name,sshUrl,isPrivate,pushedAt",
            stderr="Could not find repository"
        )
        
        repo = discover_repo("my-org", "repo1")
        assert repo is None

def test_discover_repo_os_error():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = OSError("No such file or directory")
        
        repo = discover_repo("my-org", "repo1")
        assert repo is None


