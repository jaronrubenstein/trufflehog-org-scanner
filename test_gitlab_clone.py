import subprocess
import os

os.environ["GIT_TERMINAL_PROMPT"] = "0"
token = os.environ.get("GITLAB_TOKEN", "mock")

# We will just verify if the clone command throws an authentication error using oauth2 vs nothing.
print(subprocess.run(["git", "ls-remote", f"https://oauth2:{token}@gitlab.com/gitlab-org/gitlab.git"], capture_output=True, text=True).returncode == 0)
print(subprocess.run(["git", "ls-remote", f"https://gitlab-ci-token:{token}@gitlab.com/gitlab-org/gitlab.git"], capture_output=True, text=True).returncode == 0)
