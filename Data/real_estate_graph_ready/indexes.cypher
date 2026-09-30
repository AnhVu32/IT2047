// Stable identifiers used by MATCH/MERGE operations.
CREATE CONSTRAINT listing_node_id_unique IF NOT EXISTS
FOR (n:Listing) REQUIRE n.listing_node_id IS UNIQUE;

CREATE CONSTRAINT amenity_id_unique IF NOT EXISTS
FOR (n:Amenity) REQUIRE n.amenity_id IS UNIQUE;

CREATE CONSTRAINT ward_id_unique IF NOT EXISTS
FOR (n:Ward) REQUIRE n.ward_id IS UNIQUE;

CREATE CONSTRAINT street_id_unique IF NOT EXISTS
FOR (n:Street) REQUIRE n.street_id IS UNIQUE;

CREATE CONSTRAINT geo_cluster_id_unique IF NOT EXISTS
FOR (n:GeoCluster) REQUIRE n.cluster_id IS UNIQUE;

// Common real-estate filtering fields. listing_id is intentionally non-unique
// because seven business IDs occur more than once in the source data.
CREATE INDEX listing_id_idx IF NOT EXISTS
FOR (n:Listing) ON (n.listing_id);

CREATE INDEX listing_property_type_idx IF NOT EXISTS
FOR (n:Listing) ON (n.property_type);

CREATE INDEX listing_price_range_idx IF NOT EXISTS
FOR (n:Listing) ON (n.price_range);

CREATE INDEX listing_area_idx IF NOT EXISTS
FOR (n:Listing) ON (n.area);

CREATE INDEX listing_bedrooms_idx IF NOT EXISTS
FOR (n:Listing) ON (n.bedrooms);

CREATE INDEX listing_posted_date_idx IF NOT EXISTS
FOR (n:Listing) ON (n.posted_date);

CREATE INDEX amenity_category_idx IF NOT EXISTS
FOR (n:Amenity) ON (n.category);

CREATE INDEX amenity_name_idx IF NOT EXISTS
FOR (n:Amenity) ON (n.name);

CREATE INDEX ward_name_idx IF NOT EXISTS
FOR (n:Ward) ON (n.name);

CREATE INDEX street_name_idx IF NOT EXISTS
FOR (n:Street) ON (n.name);

// Materialize WGS-84 points so distance/bounding-box predicates can use point indexes.
MATCH (n:Listing)
WHERE n.latitude IS NOT NULL AND n.longitude IS NOT NULL
SET n.location = point({latitude: n.latitude, longitude: n.longitude});

MATCH (n:Amenity)
WHERE n.latitude IS NOT NULL AND n.longitude IS NOT NULL
SET n.location = point({latitude: n.latitude, longitude: n.longitude});

MATCH (n:GeoCluster)
WHERE n.centroid_latitude IS NOT NULL AND n.centroid_longitude IS NOT NULL
SET n.location = point({latitude: n.centroid_latitude, longitude: n.centroid_longitude});

CREATE POINT INDEX listing_location_idx IF NOT EXISTS
FOR (n:Listing) ON (n.location);

CREATE POINT INDEX amenity_location_idx IF NOT EXISTS
FOR (n:Amenity) ON (n.location);

CREATE POINT INDEX geo_cluster_location_idx IF NOT EXISTS
FOR (n:GeoCluster) ON (n.location);

// Vietnamese text lookup across the human-readable listing fields.
CREATE FULLTEXT INDEX listing_text_idx IF NOT EXISTS
FOR (n:Listing) ON EACH [n.title, n.address, n.description];

CALL db.awaitIndexes(300);
