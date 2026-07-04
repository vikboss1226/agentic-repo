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

It also writes ai-agent-report.html describing what it found and did, so
the workflow can upload it as a downloadable artifact on every run.
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

REPORT_PATH = "ai-agent-report.html"

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Agentic React Flow - CI Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#fff; color:#1a1a1a; padding:2.5rem 1.5rem; }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 0.25rem; }}
  .subtitle {{ color:#5f6368; margin:0 0 2rem; font-size:0.9rem; }}
  h2 {{ font-size:1.05rem; margin:2rem 0 0.8rem; padding-bottom:0.4rem; border-bottom:1px solid #e3e3e3; }}
  .card {{ border:1px solid #e3e3e3; border-radius:10px; padding:1rem 1.2rem; margin-bottom:0.9rem; background:#fafafa; }}
  .card-title {{ font-weight:600; margin:0 0 0.4rem; display:flex; align-items:center; gap:0.6rem; }}
  .card p {{ margin:0.3rem 0; font-size:0.93rem; }}
  code {{ background:#eef0f2; padding:0.1rem 0.35rem; border-radius:4px; font-size:0.87em; }}
  .pill {{ display:inline-block; font-size:0.7rem; font-weight:600; padding:0.15rem 0.55rem; border-radius:999px; text-transform:uppercase; }}
  .pill.ok {{ background:#e8f5e9; color:#1b6b31; }}
  .pill.warn {{ background:#fff8e1; color:#8a6100; }}
  .pill.bad {{ background:#fdecea; color:#9a1c1c; }}
  .footer {{ margin-top:2.5rem; padding-top:1rem; border-top:1px solid #e3e3e3; font-size:0.8rem; color:#5f6368; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Agentic React Flow - CI Report</h1>
  <p class="subtitle">Workflow run #{run_id} - generated automatically by ai-agent/agent.py</p>

  <h2>What went wrong</h2>
  <div class="card">
    <div class="card-title">{diagnosis_title} <span class="pill {diagnosis_pill}">{diagnosis_pill}</span></div>
    <p>{diagnosis_detail}</p>
  </div>

  <h2>What the agent did</h2>
  <div class="card">
    <div class="card-title">{action_title} <span class="pill {action_pill}">{action_pill}</span></div>
    <p>{action_detail}</p>
  </div>

  <div class="footer">Any fix here was pushed to a new branch and opened as a pull request. Nothing was committed directly to main &mdash; review and merge it yourself.</div>
</div>
</body>
</html>
"""


def write_report(diagnosis_title, diagnosis_detail, diagnosis_pill, action_title, action_detail, action_pill):
    html = REPORT_TEMPLATE.format(
        run_id=RUN_ID,
        diagnosis_title=diagnosis_title,
        diagnosis_detail=diagnosis_detail,
        diagnosis_pill=diagnosis_pill,
        action_title=action_title,
        action_detail=action_detail,
        action_pill=action_pill,
    )
    with open(REPORT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {REPORT_PATH}")


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


def push_branch(branch, commit_message):
    subprocess.run(["git", "config", "user.name", "ai-agent"], check=True)
    subprocess.run(["git", "config", "user.email", "ai-agent@users.noreply.github.com"], check=True)
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", commit_message], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)


def open_pull_request(branch, title):
    """Returns (pr_url, error). Exactly one of the two is None."""
    payload = {
        "title": title,
        "head": branch,
        "base": "main",
        "body": "Opened automatically by the AI agent after a failed build. Please review before merging.",
    }
    resp = requests.post(f"https://api.github.com/repos/{REPO}/pulls", headers=HEADERS, json=payload, timeout=30)
    if not resp.ok:
        return None, f"{resp.status_code}: {resp.text}"
    return resp.json()["html_url"], None


def main():
    try:
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
            push_branch(branch, f"fix: install missing dependency {package}")
            pr_url, error = open_pull_request(branch, f"AI fix: install missing dependency {package}")

            if pr_url:
                write_report(
                    "Missing npm package",
                    f"<code>{package}</code> is imported in the code but was not listed in <code>package.json</code>.",
                    "bad",
                    "Installed the package and opened a pull request",
                    f'Ran <code>npm install {package}</code> on branch <code>{branch}</code> and opened '
                    f'<a href="{pr_url}">this pull request</a> for review.',
                    "ok",
                )
            else:
                write_report(
                    "Missing npm package",
                    f"<code>{package}</code> is imported in the code but was not listed in <code>package.json</code>.",
                    "bad",
                    "Fix branch pushed, but the pull request failed to open",
                    f"Branch <code>{branch}</code> was pushed with the fix, but opening the pull request failed: {error}",
                    "warn",
                )

        elif fix_type == "code_fix" and diagnosis.get("file") == file_path and diagnosis.get("fixed_code"):
            print(f"AI diagnosis: code fix in {file_path}")
            with open(file_path, "w") as f:
                f.write(diagnosis["fixed_code"])
            branch = f"fix/code-{int(time.time())}"
            push_branch(branch, f"fix: AI-suggested fix for {file_path}")
            pr_url, error = open_pull_request(branch, f"AI fix: correct error in {file_path}")

            if pr_url:
                write_report(
                    "Code error",
                    f"The build log pointed at <code>{file_path}</code> as the source of the failure.",
                    "bad",
                    "Rewrote the file and opened a pull request",
                    f'Replaced <code>{file_path}</code> with a corrected version on branch <code>{branch}</code> '
                    f'and opened <a href="{pr_url}">this pull request</a> for review.',
                    "ok",
                )
            else:
                write_report(
                    "Code error",
                    f"The build log pointed at <code>{file_path}</code> as the source of the failure.",
                    "bad",
                    "Fix branch pushed, but the pull request failed to open",
                    f"Branch <code>{branch}</code> was pushed with the fix, but opening the pull request failed: {error}",
                    "warn",
                )

        else:
            reason = diagnosis.get("reason", "The model did not return a usable diagnosis.")
            print("AI could not confidently diagnose or fix this failure:", reason)
            write_report(
                "Could not confidently diagnose the failure",
                reason,
                "warn",
                "No changes made",
                "The agent did not modify anything because it wasn't confident about a safe fix. Check the build log manually.",
                "warn",
            )

    except Exception as exc:
        write_report(
            "Unexpected error while running the agent",
            str(exc),
            "bad",
            "No changes made",
            "The agent hit an unexpected error before it could finish. Check the workflow run's logs for the full traceback.",
            "bad",
        )
        raise


if __name__ == "__main__":
    main()
