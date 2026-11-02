# Golden data protocol — human work remains required

The guide explicitly requires 50–100 independently human-curated, verified cases.
No such data is asserted to exist in this repository. AI-authored fixture emails,
labels, ideal summaries and scripted ratings reside only under `fixtures/`.

1. Write or lawfully obtain de-identified support emails. Do not include account
   secrets, payment credentials, sensitive identifiers or unconsented customer data.
2. People assign one primary category and a faithful ideal summary, with a rationale
   in `notes`. Resolve mixed billing/account cases according to a written intent
   policy; record genuine uncertainty instead of hiding ambiguous cases.
3. Include all four categories, short/typo/mixed-language/sarcastic examples, and
   deliberate prompt-injection attempts as untrusted email content.
4. Record `reviewed_by` and timezone-aware ISO `reviewed_at` on every case. Use an
   independent second reviewer where possible. These fields are declarations, not
   cryptographic proof that review happened; the programme cannot verify a person's
   identity. Don't use an AI identity or invented reviewer.
5. Preserve stable case IDs, and split development from a reserved release set
   before tuning prompts. Avoid duplicate or near-duplicate messages. Exact
   casefolded/whitespace duplicates are rejected; near-duplicates need human review.
6. Pilot the judge rubric against human ratings. Judge-model agreement, reliability
   across repeated runs and category/summary failure modes need calibration. Do not
   claim a judge score is independent human ground truth.
7. Freeze data with a version and content hash. Changes invalidate baseline
   comparability. Keep a held-out set inaccessible to prompt tuning; aggregate
   scores from the included fixtures cannot substitute for it.

Case schema:

```json
{
  "id": "stable-case-id",
  "email": "Human-authored or de-identified customer text",
  "expected": {"category": "billing", "summary": "Human-verified main request."},
  "difficulty": "normal",
  "notes": "Reason for the label and why this case is useful",
  "reviewed_by": "Actual reviewer identity",
  "reviewed_at": "2026-11-03T10:00:00+05:30"
}
```

An empty invalid template is provided rather than fabricating 50 human-reviewed
cases. Actual production effectiveness remains unevaluated until this work and
explicit live runs are completed.
