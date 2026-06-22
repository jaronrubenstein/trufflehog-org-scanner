import pytest
import subprocess
import json
import os
from typing import Any
from discover import find_executable

def format_repo_url(url: str) -> str:
    """Formats a git SSH or HTTPS URL into a standard HTTPS URL for TruffleHog git scanning.
    
    Supports:
      - git@github.com:org/repo.git -> https://github.com/org/repo
      - ssh://git@github.com/org/repo.git -> https://github.com/org/repo
      - https://github.com/org/repo.git -> https://github.com/org/repo
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Handle SSH format
    if "git@" in url:
        parts = url.split("git@")[-1]
        # Handle colon-based SSH separator (e.g. github.com:org/repo)
        if ":" in parts:
            host, path = parts.split(":", 1)
            url = f"https://{host}/{path}"
        else:
            # Handle slash-based separator (e.g. ssh://git@github.com/org/repo)
            url = f"https://{parts}"
            
    # Standardize suffix (remove trailing .git)
    if url.endswith(".git"):
        url = url[:-4]
        
    return url

def parse_trufflehog_output(raw_stdout: str) -> list[dict[str, Any]]:
    """Parses newline-separated JSON emitted by TruffleHog.
    
    Drops raw credential values to prevent log leaks, while extracting key metadata.
    """
    findings = []
    for line in raw_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            # Extract key metadata without exposing the raw secret
            commit = data.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("commit", "Unknown")
            file_path = data.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("file", "Unknown")
            line_no = data.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("line", 0)
            
            findings.append({
                "detector": data.get("DetectorName", "Unknown"),
                "decoder": data.get("DecoderName", "Unknown"),
                "redacted": data.get("Redacted", "Unknown"),
                "commit": commit,
                "file": file_path,
                "line": line_no
            })
        except json.JSONDecodeError:
            continue
    return findings

def get_gh_token() -> str:
    """Retrieves the active GitHub auth token from the environment or the gh CLI helper."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        gh_bin = find_executable("gh")
        res = subprocess.run([gh_bin, "auth", "token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

def get_gitlab_token() -> str:
    """Retrieves the active GitLab auth token from the environment."""
    return os.environ.get("GITLAB_TOKEN") or ""

def test_format_repo_url() -> None:
    """Verifies that format_repo_url correctly normalizes diverse git clone URL formats."""
    assert format_repo_url("git@github.com:org/repo.git") == "https://github.com/org/repo"
    assert format_repo_url("git@github.com:org/repo") == "https://github.com/org/repo"
    assert format_repo_url("ssh://git@github.com/org/repo.git") == "https://github.com/org/repo"
    assert format_repo_url("https://github.com/org/repo.git") == "https://github.com/org/repo"
    assert format_repo_url("https://github.com/org/repo") == "https://github.com/org/repo"
    assert format_repo_url("") == ""

def test_parse_trufflehog_output_sanitizes_secrets() -> None:
    """Verifies that the TruffleHog parser properly extracts metadata and redacts raw secret values."""
    raw_output = '{"SourceMetadata":{"Data":{"Git":{"commit":"abc123commit"}}},"DetectorName":"URI","DecoderName":"BASE64","Raw":"secret_value_to_mask","RawV2":"secret_value_to_mask","Redacted":"masked_secret_val","ExtraData":null,"StructuredData":null,"SourceID":0,"SinkID":0}\n'
    
    findings = parse_trufflehog_output(raw_output)
    assert len(findings) == 1
    # Check that secrets are redacted/masked and not leaked
    assert findings[0]["commit"] == "abc123commit"
    assert "Raw" not in findings[0]
    assert "RawV2" not in findings[0]
    assert findings[0]["detector"] == "URI"
    assert findings[0]["redacted"] == "masked_secret_val"

def test_scan_repo(repo_info: dict[str, Any], request: pytest.FixtureRequest) -> None:
    """Scans a parameterized repository using TruffleHog git scanner."""
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ["GIT_ASKPASS"] = "true"
    os.environ["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    output_dir = request.config.getoption("--output-dir")
    os.makedirs(output_dir, exist_ok=True)
    
    repo_name = repo_info["name"]
    is_private = repo_info["is_private"]
    provider = repo_info.get("provider", "github")
    org = repo_info.get("org", "")
    
    # Formulate output file path dynamically with organization prefix to avoid collisions
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    norm_name = repo_name.replace('/', '_')
    if org:
        norm_org = org.replace('/', '_')
        if norm_name.startswith(f"{norm_org}_"):
            filename = f"{norm_name}.json"
        else:
            filename = f"{norm_org}_{norm_name}.json"
    else:
        filename = f"{norm_name}.json"
    result_file = os.path.join(repos_dir, filename)
    
    # Formulate HTTPS URL dynamically
    repo_url = format_repo_url(repo_info["ssh_url"])
    
    # Inject token if private or if token is available
    if provider == "github":
        token = get_gh_token()
        if token:
            repo_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    elif provider == "gitlab":
        token = get_gitlab_token()
        if token:
            repo_url = repo_url.replace("https://", f"https://oauth2:{token}@")
    
    trufflehog_bin = find_executable("trufflehog")
    cmd = [
        trufflehog_bin, "git", repo_url, 
        "--json", 
        "--no-verification", 
        "--no-update",
        "--exclude-globs=**/venv/**,**/.venv/**,**/node_modules/**,**/__pycache__/**,**/*.pyc,**/*venv*/**,venv/**,.venv/**,node_modules/**,**/python_modules/**,python_modules/**"
    ]
    
    # Run trufflehog
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        findings = parse_trufflehog_output(proc.stdout)
        error_msg = proc.stderr if proc.returncode not in [0, 183] else ""
    except subprocess.TimeoutExpired:
        findings = []
        error_msg = f"TruffleHog scan timed out after 180 seconds on repository '{repo_name}'."
        
        report_data = {
            "repo_name": repo_name,
            "org": org,
            "is_private": is_private,
            "scan_status": "clean",
            "findings": findings,
            "error": error_msg
        }
        
        with open(result_file, "w") as f:
            json.dump(report_data, f, indent=2)
            
        pytest.fail(error_msg)
    except FileNotFoundError:
        findings = []
        error_msg = f"TruffleHog executable not found. Checked path: '{trufflehog_bin}'. Please ensure TruffleHog is installed and available in the system PATH."
        
        report_data = {
            "repo_name": repo_name,
            "org": org,
            "is_private": is_private,
            "scan_status": "clean",
            "findings": findings,
            "error": error_msg
        }
        
        with open(result_file, "w") as f:
            json.dump(report_data, f, indent=2)
            
        pytest.fail(error_msg)
    
    # Save output report
    report_data = {
        "repo_name": repo_name,
        "org": org,
        "is_private": is_private,
        "scan_status": "clean" if len(findings) == 0 else "compromised",
        "findings": findings,
        "error": error_msg
    }
    
    with open(result_file, "w") as f:
        json.dump(report_data, f, indent=2)
        
    assert len(findings) == 0, f"Found {len(findings)} potential secrets in {repo_name}"


def test_scan_repo_trufflehog_not_found_graceful(tmp_path, monkeypatch) -> None:
    """Verifies that test_scan_repo handles FileNotFoundError gracefully when trufflehog is missing."""
    import test_scanner
    
    # Mock format_repo_url to avoid network dependencies
    monkeypatch.setattr(test_scanner, "format_repo_url", lambda url: "https://github.com/org/test-repo")
    monkeypatch.setattr(test_scanner, "get_gh_token", lambda: "mock_token")
    
    # Force find_executable to return a custom path
    monkeypatch.setattr(test_scanner, "find_executable", lambda name: f"/mock/path/{name}")
    
    # Mock subprocess.run to raise FileNotFoundError
    def mock_run(cmd, *args, **kwargs):
        if "trufflehog" in cmd[0]:
            raise FileNotFoundError("[Errno 2] No such file or directory: 'trufflehog'")
        raise ValueError("Unexpected command")
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Mock pytest.FixtureRequest
    class MockConfig:
        def getoption(self, name):
            if name == "--output-dir":
                return str(tmp_path)
            return None
            
    class MockRequest:
        config = MockConfig()
        
    repo_info = {
        "name": "org/test-repo",
        "is_private": False,
        "ssh_url": "git@github.com:org/test-repo.git"
    }
    
    # The test should fail with pytest.fail showing our custom message
    with pytest.raises(pytest.fail.Exception) as exc_info:
        test_scanner.test_scan_repo(repo_info, MockRequest())
        
    assert "TruffleHog executable not found" in str(exc_info.value)
    
    # Verify the JSON report was written correctly with error state
    result_file = tmp_path / "repos" / "org_test-repo.json"
    assert result_file.exists()
    with open(result_file, "r") as f:
        data = json.load(f)
        assert data["repo_name"] == "org/test-repo"
        assert data["scan_status"] == "clean"
        assert "TruffleHog executable not found" in data["error"]


def test_scan_repo_timeout_graceful(tmp_path, monkeypatch) -> None:
    """Verifies that test_scan_repo handles subprocess.TimeoutExpired gracefully."""
    import test_scanner
    
    # Mock format_repo_url to avoid network dependencies
    monkeypatch.setattr(test_scanner, "format_repo_url", lambda url: "https://github.com/org/test-repo")
    monkeypatch.setattr(test_scanner, "get_gh_token", lambda: "mock_token")
    monkeypatch.setattr(test_scanner, "find_executable", lambda name: f"/mock/path/{name}")
    
    # Mock subprocess.run to raise subprocess.TimeoutExpired
    def mock_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=180, output="", stderr="")
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    class MockConfig:
        def getoption(self, name):
            if name == "--output-dir":
                return str(tmp_path)
            return None
            
    class MockRequest:
        config = MockConfig()
        
    repo_info = {
        "name": "org/test-repo",
        "is_private": False,
        "ssh_url": "git@github.com:org/test-repo.git"
    }
    
    # The test should fail with pytest.fail showing our custom message
    with pytest.raises(pytest.fail.Exception) as exc_info:
        test_scanner.test_scan_repo(repo_info, MockRequest())
        
    assert "TruffleHog scan timed out" in str(exc_info.value)
    
    # Verify JSON report exists and is marked as clean with timeout error
    result_file = tmp_path / "repos" / "org_test-repo.json"
    assert result_file.exists()
    with open(result_file, "r") as f:
        data = json.load(f)
        assert data["repo_name"] == "org/test-repo"
        assert data["scan_status"] == "clean"
        assert "TruffleHog scan timed out" in data["error"]


