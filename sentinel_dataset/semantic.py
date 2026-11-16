"""Run local multilingual E5 embeddings and retrieve nearest neighbors."""

from hashlib import sha256
from pathlib import Path

from .core import alert, digest

MODEL = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
THRESHOLD = 0.92
NEIGHBORS = 12


def embeddings(rows, model_dir, cache_dir):
    """Compute only missing exact-text vectors; persist per model-artifact revision."""
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    from .embedding_cache import VectorCache, text_key

    model_dir = Path(model_dir)
    model_path = model_dir / "model_int8.onnx"
    tokenizer_path = model_dir / "tokenizer.json"
    hashes = {}
    for path in (model_path, tokenizer_path):
        with path.open("rb") as stream:
            hasher = sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        hashes[path.name] = hasher.hexdigest()
    cache = Path(cache_dir) / digest(hashes)
    cache.mkdir(parents=True, exist_ok=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    session = None
    vectors = []
    database = VectorCache(cache / "per-text.sqlite3")
    try:
        for start in range(0, len(rows), 32):
            texts = ["passage: " + row["text"] for row in rows[start:start + 32]]
            keys = [text_key(text) for text in texts]
            found = database.get_many(keys)
            missing = [(key, text) for key, text in zip(keys, texts) if key not in found]
            # Eliminate duplicate text within the same batch, too.
            distinct = list({key: text for key, text in missing}.items())
            if distinct:
                if session is None:
                    session = ort.InferenceSession(str(model_path), sess_options=options,
                                                   providers=["CPUExecutionProvider"])
                encodings = tokenizer.encode_batch([text for _, text in distinct])
                arrays = {
                    "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
                    "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
                    "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
                }
                inputs = {item.name: arrays[item.name] for item in session.get_inputs()}
                hidden = session.run(["last_hidden_state"], inputs)[0]
                mask = arrays["attention_mask"][..., None].astype(np.float32)
                mean = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
                fresh = (mean / np.linalg.norm(mean, axis=1, keepdims=True)).astype(np.float32)
                entries = list(zip([key for key, _ in distinct], fresh))
                database.put_many(entries)
                found.update(entries)
            vectors.append(np.stack([found[key] for key in keys]))
    finally:
        database.close()
    if not vectors:
        return np.empty((0, 0), dtype=np.float32), hashes
    return np.concatenate(vectors), hashes


def semantic_scan(prior, rows, model_dir, cache_dir):
    import numpy as np

    vectors, hashes = embeddings([*prior, *rows], model_dir, cache_dir)
    size = len(vectors)
    new = len(prior)
    all_rows = [*prior, *rows]
    k = min(NEIGHBORS + 1, size)
    if size <= 3000:
        scores = vectors[new:] @ vectors.T
        indices = np.argsort(-scores, axis=1, kind="stable")[:, :k]
        values = np.take_along_axis(scores, indices, axis=1)
        method = "exact_cosine_top_k"
    else:
        import hnswlib

        index = hnswlib.Index(space="cosine", dim=vectors.shape[1])
        index.init_index(max_elements=size, ef_construction=160, M=24, random_seed=PLAN_SEED)
        index.add_items(vectors, np.arange(size), num_threads=1)
        index.set_ef(96)
        indices, distances = index.knn_query(vectors[new:], k=k, num_threads=2)
        values = 1 - distances
        method = "hnsw_cosine_top_k"
    alerts = {}
    for i, (neighbors, scores) in enumerate(zip(indices, values), new):
        for j, score in zip(neighbors, scores):
            if i != j and score >= THRESHOLD:
                item = alert(all_rows[i], all_rows[j], "semantic", score)
                alerts[item["id"]] = item
    report = {
        "status": "completed",
        "model": MODEL,
        "reference_revision": REVISION,
        "artifact_sha256": hashes,
        "search": method,
        "cosine_threshold": THRESHOLD,
        "neighbors_per_record": k - 1,
        "indexed_records": size,
        "scanned_records": len(rows),
        "candidate_pairs": len(alerts),
    }
    return sorted(alerts.values(), key=lambda item: item["id"]), report


PLAN_SEED = 41403
