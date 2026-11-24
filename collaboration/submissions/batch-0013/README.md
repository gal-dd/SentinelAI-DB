# Batch 0013

This submission contains 500 Hebrew candidates for central review. The base is `37008a61b76a0c98ddabe6ae22757c0f22dc2ab5`, where the production state is 11,000 records, checkpoint 0012 and next ID 11001. The projected count after central acceptance is 11,500.

| Domain | Records |
|---|---:|
| Missile systems | 400 |
| Uncrewed aircraft | 24 |
| Radar, sensors and space | 24 |
| Cyber and communications | 24 |
| Defense logistics | 14 |
| General controls | 14 |

For each label, the 125 records consist of 6 short texts, 50 sentences, 44 paragraphs and 25 long texts. The long texts each have at least two developed paragraphs. The records use original fictional and educational contexts, including publishing, oversight, classroom exercises and institutional decisions.

The candidate file uses the repository schema and identifies 114 new scenarios. The only catalog changes append those scenarios to `config/scenarios.json`. The JSONL order binds the candidate digest and the review artifacts.

## Verification

- `plan` and `prepare` passed with zero quota gaps, schema and document-form failures, or normalized exact duplicates. Exact checks cover signed checkpoints and external imports. The local E5 similarity scan covers the candidates and signed checkpoints.
- The initial E5 scans identified 15 and then 5 high-risk pairs. The candidate texts were revised and the original thresholds used again. The final scan found 794 routine alerts and zero requiring disposition. A fresh packet using the final candidate file reproduced the alert inventory and accepted both sets of judgments.
- The final text-first review covers 53 candidates, including 50 random and 3 targeted selections, and 24 domain judgments spanning all domain and label combinations. There are zero final disagreements or rejections. The same OpenAI Codex model authored and reviewed the records. The review is model self-review with prior exposure to the proposed labels.
- Infrastructure passed under Python 3.13.5. The full 45-test suite passed under Python 3.12.14 with the semantic dependencies installed. The Python 3.13.5 run skipped the semantic cache class because the required semantic dependencies were installed in the Python 3.12 environment. The E5 runtime and weights are identified in `quality.json`.

## Replay

Run from the repository root on this working revision with the repository-specified E5 weights installed.

```bash
python -B -m sentinel_dataset verify
python -B -m sentinel_dataset plan collaboration/submissions/batch-0013/candidates.jsonl
python -B -m sentinel_dataset prepare collaboration/submissions/batch-0013/candidates.jsonl \
  --model-dir .poc-local/e5 --packet .poc-local/batch-0013-review-packet.json
```

The matching decisions are in `review.json`. Detailed scores, artifact checksums, sample fingerprints, scan iterations and final review metrics are in `quality.json`. Historical comparison records stay in the local review packet. Central acceptance and checkpoint creation follow the repository's review procedure.
