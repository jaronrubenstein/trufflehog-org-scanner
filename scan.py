import argparse
import sys
import os
import json
import pytest
import subprocess
from discover import discover_repos, discover_repo
from report import generate_html_report

def verify_tools():
    missing = []
    for tool in ["gh", "trufflehog"]:
        try:
            subprocess.run(["which", tool], capture_output=True, check=True)
        except Exception:
            missing.append(tool)
    if missing:
        print(f"Error: Missing required system dependencies: {', '.join(missing)}", file=sys.stderr)
        print("Please ensure both are installed and on your system PATH.", file=sys.stderr)
        sys.exit(1)

def main():
    verify_tools()
    
    parser = argparse.ArgumentParser(description="TruffleHog organization secrets scanner.")
    parser.add_argument("--org", required=True, help="GitHub Organization name.")
    parser.add_argument("--repo", default="", help="Optional specific repository name to scan.")
    parser.add_argument("--output-dir", default="scans", help="Output reports directory.")
    parser.add_argument("--threads", default="auto", help="Number of parallel pytest threads.")
    parser.add_argument("--exclude", default="", help="Comma separated list of repo names to exclude.")
    
    args = parser.parse_args()
    
    if args.repo:
        print(f"🔍 Locating specific repository: {args.org}/{args.repo}")
        repo_data = discover_repo(args.org, args.repo)
        if not repo_data:
            print(f"Repository {args.org}/{args.repo} not found or unable to fetch.", file=sys.stderr)
            sys.exit(1)
        repos = [repo_data]
    else:
        print(f"🔍 Locating repositories in organization: {args.org}")
        repos = discover_repos(args.org)
        if not repos:
            print("No repositories found or unable to fetch.", file=sys.stderr)
            sys.exit(1)
            
        # Process exclusions
        exclude_list = [x.strip() for x in args.exclude.split(",") if x.strip()]
        repos = [r for r in repos if r["name"] not in exclude_list]
        print(f"📁 Discovered {len(repos)} repositories (excluding: {len(exclude_list)})")
    
    # Save list to temporary file for pytest param parsing
    temp_file = os.path.join(args.output_dir, "active_repos.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(temp_file, "w") as f:
        json.dump(repos, f)
        
    # Resolve gh auth token once and inject into environment for parallel workers
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        token = res.stdout.strip()
        if token:
            os.environ["GITHUB_TOKEN"] = token
    except Exception:
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
