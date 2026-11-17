"""Local SQLite per-text embedding cache tests (no ONNX model required)."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from sentinel_dataset.embedding_cache import VectorCache, text_key
from sentinel_dataset.semantic import embeddings


class VectorCacheTests(unittest.TestCase):
    def test_exact_text_reuse_and_persistence(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "model-a" / "vectors.sqlite3"
            key = text_key("passage: רשומה לדוגמה")
            cache = VectorCache(path)
            self.assertEqual(cache.get_many([key]), {})
            cache.put_many([(key, np.array([0.5, 1.0, -0.2], dtype=np.float32))])
            cache.close()
            reopened = VectorCache(path)
            self.assertEqual(reopened.get_many([key, key])[key].tolist(), [0.5, 1.0, -0.20000000298023224])
            self.assertNotIn(text_key("passage: דוגמה אחרת"), reopened.get_many([key]))
            reopened.close()

    def test_rejects_multidimensional_vector(self):
        with TemporaryDirectory() as tmp:
            cache = VectorCache(Path(tmp) / "vectors.sqlite3")
            with self.assertRaises(ValueError):
                cache.put_many([("bad", np.ones((2, 2), dtype=np.float32))])
            cache.close()

    def test_key_is_sensitive_to_text_content(self):
        self.assertNotEqual(text_key("passage: א"), text_key("passage: ב"))


@unittest.skipUnless(os.environ.get("SENTINEL_E5_MODEL_DIR"), "Pinned model assets not configured")
class E5CacheIntegrationTests(unittest.TestCase):
    def test_reordering_and_one_edit_preserve_vectors(self):
        model = Path(os.environ["SENTINEL_E5_MODEL_DIR"])
        a = {"text": "פרסמנו מדריך קצר על ההיסטוריה של מערכי יירוט בדיוניים."}
        b = {"text": "במערך התצפית האזרחי הציגו את תצלומי העננים ששובצו בתערוכה. " * 20}
        c = {"text": "הצוות ביקש לתאם ישיבה."}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cold, warm, edited = {}, {}, {}
            single, _ = embeddings([a], model, root / "single")
            mixed, _ = embeddings([c, a, b], model, root / "shared", cold)
            reordered, _ = embeddings([a, c, a], model, root / "shared", warm)
            one_change, _ = embeddings([a, c, {"text": "פורסם עדכון על תערוכה."}],
                                       model, root / "shared", edited)

            np.testing.assert_array_equal(mixed[1], single[0])
            np.testing.assert_array_equal(reordered, mixed[[1, 0, 1]])
            np.testing.assert_array_equal(one_change[:2], mixed[[1, 0]])
            self.assertEqual(cold["computed_unique_vectors"], 3)
            self.assertEqual(warm["computed_unique_vectors"], 0)
            self.assertEqual(warm["cached_input_occurrences"], 3)
            self.assertEqual(edited["computed_unique_vectors"], 1)


if __name__ == "__main__":
    unittest.main()
