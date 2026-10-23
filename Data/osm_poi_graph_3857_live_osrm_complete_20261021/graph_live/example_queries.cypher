// Inspect the full graph and measured route coverage.
MATCH (l:Listing) RETURN count(l) AS listings;
MATCH (a:Amenity) RETURN a.category AS category, count(*) AS features;
MATCH (:Listing)-[r:NEAR_AMENITY]->(:Amenity)
RETURN r.category AS category, r.route_status AS status, count(*) AS relationships;

// Five candidates per category for one listing. rank is Haversine rank.
MATCH (l:Listing {listing_id:'45633671'})-[r:NEAR_AMENITY]->(a:Amenity)
RETURN r.category AS category, r.rank AS rank, a.name AS amenity,
 r.straight_line_km AS straight_line_km, r.driving_distance_km AS driving_km,
 r.driving_duration_min AS driving_minutes, r.route_status AS route_status
ORDER BY category,rank;

// Listings with at least two bedrooms and a hospital/clinic within 2km by car.
MATCH (l:Listing)-[r:NEAR_AMENITY {category:'hospital',route_status:'ok'}]->(a:Amenity)
WHERE l.bedrooms >= 2 AND r.driving_distance_km <= 2
RETURN l.listing_id,l.title,a.name,a.subtype,r.driving_distance_km,r.driving_duration_min
ORDER BY r.driving_distance_km LIMIT 20;

// The best DRIVING distance among the five straight-line candidates.
// This does not prove the global nearest POI by road distance.
MATCH (l:Listing {listing_id:'45633671'})-[r:NEAR_AMENITY {category:'school',route_status:'ok'}]->(a:Amenity)
RETURN a.name,r.rank,r.driving_distance_km,r.driving_duration_min
ORDER BY r.driving_distance_km LIMIT 1;

// Listings missing safe coordinates.
MATCH (l:Listing) WHERE l.latitude IS NULL OR l.longitude IS NULL
RETURN l.listing_id,l.address_new,l.coordinate_status;
