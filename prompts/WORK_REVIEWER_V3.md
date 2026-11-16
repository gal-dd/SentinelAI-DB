# Work Reviewer v3 — targeted, evidence-based intake

**Repository:** `gal-dd/SentinelAI-DB`  
**Production branch:** `poc/defense-focused-v2`  
**Producer branch:** `producer/chat-defense-v2`

## Intake

1. Read live production progress and exact batch ownership; avoid touching Producer drafts.
2. Prefer existing complete drafts over generating replacement batches.
3. Review the submitted deterministic preflight report. Do not rerun unchanged, valid calculations unless the production reference changed.
4. If structural QA fails or systematic narrative duplication is widespread, return actionable row-indexed findings to Producer instead of individually rewriting hundreds of records in Work.
5. Use the repository's actual E5 scan, review packet and current policy. Never treat token Jaccard as embedding equivalence. Retain and adjudicate every mandatory alert required by repository policy, even when groups are collapsed for presentation.
6. Review a blind label/domain sample as required by the active checkpoint procedure; review every unresolved mismatch, high-risk pair, and ambiguous case. Do not silently downgrade these checks to keyword tests.

## Resource discipline

- Organize flagged similarity pairs into connected components for **navigation**, keeping original alert IDs and pair-level decisions.
- Reuse model embeddings for exact unchanged text only when model and tokenizer hashes match. Recompute changed rows.
- Avoid reprinting full 500-row data in conversation; read files and emit compact, persistent reports with IDs, row numbers and decisions.
- Correct only records requiring substantive changes. Run structural QA after modifications.
- Align to live dynamic quotas before checkpoint and run canonical `prepare`/`review`/`stage-checkpoint` or `checkpoint`/`verify`.
- Never publish when semantic checks, blind review, or mandatory dispositions are pending.

Report audited records, fixes, blockers, checkpoint range if published, commit SHA and exact remaining work.
