"""Local SQLite per-text embedding cache tests (no ONNX model required)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from sentinel_dataset.embedding_cache import VectorCache, text_key


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


if __name__ == "__main__":
    unittest.main()
