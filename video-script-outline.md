# Video Outline: "Agentic AI in DevOps" (8–12 min, intermediate students)

Talking-points outline, not a word-for-word script — except the hook lines,
which are written out since the exact wording matters most in the first 15
seconds.

---

## 0:00–0:30 — Hook

Don't open with a definition. Open with a moment they don't expect.

Show, on screen, a split-screen or quick cut: a GitHub Actions build failing
(red X) immediately followed by a pull request appearing with a green
checkmark — before you say a word.

Then say something like:

> "Nobody on this team wrote this fix. Nobody even looked at the error yet.
> An AI read the failed build, figured out what broke, fixed it on its own
> branch, and opened a pull request for someone to review — while you were
> watching. That's what we're building today."

Why this works for an intermediate audience: they already know what a red
CI build feels like at 11pm. You're not teaching them CI/CD — you're
showing them CI/CD doing something they've never seen it do.

## 0:30–1:30 — Ground them in what they already know

Quick recap, fast, don't over-explain since they know this part:

- A normal pipeline is deterministic: checkout, install, test, build, deploy.
- When it fails, it just... stops. A human gets pinged, reads the log,
  figures out what's wrong, fixes it, pushes again.
- That triage step — read log, diagnose, decide a fix — has always
  required a human. That's the part about to change.

## 1:30–3:00 — What "agentic" actually means (not the buzzword version)

Give them a definition that distinguishes it from "just calling ChatGPT":

- A chatbot answers a question. An **agent** is handed a task, some tools,
  and permission to act — and it decides which tool to use based on what
  it observes.
- The loop is: **perceive → reason → act**. Perceive the failed log, reason
  about what's broken, act by calling a real tool (install a package,
  rewrite a file, open a PR).
- The important shift: the *decision* of what to do is made by the model,
  not hardcoded by a developer in an if/else chain. That's what makes it
  an agent instead of a script with extra steps.

Good analogy for this audience: "A linter tells you something's wrong. An
agent tells you something's wrong, writes the patch, and hands you a PR to
approve."

## 3:00–4:30 — Why this is a DevOps culture shift, not just a feature

This is the part worth spending real time on — it's the "so what."

- DevOps culture has always been about closing the loop between
  writing code and running it in production. Agentic AI closes a *second*
  loop: between something breaking and someone finding out why.
- The job of a DevOps engineer shifts from "the first responder who reads
  every log" to "the reviewer who approves or rejects what the agent already
  proposed." Less toil, more judgment.
- This is already showing up as a trend industry-wide — self-healing
  infra, AIOps, auto-remediation bots. What you're building today is a
  small, honest version of the same pattern real companies are adopting.

## 4:30–8:00 — Live demo (your actual repo)

Walk the actual `agentic-react-flow` pipeline live:

1. Show the repo structure quickly: `build` job → `success` or `ai-fix`
   depending on outcome.
2. Break it on purpose — remove `axios` from `package.json` while
   `CommentsTable.js` still imports it. Push.
3. Show the `build` job fail in the Actions tab.
4. Show `ai-fix` kick off automatically, and narrate what's happening while
   it runs: fetching the failed job's log, sending it to OpenAI, getting
   back a diagnosis.
5. Show the result: a new branch, a pull request, and — the payoff —
   `ai-agent-report.html` as a downloadable artifact explaining in plain
   language what it found and what it did.
6. Open the PR on screen. Point out: this is still just a proposal. Nothing
   touched `main`.

## 8:00–9:00 — The one rule worth teaching beyond the demo

This is the most transferable lesson in the whole video — make sure it
lands clearly:

- Not everything an agent touches should be treated the same way.
- Infra actions that are safe and reversible (like restarting a service)
  can run automatically.
- Anything that changes code always goes through a branch + pull request,
  reviewed by a human, before it merges.
- Say plainly: "The interesting engineering problem isn't 'can AI fix my
  code' — it's 'how do I let it try, without letting it break something I
  can't undo.'" That question is what separates a toy demo from something
  a real team would trust.

## 9:00–10:30 — Wrap-up and call to action

- Recap the loop in one sentence: fail → read → reason → act → PR → human
  review.
- Invite them to try it themselves: fork the repo, break the build in a
  new way (a typo in a component, a bad import), and watch what the agent
  does with a failure it hasn't seen before.
- Close on why this matters for them specifically: employers are starting
  to expect junior engineers to know how to work *alongside* automated
  agents, not just write pipelines by hand. This is a skill, not a novelty.

---

## Optional: on-screen text/lower-thirds to prep

- "Agentic AI: perceive → reason → act"
- "Still requires human review before merge"
- "This is not autocomplete. This is autonomy with a leash."
