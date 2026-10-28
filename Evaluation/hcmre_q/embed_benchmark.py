"""Encode the benchmark queries (and optionally the 3,037 listings) with the SAME
OpenAI-compatible embedding endpoint the backend uses (LM Studio, OpenRouter, ...).

Run this on the machine where the embedding server lives, then run eval_benchmark.py.
Only the Python standard library + numpy are needed.

  # query vectors that match the document vectors stored in backups/real_estate_2026-07-31.dump
  python embed_benchmark.py --model text-embedding-qwen3-embedding-0.6b \
         --base-url http://127.0.0.1:1234/v1

  # a different model (e.g. the current default qwen/qwen3-embedding-4b): re-encode the corpus too
  python embed_benchmark.py --model qwen/qwen3-embedding-4b --corpus

Prefixes follow backend/src/search/embedding.py exactly: "query: " / "passage: ".
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def embed(texts, base_url, model, api_key, dims, batch=16, timeout=120):
    endpoint = base_url.rstrip("/")
    endpoint = endpoint if endpoint.endswith("/embeddings") else endpoint + "/embeddings"
    out = []
    for start in range(0, len(texts), batch):
        chunk = texts[start:start + batch]
        payload = {"model": model, "input": chunk}
        if dims:
            payload["dimensions"] = dims
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {api_key}"} if api_key else {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))["data"]
        vecs = [item["embedding"] for item in sorted(data, key=lambda x: x.get("index", 0))]
        out.extend(vecs)
        print(f"  {min(start + batch, len(texts))}/{len(texts)}", end="\r", flush=True)
    arr = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    assert np.all(np.isfinite(arr)) and np.all(norms > 0), "invalid vectors returned"
    print()
    return arr / norms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    ap.add_argument("--model", default="text-embedding-qwen3-embedding-0.6b")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--dimensions", type=int, default=0, help="send 'dimensions' (only for models that support it)")
    ap.add_argument("--queries", default=str(HERE / "data" / "queries.jsonl"))
    ap.add_argument("--snapshot", default=str(HERE / "snapshot"))
    ap.add_argument("--corpus", action="store_true", help="also re-encode the 3,037 listings (search_text)")
    args = ap.parse_args()

    snap = Path(args.snapshot)
    tag = args.model.split("/")[-1].replace("text-embedding-", "")
    queries = [json.loads(line) for line in open(args.queries, encoding="utf-8")]
    t0 = time.time()
    q = embed(["query: " + x["text"] for x in queries], args.base_url, args.model, args.api_key, args.dimensions)
    np.save(snap / f"query_embeddings_{tag}.npy", q)
    meta = {"model": args.model, "base_url": args.base_url, "prefix": "query: ", "dims": int(q.shape[1]),
            "qids": [x["qid"] for x in queries], "seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(snap / f"query_embeddings_{tag}.json", "w", encoding="utf-8"), indent=1)
    print(f"saved {q.shape} query vectors -> {snap / f'query_embeddings_{tag}.npy'}")

    if args.corpus:
        import csv
        with gzip.open(snap / "properties_snapshot.csv.gz", "rt", encoding="utf-8") as fh:
            rows = sorted(csv.DictReader(fh), key=lambda r: int(r["id"]))
        d = embed(["passage: " + (r["search_text"] or "") for r in rows], args.base_url, args.model,
                  args.api_key, args.dimensions)
        np.save(snap / f"doc_embeddings_{tag}.npy", d.astype(np.float16))
        print(f"saved {d.shape} document vectors -> {snap / f'doc_embeddings_{tag}.npy'}")


if __name__ == "__main__":
    main()
