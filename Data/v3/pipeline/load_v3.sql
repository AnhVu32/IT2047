-- Load Data/v3 into PostgreSQL in one transaction. Run with psql after prepare_postgres.py:
--   psql -v ON_ERROR_STOP=1 -d real_estate -f load_v3.sql        (the CSVs must be at /tmp inside that host/container)
--
-- * Existing properties keep their primary key (id); matching is by listing_id.
-- * The 7 legacy duplicate listing_ids are collapsed to the lowest id.
-- * search_text / embedding are cleared for every row: the stored vectors were produced by another model
--   (text-embedding-qwen3-embedding-0.6b) than the one the API queries with, so build_search_index.py must
--   regenerate all of them.
-- * listing_amenity_distances is replaced entirely by the v3 Top-5 edges.
\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE stg AS SELECT * FROM properties WHERE false;
ALTER TABLE stg ADD COLUMN source text;

\copy stg (listing_id, listing_type, property_type, city_province, district, posted_date, expiry_date, images, folder, title, address, old_address, location_link, latitude_longitude, description, legal_status, furnishing, balcony_direction, house_direction, former_admin_area, geo_cluster_150m, data_quality_flags, area_price_history, price_range, area, frontage, access_road, coordinate_confidence, bedrooms, bathrooms, pool, gym, park, bbq, kids_playground, sports_court, security_24h, reception, elevator, parking, near_metro, near_bus, near_highway, near_school, near_hospital, near_mall, near_market, near_park, river_view, park_view, city_view, balcony, garden, garage, terrace, source) FROM '/tmp/properties_v3.csv' WITH (FORMAT csv, HEADER true)

SELECT count(*) AS staged, count(DISTINCT listing_id) AS staged_unique FROM stg;

DELETE FROM properties p USING properties q WHERE p.listing_id = q.listing_id AND p.id > q.id;

UPDATE properties p SET
    listing_type = s.listing_type, posted_date = s.posted_date, expiry_date = s.expiry_date,
    property_type = s.property_type, city_province = s.city_province, district = s.district,
    images = s.images, folder = s.folder, title = s.title, address = s.address, old_address = s.old_address,
    location_link = s.location_link, latitude_longitude = s.latitude_longitude, description = s.description,
    area_price_history = s.area_price_history, price_range = s.price_range, area = s.area,
    bedrooms = s.bedrooms, bathrooms = s.bathrooms, legal_status = s.legal_status, furnishing = s.furnishing,
    balcony_direction = s.balcony_direction, house_direction = s.house_direction,
    pool = s.pool, gym = s.gym, park = s.park, bbq = s.bbq, kids_playground = s.kids_playground,
    sports_court = s.sports_court, security_24h = s.security_24h, reception = s.reception,
    elevator = s.elevator, parking = s.parking, near_metro = s.near_metro, near_bus = s.near_bus,
    near_highway = s.near_highway, near_school = s.near_school, near_hospital = s.near_hospital,
    near_mall = s.near_mall, near_market = s.near_market, near_park = s.near_park,
    river_view = s.river_view, park_view = s.park_view, city_view = s.city_view, balcony = s.balcony,
    garden = s.garden, garage = s.garage, terrace = s.terrace, frontage = s.frontage, access_road = s.access_road,
    former_admin_area = s.former_admin_area, geo_cluster_150m = s.geo_cluster_150m,
    data_quality_flags = s.data_quality_flags, coordinate_confidence = s.coordinate_confidence,
    search_text = NULL, search_text_version = NULL, embedding = NULL, embedding_model = NULL,
    updated_at = now()
FROM stg s WHERE p.listing_id = s.listing_id;

INSERT INTO properties (listing_id, listing_type, property_type, city_province, district, posted_date, expiry_date,
    images, folder, title, address, old_address, location_link, latitude_longitude, description, legal_status,
    furnishing, balcony_direction, house_direction, former_admin_area, geo_cluster_150m, data_quality_flags,
    area_price_history, price_range, area, frontage, access_road, coordinate_confidence, bedrooms, bathrooms,
    pool, gym, park, bbq, kids_playground, sports_court, security_24h, reception, elevator, parking, near_metro,
    near_bus, near_highway, near_school, near_hospital, near_mall, near_market, near_park, river_view, park_view,
    city_view, balcony, garden, garage, terrace)
SELECT listing_id, listing_type, property_type, city_province, district, posted_date, expiry_date,
    images, folder, title, address, old_address, location_link, latitude_longitude, description, legal_status,
    furnishing, balcony_direction, house_direction, former_admin_area, geo_cluster_150m, data_quality_flags,
    area_price_history, price_range, area, frontage, access_road, coordinate_confidence, bedrooms, bathrooms,
    pool, gym, park, bbq, kids_playground, sports_court, security_24h, reception, elevator, parking, near_metro,
    near_bus, near_highway, near_school, near_hospital, near_mall, near_market, near_park, river_view, park_view,
    city_view, balcony, garden, garage, terrace
FROM stg s WHERE NOT EXISTS (SELECT 1 FROM properties p WHERE p.listing_id = s.listing_id)
ORDER BY s.listing_id;

-- Listings in the database but not in v3 are reported, never deleted.
SELECT count(*) AS properties_not_in_v3 FROM properties p WHERE NOT EXISTS (SELECT 1 FROM stg s WHERE s.listing_id = p.listing_id);

TRUNCATE listing_amenity_distances;
\copy listing_amenity_distances (listing_id, listing_node_id, amenity_id, amenity_name, category, rank, is_nearest, straight_line_km, driving_distance_km, driving_duration_min, threshold_km) FROM '/tmp/listing_amenity_distances_v3.csv' WITH (FORMAT csv, HEADER true)

COMMIT;
ANALYZE properties;
ANALYZE listing_amenity_distances;
