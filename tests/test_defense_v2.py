from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sentinel_dataset import checkpoints as cp
from sentinel_dataset.core import LABELS, export_rows, fingerprint, json_bytes, validate_rows
from sentinel_dataset.domains import batch_targets, cumulative_targets, require_coverage, review_sample, verify_domain_review


class DefenseV2Tests(unittest.TestCase):
    def rows(self, checkpoint=1):
        return [{"primary_domain": domain, "label": LABELS[i % 4], "text": f"{domain}-{i}"}
                for domain, count in batch_targets(checkpoint).items() for i in range(count)]

    def test_empty_state_ignores_archived_checkpoint_and_pilot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in (cp.PILOT_DATA, cp.PILOT_META, cp.PILOT_REPORT, *cp.batch_paths(1), cp.PROGRESS):
                cp.write_file(root / "archive/general-v1" / name, b"not parseable")
            cp.write_file(root / cp.PROGRESS, json_bytes(cp.initial_state(root)))
            state, rows = cp.load_progress(root)
            self.assertEqual((state["last_checkpoint"], state["next_id"], rows), (0, 1, []))
            self.assertEqual(state["length_plan"]["next_checkpoint_label_lengths"][LABELS[0]], [6, 50, 44, 25])
            self.assertEqual(export_rows([{"text": "דוגמה", "label": LABELS[0]}], state["next_id"])[0]["ID"], 1)
            with self.assertRaisesRegex(ValueError, "Archive paths"):
                cp.active_path(root / "archive/general-v1" / cp.PILOT_DATA, root)

    def test_exact_duplicates_only_against_active_rows(self):
        row = {"primary_domain": "missile_systems", "label": "בלמס", "text": "מושגי יסוד ביירוט",
               "length": "short", "origin": "synthetic", "scenario_id": "explain",
               "source_group_id": "explain", "style": "glossary", "rationale": "עיון פומבי",
               "edge_case": False, "pair_id": None, "source_id": None}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            cp.write_file(root / "archive/general-v1" / cp.PILOT_DATA, json_bytes([row]))
            prior = cp.load_pilot(root)
            self.assertEqual(validate_rows([row], {"explain": {}}, {}, prior), [])
            with self.assertRaisesRegex(ValueError, "Exact duplicate"):
                validate_rows([row], {"explain": {}}, {}, [row])

    def test_external_exact_text_guard_uses_canonical_normalization(self):
        from sentinel_dataset.core import reject_external_text_duplicates
        imported = [{"ID": 2501, "אובייקט": "מוזיאון  טילים ציבורי", "סיווג": "בלמס"}]
        with self.assertRaisesRegex(ValueError, "external ID 2501"):
            reject_external_text_duplicates([{"text": "מוזיאון טילים ציבורי"}], imported)
        reject_external_text_duplicates([{"text": "מאמר היסטורי נוסף"}], imported)

    def test_domain_counts_and_missile_floor(self):
        rows = self.rows()
        metrics = require_coverage(rows)
        self.assertEqual(metrics["domain_counts"]["missile_systems"], 300)
        self.assertEqual(metrics["missile_domain_percentage"], 60)
        rows[0]["primary_domain"] = "defense_logistics"
        with self.assertRaisesRegex(ValueError, "below the required minimum"):
            require_coverage(rows)

    def test_prospective_quota_change_preserves_history(self):
        old = self.rows(10)
        new = self.rows(11)
        self.assertEqual(require_coverage(old, checkpoint=10)["domain_counts"]["missile_systems"], 300)
        self.assertEqual(require_coverage(new, checkpoint=11)["missile_domain_percentage"], 80)
        self.assertEqual(sum(batch_targets(11).values()), 500)
        self.assertEqual(cumulative_targets(10)["missile_systems"], 3000)
        self.assertEqual(cumulative_targets(11)["missile_systems"], 3400)
        mixed = [row for _ in range(10) for row in old] + new
        self.assertEqual(require_coverage(mixed, 11)["domain_counts"]["missile_systems"], 3400)
        with self.assertRaises(ValueError):
            require_coverage(old, checkpoint=11)
        with self.assertRaises(ValueError):
            require_coverage(new, checkpoint=10)

    def test_final_total_includes_external_without_claiming_review(self):
        reviewed = [{"label": label} for label in LABELS for _ in range(23750)]
        external = [{"סיווג": label} for label in LABELS for _ in range(1250)]
        self.assertEqual(cp.verify_final_totals({"production_records": 100000}, reviewed, external),
                         dict.fromkeys(LABELS, 25000))
        with self.assertRaises(ValueError):
            cp.verify_final_totals({"production_records": 105000}, reviewed, external)

    def test_stratified_semantic_review_requires_contextual_decisions(self):
        rows = self.rows()
        index = {fingerprint(row): row for row in rows}
        judgments = {key: {"primary_domain": index[key]["primary_domain"], "reason": "context"}
                     for key in review_sample(rows, 1)}
        self.assertEqual(verify_domain_review(rows, 1, judgments)["reviewed"], 24)
        next(iter(judgments.values()))["primary_domain"] = "different"
        with self.assertRaisesRegex(ValueError, "requires correction"):
            verify_domain_review(rows, 1, judgments)

    def test_publisher_rejects_legacy_branch(self):
        with patch.object(cp, "git") as git:
            with self.assertRaisesRegex(ValueError, "Check out"):
                cp.preflight("origin", branch="poc/security-classification-dataset")
            git.assert_not_called()
