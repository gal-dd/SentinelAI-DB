"""Civilian-only cache integrity regressions; no model download or inference."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sentinel_dataset.core import digest
from sentinel_dataset.semantic import embeddings


class SemanticCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
            import onnxruntime
            import tokenizers
        except ImportError as error:
            raise unittest.SkipTest('E5 test environment is required') from error
        cls.np = numpy

    def setUp(self):
        self.folder = TemporaryDirectory(prefix='civil-npy-cache-')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.model = self.root / 'model'
        self.model.mkdir()
        # Intentionally fake assets: cache validation must not instantiate ONNX.
        payloads = {'model_int8.onnx': b'civil fixture', 'tokenizer.json': b'{}'}
        for name, content in payloads.items():
            (self.model / name).write_bytes(content)
        hashes = {name: sha256(content).hexdigest() for name, content in payloads.items()}
        self.rows = [{'text': 'Town library hours.'}, {'text': 'City park opening.'}]
        texts = ['passage: ' + row['text'] for row in self.rows]
        self.cache = self.root / 'cache'
        self.path = self.cache / digest(hashes) / f'{digest(texts)}.npy'
        self.path.parent.mkdir(parents=True)

    def read_cached(self):
        with patch('tokenizers.Tokenizer'), \
             patch('onnxruntime.InferenceSession', side_effect=AssertionError('Unexpected inference')):
            return embeddings(self.rows, self.model, self.cache)[0]

    def test_rejects_wrong_row_count_dimension_and_rank(self):
        for shape in ((1, 7), (1, 384), (2, 383), (768,)):
            with self.subTest(shape=shape):
                self.np.save(self.path, self.np.zeros(shape, dtype=self.np.float32), allow_pickle=False)
                with self.assertRaisesRegex(ValueError, 'Invalid embedding cache'):
                    self.read_cached()

    def test_rejects_wrong_dtype(self):
        for dtype in (self.np.float64, self.np.int32):
            with self.subTest(dtype=dtype):
                self.np.save(self.path, self.np.ones((2, 384), dtype=dtype), allow_pickle=False)
                with self.assertRaisesRegex(ValueError, 'Invalid embedding cache'):
                    self.read_cached()

    def test_rejects_nonfinite_cached_values(self):
        for value in (self.np.nan, self.np.inf, -self.np.inf):
            with self.subTest(value=value):
                array = self.np.zeros((2, 384), dtype=self.np.float32)
                array[0, 0] = value
                self.np.save(self.path, array, allow_pickle=False)
                with self.assertRaisesRegex(ValueError, 'Invalid embedding cache'):
                    self.read_cached()

    def test_valid_cache_is_unchanged_and_needs_no_inference(self):
        array = self.np.zeros((2, 384), dtype=self.np.float32)
        array[:, 0] = 1
        self.np.save(self.path, array, allow_pickle=False)
        before = self.path.read_bytes()
        self.np.testing.assert_array_equal(self.read_cached(), array)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
