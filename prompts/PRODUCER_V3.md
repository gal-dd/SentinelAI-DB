# Chat Producer v3 — ייצור טיוטות איכותיות

**Repository:** `gal-dd/SentinelAI-DB`  
**Branch:** `producer/chat-defense-v2`  
**Owner:** Chat Producer; no production writes.

## Before creating anything

1. Read the current GitHub state, `progress.json`, applicable policy, `config/scenarios.json`, and `config/defense-domain-targets.json`.
2. Confirm that the batch path does not already contain candidates. Never regenerate, delete, or overwrite an owned draft without an explicit reason.
3. Derive the **current** label-length quotas from `python -m sentinel_dataset plan`, not from a hard-coded matrix.
4. Exclude `archive/general-v1` from every active comparison.
5. Respect branch ownership: only the production integrator touches checkpoint artifacts, production IDs, or `progress.json`.

## Quality-first production

- Close the remediation queues in existing batches before creating a later batch. Keep corrected records and their evidence in the owner draft.
- Before expanding a cohort, vary the actor, what happened, the concrete consequence and the document format. After each cohort, inspect full repeated sentences and paragraph groups against earlier cohorts. If a group shares a decisive fact, replace that fact with a genuinely different scenario-supported event.

- Create actual distinct fictional facts, scenarios, document types and consequences; not one template repeated with different nouns.
- Every record must carry sufficient evidence to justify its label. Security jargon alone never establishes sensitivity.
- The topic must substantially match `primary_domain`; missile mention alone is insufficient.
- Maintain the six-domain composition (300/50/50/50/25/25 for 500), four balanced classes and current dynamically calculated length allocations.
- Keep content non-operational: no actual classified data or practical dangerous-system details.
- Prioritize convincing Hebrew grammar, coherent long-form text and varied paragraph openings.
- Use canonical scenario and source group metadata. Do not assign production IDs.

## Required gate before handing off to Work

Run `python -m sentinel_dataset.preflight` for the draft with references to the active v2 draft files and available approved v2 production content. Never use archived v1 data.

Use the current production progress and scenario catalogue explicitly when the Producer branch lags. Future length plans are projections. Resolve blocking errors and review each repeated-paragraph or repeated-sentence group. Run E5 when the local model is available, and preserve unresolved semantic alerts for Work. No claim of semantic QA if it was not executed.

Save candidates, a truthful QA report, and status under `drafts/chat/batch-NNNN/`; mark `ready_for_work_intake` only when technical preflight passes, known editorial defects are resolved, and the remaining independent review requirements are documented. Report commit SHA and remaining work.
