# Agentic React Flow

A React app deployed to AWS EC2 through GitHub Actions, with a Python AI
agent that wakes up when the pipeline fails, reads the failure, and either
fixes it or escalates it.

## Architecture

```
Developer push (master)
        │
        ▼
GitHub Actions: build-test-deploy
        │
   ┌────┴────┐
   success   failure
   │            │
   ▼            ▼
Deploy to    ai-agent-recovery job
EC2 + nginx  (Python, OpenAI Responses API)
             │
      read failed job logs
             │
      classify + reason
             │
      ┌──────┴──────┐
   code issue     infra issue
      │              │
   new branch     restart nginx/pm2,
   + PR (human    clean disk (done
   reviews it)    directly, no PR)
```

**The one rule the agent can never break:** it never commits to `master`.
Code-side fixes (`install_dependency`, `run_lint_fix`, `run_prettier`) always
push to a brand-new branch, and the orchestrator (`ai-agent/agent.py`) opens
a PR for it — even if the model forgets to ask for one — before it ever
finishes. Infra actions (`restart_nginx`, `restart_pm2`, `clean_disk`) are
safe and reversible, so those run immediately with no PR. This mirrors how
enterprise DevOps teams split "safe to automate" from "needs a human."

## How the agent reasons

`ai-agent/agent.py` uses OpenAI's **Responses API with tool calling**
(not a plain chat completion). The model is given a menu of tools — the
same ones listed in Phase 3/4 below — and decides for itself which to call
based on the log excerpt. A regex-based heuristic in `analyzer.py`
(missing module, syntax error, ESLint, formatting, nginx, pm2, disk full,
OOM) is passed along only as a *hint*; the model can override it. This is
what makes it an agent rather than a big if/else block: the reasoning step
picks the tool, the tool doesn't pick itself.

## Repo layout

```
agentic-react-flow/
├── src/, public/, package.json     # the React app (Create React App)
├── .github/workflows/deploy.yml    # CI/CD + failure-triggered recovery
├── ai-agent/
│   ├── agent.py         # orchestrator: OpenAI tool-calling loop
│   ├── analyzer.py       # log reader + heuristic error classifier
│   ├── fixer.py           # code-side fixes (branch + push only)
│   ├── github_api.py    # PRs, issues, workflow reruns
│   ├── deploy.py          # EC2 deploy + infra recovery + health check
│   └── notify.py          # optional Slack notification
└── requirements.txt
```

## Required GitHub secrets

| Secret | Purpose |
|---|---|
| `OPENAI_API_KEY` | Lets the agent call the OpenAI Responses API |
| `EC2_HOST` | Public IP/DNS of the EC2 instance |
| `EC2_USERNAME` | SSH user (typically `ubuntu`) |
| `EC2_SSH_KEY` | Private key (PEM contents) for SSH/rsync access |
| `SLACK_WEBHOOK_URL` | Optional — enables the Slack summary in `notify.py` |

`GITHUB_TOKEN` is provided automatically by Actions; the workflow's
`permissions:` block grants it `contents: write`, `pull-requests: write`,
`issues: write`, and `actions: write` so the agent can push branches, open
PRs/issues, and re-run the workflow.

## EC2 prerequisites (one-time)

1. Ubuntu instance with nginx installed, serving `/var/www/agentic-react-flow`.
2. Security group open on 22 (SSH) and 80 (HTTP).
3. The public half of `EC2_SSH_KEY` added to the instance's `~/.ssh/authorized_keys`.
4. If you also run a Node/Express process alongside the static build, install
   `pm2` so `restart_pm2` has something to manage — otherwise you can ignore
   that tool.

## Error categories the agent recognizes

| Signal in the log | What the agent does |
|---|---|
| Missing npm package | `install_dependency` → branch + PR |
| Syntax error | `open_manual_review_issue` (never auto-edits code) |
| ESLint error | `run_lint_fix` → branch + PR |
| Formatting | `run_prettier` → branch + PR |
| nginx failed | `restart_nginx` (direct) |
| PM2 crashed | `restart_pm2` (direct) |
| Disk full | `clean_disk` (direct) |
| Out of memory | `open_manual_review_issue` (needs a human sizing decision) |

## Suggested build order

1. React app + basic GitHub Actions CI (already done here).
2. Automatic deploy to EC2 on push — the `build-test-deploy` job.
3. `analyzer.py` reading real workflow logs.
4. Wire in OpenAI classification on top of the heuristic.
5. Safe fix engine, starting with `install_dependency` only.
6. `github_api.py` — PR creation and workflow rerun.
7. `deploy.py`'s infra recovery + health checks.

Build and confirm each step before adding the next — that's the fastest way
to trust what the agent is doing before it's making decisions unattended.

## Try it

Trigger the `install_dependency` path by importing a package in `src/App.js`
that isn't in `package.json` (e.g. `import axios from 'axios';` without
running `npm install axios`), then push to `master`. The build should fail,
`ai-agent-recovery` should run, and you should see a new `fix/install-axios-*`
branch and PR appear.

---

# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
