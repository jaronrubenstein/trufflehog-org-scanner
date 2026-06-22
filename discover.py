import subprocess
import json
import sys
import os
import shutil
import urllib.parse
from typing import Any

def find_executable(name: str) -> str:
    """Finds the absolute path of an executable, checking common fallback paths if not on PATH."""
    path = shutil.which(name)
    if path:
        return path
    # Fallback paths for macOS / Linux
    fallback_paths = [
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
        f"/bin/{name}"
    ]
    for p in fallback_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return name

def discover_repos(org: str, provider: str = "github") -> list[dict[str, Any]]:
    """Fetches all repositories for the given organization."""
    if provider == "gitlab":
        glab_bin = find_executable("glab")
        cmd = [
            glab_bin, "api", f"groups/{org}/projects?include_subgroups=true&per_page=100", "--paginate"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            raw_data = res.stdout
            decoder = json.JSONDecoder()
            pos = 0
            results = []
            while pos < len(raw_data):
                while pos < len(raw_data) and raw_data[pos].isspace():
                    pos += 1
                if pos == len(raw_data):
                    break
                obj, end = decoder.raw_decode(raw_data, pos)
                results.extend(obj)
                pos = end

            repos = []
            for r in results:
                repos.append({
                    "name": r.get("path_with_namespace"),
                    "ssh_url": r.get("ssh_url_to_repo"),
                    "is_private": r.get("visibility") != "public",
                    "pushed_at": r.get("last_activity_at")
                })
            repos.sort(key=lambda x: x["pushed_at"] if x["pushed_at"] else "", reverse=True)
            return repos
        except (subprocess.CalledProcessError, OSError) as e:
            if isinstance(e, subprocess.CalledProcessError):
                print(f"Error fetching repos via glab: {e.stderr}", file=sys.stderr)
            else:
                print(f"Error executing glab binary (system error): {e}", file=sys.stderr)
            return []
    else:
        gh_bin = find_executable("gh")
        cmd = [
            gh_bin, "repo", "list", org,
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

def discover_repo(org: str, repo: str, provider: str = "github") -> dict[str, Any] | None:
    """Fetches metadata for a single specific repository under the given organization."""
    if provider == "gitlab":
        encoded_id = urllib.parse.quote(f"{org}/{repo}", safe="")
        glab_bin = find_executable("glab")
        cmd = [
            glab_bin, "api", f"projects/{encoded_id}"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            r = json.loads(res.stdout)
            return {
                "name": r.get("path_with_namespace"),
                "ssh_url": r.get("ssh_url_to_repo"),
                "is_private": r.get("visibility") != "public",
                "pushed_at": r.get("last_activity_at")
            }
        except (subprocess.CalledProcessError, OSError) as e:
            if isinstance(e, subprocess.CalledProcessError):
                print(f"Error fetching repo {org}/{repo} via glab: {e.stderr}", file=sys.stderr)
            else:
                print(f"Error executing glab binary (system error): {e}", file=sys.stderr)
                return None
    else:
        if "/" in repo:
            repo = repo.split("/")[-1]
        gh_bin = find_executable("gh")
        cmd = [
            gh_bin, "repo", "view", f"{org}/{repo}",
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


