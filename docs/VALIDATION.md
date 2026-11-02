# Validation record — 3 November 2026

## Observed

- **74 unit/integration tests passed** on local Python 3.12.14.
- The same **74 tests passed inside the final Docker image**, source mounted
  read-only, networking disabled and nonroot execution.
- The packaged CLI demo passed inside that network-disabled image: regression
  critical, recovery pass, slow-drift warning, prepared Slack payload not delivered.
- Installed wheel/CLI on the host, generated the demo report and verified the
  regression/recovery/drift contracts.
- [GitHub CI passed](https://github.com/nymav/modelguard/actions/runs/41516882360)
  on implementation commit `c49673189414beeac92ed0558dd45413fad7fefe`: Python
  3.11/3.12/3.13 tests, wheel build, Docker build, offline container demo and suite.
- The actual generated HTML report was opened and inspected in the browser. It
  shows four regressed case pairs, per-category deltas, history and the explicit
  synthetic-fixture disclaimer. The exact paired p-value is 0.375; the critical
  gate is operational, not a claim of statistical significance.

## Controlled demo

| Quantity | Result |
|---|---:|
| Synthetic scenarios | 16 |
| Baseline pass rate | 13/16 = 81.25% |
| Candidate pass rate | 10/16 = 62.5% |
| Regressions / improvements | 4 / 1 |
| Operational drop | 18.75 percentage points → critical |
| Recovery pass rate | 15/16 = 93.75% → pass |
| Separately configured slow-drift fixture | Warning after seven runs; no individual step triggers |

These are scripted classifier outputs and rubric ratings. The software is what
is evaluated here; the fixture rates do not measure a real model or establish
human-verified ground truth. No test count is an accuracy estimate.

## Remaining release work

1. People must independently curate and review the guide's 50–100-case golden
   dataset. Human review fields are declarations, not proof of reviewer identity.
2. Run explicitly authorized live model and judge calls; calibrate ratings against
   humans and assess repeated-run variance, refusals and real provider telemetry.
3. Validate actual Slack delivery only when explicitly requested/configured.
4. Enable trusted live prompt CI, PR comments and required branch protection only
   after gold, secrets and a baseline are approved. Current PR checks are clearly
   labelled fixture contracts and publish run summaries/artifacts.
5. Record the walkthrough; only a truthful script is included.

Source budget/failure/identity checks improve operational safety. They do not
justify calling the build a deployed production service. See the source-step
matrix for complete scope accounting.
