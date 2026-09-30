# Real-estate graph-ready dataset — V2 address mapping

This package supports queries using both current and former administrative addresses.

## Verified coverage
- Listings: 3,037
- Current-address coverage: 3,037/3,037
- Former-address coverage: 3,037/3,037
- FormerAdminArea nodes: 32
- Listing → FormerAdminArea edges: 3,037
- Ward → FormerAdminArea mappings: 122
- Ward nodes: 112

## Address graph

```text
(:Listing)-[:IN_WARD]->(:Ward)
(:Listing)-[:IN_FORMER_AREA]->(:FormerAdminArea)
(:Ward)-[:MAPPED_FROM {supporting_listing_count}]->(:FormerAdminArea)
```

Ward-to-former-area mapping is many-to-many because some current wards contain data associated with multiple former administrative areas.

## New and updated files
- `Final_Data_graph_ready_filtered.csv`
  - `address_new`
  - `address_old`
  - `address_new_normalized`
  - `address_old_normalized`
- `neo4j_listing_nodes.csv`: includes the same four address properties.
- `neo4j_ward_nodes.csv`: adds normalized name and aliases; removes the ambiguous single former-area property.
- `neo4j_former_admin_area_nodes.csv`
- `neo4j_listing_in_former_area_relationships.csv`
- `neo4j_ward_mapped_from_former_area_relationships.csv`
- `neo4j_post_import_setup.cypher`

## Bulk import example

```bash
neo4j-admin database import full graphdb \
  --id-type=string \
  --nodes=neo4j_listing_nodes.csv \
  --nodes=neo4j_amenity_nodes.csv \
  --nodes=neo4j_ward_nodes.csv \
  --nodes=neo4j_street_nodes.csv \
  --nodes=neo4j_geo_cluster_nodes.csv \
  --nodes=neo4j_former_admin_area_nodes.csv \
  --relationships=neo4j_listing_near_amenity_relationships.csv \
  --relationships=neo4j_listing_in_ward_relationships.csv \
  --relationships=neo4j_listing_on_street_relationships.csv \
  --relationships=neo4j_street_in_ward_relationships.csv \
  --relationships=neo4j_listing_in_cluster_relationships.csv \
  --relationships=neo4j_listing_in_former_area_relationships.csv \
  --relationships=neo4j_ward_mapped_from_former_area_relationships.csv \
  --multiline-fields=true \
  --overwrite-destination=true
```

After import, run `neo4j_post_import_setup.cypher`.

## Example old-address query

```cypher
MATCH (l:Listing)-[:IN_FORMER_AREA]->(f:FormerAdminArea)
MATCH (l)-[:IN_WARD]->(w:Ward)
WHERE f.normalized_name = $former_area_normalized
  AND ($price_max IS NULL OR l.price_range <= $price_max)
RETURN
  l.listing_node_id,
  l.title,
  l.address_old,
  l.address_new,
  f.name AS former_area,
  w.name AS current_ward,
  l.price_range
ORDER BY l.price_range
LIMIT $limit;
```

Example parameters:

```json
{
  "former_area_normalized": "quan 2",
  "price_max": 6,
  "limit": 20
}
```
