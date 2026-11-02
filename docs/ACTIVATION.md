# Finish P01 activation

## Current blockers confirmed by the owner

- No OpenAI API key is ready.
- No Slack incoming webhook is ready.
- No existing human-reviewed dataset is available.
- GitHub's branch-protection API returns HTTP 403 for this private repository:
  an eligible paid GitHub plan is required to enforce required merge checks.
  The repository stays private. No upgrade or public exposure is performed.

These are prerequisites, not passing validation results. The live quality workflow
writes **blocked**, fails the check, and explains missing configuration. It does
not silently substitute fixture results. API calls and Slack delivery remain off.

## Create and review genuine data

The supplied `data/authoring.csv` contains 64 blank rows. People write or lawfully
source de-identified emails, assign categories and ideal summaries, and explain
labels in the notes. Blank rows can remain unused if at least 50 complete cases
cover all four categories. Do not copy AI-authored fixtures into this file and
claim human authorship.

```sh
modelguard dataset-import --input data/authoring.csv \
  --output data/review-queue.json --version support-gold-v1 \
  --declare-human-authored
modelguard dataset-review --queue data/review-queue.json --reviewer 'ACTUAL HUMAN NAME'
modelguard dataset-freeze --queue data/review-queue.json --output data/golden.json
modelguard validate-dataset data/golden.json --require-gold
```

`dataset-review` requires an interactive terminal and an individual `approve`
decision after displaying each email, label, summary and rationale. It does not
have an approve-all or piped-input mode. Review hashes bind approvals to the case
contents: subsequent edits require another review. Human identity/authorship are
still declarations, not independent verification. Unit tests simulate review
records only in temporary fixtures; no real gold is shipped.

## Secure GitHub setup

In repository **Settings → Secrets and variables → Actions**, configure:

| Type | Name | Value |
|---|---|---|
| Secret | `OPENAI_API_KEY` | Your provider key |
| Secret | `SLACK_WEBHOOK_URL` | Your Slack incoming webhook, when delivery is wanted |
| Variable | `MODELGUARD_MODEL_ID` | Explicit supported classifier model ID |
| Variable | `MODELGUARD_JUDGE_MODEL_ID` | Explicit supported judge model ID |
| Variable | `MODELGUARD_PROMPT_PATH` | Prompt file, e.g. `prompts/v1.yaml` |
| Variable | `MODELGUARD_LIVE_ENABLED` | `true` only after data, models and costs are approved |
| Variable | `MODELGUARD_SEND_SLACK` | `true` only when actual Slack delivery is wanted |

Never paste credentials into chat, source files, reports or Git commands. GitHub's
secret-setting form or `gh secret set NAME --repo nymav/modelguard` accepts them
without embedding them in source. Setting variables is not performed implicitly.

Commit reviewed gold before evaluating a prompt PR. The workflow uses the base
commit's trusted evaluator and dependencies. Candidate code is never installed;
only bounded YAML/JSON Git blobs are read. Changing gold in the same PR blocks
comparison and requires a separately reviewed dataset/baseline update. Forks
receive no API secrets or PR-write operation and fail readiness instead of being
mistaken for a passing quality check. No `pull_request_target` execution is used.

## Live execution and persistence

On prompt PRs, the workflow evaluates base and candidate prompts on the same gold
with explicit model/judge IDs. Both runs share a maximum 800-attempt budget. At
100 cases, worst-case classification+judge retries consume that whole budget.
This is a request cap, not a dollar-cost guarantee. Approve provider spending
controls first. A manual default-branch run compares the current prompt to itself
in two independent calls and can measure repeat-run variability.

It writes HTML/JSON evidence, posts/updates its own bot-owned PR summary, and
fails critical/operational/blocked results. Cached trend history contains only
aggregate rates and identity fields, never emails, raw outputs or credentials.
Only manual default-branch runs save cache history; PRs cannot poison the
trusted history. Cache eviction can reset the trend window, which then reports
insufficient history. Report artifacts expire after seven days. Gold must be
appropriately de-identified because it is versioned in the private repository.

If your GitHub plan permits it, configure **Live quality evaluation** as a required
branch status check. On the currently observed plan, GitHub refuses this setting;
a failing workflow alone cannot guarantee merge prevention.

## Walkthrough

`docs/WALKTHROUGH.md` remains the recording script. A real end-to-end video showing
paid evaluation and an actual received Slack alert cannot be produced until the
missing data and service prerequisites are supplied. No simulated alert or
synthetic result is presented as a live deployment.
