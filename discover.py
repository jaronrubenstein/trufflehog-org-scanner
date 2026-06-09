import subprocess
import json
import sys
from typing import Any

def discover_repos(org: str) -> list[dict[str, Any]]:
    """Fetches all repositories for the given GitHub organization."""
    cmd = [
        "gh", "repo", "list", org,
        "--json", "name,sshUrl,isPrivate,pushedAt",
        "--limit", "1000"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_repos = json.loads(res.stdout)
        
        # Format keys for uniform internal usage
        repos = []
        for r in raw_repos:
            repos.append({
                "name": r["name"],
                "ssh_url": r["sshUrl"],
                "is_private": r["isPrivate"],
                "pushed_at": r["pushedAt"]
            })
        # Sort by updatedAt/pushedAt desc
        repos.sort(key=lambda x: x["pushed_at"], reverse=True)
        return repos
    except (subprocess.CalledProcessError, OSError) as e:
        if isinstance(e, subprocess.CalledProcessError):
            print(f"Error fetching repos via gh: {e.stderr}", file=sys.stderr)
        else:
            print(f"Error executing gh binary (system error): {e}", file=sys.stderr)
        return []

def discover_repo(org: str, repo: str) -> dict[str, Any] | None:
    """Fetches metadata for a single specific repository under the given organization."""
    if "/" in repo:
        repo = repo.split("/")[-1]
    cmd = [
        "gh", "repo", "view", f"{org}/{repo}",
        "--json", "name,sshUrl,isPrivate,pushedAt"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        r = json.loads(res.stdout)
        return {
            "name": r["name"],
            "ssh_url": r["sshUrl"],
            "is_private": r["isPrivate"],
            "pushed_at": r["pushedAt"]
        }
    except (subprocess.CalledProcessError, OSError) as e:
        if isinstance(e, subprocess.CalledProcessError):
            print(f"Error fetching repo {org}/{repo} via gh: {e.stderr}", file=sys.stderr)
        else:
            print(f"Error executing gh binary (system error): {e}", file=sys.stderr)
        return None

