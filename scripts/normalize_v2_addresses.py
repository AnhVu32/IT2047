#!/usr/bin/env python3
"""Repair Vietnamese accent-free search fields in the V2 graph CSV package."""

from __future__ import annotations

import argparse
import csv
import os
import re
import stat
import tempfile
import unicodedata
from pathlib import Path


DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "Data"
    / "real_estate_graph_ready_v2_address_mapping"
)


def normalize(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def flawed_normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def repair_aliases(value: str) -> str:
    tokens = [token.strip() for token in value.split("|") if token.strip()]
    generated_bad = {
        flawed_normalize(token)
        for token in tokens
        if flawed_normalize(token) != normalize(token)
    }
    repaired: list[str] = []
    for token in tokens:
        if token not in generated_bad and token not in repaired:
            repaired.append(token)
        normalized = normalize(token)
        if normalized and normalized not in repaired:
            repaired.append(normalized)
    return "|".join(repaired)


def rewrite_csv(path: Path, transform) -> int:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {path}")
        rows = list(reader)
        fieldnames = reader.fieldnames

    changed = 0
    for row in rows:
        before = row.copy()
        transform(row)
        changed += row != before

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.chmod(temp_name, original_mode | 0o044)
        os.replace(temp_name, path)
    except Exception:
        os.unlink(temp_name)
        raise
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", nargs="?", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()

    jobs = {
        "Final_Data_graph_ready_filtered.csv": lambda row: row.update(
            address_new_normalized=normalize(row["address_new"]),
            address_old_normalized=normalize(row["address_old"]),
        ),
        "neo4j_listing_nodes.csv": lambda row: row.update(
            {
                "address_new_normalized:string": normalize(row["address_new:string"]),
                "address_old_normalized:string": normalize(row["address_old:string"]),
            }
        ),
        "neo4j_ward_nodes.csv": lambda row: row.update(
            {
                "normalized_name:string": normalize(row["name:string"]),
                "aliases:string": repair_aliases(row["aliases:string"]),
            }
        ),
        "neo4j_former_admin_area_nodes.csv": lambda row: row.update(
            {
                "normalized_name:string": normalize(row["name:string"]),
                "normalized_former_city_province:string": normalize(
                    row["former_city_province:string"]
                ),
                "aliases:string": repair_aliases(row["aliases:string"]),
            }
        ),
    }

    for filename, transform in jobs.items():
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"{filename}: {rewrite_csv(path, transform)} rows updated")


if __name__ == "__main__":
    main()
