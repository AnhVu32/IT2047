#!/usr/bin/env python3
"""Backfill PostgreSQL search_text, graph-derived metadata and E5 embeddings.

Run from the backend directory. Embeddings are requested from the configured
OpenAI-compatible embedding endpoint.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_DATA_DIR = BACKEND_ROOT / "Data" if (BACKEND_ROOT / "Data").exists() else REPO_ROOT / "Data"
DATA_DIR = Path(os.getenv("SEARCH_DATA_DIR", str(DEFAULT_DATA_DIR)))
sys.path.insert(0, str(BACKEND_ROOT))

from src.search.embedding import embedding_model  # noqa: E402
from src.search.text_builder import build_listing_search_text  # noqa: E402
from src.settings.event import postgres_client  # noqa: E402
from src.settings.config import APPLICATION  # noqa: E402


def as_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def as_int(value):
    try:
        return int(float(value)) if value not in (None, "") else None
    except ValueError:
        return None


def as_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def as_date(value):
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def import_properties(csv_path: Path) -> None:
    existing = postgres_client.fetch_mappings("SELECT COUNT(*) AS total FROM properties")[0]["total"]
    if existing:
        print(f"[index] properties already contains {existing} rows; skipping catalog import")
        return
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    boolean_fields = (
        "pool", "gym", "park", "bbq", "kids_playground", "sports_court",
        "security_24h", "reception", "elevator", "parking", "near_metro",
        "near_bus", "near_highway", "near_school", "near_hospital", "near_mall",
        "near_market", "near_park", "river_view", "park_view", "city_view",
        "balcony", "garden", "garage", "terrace",
    )
    imported = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            params = {
                "listing_id": as_int(row.get("listing_id")), "listing_type": row.get("listing_type") or None,
                "posted_date": as_date(row.get("posted_date")), "expiry_date": as_date(row.get("expiry_date")),
                "property_type": row.get("property_type") or None, "city_province": row.get("city_province") or None,
                "district": row.get("district") or None, "folder": row.get("Folder") or row.get("folder") or None,
                "title": row.get("title") or None, "address": row.get("address") or None,
                "old_address": row.get("old_address") or None, "location_link": row.get("location_link") or None,
                "latitude_longitude": row.get("latitude_longitude") or None,
                "description": row.get("description") or None,
                "area_price_history": as_float(row.get("area_price_history")),
                "price_range": as_float(row.get("price_range")), "area": as_float(row.get("area")),
                "bedrooms": as_int(row.get("bedrooms")), "bathrooms": as_int(row.get("bathrooms")),
                "legal_status": row.get("legal_status") or None, "furnishing": row.get("furnishing") or None,
                "balcony_direction": row.get("balcony_direction") or None,
                "house_direction": row.get("house_direction") or None,
                "frontage": as_float(row.get("frontage")), "access_road": as_float(row.get("access_road")),
            }
            params.update({field: as_bool(row.get(field)) for field in boolean_fields})
            if params["listing_id"] is None:
                continue
            columns = list(params)
            postgres_client.execute_write(
                f"INSERT INTO properties ({', '.join(columns)}) VALUES ({', '.join(':' + key for key in columns)})",
                **params,
            )
            imported += 1
    print(f"[index] imported {imported} properties from {csv_path.name}")


def import_graph_metadata(graph_dir: Path) -> None:
    nodes_path = graph_dir / "neo4j_listing_nodes.csv"
    amenities_path = graph_dir / "neo4j_amenity_nodes.csv"
    relationships_path = graph_dir / "neo4j_listing_near_amenity_relationships.csv"
    if not all(path.exists() for path in (nodes_path, amenities_path, relationships_path)):
        print("[index] graph-ready CSV files not found; skipping distance metadata")
        return

    node_to_listing = {}
    with nodes_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            node_id = row.get(":START_ID(Listing)") or row.get("listing_node_id:ID(Listing)")
            listing_id = row.get("listing_id:string")
            if not node_id or not listing_id:
                continue
            node_to_listing[node_id] = listing_id
            postgres_client.execute_write(
                """
                UPDATE properties SET former_admin_area=:former_admin_area,
                    geo_cluster_150m=:geo_cluster, data_quality_flags=:flags,
                    coordinate_confidence=:confidence
                WHERE listing_id::text=:listing_id
                """,
                former_admin_area=row.get("former_admin_area:string") or None,
                geo_cluster=row.get("geo_cluster_150m:string") or None,
                flags=row.get("data_quality_flags:string") or None,
                confidence=as_float(row.get("coordinate_confidence:float")),
                listing_id=listing_id,
            )

    amenity_names = {}
    with amenities_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            amenity_names[row.get("amenity_id:ID(Amenity)")] = row.get("name:string")

    imported = 0
    with relationships_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            node_id = row.get(":START_ID(Listing)")
            amenity_id = row.get(":END_ID(Amenity)")
            listing_id = node_to_listing.get(node_id)
            if not listing_id or not amenity_id:
                continue
            postgres_client.execute_write(
                """
                INSERT INTO listing_amenity_distances (
                    listing_id, listing_node_id, amenity_id, amenity_name, category,
                    rank, is_nearest, straight_line_km, driving_distance_km,
                    driving_duration_min, threshold_km
                ) VALUES (
                    :listing_id, :listing_node_id, :amenity_id, :amenity_name, :category,
                    :rank, :is_nearest, :straight_line_km, :driving_distance_km,
                    :driving_duration_min, :threshold_km
                ) ON CONFLICT (listing_node_id, amenity_id) DO UPDATE SET
                    amenity_name=EXCLUDED.amenity_name, category=EXCLUDED.category,
                    rank=EXCLUDED.rank, is_nearest=EXCLUDED.is_nearest,
                    straight_line_km=EXCLUDED.straight_line_km,
                    driving_distance_km=EXCLUDED.driving_distance_km,
                    driving_duration_min=EXCLUDED.driving_duration_min,
                    threshold_km=EXCLUDED.threshold_km
                """,
                listing_id=listing_id, listing_node_id=node_id, amenity_id=amenity_id,
                amenity_name=amenity_names.get(amenity_id), category=row.get("category:string") or "unknown",
                rank=as_int(row.get("rank:int")), is_nearest=as_bool(row.get("is_nearest:boolean")),
                straight_line_km=as_float(row.get("straight_line_km:float")),
                driving_distance_km=as_float(row.get("driving_distance_km:float")),
                driving_duration_min=as_float(row.get("driving_duration_min:float")),
                threshold_km=as_float(row.get("threshold_km:float")),
            )
            imported += 1
    print(f"[index] imported {imported} listing/amenity distance rows")


def backfill(batch_size: int, skip_embeddings: bool, force: bool = False) -> None:
    where = "" if (skip_embeddings or force) else "WHERE embedding IS NULL"
    rows = postgres_client.fetch_mappings(f"SELECT * FROM properties {where} ORDER BY id")
    print(f"[index] building search text for {len(rows)} properties")
    if not skip_embeddings:
        print(
            f"[index] embedding provider: {embedding_model.provider}; "
            f"device: {embedding_model.device_name}"
        )
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        texts = [build_listing_search_text(row) for row in batch]
        vectors = None if skip_embeddings else embedding_model.encode(texts, kind="passage")
        if not skip_embeddings and vectors is None:
            raise RuntimeError(
                "Embedding generation is unavailable. Check the local model or LM Studio "
                "configuration; use --skip-embeddings for text-only indexing."
            )
        for index, (row, search_text) in enumerate(zip(batch, texts)):
            vector = None if vectors is None else "[" + ",".join(f"{float(x):.8f}" for x in vectors[index]) + "]"
            postgres_client.execute_write(
                """
                UPDATE properties SET search_text=:search_text,
                    embedding=CASE WHEN :embedding IS NULL THEN embedding ELSE CAST(:embedding AS vector) END,
                    embedding_model=CASE WHEN :embedding IS NULL THEN embedding_model ELSE :model END,
                    search_text_version='v1'
                WHERE id=:id
                """,
                search_text=search_text, embedding=vector, model=embedding_model.model_name, id=row["id"],
            )
        print(f"[index] processed {min(start + batch_size, len(rows))}/{len(rows)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--skip-graph-metadata", action="store_true")
    parser.add_argument("--skip-catalog-import", action="store_true")
    parser.add_argument("--force", action="store_true", help="Regenerate embeddings that already exist")
    args = parser.parse_args()
    command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), "head")
    postgres_client.start()
    try:
        if not args.skip_catalog_import:
            import_properties(DATA_DIR / "Final_Data.csv")
        if not args.skip_graph_metadata:
            import_graph_metadata(DATA_DIR / "real_estate_graph_ready_v2_address_mapping")
        backfill(args.batch_size, args.skip_embeddings, args.force)
    finally:
        postgres_client.stop()


if __name__ == "__main__":
    main()
