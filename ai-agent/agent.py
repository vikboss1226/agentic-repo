"""
Simple agentic fixer.

Runs only when the build job fails. Reads the failed job's log once, and
asks OpenAI to list every issue it can find in that log (missing packages,
code errors, or anything it isn't confident about) in a single pass. Every
fix it's confident about - installing packages, rewriting files - is
applied together, committed to ONE new branch, and opened as ONE pull
request. It never commits to main directly.

Writes a single ai-agent-report.html summarizing everything found and done
on this run - not one report per fix.
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
FILE_PATTERN = re.compile(r"src/[\w./-]+\.(?:js|jsx|ts|tsx)")
MAX_FILES = 3  # don't blow up the prompt if the log mentions a lot of files

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
  <p class="subtitle">Workflow run #{run_id} - one pass, generated automatically by ai-agent/agent.py</p>

  <h2>Issues found</h2>
  {issue_cards}

  <h2>Outcome</h2>
  {outcome_card}

  <div class="footer">Any fixes here were pushed to a single new branch and opened as one pull request. Nothing was committed directly to main &mdash; review and merge it yourself.</div>
</div>
</body>
</html>
"""

CARD_TEMPLATE = """
  <div class="card">
    <div class="card-title">{title} <span class="pill {pill}">{pill}</span></div>
    <p>{detail}</p>
  </div>
"""


def render_report(issues, applied, failed, pr_url, pr_error):
    cards = ""
    if not issues:
        cards += CARD_TEMPLATE.format(title="No issues identified", pill="ok", detail="The AI did not find anything to diagnose in this log.")
    for issue in issues:
        itype = issue.get("type")
        if itype == "missing_package":
            cards += CARD_TEMPLATE.format(
                title=f"Missing package: <code>{issue.get('package', '?')}</code>",
                pill="bad",
                detail=issue.get("explanation", ""),
            )
        elif itype == "code_fix":
            cards += CARD_TEMPLATE.format(
                title=f"Code issue in <code>{issue.get('file', '?')}</code>",
                pill="bad",
                detail=issue.get("explanation", ""),
            )
        else:
            cards += CARD_TEMPLATE.format(
                title="Issue found, not confidently fixable",
                pill="warn",
                detail=issue.get("explanation", "No details given."),
            )

    if pr_url:
        outcome = CARD_TEMPLATE.format(
            title="Fixes applied, pull request opened",
            pill="ok",
            detail=f'{len(applied)} fix(es) committed on one branch: {"; ".join(applied)}. '
                   f'<a href="{pr_url}">Review the pull request</a> to merge.',
        )
    elif applied:
        outcome = CARD_TEMPLATE.format(
            title="Fixes pushed, but the pull request failed to open",
            pill="warn",
            detail=f'{len(applied)} fix(es) pushed to a branch ({"; ".join(applied)}), but opening the PR failed: {pr_error}',
        )
    else:
        outcome = CARD_TEMPLATE.format(
            title="No changes made",
            pill="warn",
            detail="Nothing was confidently fixable, so nothing was changed. Check the build log manually.",
        )

    if failed:
        outcome += CARD_TEMPLATE.format(
            title=f"{len(failed)} attempted fix(es) failed and were skipped",
            pill="bad",
            detail="; ".join(failed) + ". These need a human to look at directly.",
        )

    html = REPORT_TEMPLATE.format(run_id=RUN_ID, issue_cards=cards, outcome_card=outcome)
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
    return log_text[-8000:]  # keep the prompt bounded, only the tail matters


def find_mentioned_files(log_text):
    """All distinct real src/ files the log mentions, in order of appearance."""
    found = []
    for match in FILE_PATTERN.finditer(log_text):
        path = match.group(0)
        if path not in found and os.path.isfile(path):
            found.append(path)
        if len(found) >= MAX_FILES:
            break
    return found


def diagnose(log_text, files):
    """Ask the model to list every issue it can find and how to fix each one."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    context = f"Build log:\n{log_text}\n"
    for path in files:
        with open(path) as f:
            context += f"\nCurrent contents of {path}:\n{f.read()}\n"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a CI failure triage agent for a React app. Read the "
                    "build log and any file contents given, and list every issue "
                    "you can find - there may be more than one. Reply with strict "
                    "JSON only, in this shape:\n"
                    '{"issues": [\n'
                    '  {"type": "missing_package", "package": "<npm package name>", '
                    '"explanation": "<one sentence, human-readable>"},\n'
                    '  {"type": "code_fix", "file": "<exact path you were given>", '
                    '"fixed_code": "<the full corrected file contents>", '
                    '"explanation": "<one sentence, human-readable>"},\n'
                    '  {"type": "unknown", "explanation": "<why this one can\'t be fixed safely>"}\n'
                    "]}\n"
                    "Only use code_fix for a file whose current contents you were "
                    "actually given above - never invent a path. If you aren't "
                    "confident about a fix, report it as type unknown instead of "
                    "guessing. If there is nothing to report, return an empty list.\n\n"
                    "Important - distinguishing real failures from noise:\n"
                    "- Lines starting with 'npm warn deprecated' are routine notices "
                    "about transitive dependencies. They are never the cause of a "
                    "failure and must never be reported as missing_package. Ignore them.\n"
                    "- Only report missing_package when the log shows an actual "
                    "resolution failure for code this project imports directly, e.g. "
                    "'Cannot find module' or \"Module not found: Can't resolve\".\n"
                    "- An 'ERESOLVE'/peer dependency conflict is NOT a missing package "
                    "and must not be 'fixed' by installing the package named in the "
                    "conflict. These require a human to decide how to resolve the "
                    "version conflict - report these as type unknown."
                ),
            },
            {"role": "user", "content": context},
        ],
    )
    return json.loads(response.choices[0].message.content).get("issues", [])


def set_output(name, value):
    """Write a step output so later jobs (e.g. the approval-gated deploy) can read it."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")


def push_branch(branch, commit_message):
    subprocess.run(["git", "config", "user.name", "ai-agent"], check=True)
    subprocess.run(["git", "config", "user.email", "ai-agent@users.noreply.github.com"], check=True)
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", commit_message], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)


def open_pull_request(branch, title, body):
    """Returns (pr_url, error). Exactly one of the two is None."""
    payload = {"title": title, "head": branch, "base": "main", "body": body}
    resp = requests.post(f"https://api.github.com/repos/{REPO}/pulls", headers=HEADERS, json=payload, timeout=30)
    if not resp.ok:
        return None, f"{resp.status_code}: {resp.text}"
    return resp.json()["html_url"], None


def main():
    try:
        log_text = get_failed_log()
        files = find_mentioned_files(log_text)
        issues = diagnose(log_text, files)

        applied = []
        failed = []
        for issue in issues:
            itype = issue.get("type")
            try:
                if itype == "missing_package" and issue.get("package"):
                    package = issue["package"]
                    print(f"Installing missing package: {package}")
                    subprocess.run(["npm", "install", package, "--save"], check=True)
                    applied.append(f"installed {package}")

                elif itype == "code_fix" and issue.get("file") in files and issue.get("fixed_code"):
                    print(f"Applying code fix to {issue['file']}")
                    with open(issue["file"], "w") as f:
                        f.write(issue["fixed_code"])
                    applied.append(f"fixed {issue['file']}")
            except Exception as action_error:
                # One bad action shouldn't take down the fixes that did work.
                label = issue.get("package") or issue.get("file") or itype
                print(f"Action failed for {label}: {action_error}")
                failed.append(f"{label} ({action_error})")

        pr_url, pr_error = None, None
        branch = None
        if applied:
            branch = f"fix/ai-{int(time.time())}"
            push_branch(branch, "fix: AI agent - " + "; ".join(applied))
            body = (
                "Opened automatically by the AI agent after a failed build.\n\n"
                "Fixes in this PR:\n" + "\n".join(f"- {a}" for a in applied) +
                "\n\nPlease review before merging."
            )
            pr_url, pr_error = open_pull_request(branch, f"AI fix: {len(applied)} issue(s) from failed build", body)
            # Let the workflow know a fix branch exists, so it can offer a
            # manual-approval deploy of the fix without waiting for the PR to merge.
            set_output("branch", branch)

        render_report(issues, applied, failed, pr_url, pr_error)

    except Exception as exc:
        with open(REPORT_PATH, "w") as f:
            f.write(
                "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:2rem'>"
                "<h1>Agent error</h1>"
                f"<p>The agent hit an unexpected error before it could finish: <code>{exc}</code></p>"
                "<p>Check the workflow run's logs for the full traceback.</p>"
                "</body></html>"
            )
        raise


if __name__ == "__main__":
    main()
