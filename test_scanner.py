import pytest
import subprocess
import json
import os
from typing import Any

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
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

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
    output_dir = request.config.getoption("--output-dir")
    os.makedirs(output_dir, exist_ok=True)
    
    repo_name = repo_info["name"]
    is_private = repo_info["is_private"]
    
    # Formulate HTTPS URL dynamically
    repo_url = format_repo_url(repo_info["ssh_url"])
    
    # Inject token if private or if token is available
    token = get_gh_token()
    if token:
        repo_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    
    cmd = ["trufflehog", "git", repo_url, "--json", "--no-verification"]
    
    # Run trufflehog
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    # Exit code of TruffleHog: 0 if no secrets, 183 if secrets found, or others on error
    findings = parse_trufflehog_output(proc.stdout)
    
    # Save output report
    repos_dir = os.path.join(output_dir, "repos")
    os.makedirs(repos_dir, exist_ok=True)
    result_file = os.path.join(repos_dir, f"{repo_name.replace('/', '_')}.json")
    
    report_data = {
        "repo_name": repo_name,
        "is_private": is_private,
        "scan_status": "clean" if len(findings) == 0 else "compromised",
        "findings": findings,
        "error": proc.stderr if proc.returncode not in [0, 183] else ""
    }
    
    with open(result_file, "w") as f:
        json.dump(report_data, f, indent=2)
        
    assert len(findings) == 0, f"Found {len(findings)} potential secrets in {repo_name}"
