#!/usr/bin/env python3
"""Write the staging CSVs that load_v3.sql copies into PostgreSQL (properties + listing_amenity_distances).

Output goes to Data/v3/postgres/. Pure standard library.
"""
import csv
import re
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)
V3 = Path(__file__).resolve().parents[1]
OUT = V3 / "postgres"

BOOLEANS = ["pool", "gym", "park", "bbq", "kids_playground", "sports_court", "security_24h", "reception", "elevator",
            "parking", "near_metro", "near_bus", "near_highway", "near_school", "near_hospital", "near_mall",
            "near_market", "near_park", "river_view", "park_view", "city_view", "balcony", "garden", "garage", "terrace"]
TEXT = ["listing_type", "property_type", "city_province", "district", "title", "address", "old_address", "location_link",
        "latitude_longitude", "description", "legal_status", "furnishing", "balcony_direction", "house_direction",
        "former_admin_area", "geo_cluster_150m", "data_quality_flags"]
FLOATS = ["area_price_history", "price_range", "area", "frontage", "access_road", "coordinate_confidence"]
INTS = ["bedrooms", "bathrooms"]


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def date(value):
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value or "")
    if m:
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or "") else ""


def boolean(value):
    v = str(value or "").strip().lower()
    return "true" if v in ("1", "true", "yes") else "false" if v in ("0", "false", "no") else ""


def number(value, integer=False):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(x)) if integer else repr(x)


def main():
    OUT.mkdir(exist_ok=True)
    rows = read(V3 / "master_v3.csv")
    fields = (["listing_id"] + TEXT[:4] + ["posted_date", "expiry_date", "images", "folder"] + TEXT[4:] + FLOATS
              + INTS + BOOLEANS + ["source"])
    with open(OUT / "properties_v3.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for r in rows:
            out = {"listing_id": r["listing_id"], "posted_date": date(r["posted_date"]),
                   "expiry_date": date(r["expiry_date"]), "images": r["images"] or "[]", "folder": r["Folder"],
                   "source": r["source"]}
            out.update({c: r[c] for c in TEXT})
            out.update({c: number(r[c]) for c in FLOATS})
            out.update({c: number(r[c], integer=True) for c in INTS})
            out.update({c: boolean(r[c]) for c in BOOLEANS})
            w.writerow(out)

    names = {r["amenity_id:ID(Amenity)"]: r["name:string"] for r in read(V3 / "graph" / "neo4j_amenity_nodes.csv")}
    n = 0
    with open(OUT / "listing_amenity_distances_v3.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["listing_id", "listing_node_id", "amenity_id", "amenity_name", "category", "rank", "is_nearest",
                    "straight_line_km", "driving_distance_km", "driving_duration_min", "threshold_km"])
        for r in read(V3 / "graph" / "neo4j_listing_near_amenity_relationships.csv"):
            lid, aid = r[":START_ID(Listing)"], r[":END_ID(Amenity)"]
            w.writerow([lid, lid, aid, names.get(aid, ""), r["category:string"], r["rank:int"], r["is_nearest:boolean"],
                        r["straight_line_km:float"], r["driving_distance_km:float"], r["driving_duration_min:float"],
                        r["threshold_km:float"]])
            n += 1
    print("properties", len(rows), "amenity distance rows", n)


if __name__ == "__main__":
    main()
