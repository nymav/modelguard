# Module boundaries

| Module | Responsibility |
|---|---|
| `models` | Strict Pydantic inputs, predictions, observations, results and run contracts |
| `config` | Immutable PromptConfig dataclass, safe bounded YAML, canonical hashes and practical thresholds |
| `dataset` | Unique case/input enforcement, dataset/case identity, human-review release gate |
| `feature` | Reusable `classify_email(email, prompt, provider)` → typed Prediction + raw observation |
| `providers` | Scripted replay / bounded OpenAI Responses transport, refusal handling, request budget |
| `runner` | Async semaphore, classification and judge stages, per-case failure retention |
| `scoring` | Exact category match, summary policy, measured latency/tokens, coverage of telemetry |
| `statistics` | Exact McNemar, Wilson interval, nearest-rank percentiles |
| `comparison` | Compatibility gate, paired flips, per-category change, rolling drift |
| `store` | SQLite immutable run IDs and explicit baseline pointer |
| `reporting` | Escaped standalone HTML, JSON/Markdown artifacts, atomic per-file writes |
| `notifications` | Privacy-limited Slack payload; explicit separate delivery |
| `demo` | Controlled baseline → regression → recovery plus independently labelled slow-drift fixture |
| `authoring` | Blank CSV, human-authorship declaration, interactive case review, content-bound gold freeze |
| `ci` | Trusted-engine baseline/candidate Git blob evaluation and explicit blocked readiness state |
| `github` | Same-repository PR summary upsert with stale-head and bot-owner checks |
| `history` | Aggregate-only persistent CI trend history |
| `cli` | Offline/live separation, validation, artifact operations and CI exit codes |

Data flow: prompt + dataset → typed feature → raw observations → scores → immutable
run → compatible baseline comparison → HTML/JSON + prepared alert.

The classifier never receives a gold category or ideal summary. Only the judge
receives the reference summary, in a separate call. Replay is a fixture adapter;
it is not a local model, simulated latency or an accuracy benchmark.
