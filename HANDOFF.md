# SentinelAI-DB — Defense-focused v2

**Active branch:** `poc/defense-focused-v2`. The old general-purpose dataset (4,500 approved production records + 200 pilot records + associated metadata, reports, and drafts) is preserved under `archive/general-v1/` and in the historical branch `poc/security-classification-dataset`. **Do not include archive in the active dataset, duplicates scan, model training export or quota calculations.**

## Restart status
- Active records: **0 / 100,000**. First batch `0001`, IDs **1–500**; `progress.json` is reset.
- At least **60%** of accepted records must be substantively about missile-related systems, not just contain the word 'missile'. See `config/defense-domain-targets.json`.
- Other domains: unmanned aircraft 10%, radar/sensors/space 10%, cyber/communications/C2 10%, defense logistics 5%, general negative controls 5%.
- Four sensitivity labels remain balanced. Keep existing length quotas (short 5%, sentence 40%, paragraph 35%, long 20%) per label and checkpoint.
- Use fictional, non-operational examples and no real classified information or actionable weapons instructions.
- Maintain **primary_domain** in separate metadata, and checkpoint domain quotas and QA report for each batch.

## Important engineering migration
Legacy `sentinel_dataset/checkpoints.py` assumes the old pilot exists, and hard-codes the old branch. **Update verification, checkpoint and publishing code before accepting the first new batch.** The v2 branch must support an empty dataset, no legacy pilot, `next_id=1`, and a branch-name parameter; it must exclude `archive/general-v1/` unconditionally. Validate with `python -m sentinel_dataset verify`, `plan`, test suite, and a no-write dry run before publication.

## Parallel worker coordination
Only the publisher writes active `data/checkpoints`, `metadata/checkpoints`, `reports/checkpoints`, `progress.json`. Other workers author drafts in separate paths `drafts/work/` vs `drafts/chat/` or separate working branches. Reserve batch numbers with coordination; no silent resetting of the main branch or overwriting other workers.

## Historical safeguard
Do not delete `archive/general-v1/` and do not change `poc/security-classification-dataset`. Check `archive/general-v1/archive-manifest.json` for source commit and counts.
