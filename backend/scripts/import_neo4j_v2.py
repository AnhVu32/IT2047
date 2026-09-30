#!/usr/bin/env python3
"""Idempotently import the V2 graph CSV package into a local or remote Neo4j."""

from __future__ import annotations

import argparse
import csv
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_DATA_DIR = (
    (BACKEND_ROOT / "Data") if (BACKEND_ROOT / "Data").is_dir() else (REPO_ROOT / "Data")
) / "real_estate_graph_ready_v2_address_mapping"

NODE_FILES = (
    ("neo4j_listing_nodes.csv", "Listing", "listing_node_id:ID(Listing)", "listing_node_id"),
    ("neo4j_amenity_nodes.csv", "Amenity", "amenity_id:ID(Amenity)", "amenity_id"),
    ("neo4j_ward_nodes.csv", "Ward", "ward_id:ID(Ward)", "ward_id"),
    ("neo4j_street_nodes.csv", "Street", "street_id:ID(Street)", "street_id"),
    ("neo4j_geo_cluster_nodes.csv", "GeoCluster", "cluster_id:ID(GeoCluster)", "cluster_id"),
    (
        "neo4j_former_admin_area_nodes.csv",
        "FormerAdminArea",
        "former_area_id:ID(FormerAdminArea)",
        "former_area_id",
    ),
)

RELATIONSHIP_FILES = (
    (
        "neo4j_listing_near_amenity_relationships.csv",
        "Listing", "listing_node_id", ":START_ID(Listing)",
        "Amenity", "amenity_id", ":END_ID(Amenity)", "NEAR_AMENITY",
    ),
    (
        "neo4j_listing_in_ward_relationships.csv",
        "Listing", "listing_node_id", ":START_ID(Listing)",
        "Ward", "ward_id", ":END_ID(Ward)", "IN_WARD",
    ),
    (
        "neo4j_listing_on_street_relationships.csv",
        "Listing", "listing_node_id", ":START_ID(Listing)",
        "Street", "street_id", ":END_ID(Street)", "ON_STREET",
    ),
    (
        "neo4j_street_in_ward_relationships.csv",
        "Street", "street_id", ":START_ID(Street)",
        "Ward", "ward_id", ":END_ID(Ward)", "IN_WARD",
    ),
    (
        "neo4j_listing_in_cluster_relationships.csv",
        "Listing", "listing_node_id", ":START_ID(Listing)",
        "GeoCluster", "cluster_id", ":END_ID(GeoCluster)", "IN_CLUSTER",
    ),
    (
        "neo4j_listing_in_former_area_relationships.csv",
        "Listing", "listing_node_id", ":START_ID(Listing)",
        "FormerAdminArea", "former_area_id", ":END_ID(FormerAdminArea)",
        "IN_FORMER_AREA",
    ),
    (
        "neo4j_ward_mapped_from_former_area_relationships.csv",
        "Ward", "ward_id", ":START_ID(Ward)",
        "FormerAdminArea", "former_area_id", ":END_ID(FormerAdminArea)",
        "MAPPED_FROM",
    ),
)

CONSTRAINTS = (
    "CREATE CONSTRAINT listing_node_id_unique IF NOT EXISTS FOR (n:Listing) REQUIRE n.listing_node_id IS UNIQUE",
    "CREATE CONSTRAINT amenity_id_unique IF NOT EXISTS FOR (n:Amenity) REQUIRE n.amenity_id IS UNIQUE",
    "CREATE CONSTRAINT ward_id_unique IF NOT EXISTS FOR (n:Ward) REQUIRE n.ward_id IS UNIQUE",
    "CREATE CONSTRAINT street_id_unique IF NOT EXISTS FOR (n:Street) REQUIRE n.street_id IS UNIQUE",
    "CREATE CONSTRAINT geo_cluster_id_unique IF NOT EXISTS FOR (n:GeoCluster) REQUIRE n.cluster_id IS UNIQUE",
    "CREATE CONSTRAINT former_area_id_unique IF NOT EXISTS FOR (n:FormerAdminArea) REQUIRE n.former_area_id IS UNIQUE",
)


def property_name(header: str) -> str:
    return header.split(":", 1)[0]


def typed_value(header: str, value: str) -> Any:
    if value == "":
        return None
    type_name = header.rsplit(":", 1)[-1]
    if type_name in {"int", "long"}:
        return int(float(value))
    if type_name in {"float", "double"}:
        return float(value)
    if type_name == "boolean":
        return value.strip().lower() in {"true", "1", "yes"}
    if type_name == "date":
        return date.fromisoformat(value)
    return value


def batches(rows: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def import_nodes(session, data_dir: Path, batch_size: int) -> None:
    for filename, label, id_header, id_property in NODE_FILES:
        path = data_dir / filename
        source_rows = csv_rows(path)

        def prepared():
            for source in source_rows:
                properties = {
                    property_name(header): typed_value(header, value)
                    for header, value in source.items()
                    if header not in {id_header, ":LABEL"}
                }
                yield {"id": source[id_header], "properties": properties}

        query = (
            f"UNWIND $rows AS row MERGE (n:{label} {{{id_property}: row.id}}) "
            "SET n += row.properties"
        )
        if label == "Listing":
            query += " SET n.address = n.address_new"
        if label == "Ward":
            query += " REMOVE n.former_admin_area"
        imported = 0
        for batch in batches(prepared(), batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        print(f"[neo4j-v2] {filename}: {imported} nodes merged")


def import_relationships(session, data_dir: Path, batch_size: int) -> None:
    for config in RELATIONSHIP_FILES:
        filename, start_label, start_prop, start_header, end_label, end_prop, end_header, rel_type = config

        def prepared():
            for source in csv_rows(data_dir / filename):
                properties = {
                    property_name(header): typed_value(header, value)
                    for header, value in source.items()
                    if header not in {start_header, end_header, ":TYPE"}
                }
                yield {
                    "start": source[start_header],
                    "end": source[end_header],
                    "properties": properties,
                }

        query = (
            f"UNWIND $rows AS row MATCH (a:{start_label} {{{start_prop}: row.start}}) "
            f"MATCH (b:{end_label} {{{end_prop}: row.end}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r += row.properties"
        )
        imported = 0
        for batch in batches(prepared(), batch_size):
            session.run(query, rows=batch).consume()
            imported += len(batch)
        print(f"[neo4j-v2] {filename}: {imported} relationships merged")


def run_post_import_setup(session, data_dir: Path) -> None:
    setup_path = data_dir / "neo4j_post_import_setup.cypher"
    content = "\n".join(
        line for line in setup_path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//")
    )
    session.run("DROP INDEX listing_text_idx IF EXISTS").consume()
    for statement in content.split(";"):
        if statement.strip():
            session.run(statement.strip()).consume()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    missing = [name for name, *_ in (*NODE_FILES, *RELATIONSHIP_FILES) if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing V2 files: {', '.join(missing)}")

    uri = os.environ["NEO4J_URI"]
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            before_nodes = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            before_relationships = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS count"
            ).single()["count"]
            print(
                f"[neo4j-v2] before: nodes={before_nodes}, "
                f"relationships={before_relationships}"
            )
            for statement in CONSTRAINTS:
                session.run(statement).consume()
            import_nodes(session, data_dir, args.batch_size)
            import_relationships(session, data_dir, args.batch_size)
            run_post_import_setup(session, data_dir)
            after_nodes = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            after_relationships = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS count"
            ).single()["count"]
            print(
                f"[neo4j-v2] after: nodes={after_nodes}, "
                f"relationships={after_relationships}"
            )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
