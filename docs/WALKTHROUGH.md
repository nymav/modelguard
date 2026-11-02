# Three-minute walkthrough script (not a recorded video)

- 0:00–0:25: Explain the feature under test: email → category + summary. Show prompt
  versions and the warning that the included dataset is synthetic software-test data.
- 0:25–1:00: Run `modelguard demo`. Show baseline 13/16 and candidate 10/16. Explain
  the four pass-to-fail flips and one improvement; don't present them as live quality.
- 1:00–1:40: Open `artifacts/demo/regression/report.html`. Inspect a regressed case,
  category deltas, paired p-value and the deliberately separate practical gate.
- 1:40–2:10: Open recovery and slow-drift artifacts. Show recovery 15/16 and the
  configured 7-run test where individual changes pass but the average triggers.
- 2:10–2:35: Show prepared Slack JSON, labelled “not sent”. Explain actual delivery
  needs explicit configuration; don't stage a fake received alert.
- 2:35–3:00: Show the human-reviewed dataset protocol, explicit live model/judge
  IDs, request cap, CI exit codes and the remaining live-validation requirements.

## Actual offline deliverable — 0.2.0

A three-minute 1920×1080 captioned MP4 was rendered from actual CLI output,
regression/recovery report screenshots, the controlled drift fixture and the
real private PR's blocked bot comment. It has no audio and is not a Loom upload.
The video explicitly identifies scripted outputs, absent human gold, zero paid
calls and no delivered Slack alert. The live demonstration remains pending the
owner-supplied prerequisites.

Reproducible script: `scripts/render_walkthrough.py`; dev-only dependencies are
Pillow and imageio-ffmpeg. Browser screenshot assets and a chapter manifest are
under `artifacts/walkthrough-assets/`. The exported video is delivered separately
as `ModelGuard_P01_Offline_Walkthrough.mp4`.
