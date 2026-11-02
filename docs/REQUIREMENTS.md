# P01 requirements and observed scope

| Source step | Implementation / remaining work |
|---|---|
| F01-T01 support classifier | `feature.classify_email`, four categories and typed summary |
| F01-T02 versioned prompts | Three bounded YAML versions, timezone/version/content identity |
| F01-T03 typed contract | Frozen PromptConfig dataclass plus Pydantic contracts |
| F02-T01 human-curated 50–100 gold cases | **Pending actual human data.** Blank 64-row CSV plus import, individual interactive review and freeze commands implemented; no manufactured gold |
| F02-T02 challenging inputs | Synthetic short, mixed-language, typo, sarcasm, ambiguity and injection fixtures; human review pending |
| F02-T03 versioned case data | Stable IDs, notes, difficulty, hashes, content-bound review decisions and frozen export |
| F03-T01 async runner | Bounded async runner, per-case observations, live/replay separation |
| F03-T02 scoring | Category match, separate judge 1–5, observed latency and tokens; paid provider validation pending |
| F03-T03 paired comparison | Rates, category deltas, exact regressed/improved IDs, incompatible-run refusal |
| F03-T04 thresholds / significance | Configurable 3/8 pp gates plus exact McNemar; explicitly separate concepts |
| F04-T01 report | Escaped HTML, old/new outputs, history chart, metadata and JSON |
| F04-T02 Slack | Payload + validated opt-in sender; live delivery not performed |
| F04-T03 slow drift | Seven-run window, insufficient-history/error states, scripted gradual-decline check |
| F05-T01 PR integration | Prompt-path fixture check + run summary + artifacts. Live workflow and guarded PR comment upsert implemented; real provider/gold validation pending. GitHub rejects private branch protection on the observed plan (403) |
| F05-T02 Docker | Nonroot pinned Python image, explicit runtime credentials/budgets, offline validation |
| F05-T03 onboarding docs | README plus modules, data protocol and operations/limits |
| F06-T01 Loom walkthrough | Three-minute captioned offline MP4 produced from real execution evidence; live model/received-Slack Loom recording still awaits prerequisites |
| F06-T02 design explanation | README architecture decision describes dataset identity, practical gates and drift |

“Implemented” means code exists and its bounded tests are recorded separately;
it does not certify a paid service, human-reviewed data, live alert delivery or
real-world model quality. Optional RAGAS/DeepEval is not added: this narrow typed
classification task uses directly inspectable scoring and a separately versioned
judge rubric rather than an opaque framework aggregate.
