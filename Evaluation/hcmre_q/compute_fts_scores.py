"""Recompute the production lexical score for every benchmark query.

The backend ranks lexical matches with
    ts_rank_cd(to_tsvector('simple', COALESCE(search_text, '')), plainto_tsquery('simple', :query))
(backend/src/search/repository.py). This script runs exactly that expression against a
PostgreSQL database that holds the `properties` table (e.g. the docker-compose DB after
restoring backups/real_estate_2026-07-31.dump) and writes snapshot/fts_scores.csv.

  python compute_fts_scores.py --dsn "postgresql://postgres:changeme@localhost:5433/real_estate"

Only non-zero scores are stored: with plainto_tsquery every query word is AND-ed, so a
listing that misses any word gets 0 (ts_rank_cd returns 0 when the query does not match).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SQL = """
SELECT id, ts_rank_cd(to_tsvector('simple', COALESCE(search_text, '')), plainto_tsquery('simple', %(q)s)) AS s
FROM properties
WHERE is_active = true AND is_deleted = false
  AND to_tsvector('simple', COALESCE(search_text, '')) @@ plainto_tsquery('simple', %(q)s)
"""


def connect(dsn: str):
    try:
        import psycopg  # psycopg 3 (installed with the backend requirements)
        return psycopg.connect(dsn)
    except ImportError:
        import psycopg2
        return psycopg2.connect(dsn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--queries", default=str(HERE / "data" / "queries.jsonl"))
    ap.add_argument("--out", default=str(HERE / "snapshot" / "fts_scores.csv"))
    args = ap.parse_args()
    queries = [json.loads(line) for line in open(args.queries, encoding="utf-8")]
    conn = connect(args.dsn)
    n = 0
    with conn, conn.cursor() as cur, open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "doc_id", "text_score"])
        for q in queries:
            cur.execute(SQL, {"q": q["text"]})
            for doc_id, score in cur.fetchall():
                w.writerow([q["qid"], doc_id, float(score)])
                n += 1
    print(f"{n} non-zero (query, listing) pairs written to {args.out}")


if __name__ == "__main__":
    main()
