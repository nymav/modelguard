# ModelGuard

ModelGuard compares a candidate LLM prompt/model with a pinned baseline on the
same support-email cases. It reports category accuracy, summary ratings, paired
regressions/improvements, observed latency and token use, and rolling degradation.
SQLite retains immutable runs; escaped HTML and JSON retain the evidence behind
CI exit codes. **0.1.0 is a locally validated pilot, not a live production deployment.**

## Run the included demonstration

Python 3.11+; use Python 3.12 locally.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/modelguard demo --output artifacts/demo
```

Open `artifacts/demo/regression/report.html`. The demo runs the actual evaluator
against 16 **synthetic system-test scenarios and scripted responses**. Its baseline
passes 13/16 cases, its candidate 10/16 (four regressions, one improvement), and a
recovery 15/16. These are designed fixture outcomes, not evidence that a real
model achieved those scores. Missing timings/tokens remain “not measured”. A
separate slow-drift fixture explicitly configures a 7 pp warning threshold because
its 16-case sample changes in 6.25 pp increments. Six individual steps pass while
the 7-run average falls below 93%. Default release thresholds remain 3 pp / 8 pp.

No API key, Slack delivery, PR comment or paid request is used by this demo.

## Evaluate a real prompt

First, people must independently curate and review 50–100 cases using
`data/golden.template.json` and `docs/DATASET_PROTOCOL.md`. The empty template
intentionally fails validation. There is **no approved golden dataset included**.
Do not simply rename the synthetic fixtures as human-reviewed ground truth.

```sh
modelguard validate-dataset data/golden.json --require-gold
modelguard live --prompt prompts/v1.yaml --dataset data/golden.json \
  --model YOUR_EXPLICIT_MODEL_ID --judge-model YOUR_EXPLICIT_JUDGE_ID \
  --allow-live --db .run/history.sqlite --output .run/baseline
```

Set `OPENAI_API_KEY` in your environment; never commit it. `--allow-live` explicitly
allows transmitting dataset emails to OpenAI and incurring provider charges.
Choose supported explicit model IDs; model availability is not assumed. Calls
use Responses strict structured outputs and `store: false`, with local Pydantic
validation and explicit refusal/incomplete-response handling. This integration
follows [official structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
Live provider compatibility has not been exercised with an actual API key.

Each live run requires human-reviewed gold; defaults are four concurrent cases,
100 cases maximum, 400 total request attempts, one retry, 30 seconds per attempt,
and 500 output tokens per classification/judge. The request budget must reserve
worst-case classification + judge retries before running. This limits requests
and output tokens, **not a guaranteed dollar cost**. Use explicit provider-side
spending controls. `--category-only` skips summary judging and changes the scoring
identity, preventing comparison with fully judged runs.

The judge receives the email, reference summary and candidate summary, not the
classification instructions. Its rubric rates relevance/faithfulness 1–5; a case
passes when its category matches and its score meets the configured minimum
(default 3). Judge outputs are measurements to calibrate with humans, not truth.

## Pin and compare a baseline

A run prints its ID and writes `run.json`. Promote a valid live gold run only after
reviewing its report and suitability. Baseline promotion is explicit:

```sh
modelguard baseline --db .run/history.sqlite --run BASELINE_RUN_ID --name production
modelguard compare --db .run/history.sqlite --baseline-name production \
  --candidate CANDIDATE_RUN_ID --output .run/comparison
```

Or pass `--baseline BASELINE_RUN_ID` to compare two explicit run IDs. Dataset hashes,
per-case hashes, provider mode, judge/rubric, summary-score policy and engine version
must match. Different prompt/model IDs are the intended experimental variable.
Changed datasets or judges require a new baseline rather than an apparently
improved aggregate. Existing run IDs cannot be overwritten.

Exit codes: **0** = completed/pass or warning, **2** = critical quality drop,
**3** = operational/configuration failure. A warning is visible but does not block
by default. In `compare`, provider/judge errors fail operationally; they cannot
silently reduce the denominator. Threshold environment variables are in
`.env.example`. Defaults are 3 pp warning / 8 pp critical. These are practical gates;
we separately report the exact paired McNemar p-value and descriptive Wilson
intervals. None establishes broad real-world accuracy from a small correlated set.

## Reports, history and alerting

`compare` writes `report.html`, `comparison.json`, `summary.md` and
`slack-payload.json`. The report includes regressed outputs side by side,
per-category deltas, all case outcomes, measurements, run identity and history.
History excludes future runs from drift calculations. Seven compatible runs are
required; insufficient history is not reported as a clean drift pass.

Slack payload creation is offline. Delivering one is a separate opt-in operation:

```sh
modelguard notify --payload .run/comparison/slack-payload.json
# Only when delivery is wanted and SLACK_WEBHOOK_URL is configured:
modelguard notify --payload .run/comparison/slack-payload.json --send-slack
```

Only official Slack incoming webhooks are accepted; redirects are refused. Alerts
contain counts and provenance, not raw emails. `MODELGUARD_REPORT_URL` optionally
adds an HTTPS report link. The demo saves a payload; it does not pretend an alert
was sent. GitHub Actions currently publishes a run summary and report artifacts.
PR comment writes and live prompt gating remain deployment work, explicitly
recorded in `docs/REQUIREMENTS.md`.

## Validation and container operation

```sh
python -m unittest discover -s tests -v
modelguard demo --output artifacts/demo
python scripts/assert_demo.py artifacts/demo/demo.json
docker build -t modelguard:0.1.0 .
docker run --rm --network none --read-only \
  --tmpfs /results:rw,uid=10001 --tmpfs /tmp modelguard:0.1.0
```

The image runs as UID 10001 and contains prompts, fixtures and the evaluator.
Provide a writable volume for real history and reports; keep credentials in runtime
environment variables. SQLite and generated files may contain sensitive emails or
model outputs. Apply your own retention policy; neither the demo nor CI uploads
live customer messages. CI tests Python 3.11/3.12/3.13 and a network-disabled Docker
run. `docs/VALIDATION.md` records observed checks rather than inferred readiness.

## Architecture decision

Scoring, operational failures and statistical inference are deliberately separate.
A 3 pp practical drop can matter even when a small sample has weak statistical
power. Conversely, significant change on a convenient fixture does not prove a
production regression. Dataset identity prevents silent benchmark replacement;
slow drift catches low-amplitude changes that per-run thresholds can miss. That
separation is more useful than a single impressive-looking accuracy number.

See `docs/MODULES.md`, `docs/DATASET_PROTOCOL.md` and `docs/REQUIREMENTS.md`.
MIT licensed. Scope is based on P01 of the user-provided BASWE project guide;
the guide itself is not distributed or relicensed.
