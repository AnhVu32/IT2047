# Real-estate graph-ready dataset

## Output summary
- Source rows: 3,037
- Source columns: 209
- Filtered wide columns: 156
- Unique listing graph IDs: 3,037
- Business listing IDs duplicated: 7
- Amenity nodes: 1,896
- Listing–amenity relationships: 27,333
- Ward nodes: 112
- Street nodes: 1,137
- GeoCluster nodes: 1,069
- Listings with at least one quality flag: 44

## Main files
- `Final_Data_graph_ready_filtered.csv`: curated wide table for inspection or custom ETL.
- `neo4j_listing_nodes.csv`: Listing node import.
- `neo4j_amenity_nodes.csv`: deduplicated Amenity node import.
- `neo4j_listing_near_amenity_relationships.csv`: `NEAR_AMENITY` edges.
- `neo4j_ward_nodes.csv`, `neo4j_street_nodes.csv`, `neo4j_geo_cluster_nodes.csv`: location nodes.
- Relationship files connect Listing → Ward, Street and GeoCluster, plus Street → Ward.
- `column_manifest.csv`: exact keep/drop decision and reason for every source column.

## Important decisions
- Removed pipeline/audit fields: source markers, routing source, enrichment timestamps and map links.
- Removed duplicated raw coordinates and duplicate administrative/street fields.
- Removed legacy `near_*` flags extracted from ad text; computed driving distances and threshold flags are retained.
- Preserved all source rows. Duplicated `listing_id` values receive unique `listing_node_id` values such as `123__1`, `123__2`.
- Dates use ISO `YYYY-MM-DD`; booleans use `true/false`.
- Invalid typed numeric values are blanked in graph import files and recorded in `data_quality_flags`.
- Current amenity relationships represent only the nearest amenity (`rank=1`, `is_nearest=true`).
- Hospital has no source threshold flag, so `within_threshold` and `threshold_km` are blank for hospital edges.

## Neo4j bulk-import note
Because `description` can contain line breaks, enable multiline CSV fields when importing.

Example structure:
```bash
neo4j-admin database import full graphdb \
  --nodes=neo4j_listing_nodes.csv \
  --nodes=neo4j_amenity_nodes.csv \
  --nodes=neo4j_ward_nodes.csv \
  --nodes=neo4j_street_nodes.csv \
  --nodes=neo4j_geo_cluster_nodes.csv \
  --relationships=neo4j_listing_near_amenity_relationships.csv \
  --relationships=neo4j_listing_in_ward_relationships.csv \
  --relationships=neo4j_listing_on_street_relationships.csv \
  --relationships=neo4j_street_in_ward_relationships.csv \
  --relationships=neo4j_listing_in_cluster_relationships.csv \
  --multiline-fields=true \
  --overwrite-destination=true
```
