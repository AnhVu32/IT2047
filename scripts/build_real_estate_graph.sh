#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_DIR/Data/real_estate_graph_ready_v2_address_mapping"
CONTAINER_DATA_DIR="/csv/real_estate_graph_ready"

force=false
case "${1:-}" in
  "") ;;
  --force) force=true ;;
  -h|--help)
    echo "Usage: $0 [--force]"
    echo "  --force  Replace an existing non-empty Neo4j database."
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    echo "Usage: $0 [--force]" >&2
    exit 2
    ;;
esac

required_files=(
  neo4j_listing_nodes.csv
  neo4j_amenity_nodes.csv
  neo4j_ward_nodes.csv
  neo4j_street_nodes.csv
  neo4j_geo_cluster_nodes.csv
  neo4j_former_admin_area_nodes.csv
  neo4j_listing_near_amenity_relationships.csv
  neo4j_listing_in_ward_relationships.csv
  neo4j_listing_on_street_relationships.csv
  neo4j_street_in_ward_relationships.csv
  neo4j_listing_in_cluster_relationships.csv
  neo4j_listing_in_former_area_relationships.csv
  neo4j_ward_mapped_from_former_area_relationships.csv
  neo4j_post_import_setup.cypher
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$DATA_DIR/$file" ]]; then
    echo "Missing required file: $DATA_DIR/$file" >&2
    exit 1
  fi
done

cd "$PROJECT_DIR"

echo "Starting Neo4j to inspect the current database..."
docker compose up -d --wait neo4j

node_count="$({
  docker compose exec -T neo4j sh -lc \
    'neo_user=${NEO4J_AUTH%%/*}; neo_pass=${NEO4J_AUTH#*/}; /var/lib/neo4j/bin/cypher-shell -u "$neo_user" -p "$neo_pass" --format plain "MATCH (n) RETURN count(n) AS nodes;"'
} | tail -n 1 | tr -d '\r')"

if [[ ! "$node_count" =~ ^[0-9]+$ ]]; then
  echo "Could not determine the current Neo4j node count: $node_count" >&2
  exit 1
fi

if (( node_count > 0 )) && [[ "$force" != true ]]; then
  echo "Refusing to replace a non-empty database ($node_count nodes)." >&2
  echo "Run '$0 --force' if replacing it is intentional." >&2
  exit 1
fi

restore_neo4j() {
  echo "Ensuring Neo4j is running..."
  docker compose up -d neo4j >/dev/null
}
trap restore_neo4j EXIT

echo "Stopping Neo4j for offline bulk import..."
docker compose stop neo4j

echo "Importing real-estate nodes and relationships..."
docker compose run --rm --no-deps neo4j \
  neo4j-admin database import full neo4j \
  --nodes="$CONTAINER_DATA_DIR/neo4j_listing_nodes.csv" \
  --nodes="$CONTAINER_DATA_DIR/neo4j_amenity_nodes.csv" \
  --nodes="$CONTAINER_DATA_DIR/neo4j_ward_nodes.csv" \
  --nodes="$CONTAINER_DATA_DIR/neo4j_street_nodes.csv" \
  --nodes="$CONTAINER_DATA_DIR/neo4j_geo_cluster_nodes.csv" \
  --nodes="$CONTAINER_DATA_DIR/neo4j_former_admin_area_nodes.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_listing_near_amenity_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_listing_in_ward_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_listing_on_street_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_street_in_ward_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_listing_in_cluster_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_listing_in_former_area_relationships.csv" \
  --relationships="$CONTAINER_DATA_DIR/neo4j_ward_mapped_from_former_area_relationships.csv" \
  --multiline-fields=true \
  --overwrite-destination=true \
  --strict=true \
  --report-file=/data/import-real-estate.report

echo "Starting Neo4j and creating constraints/indexes..."
docker compose up -d --wait neo4j
docker compose exec -T neo4j sh -lc \
  'neo_user=${NEO4J_AUTH%%/*}; neo_pass=${NEO4J_AUTH#*/}; /var/lib/neo4j/bin/cypher-shell -u "$neo_user" -p "$neo_pass" --fail-fast -f /csv/real_estate_graph_ready/neo4j_post_import_setup.cypher'

trap - EXIT

echo "Verifying imported graph..."
docker compose exec -T neo4j sh -lc \
  'neo_user=${NEO4J_AUTH%%/*}; neo_pass=${NEO4J_AUTH#*/}; /var/lib/neo4j/bin/cypher-shell -u "$neo_user" -p "$neo_pass" --format plain "MATCH (n) RETURN count(n) AS nodes; MATCH ()-[r]->() RETURN count(r) AS relationships; SHOW INDEXES YIELD state RETURN state, count(*) AS indexes ORDER BY state;"'

echo "Real-estate graph build complete."
