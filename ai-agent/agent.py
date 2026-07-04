"""
Simple agentic fixer.

Runs only when the build job fails. Reads the failed job's log and asks
OpenAI to diagnose the failure. Depending on the diagnosis it either:
  - installs a missing npm package, or
  - rewrites the one source file the log points to, with a corrected
    version the model wrote, or
  - does nothing, if the model isn't confident it can fix it safely.

Either kind of fix lands on a new branch and a PR is opened for review.
The agent never commits to main directly.
"""

import json
import os
import re
import subprocess
import time

import requests
from openai import OpenAI

REPO = os.environ["GITHUB_REPOSITORY"]
RUN_ID = os.environ["GITHUB_RUN_ID"]
TOKEN = os.environ["GITHUB_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

# Matches source file paths the log might mention, e.g. "src/App.js".
FILE_PATTERN = re.compile(r"(src/[\w./-]+\.(?:js|jsx|ts|tsx))")


def get_failed_log():
    """Grab the log text for whichever job in this run failed."""
    jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/jobs"
    jobs = requests.get(jobs_url, headers=HEADERS, timeout=30).json()["jobs"]
    failed_job = next((j for j in jobs if j["conclusion"] == "failure"), jobs[0])

    logs_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{failed_job['id']}/logs"
    log_text = requests.get(logs_url, headers=HEADERS, timeout=60).text
    return log_text[-6000:]  # keep the prompt small, only the tail matters


def find_mentioned_file(log_text):
    """If the log points at a real src/ file, return its path so we can give
    the model the actual file contents instead of asking it to guess blind."""
    match = FILE_PATTERN.search(log_text)
    if match and os.path.isfile(match.group(1)):
        return match.group(1)
    return None


def diagnose(log_text, file_path, file_content):
    """Ask the model what's wrong and, if it can, how to fix it."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    context = f"Build log:\n{log_text}\n"
    if file_path:
        context += f"\nCurrent contents of {file_path}:\n{file_content}\n"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a CI failure triage agent for a React app. Read the "
                    "build log (and the source file, if given) and decide what "
                    "went wrong. Reply with strict JSON only, matching one of "
                    "these shapes:\n"
                    '{"type": "missing_package", "package": "<npm package name>"}\n'
                    '{"type": "code_fix", "file": "<the exact path you were given>", '
                    '"fixed_code": "<the full corrected file contents>"}\n'
                    '{"type": "unknown", "reason": "<short explanation>"}\n'
                    "Only return code_fix if you were given the file's current "
                    "contents and are confident about the exact fix. Otherwise "
                    "return unknown rather than guessing."
                ),
            },
            {"role": "user", "content": context},
        ],
    )
    return json.loads(response.choices[0].message.content)


def push_branch_and_pr(branch, commit_message, pr_title):
    subprocess.run(["git", "config", "user.name", "ai-agent"], check=True)
    subprocess.run(["git", "config", "user.email", "ai-agent@users.noreply.github.com"], check=True)
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", commit_message], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)

    payload = {
        "title": pr_title,
        "head": branch,
        "base": "main",
        "body": "Opened automatically by the AI agent after a failed build. Please review before merging.",
    }
    resp = requests.post(f"https://api.github.com/repos/{REPO}/pulls", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    print("Opened PR:", resp.json()["html_url"])


def main():
    log_text = get_failed_log()
    file_path = find_mentioned_file(log_text)
    file_content = open(file_path).read() if file_path else None

    diagnosis = diagnose(log_text, file_path, file_content)
    fix_type = diagnosis.get("type")

    if fix_type == "missing_package" and diagnosis.get("package"):
        package = diagnosis["package"]
        print(f"AI diagnosis: missing package '{package}'")
        subprocess.run(["npm", "install", package, "--save"], check=True)
        branch = f"fix/install-{package.replace('/', '-')}-{int(time.time())}"
        push_branch_and_pr(
            branch,
            f"fix: install missing dependency {package}",
            f"AI fix: install missing dependency {package}",
        )

    elif fix_type == "code_fix" and diagnosis.get("file") == file_path and diagnosis.get("fixed_code"):
        print(f"AI diagnosis: code fix in {file_path}")
        with open(file_path, "w") as f:
            f.write(diagnosis["fixed_code"])
        branch = f"fix/code-{int(time.time())}"
        push_branch_and_pr(
            branch,
            f"fix: AI-suggested fix for {file_path}",
            f"AI fix: correct error in {file_path}",
        )

    else:
        print("AI could not confidently diagnose or fix this failure:")
        print(diagnosis.get("reason", diagnosis))


if __name__ == "__main__":
    main()
