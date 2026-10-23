#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
database_name="${1:-graphdb}"
# Run only for a NEW database. No overwrite/delete option is passed.
neo4j-admin database import full "$database_name" \
 --id-type=string \
 --nodes=neo4j_listing_nodes.csv \
 --nodes=neo4j_amenity_nodes.csv \
 --nodes=neo4j_cluster_nodes.csv \
 --nodes=neo4j_ward_nodes.csv \
 --nodes=neo4j_former_admin_area_nodes.csv \
 --relationships=neo4j_listing_amenity_edges.csv \
 --relationships=neo4j_listing_cluster_edges.csv \
 --relationships=neo4j_listing_ward_edges.csv \
 --relationships=neo4j_listing_former_area_edges.csv \
 --relationships=neo4j_ward_former_area_edges.csv \
 --multiline-fields=true
