"""Re-create snapshot/ from the PostgreSQL backup (needs `pg_restore` 16 on PATH).

  python extract_snapshot.py --dump ../../backups/real_estate_2026-07-31.dump

Writes:
  snapshot/properties_snapshot.csv.gz       properties table without the vector column
  snapshot/listing_amenity_distances.csv.gz nearest amenity per category (rank = 1)
  snapshot/qwen3_0.6b_doc_embeddings.npy    the stored pgvector embeddings (float16, ordered by properties.id)
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def copy_block(dump: Path, table: str) -> pd.DataFrame:
    sql = subprocess.run(["pg_restore", "--data-only", "-t", table, "-f", "-", str(dump)],
                         check=True, capture_output=True, text=True, encoding="utf-8").stdout
    cols, rows, copying = None, [], False
    for line in sql.splitlines():
        if line.startswith(f"COPY public.{table} "):
            cols = [c.strip() for c in line[line.index("(") + 1:line.index(")")].split(",")]
            copying = True
            continue
        if copying:
            if line.startswith("\\."):
                break
            rows.append([None if x == "\\N" else x.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
                         for x in line.split("\t")])
    return pd.DataFrame(rows, columns=cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(HERE.parents[1] / "backups" / "real_estate_2026-07-31.dump"))
    ap.add_argument("--out", default=str(HERE / "snapshot"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    props = copy_block(Path(args.dump), "properties")
    props["id"] = props["id"].astype(int)
    props = props.sort_values("id").reset_index(drop=True)
    emb = np.array([np.array(v.strip("[]").split(","), dtype=np.float32) for v in props["embedding"]])
    np.save(out / "qwen3_0.6b_doc_embeddings.npy", emb.astype(np.float16))
    props.drop(columns=["embedding"]).to_csv(out / "properties_snapshot.csv.gz", index=False, compression="gzip")
    lad = copy_block(Path(args.dump), "listing_amenity_distances")
    lad.to_csv(out / "listing_amenity_distances.csv.gz", index=False, compression="gzip")
    print(f"properties {props.shape}, embeddings {emb.shape} ({props['embedding_model'].iloc[0]}), amenities {lad.shape}")


if __name__ == "__main__":
    main()
