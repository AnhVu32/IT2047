"""Query (and document) vectors for the Deep Learning systems of eval_benchmark.py.

Run on the machine that serves the embedding model (LM Studio or any OpenAI-compatible endpoint). Uses the same
prefixes as backend/src/search/embedding.py ("query: " / "passage: ") and, like the backend, sends one query per
request (--query-batch 1: some servers give slightly different vectors for different batch sizes). Only needs
numpy (+ psycopg2 for --doc-vectors-from-db).

    # model of the app (.env): qwen/qwen3-embedding-4b, 1024 dimensions
    python embed_benchmark.py --model qwen/qwen3-embedding-4b --dimensions 1024 --corpus
    # or reuse the document vectors already in PostgreSQL (after build_search_index.py on the v3.1 data) —
    # the exact vectors the live system searches, so use this to compare with run_live.py
    python embed_benchmark.py --model qwen/qwen3-embedding-4b --dimensions 1024 \
        --doc-vectors-from-db "postgresql://postgres:changeme@localhost:5433/real_estate"

Writes snapshot/query_embeddings_<tag>.npy, snapshot/doc_embeddings_<tag>.npy (float32: the ranker rounds
final_score to 4 decimals, and float16 noise of ~1e-4 was enough to reorder a few results) and
snapshot/embeddings_<tag>.json, then: python eval_benchmark.py --embedding-tag <tag>
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

import runlog

HERE = Path(__file__).resolve().parent


def embed(texts, base_url, model, api_key, dims, batch=16, timeout=180, label="texts"):
    endpoint = base_url.rstrip("/")
    endpoint = endpoint if endpoint.endswith("/embeddings") else endpoint + "/embeddings"
    out = []
    starts = range(0, len(texts), batch)
    for start in runlog.progress(starts, f"{label} (batches of {batch})", total=len(starts)):
        payload = {"model": model, "input": texts[start:start + batch]}
        if dims:
            payload["dimensions"] = dims
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {api_key}"} if api_key else {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))["data"]
        out.extend(item["embedding"] for item in sorted(data, key=lambda x: x.get("index", 0)))
    arr = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    if not (np.all(np.isfinite(arr)) and np.all(norms > 0)):
        raise SystemExit("the endpoint returned invalid vectors")
    return arr / norms


def doc_vectors_from_db(dsn: str, doc_ids: list[int]) -> np.ndarray:
    import psycopg2
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT listing_id, embedding::text FROM properties WHERE embedding IS NOT NULL "
                    "AND is_active = true AND is_deleted = false")
        vec = {int(lid): np.asarray(json.loads(e), dtype=np.float32) for lid, e in cur.fetchall()}
    missing = [d for d in doc_ids if d not in vec]
    if missing:
        raise SystemExit(f"{len(missing)} listings have no embedding in the database (e.g. {missing[:5]}); "
                         "run build_search_index.py first or use --corpus")
    arr = np.stack([vec[d] for d in doc_ids])
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    ap.add_argument("--model", default="qwen/qwen3-embedding-4b")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--dimensions", type=int, default=1024, help="0 = do not send 'dimensions'")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--snapshot", default=str(HERE / "snapshot"))
    ap.add_argument("--query-batch", type=int, default=1, help="queries per request (the backend sends 1)")
    ap.add_argument("--batch", type=int, default=16, help="documents per request (build_search_index.py: 16)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--corpus", action="store_true", help="encode the 6,703 snapshot search_texts as well")
    g.add_argument("--doc-vectors-from-db", metavar="DSN", help="read document vectors from PostgreSQL instead")
    args = ap.parse_args()

    snap = Path(args.snapshot)
    tag = args.model.split("/")[-1].replace("text-embedding-", "")
    queries = [json.loads(line) for line in open(Path(args.data) / "queries.jsonl", encoding="utf-8")]
    with gzip.open(snap / "properties.csv.gz", "rt", encoding="utf-8") as fh:
        rows = sorted(csv.DictReader(fh), key=lambda r: int(r["doc_id"]))
    doc_ids = [int(r["doc_id"]) for r in rows]
    t0 = time.time()
    runlog.stage(f"embed {len(queries)} queries with {args.model} at {args.base_url} (tag {tag})")
    q = embed(["query: " + x["text"].strip() for x in queries], args.base_url, args.model, args.api_key,
              args.dimensions, batch=args.query_batch, label="queries")
    np.save(snap / f"query_embeddings_{tag}.npy", q)
    if args.doc_vectors_from_db:
        runlog.stage("read the document vectors from PostgreSQL")
        d, source = doc_vectors_from_db(args.doc_vectors_from_db, doc_ids), "postgresql properties.embedding"
    elif args.corpus:
        runlog.stage(f"embed {len(rows)} listings (search_text of the snapshot)")
        d = embed(["passage: " + (r["search_text"] or "") for r in rows], args.base_url, args.model, args.api_key,
                  args.dimensions, batch=args.batch, label="documents")
        source = "snapshot search_text"
    else:
        raise SystemExit("choose --corpus or --doc-vectors-from-db")
    if d.shape[1] != q.shape[1]:
        raise SystemExit(f"query vectors have {q.shape[1]} dimensions, document vectors {d.shape[1]}")
    np.save(snap / f"doc_embeddings_{tag}.npy", d.astype(np.float32))
    meta = {"model": args.model, "base_url": args.base_url, "dimensions": int(q.shape[1]), "doc_source": source,
            "prefixes": ["query: ", "passage: "], "query_batch": args.query_batch, "doc_batch": args.batch,
            "qids": [x["qid"] for x in queries], "doc_ids": doc_ids, "seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(snap / f"embeddings_{tag}.json", "w", encoding="utf-8"), indent=1)
    print(f"saved {q.shape} query and {d.shape} document vectors (tag {tag})")


if __name__ == "__main__":
    runlog.run("embed_benchmark", main)
