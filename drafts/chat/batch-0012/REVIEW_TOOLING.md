# Reusable review ledger — experimental

This branch contains a **read-only** reconciliation helper, not a publisher. It requires an actual review ledger and a fresh packet from the existing QA pipeline. It never supplies a missing label, reason, or similarity decision. Review evidence is bound to candidate fingerprints, exact text SHA-256, production progress SHA-256 and checkpoint number. Previously reviewed pairs absent from the current packet do not block; a new pair always requires an explicit decision. Keep external-cohort screening and content safety checks separate. Do not use this as a shortcut around any existing publication gate.

Run: `python -B -m unittest discover -s tests -p test_review_reconciliation.py -v`.

The partial wave script checks structural validity, lexical screening and exact duplicates against its branch baseline. It does not perform E5 or independent content review. Re-run against the actual next production baseline before any publication. No production writes from this workflow.
