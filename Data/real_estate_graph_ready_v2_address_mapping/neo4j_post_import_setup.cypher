// Stable identifiers used by MATCH/MERGE operations.
CREATE CONSTRAINT listing_node_id_unique IF NOT EXISTS
FOR (l:Listing) REQUIRE l.listing_node_id IS UNIQUE;

CREATE CONSTRAINT amenity_id_unique IF NOT EXISTS
FOR (a:Amenity) REQUIRE a.amenity_id IS UNIQUE;

CREATE CONSTRAINT ward_id_unique IF NOT EXISTS
FOR (w:Ward) REQUIRE w.ward_id IS UNIQUE;

CREATE CONSTRAINT street_id_unique IF NOT EXISTS
FOR (s:Street) REQUIRE s.street_id IS UNIQUE;

CREATE CONSTRAINT geo_cluster_id_unique IF NOT EXISTS
FOR (g:GeoCluster) REQUIRE g.cluster_id IS UNIQUE;

CREATE CONSTRAINT former_area_id_unique IF NOT EXISTS
FOR (f:FormerAdminArea) REQUIRE f.former_area_id IS UNIQUE;

// Common structured filters.
CREATE INDEX listing_id_idx IF NOT EXISTS FOR (l:Listing) ON (l.listing_id);
CREATE INDEX listing_property_type_idx IF NOT EXISTS FOR (l:Listing) ON (l.property_type);
CREATE INDEX listing_price_range_idx IF NOT EXISTS FOR (l:Listing) ON (l.price_range);
CREATE INDEX listing_area_idx IF NOT EXISTS FOR (l:Listing) ON (l.area);
CREATE INDEX listing_bedrooms_idx IF NOT EXISTS FOR (l:Listing) ON (l.bedrooms);
CREATE INDEX listing_posted_date_idx IF NOT EXISTS FOR (l:Listing) ON (l.posted_date);
CREATE INDEX amenity_category_idx IF NOT EXISTS FOR (a:Amenity) ON (a.category);
CREATE INDEX amenity_name_idx IF NOT EXISTS FOR (a:Amenity) ON (a.name);
CREATE INDEX ward_name_idx IF NOT EXISTS FOR (w:Ward) ON (w.name);
CREATE INDEX street_name_idx IF NOT EXISTS FOR (s:Street) ON (s.name);

// Materialize WGS-84 points for distance and bounding-box searches.
MATCH (l:Listing)
WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
SET l.location = point({latitude: l.latitude, longitude: l.longitude});

MATCH (a:Amenity)
WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
SET a.location = point({latitude: a.latitude, longitude: a.longitude});

MATCH (g:GeoCluster)
WHERE g.centroid_latitude IS NOT NULL AND g.centroid_longitude IS NOT NULL
SET g.location = point({latitude: g.centroid_latitude, longitude: g.centroid_longitude});

CREATE POINT INDEX listing_location_idx IF NOT EXISTS FOR (l:Listing) ON (l.location);
CREATE POINT INDEX amenity_location_idx IF NOT EXISTS FOR (a:Amenity) ON (a.location);
CREATE POINT INDEX geo_cluster_location_idx IF NOT EXISTS FOR (g:GeoCluster) ON (g.location);

// Text search across listing content and both address systems.
CREATE FULLTEXT INDEX listing_text_idx IF NOT EXISTS
FOR (l:Listing) ON EACH [
  l.title,
  l.address,
  l.address_new,
  l.address_old,
  l.address_new_normalized,
  l.address_old_normalized,
  l.description
];

CREATE FULLTEXT INDEX ward_name_fulltext IF NOT EXISTS
FOR (w:Ward)
ON EACH [w.name, w.normalized_name, w.aliases];

CREATE FULLTEXT INDEX former_area_name_fulltext IF NOT EXISTS
FOR (f:FormerAdminArea)
ON EACH [
  f.name,
  f.normalized_name,
  f.old_address,
  f.aliases,
  f.former_city_province
];

CALL db.awaitIndexes(300);
