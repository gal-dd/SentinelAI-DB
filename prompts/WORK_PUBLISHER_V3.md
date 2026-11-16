# Work Publisher v3 — production integration

Production is owned exclusively by the Work integrator in `poc/defense-focused-v2`.

1. Re-read the live `progress.json` and validate its last checkpoint. Never trust earlier conversation progress.
2. Import the specified completed draft from its owner branch; do not rewrite files in `drafts/chat`.
3. Derive the next length requirements dynamically with `python -m sentinel_dataset plan`. Do not assume 6/50/44/25 when the accepted cumulative quotas call for 7/50/43/25.
4. Require valid schema, documentary form, active v2 domain coverage, label/domain blind review, semantic similarity assessment, and dispositions required by the existing policy.
5. Check for repeated substantive prose even if token Jaccard produced no alerts. Resolve before publication.
6. Stage using existing repository commands. Publish the checkpoint data, metadata, QA report, `progress.json`, and `HANDOFF.md` as one verified commit.
7. Read the remote branch head again. If it advanced, stop and reconcile rather than overwriting.
8. Exclude `archive/general-v1` from all validation and training paths.

Do not weaken review thresholds or approve unresolved alerts to improve throughput. Return failed candidates to Producer with exact reasons. State actual production IDs and SHA only after remote verification.
