import argparse
import sys
import os
import json
import pytest
import subprocess
import shutil
from discover import discover_repos, discover_repo, find_executable
from report import generate_html_report

def verify_tools(provider: str = "github"):
    missing = []
    tools_to_check = ["gh", "trufflehog"] if provider == "github" else ["glab", "trufflehog"]
    for tool in tools_to_check:
        path = find_executable(tool)
        # If the path returned is just the name and shutil.which doesn't find it, it's missing
        if path == tool and not shutil.which(tool):
            missing.append(tool)
    if missing:
        print(f"Error: Missing required system dependencies: {', '.join(missing)}", file=sys.stderr)
        print("Please ensure both are installed and on your system PATH.", file=sys.stderr)
        sys.exit(1)

def remove_scan_results(output_dir: str, remove_org: str = None, remove_repo: str = None) -> bool:
    """Removes scan results for a given organization or repository from output_dir.
    
    Returns True if any files were deleted, False otherwise.
    """
    repos_dir = os.path.join(output_dir, "repos")
    if not os.path.exists(repos_dir):
        print(f"No scan results directory found at: {repos_dir}")
        return False
        
    deleted_files = []
    
    # Iterate over all JSON files in repos_dir
    for filename in os.listdir(repos_dir):
        if not filename.endswith(".json"):
            continue
            
        file_path = os.path.join(repos_dir, filename)
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception:
            # Skip unreadable/corrupt files
            continue
            
        repo_name = data.get("repo_name", "")
        # Fallback org extraction
        org = data.get("org")
        if not org:
            if "/" in repo_name:
                org = repo_name.split("/")[0]
            else:
                base = os.path.splitext(filename)[0]
                if "_" in base:
                    org = base.split("_")[0]
                else:
                    org = ""
                    
        should_delete = False
        
        if remove_org:
            # Case-insensitive match on org name
            if org.lower() == remove_org.lower():
                should_delete = True
            # Also fallback to match filename prefix
            elif filename.lower().startswith(remove_org.lower() + "_"):
                should_delete = True
                
        elif remove_repo:
            # Check if matching full repo name (e.g. org/repo) or just the repo suffix (e.g. repo)
            if repo_name.lower() == remove_repo.lower():
                should_delete = True
            elif "/" in remove_repo:
                # If remove_repo has a slash, match it directly against repo_name
                if repo_name.lower() == remove_repo.lower():
                    should_delete = True
            else:
                # If remove_repo is just the name (e.g. "repo1"), match exact name or name suffix
                if repo_name.lower() == remove_repo.lower() or repo_name.lower().endswith("/" + remove_repo.lower()):
                    should_delete = True
            # Fallback filename match (e.g. if the file is my-org_repo1.json and they asked to remove repo1)
            base_filename = os.path.splitext(filename)[0]
            if base_filename.lower() == remove_repo.lower().replace('/', '_'):
                should_delete = True
            elif base_filename.lower().endswith("_" + remove_repo.lower().replace('/', '_')):
                should_delete = True
                
        if should_delete:
            try:
                os.remove(file_path)
                deleted_files.append(filename)
            except Exception as e:
                print(f"Error deleting file {filename}: {e}", file=sys.stderr)
                
    if deleted_files:
        print(f"🗑️ Successfully removed {len(deleted_files)} scan file(s):")
        for f in deleted_files:
            print(f"  - {f}")
        return True
    else:
        print("ℹ️ No matching scan results found to remove.")
        return False


def main():
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ["GIT_ASKPASS"] = "true"
    os.environ["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    
    parser = argparse.ArgumentParser(description="TruffleHog organization secrets scanner.")
    parser.add_argument("--org", help="GitHub Organization name.")
    parser.add_argument("--repo", default="", help="Optional specific repository name to scan.")
    parser.add_argument("--output-dir", default="scans", help="Output reports directory.")
    parser.add_argument("--threads", default="auto", help="Number of parallel pytest threads.")
    parser.add_argument("--exclude", default="", help="Comma separated list of repo names to exclude.")
    parser.add_argument("--provider", default="github", choices=["github", "gitlab"], help="Version control provider.")
    parser.add_argument("--remove-org", help="Remove all scan results for the specified organization.")
    parser.add_argument("--remove-repo", help="Remove all scan results for the specified repository.")
    
    args = parser.parse_args()
    
    # Enforce that --org is provided if we are not performing a removal action
    if not args.remove_org and not args.remove_repo:
        if not args.org:
            parser.error("the following arguments are required: --org")
            
    # Handle removal action if specified
    if args.remove_org or args.remove_repo:
        remove_scan_results(args.output_dir, args.remove_org, args.remove_repo)
        print("📊 Updating dashboard...")
        html_report = generate_html_report(args.output_dir)
        print(f"✅ Dashboard updated! HTML Summary saved to: {html_report}")
        sys.exit(0)
        
    verify_tools(args.provider)

    if args.repo:
        print(f"🔍 Locating specific repository: {args.org}/{args.repo}")
        repo_data = discover_repo(args.org, args.repo, args.provider)
        if not repo_data:
            print(f"Repository {args.org}/{args.repo} not found or unable to fetch.", file=sys.stderr)
            sys.exit(1)
        repos = [repo_data]
    else:
        print(f"🔍 Locating repositories in organization: {args.org}")
        repos = discover_repos(args.org, args.provider)
        if not repos:
            print("No repositories found or unable to fetch.", file=sys.stderr)
            sys.exit(1)
            
        # Process exclusions
        exclude_list = [x.strip() for x in args.exclude.split(",") if x.strip()]
        repos = [r for r in repos if r["name"] not in exclude_list]
        print(f"📁 Discovered {len(repos)} repositories (excluding: {len(exclude_list)})")
    
    for repo in repos:
        repo["provider"] = args.provider
        repo["org"] = args.org

    # Save list to temporary file for pytest param parsing
    temp_file = os.path.join(args.output_dir, "active_repos.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(temp_file, "w") as f:
        json.dump(repos, f)
        
    if args.provider == "github":
        # Resolve gh auth token once and inject into environment for parallel workers
        try:
            gh_bin = find_executable("gh")
            res = subprocess.run([gh_bin, "auth", "token"], capture_output=True, text=True, check=True)
            token = res.stdout.strip()
            if token:
                os.environ["GITHUB_TOKEN"] = token
        except Exception:
            pass
    elif args.provider == "gitlab":
        pass
        
    # Execute pytest with pytest-xdist parallelization
    pytest_args = [
        "-v",
        "test_scanner.py",
        f"--repo-list-file={temp_file}",
        f"--output-dir={args.output_dir}",
    ]
    
    if args.threads != "1":
        pytest_args.extend(["-n", args.threads])
        
    print(f"🚀 Running parallel secrets scan via pytest...")
    exit_code = pytest.main(pytest_args)
    
    print("📊 Compiling results...")
    html_report = generate_html_report(args.output_dir)
    print(f"✅ Scanning complete! HTML Summary saved to: {html_report}")
    
    # Clean up temporary JSON config
    if os.path.exists(temp_file):
        os.remove(temp_file)

if __name__ == "__main__":
    main()
