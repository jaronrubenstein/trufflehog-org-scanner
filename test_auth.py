import subprocess
import os

def get_gitlab_token():
    token = os.environ.get("GITLAB_TOKEN")
    if token:
        return token
    try:
        gh_bin = "bin/bin/glab"
        res = subprocess.run([gh_bin, "auth", "status", "-t"], capture_output=True, text=True, check=False)
        for line in res.stdout.splitlines() + res.stderr.splitlines():
            if "Token: " in line:
                return line.split("Token: ")[1].strip()
    except Exception:
        pass
    return ""

print(get_gitlab_token())
