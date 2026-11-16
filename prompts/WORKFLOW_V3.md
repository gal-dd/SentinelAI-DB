# SentinelAI-DB v2 — efficiency workflow v3

This document supplements, not replaces, the canonical policy, checkpoint contract or security restrictions.

**Separation of duties:** Producer (`producer/chat-defense-v2`) authors drafts. Work Reviewer performs independent evaluation. Work Publisher alone commits to `poc/defense-focused-v2`. No stage may modify or count `archive/general-v1`.

## Steps

1. **Plan:** obtain live `progress.json` and `python -m sentinel_dataset plan`. Identify current valid batch and row quotas.
2. **Produce:** author candidate records with distinct fictional scenarios, natural Hebrew and evidence-backed labels, preserving domain allocations.
3. **Preflight:** run the standalone deterministic command below, with reference files from active v2 drafts/checkpoints only. A JSON report is saved locally.
4. **Triage:** fix blockers first; review repeated paragraphs and substantial repeated sentences. Do not assume warning equals duplication or similarity equals a reason to remove a record.
5. **Semantic review:** run existing E5 checks and group alerts by connected components for navigation, retaining individual original alert IDs, judgments, and hashes. Do not automatically clear mandatory alerts.
6. **Blind review and publish:** Work uses existing `prepare`, `review`, `checkpoint` and `verify` process and confirms remote commit.

Example:

```bash
python -m sentinel_dataset.preflight drafts/chat/batch-0007/candidates.jsonl \\
  --reference drafts/chat/batch-0006/candidates.jsonl \\
  --output .poc-local/preflight-0007.json
```

The default quota check uses live `progress.json`. Run `--skip-live-quotas` only to inspect an older candidate batch independently, never to approve production. Reference files accept both candidate `text` and published `אובייקט` field shapes. The preflight does **not** replace semantic E5 screening or independent judgment. Its current fast lexical checks cover exact matches and repeated complete sentences/paragraphs; deep paraphrases can evade them.

## Efficiency metrics to record

Store candidate rows, invalid rows, number of exact matches, repeated-substance groups, rows affected, semantic groups/pairs, model cache hits/misses, rows edited, blind label/domain agreements and valid checkpoint SHA. Do not report estimated Work token savings as measured unless actual usage was recorded.

## Ownership and failure policy

If many records repeat the same facts or fail blind labeling, stop individual Work rewrites and send an indexed correction packet to Producer. A candidate batch remains a draft until required review decisions are complete. Work or a future session can resume from repository files without relying on chat context.
