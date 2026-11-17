"""Run local multilingual E5 embeddings and retrieve nearest neighbors."""

from hashlib import sha256
from pathlib import Path

from .core import alert, digest

MODEL = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
THRESHOLD = 0.92
NEIGHBORS = 12
CACHE_RECIPE = "int8-cpu-single-input-mean-l2-f32-v1"


def embeddings(rows, model_dir, cache_dir, cache_metrics=None):
    """Compute only missing exact-text vectors; persist per model-artifact revision."""
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer, __version__ as tokenizer_version

    ort.disable_telemetry_events()

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
    namespace = {
        "artifacts": hashes,
        "recipe": CACHE_RECIPE,
        "onnxruntime": ort.__version__,
        "tokenizers": tokenizer_version,
        "numpy": np.__version__,
    }
    cache = Path(cache_dir) / digest(namespace)
    cache.mkdir(parents=True, exist_ok=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = tokenizer = None
    hits = computed = 0
    vectors = []
    database = VectorCache(cache / "per-text.sqlite3")
    try:
        for start in range(0, len(rows), 32):
            texts = ["passage: " + row["text"] for row in rows[start:start + 32]]
            keys = [text_key(text) for text in texts]
            found = database.get_many(keys)
            hits += sum(key in found for key in keys)
            missing = {key: text for key, text in zip(keys, texts) if key not in found}
            if missing and session is None:
                tokenizer = Tokenizer.from_file(str(tokenizer_path))
                tokenizer.enable_truncation(max_length=512)
                session = ort.InferenceSession(str(model_path), sess_options=options,
                                               providers=["CPUExecutionProvider"])
                input_names = [item.name for item in session.get_inputs()]
            entries = []
            for key, text in missing.items():
                # Dynamic INT8 activation quantization depends on neighboring batch
                # members. A single input makes a cached vector independent of them.
                encoding = tokenizer.encode(text)
                arrays = {
                    "input_ids": [encoding.ids],
                    "attention_mask": [encoding.attention_mask],
                    "token_type_ids": [encoding.type_ids],
                }
                inputs = {name: np.asarray(arrays[name], dtype=np.int64) for name in input_names}
                hidden = session.run(["last_hidden_state"], inputs)[0]
                mask = inputs["attention_mask"][..., None].astype(np.float32)
                mean = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
                vector = (mean / np.linalg.norm(mean, axis=1, keepdims=True))[0].astype(np.float32)
                entries.append((key, vector))
            if entries:
                database.put_many(entries)
                found.update(entries)
                computed += len(entries)
            vectors.append(np.stack([found[key] for key in keys]))
    finally:
        database.close()
    if cache_metrics is not None:
        cache_metrics.update(recipe=CACHE_RECIPE, cached_input_occurrences=hits, computed_unique_vectors=computed)
    if not vectors:
        return np.empty((0, 0), dtype=np.float32), hashes
    return np.concatenate(vectors), hashes


def semantic_scan(prior, rows, model_dir, cache_dir):
    import numpy as np

    cache_metrics = {}
    vectors, hashes = embeddings([*prior, *rows], model_dir, cache_dir, cache_metrics)
    size = len(vectors)
    new = len(prior)
    all_rows = [*prior, *rows]
    k = min(NEIGHBORS + 1, size)
    if not size:
        indices = values = []
        method = "exact_cosine_top_k"
    elif size <= 3000:
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
        "embedding_cache": cache_metrics,
        "search": method,
        "cosine_threshold": THRESHOLD,
        "neighbors_per_record": max(0, k - 1),
        "indexed_records": size,
        "scanned_records": len(rows),
        "candidate_pairs": len(alerts),
    }
    return sorted(alerts.values(), key=lambda item: item["id"]), report


PLAN_SEED = 41403
