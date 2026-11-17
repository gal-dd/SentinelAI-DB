"""SQLite cache of normalized float32 embeddings, keyed by exact input text.

The caller creates a separate DB per model/tokenizer artifact digest. This
prevents stale embeddings after a model revision. Database is local and ignored
by Git when placed inside .poc-local/.
"""
from hashlib import sha256
from pathlib import Path
import sqlite3


def text_key(text):
    return sha256(text.encode("utf-8")).hexdigest()


class VectorCache:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS embeddings "
            "(text_hash TEXT PRIMARY KEY, dimension INTEGER NOT NULL, vector BLOB NOT NULL)"
        )
        self.connection.commit()

    def get_many(self, keys):
        import numpy as np

        unique = list(dict.fromkeys(keys))
        if not unique:
            return {}
        results = {}
        for offset in range(0, len(unique), 400):
            batch = unique[offset:offset + 400]
            placeholders = ",".join("?" for _ in batch)
            query = ("SELECT text_hash, dimension, vector FROM embeddings "
                     "WHERE text_hash IN (" + placeholders + ")")
            for key, dimension, raw in self.connection.execute(query, batch):
                if len(raw) != 4 * dimension:
                    raise ValueError("Embedding cache dimension mismatch")
                array = np.frombuffer(raw, dtype=np.float32).copy()
                if not np.isfinite(array).all():
                    raise ValueError("Expected finite embedding cache values")
                results[key] = array
        return results

    def put_many(self, records):
        """records: iterable of (SHA256 text hash, normalized 1-D float32 vector)."""
        import numpy as np

        prepared = []
        for key, vector in records:
            array = np.asarray(vector, dtype=np.float32)
            if array.ndim != 1 or not array.size:
                raise ValueError("Expected a nonempty 1-D embedding")
            if not np.isfinite(array).all():
                raise ValueError("Expected finite embedding cache values")
            prepared.append((key, int(array.shape[0]), array.tobytes()))
        self.connection.executemany(
            "INSERT OR REPLACE INTO embeddings(text_hash, dimension, vector) VALUES (?, ?, ?)",
            prepared,
        )
        self.connection.commit()

    def close(self):
        self.connection.close()
