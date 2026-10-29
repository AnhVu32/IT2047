"""Freeze what the offline replicas of the search system need, from Data/v3 (v3.1) — PROTOCOL.md §7 D.

    python make_snapshot.py                                   # snapshot/properties.csv.gz + amenity evidence
    python make_snapshot.py --dsn postgresql://user:pw@host:port/db   # + snapshot/fts_scores.csv

* properties.csv.gz   the `properties` rows as the API reads them after build_search_index.py
                      (doc_id = listing_id; created_rank = load order, i.e. the created_at tie-break), with
                      search_text built by backend/src/search/text_builder.py.
* amenity_evidence.csv.gz   rank-1 amenity per category (what repository.py sends to the ranker).
* fts_scores.csv      production lexical score of every query:
                      ts_rank_cd(to_tsvector('simple', search_text), plainto_tsquery('simple', query)).
                      Needs any PostgreSQL ≥ 12; the table is created in a temporary schema and dropped.
* manifest.json       sha256 of the inputs (Data/v3 files, text_builder.py) and outputs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import pandas as pd

import runlog

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
V3 = REPO / "Data" / "v3"
SNAP = HERE / "snapshot"

BOOL = ["pool", "gym", "park", "bbq", "kids_playground", "sports_court", "security_24h", "reception", "elevator",
        "parking", "near_metro", "near_bus", "near_highway", "near_school", "near_hospital", "near_mall", "near_market",
        "near_park", "river_view", "park_view", "city_view", "balcony", "garden", "garage", "terrace"]
FLOAT = ["area_price_history", "price_range", "area", "frontage", "access_road", "coordinate_confidence"]
INT = ["bedrooms", "bathrooms"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def typed(row: dict) -> dict:
    """Python values as psycopg returns them from the `properties` columns."""
    out = dict(row)
    for k in FLOAT:
        v = out.get(k)
        out[k] = None if v in ("", None) or (isinstance(v, float) and math.isnan(v)) else float(v)
    for k in INT:
        v = out.get(k)
        out[k] = None if v in ("", None) or (isinstance(v, float) and math.isnan(v)) else int(float(v))
    for k in BOOL:
        out[k] = str(out.get(k)).strip().lower() in ("1", "1.0", "true", "t")
    for k, v in list(out.items()):
        if isinstance(v, float) and math.isnan(v):
            out[k] = None
    return out


def build_properties() -> pd.DataFrame:
    sys.path.insert(0, str(REPO / "backend"))
    from src.search.text_builder import build_listing_search_text  # noqa: E402  (system side, not labels)

    raw = pd.read_csv(V3 / "postgres" / "properties_v3.csv", dtype=str, keep_default_na=False)
    rows = []
    for rank, r in enumerate(raw.to_dict("records")):
        item = typed(r)
        item["doc_id"] = int(item["listing_id"])
        item["created_rank"] = rank
        item["search_text"] = build_listing_search_text(item)
        rows.append(item)
    df = pd.DataFrame(rows)
    keep = ["doc_id", "listing_id", "created_rank", "listing_type", "property_type", "district", "former_admin_area",
            "posted_date", "title", "address", "description", "price_range", "area", "bedrooms", "bathrooms",
            "legal_status", "furnishing", "house_direction", "balcony_direction", "geo_cluster_150m",
            "data_quality_flags", "coordinate_confidence", "frontage", "access_road", "area_price_history", *BOOL,
            "search_text"]
    return df[keep]


def amenity_evidence() -> pd.DataFrame:
    lad = pd.read_csv(V3 / "postgres" / "listing_amenity_distances_v3.csv", dtype={"listing_id": str})
    lad = lad[lad["rank"] <= 1]
    return lad[["listing_id", "category", "amenity_name", "driving_distance_km", "driving_duration_min", "threshold_km"]]


def fts_scores(dsn: str, props: pd.DataFrame, queries: list[dict]) -> pd.DataFrame:
    import psycopg2  # noqa: E402

    conn = psycopg2.connect(dsn)
    out = []
    with conn, conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE hcmre_props (doc_id bigint PRIMARY KEY, search_text text)")
        buf = io.StringIO()
        csv.writer(buf).writerows(props[["doc_id", "search_text"]].itertuples(index=False))
        buf.seek(0)
        cur.copy_expert("COPY hcmre_props FROM STDIN WITH (FORMAT csv)", buf)
        cur.execute("ALTER TABLE hcmre_props ADD COLUMN tsv tsvector")
        cur.execute("UPDATE hcmre_props SET tsv = to_tsvector('simple', COALESCE(search_text, ''))")
        for q in runlog.progress(queries, "queries (full-text score)"):
            cur.execute("SELECT doc_id, ts_rank_cd(tsv, plainto_tsquery('simple', %s)) FROM hcmre_props "
                        "WHERE tsv @@ plainto_tsquery('simple', %s)", (q["text"], q["text"]))
            out += [(q["qid"], int(d), float(s)) for d, s in cur.fetchall()]
    conn.close()
    return pd.DataFrame(out, columns=["qid", "doc_id", "text_score"]).sort_values(["qid", "doc_id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", help="PostgreSQL DSN for the lexical scores (skip to keep snapshot/fts_scores.csv)")
    ap.add_argument("--data", default=str(HERE / "data"))
    args = ap.parse_args()
    SNAP.mkdir(exist_ok=True)
    runlog.stage("properties.csv.gz: rows as the API reads them, search_text from backend text_builder.py")
    props = build_properties()
    with gzip.GzipFile(SNAP / "properties.csv.gz", "wb", mtime=0) as fh:
        fh.write(props.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    runlog.stage("amenity_evidence.csv.gz")
    with gzip.GzipFile(SNAP / "amenity_evidence.csv.gz", "wb", mtime=0) as fh:
        fh.write(amenity_evidence().to_csv(index=False, lineterminator="\n").encode("utf-8"))
    if args.dsn:
        runlog.stage("fts_scores.csv: PostgreSQL ts_rank_cd for every query")
        queries = [json.loads(line) for line in open(Path(args.data) / "queries.jsonl", encoding="utf-8")]
        fts_scores(args.dsn, props, queries).to_csv(SNAP / "fts_scores.csv", index=False, lineterminator="\n")
    manifest = {"inputs": {p: sha256(REPO / p) for p in ("Data/v3/postgres/properties_v3.csv",
                                                           "Data/v3/postgres/listing_amenity_distances_v3.csv",
                                                           "backend/src/search/text_builder.py")},
                "outputs": {p.name: sha256(p) for p in sorted(SNAP.glob("*")) if p.name != "manifest.json"
                            and not p.name.endswith(".npy")}}
    json.dump(manifest, open(SNAP / "manifest.json", "w", encoding="utf-8"), indent=1)
    runlog.stage(f"done: {SNAP}")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    runlog.run("make_snapshot", main)
