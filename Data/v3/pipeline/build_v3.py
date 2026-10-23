#!/usr/bin/env python3
"""Merge the legacy 3,037-listing dataset with the live-OSM 3,857-listing dataset into Data/v3.

Policy
  * A listing present in both datasets takes the NEW (live) record; the legacy values of the
    fields that changed are kept in the prev_* columns and in reports/overlap_changes.csv.
  * Listings only in the new dataset keep the package's Top-5 edges and OSRM routes verbatim.
  * Listings only in the legacy dataset get Top-5 recomputed against the live POI catalog
    (same method as the live package) and routed with OSRM.
  * Nothing under the two source packages is modified.

Stages (each can be re-run):
  assemble   offline: merged rows, 150 m clusters, legacy-only Top-5 edges, image manifest
  route      OSRM matrices for the legacy-only edges (sends coordinates to --osrm-url)
  finalize   apply routes, write master_v3.csv, graph/ CSVs and reports
  validate   integrity checks on the written files
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

csv.field_size_limit(sys.maxsize)

V3 = Path(__file__).resolve().parents[1]
DATA = V3.parent
REPO = DATA.parent
NEW = DATA / "osm_poi_graph_3857_live_osrm_complete_20261021"
NEWG = NEW / "graph_live"
OLD = DATA / "real_estate_graph_ready_v2_address_mapping"
LEGACY_FINAL = DATA / "Final_Data.csv"
IMAGES = REPO / "images"
WORK = V3 / "work"
GRAPH = V3 / "graph"
REPORTS = V3 / "reports"
CACHE = V3 / "live_cache" / "osrm"
ASSEMBLED = WORK / "assembled.pkl"

CATS = ["hospital", "school", "college_university", "metro", "mall", "market", "supermarket", "park", "bus_stop"]
RADIUS = dict(zip(CATS, [7, 3, 7, 5, 7, 3, 3, 5, 2]))
# Driving-distance thresholds used by the legacy graph and the live package (hospital has none).
LIMITS = {"school": 2, "college_university": 5, "metro": 3, "mall": 5, "market": 2,
          "supermarket": 2, "park": 5, "bus_stop": 2}
CLUSTER_M = 150
OSRM_MAX_COORDS = 100
OSRM_MAX_SOURCES = 32
POI_STAMP_COLS = {"travel_enriched_at", "amenities_travel_enriched_at", "amenity_types_within_threshold_count",
                  "nearby_category_count", "nearby_categories", "poi_snapshot_at", "top5_basis"}
EXTRA_COLS = ["listing_node_id", "source", "data_quality_flags", "address_new", "address_old",
              "address_new_normalized", "address_old_normalized", "prev_posted_date", "prev_expiry_date",
              "prev_price_range", "images", "image_count"]
POI_COL = re.compile(r"^(?:nearest_)?(?:%s)_" % "|".join(CATS))
BOOL_NODE_COLS = {"pool", "gym", "park", "bbq", "kids_playground", "sports_court", "security_24h", "reception",
                  "elevator", "parking", "river_view", "park_view", "city_view", "balcony", "garden", "garage",
                  "terrace"}


# --------------------------------------------------------------------------- helpers
def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames)


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(text):
    """Lowercase ASCII with single spaces; matches the legacy *_normalized columns."""
    text = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(text):
    return norm(text).replace(" ", "-")


def is_poi_col(col):
    # park_view only looks like a park_* POI column; it is a listing attribute.
    return col != "park_view" and (bool(POI_COL.match(col)) or col.startswith("within_") or col in POI_STAMP_COLS)


def valid_xy(row):
    try:
        return float(row["latitude"]), float(row["longitude"])
    except (KeyError, TypeError, ValueError):
        return None


def sphere(latlon):
    a = np.radians(np.asarray(latlon, float))
    return np.column_stack((np.cos(a[:, 0]) * np.cos(a[:, 1]), np.cos(a[:, 0]) * np.sin(a[:, 1]), np.sin(a[:, 0])))


def iso_date(value):
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value or "")
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else (value or "")


def as_bool_text(value):
    v = str(value or "").strip().lower()
    return "true" if v in ("1", "true", "yes") else "false" if v in ("0", "false", "no") else ""


# --------------------------------------------------------------------------- images
def scan_images(listing_ids):
    """Index images/ (main folder plus 'images N' parts) by listing id and classify file content."""
    entries, excluded = collections.defaultdict(list), []
    sniff = collections.Counter()
    for dirpath, _, files in os.walk(IMAGES):
        for name in files:
            if not name.lower().endswith(".jpg"):
                continue
            path = Path(dirpath) / name
            parts = path.relative_to(IMAGES).parts
            group = "main"
            if parts[0].startswith("images "):
                group, parts = parts[0], parts[1:]
            if len(parts) != 4:
                excluded.append((str(path), "unexpected_depth"))
                continue
            kind = classify_image(path)
            sniff[kind] += 1
            lid = parts[2]
            if kind in ("jpeg_truncated", "unknown"):
                excluded.append((str(path.relative_to(REPO)), kind))
            elif lid not in listing_ids:
                excluded.append((str(path.relative_to(REPO)), "listing_not_in_v3"))
            else:
                entries[lid].append({"listing_id": lid, "key": "images/" + "/".join(parts), "group": group,
                                     "local_path": str(path.relative_to(REPO)), "detected_type": kind,
                                     "size_bytes": path.stat().st_size})
    keys = collections.Counter(e["key"] for v in entries.values() for e in v)
    dup = [k for k, n in keys.items() if n > 1]
    if dup:
        raise SystemExit("duplicate image keys: %r" % dup[:3])
    for lid, items in entries.items():
        items.sort(key=lambda e: (e["group"] != "main", e["key"]))
    return entries, excluded, dict(sniff)


def classify_image(path):
    with open(path, "rb") as f:
        head = f.read(12)
        f.seek(-2, 2)
        tail = f.read(2)
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg" if tail == b"\xff\xd9" else "jpeg_truncated"
    if head[:4] == b"\x89PNG":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return "unknown"


# --------------------------------------------------------------------------- assemble
def assemble(_args):
    WORK.mkdir(parents=True, exist_ok=True)
    new_rows, f_new = read_csv(NEWG / "listings_osm_osrm_enriched.csv")
    prior_rows, f_prior = read_csv(NEW / "prior" / "listings_209cols_osm_cache_enriched.csv")
    new_edges, _ = read_csv(NEWG / "listing_amenity_top5_edges.csv")
    pois, _ = read_csv(NEWG / "osm_poi_nodes.csv")
    final_rows, _ = read_csv(LEGACY_FINAL)
    old_master, _ = read_csv(OLD / "Final_Data_graph_ready_filtered.csv")
    stamp = json.loads((NEWG / "summary.json").read_text())["osm_snapshot_at"]
    report = {"osm_snapshot_at": stamp}

    # ---- legacy side: one row per listing_id (the duplicate_index=1 record)
    legacy_final = {}
    for r in final_rows:
        legacy_final.setdefault(r["listing_id"], r)
    legacy = {r["listing_id"]: r for r in old_master if r["duplicate_index"] == "1"}
    assert set(legacy) == set(legacy_final), "legacy id sets differ"
    dup_title_mismatch = [i for i in legacy if legacy[i]["title"] != legacy_final[i]["title"]]
    report["legacy_rows"] = len(final_rows)
    report["legacy_unique"] = len(legacy)
    report["legacy_duplicate_ids_collapsed"] = len(final_rows) - len(legacy)
    report["legacy_title_mismatch_between_final_and_graph"] = len(dup_title_mismatch)

    # ---- new side: restore listing attributes the live builder wiped by prefix
    prior_by = {r["listing_id"]: r for r in prior_rows}
    restored = []
    for col in f_prior:
        if col in f_new and not is_poi_col(col):
            live_any = any(r[col].strip() for r in new_rows)
            prior_any = any(r[col].strip() for r in prior_rows)
            if prior_any and not live_any:
                restored.append(col)
                for r in new_rows:
                    r[col] = prior_by[r["listing_id"]][col]
    report["restored_columns_wiped_in_live_package"] = restored

    fields = list(f_new)
    for col in [h.split(":")[0] for h in read_csv(OLD / "neo4j_listing_nodes.csv")[1]] + EXTRA_COLS:
        if col and col not in fields:
            fields.append(col)

    # ---- build rows
    new_by = {r["listing_id"]: r for r in new_rows}
    rows = {}
    for lid, src in new_by.items():
        row = dict.fromkeys(fields, "")
        row.update(src)
        row["source"] = "both" if lid in legacy else "new"
        if lid in legacy:
            row["prev_posted_date"] = legacy_final[lid]["posted_date"]
            row["prev_expiry_date"] = legacy_final[lid]["expiry_date"]
            row["prev_price_range"] = legacy_final[lid]["price_range"]
        rows[lid] = row
    legacy_only = [i for i in legacy if i not in new_by]
    for lid in legacy_only:
        row = dict.fromkeys(fields, "")
        graph, base = legacy[lid], legacy_final[lid]
        for col, val in graph.items():
            if col in row and not is_poi_col(col) and val != "":
                row[col] = val
        for col, val in base.items():  # raw crawl columns win, as in the live package
            if col in row:
                row[col] = val
        flags = [t for t in re.split(r"[|;,]\s*", graph["data_quality_flags"]) if t and t != "duplicate_listing_id"]
        row["data_quality_flags"] = "|".join(flags)
        row["source"] = "old"
        row["street_name"] = row["road_name_final"]
        if row["ward_commune"] and row["geohash_7"]:
            row["location_graph_key"] = row["ward_commune"] + "|" + row["geohash_7"]
        rows[lid] = row
    for row in rows.values():
        lid = row["listing_id"]
        row["listing_node_id"] = lid
        row["address_new"] = row["address"]
        row["address_old"] = row["old_address"]
        if lid in legacy:
            row["address_new_normalized"] = legacy[lid]["address_new_normalized"]
            row["address_old_normalized"] = legacy[lid]["address_old_normalized"]
        else:
            row["address_new_normalized"] = norm(row["address"])
            row["address_old_normalized"] = norm(row["old_address"])
    report["address_normalizer_matches_legacy"] = "%d/%d" % (
        sum(norm(legacy[i]["address_new"]) == legacy[i]["address_new_normalized"] for i in legacy), len(legacy))
    order = sorted(rows, key=int)
    report["listings"] = {"total": len(rows), "new_only": sum(r["source"] == "new" for r in rows.values()),
                          "legacy_only": len(legacy_only), "both": sum(r["source"] == "both" for r in rows.values())}

    # ---- 150 m clusters recomputed on the union (single linkage, as the sources do)
    located = [i for i in order if valid_xy(rows[i])]
    xy = np.array([valid_xy(rows[i]) for i in located])
    pts = np.column_stack(((xy[:, 1] - 106.7) * 111320 * math.cos(math.radians(10.8)), (xy[:, 0] - 10.8) * 110574))
    parent = list(range(len(located)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, j in cKDTree(pts).query_pairs(CLUSTER_M):
        parent[find(i)] = find(j)
    comps = collections.defaultdict(list)
    for idx in range(len(located)):
        comps[find(idx)].append(idx)
    clusters = []
    for number, members in enumerate(sorted(comps.values(), key=lambda m: min(int(located[i]) for i in m)), 1):
        cid = "G%04d" % number
        ids = [located[i] for i in members]
        for lid in ids:
            rows[lid]["geo_cluster_150m"] = cid
            rows[lid]["geo_cluster_size"] = str(len(ids))
        mean = xy[members].mean(axis=0)
        gh6 = collections.Counter(rows[i]["geohash_6"] for i in ids if rows[i]["geohash_6"]).most_common(1)
        gh7 = collections.Counter(rows[i]["geohash_7"] for i in ids if rows[i]["geohash_7"]).most_common(1)
        clusters.append({"cluster_id": cid, "centroid_latitude": round(float(mean[0]), 7),
                         "centroid_longitude": round(float(mean[1]), 7), "listing_count": len(ids),
                         "representative_geohash_6": gh6[0][0] if gh6 else "",
                         "representative_geohash_7": gh7[0][0] if gh7 else "", "members": ids})
    located_set = set(located)
    for lid in order:
        if lid not in located_set:
            rows[lid]["geo_cluster_150m"] = rows[lid]["geo_cluster_size"] = ""
    report["clusters"] = {"listings_clustered": len(located), "clusters": len(clusters),
                          "singletons": sum(c["listing_count"] == 1 for c in clusters)}

    # ---- Top-5 for legacy-only listings against the live catalog
    poi_by = {p["osm_id"]: p for p in pois}
    edges = []
    targets = [i for i in legacy_only if valid_xy(rows[i])]
    xyz = sphere([valid_xy(rows[i]) for i in targets])
    for cat in CATS:
        arr = [p for p in pois if cat in p["category"].split("|")]
        tree = cKDTree(sphere([[float(p["latitude"]), float(p["longitude"])] for p in arr]))
        dd, ii = tree.query(xyz, k=min(5, len(arr)))
        dd, ii = np.atleast_2d(dd), np.atleast_2d(ii)
        for n, lid in enumerate(targets):
            for rank, (chord, idx) in enumerate(zip(dd[n], ii[n]), 1):
                km = 12742 * math.asin(min(1, float(chord) / 2))
                if km > RADIUS[cat]:
                    continue
                edges.append({"listing_node_id": lid, "osm_id": arr[int(idx)]["osm_id"], "category": cat,
                              "rank": rank, "straight_line_km": round(km, 6), "driving_distance_km": "",
                              "driving_duration_min": "", "route_source": "", "route_status": "pending",
                              "source_snap_m": "", "destination_snap_m": "", "route_enriched_at": "",
                              "poi_data_source": arr[int(idx)]["source"], "osm_snapshot_at": stamp,
                              "coordinate_status": rows[lid]["coordinate_status"]})
    report["legacy_only_edges"] = {"listings_with_coordinates": len(targets), "edges": len(edges),
                                   "listings_without_coordinates": len(legacy_only) - len(targets)}

    # ---- administrative structure (canonical ids; the legacy ids dropped 'đ' from slugs)
    admin = build_admin(rows, legacy, new_rows, report)

    # ---- images
    entries, excluded, sniff = scan_images(set(rows))
    for lid, row in rows.items():
        keys = [e["key"] for e in entries.get(lid, [])]
        row["images"] = json.dumps(keys, ensure_ascii=False)
        row["image_count"] = str(len(keys))
    report["images"] = {"files_indexed": sum(len(v) for v in entries.values()), "content_types": sniff,
                        "listings_with_images": len(entries), "listings_without_images": len(rows) - len(entries),
                        "excluded_files": len(excluded)}
    manifest = [e for lid in order for e in entries.get(lid, [])]

    with open(ASSEMBLED, "wb") as f:
        pickle.dump({"fields": fields, "rows": [rows[i] for i in order], "legacy_only": legacy_only,
                     "edges_legacy_only": edges, "new_edges": new_edges, "pois": pois, "clusters": clusters,
                     "admin": admin, "manifest": manifest, "excluded_images": excluded, "stamp": stamp,
                     "report": report, "legacy_prev": {i: legacy_final[i] for i in legacy if i in new_by}}, f)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def ward_key(row):
    """Canonical ward id from the master columns (ascii slug that keeps 'd' for 'đ')."""
    name, kind = row.get("ward_commune_name", ""), row.get("ward_commune_type", "")
    if not name or not kind or not row.get("city_province"):
        return ""
    return "ward|%s|%s" % (slug(row["city_province"]), slug(kind + " " + name))


def build_admin(rows, legacy, new_rows, report):
    old_nodes, _ = read_csv(OLD / "neo4j_listing_nodes.csv")
    node_listing = {r["listing_node_id:ID(Listing)"]: r["listing_id:string"] for r in old_nodes
                    if r["duplicate_index:int"] == "1"}
    old_wards = {r["ward_id:ID(Ward)"]: r for r in read_csv(OLD / "neo4j_ward_nodes.csv")[0]}
    new_wards = {r["ward_id:ID(Ward)"]: r for r in read_csv(NEWG / "neo4j_ward_nodes.csv")[0]}
    old_former = {r["former_area_id:ID(FormerAdminArea)"]: r for r in read_csv(OLD / "neo4j_former_admin_area_nodes.csv")[0]}
    new_former = {r["former_area_id:ID(FormerAdminArea)"]: r for r in read_csv(NEWG / "neo4j_former_admin_area_nodes.csv")[0]}

    def ward_canon(wid, source):
        if source == "new":
            name = new_wards[wid]["name:string"]
            return "ward|%s|%s" % (slug(new_wards[wid]["city_province:string"]), slug(name))
        row = old_wards[wid]
        return "ward|%s|%s" % (slug(row["city_province:string"]), slug(row["ward_type:string"] + " " + row["name:string"]))

    def former_canon(fid, source):
        row = (new_former if source == "new" else old_former)[fid]
        return "former-area|%s|%s" % (slug(row["former_city_province:string"]), slug(row["name:string"]))

    # the canonical formula must reproduce the new package ids, otherwise the merge key is unsafe
    report["canonical_ids_reproduce_new_package"] = {
        "wards": "%d/%d" % (sum(ward_canon(i, "new") == i for i in new_wards), len(new_wards)),
        "former_areas": "%d/%d" % (sum(former_canon(i, "new") == i for i in new_former), len(new_former))}

    ward_of, former_of = {}, {}
    for r in read_csv(OLD / "neo4j_listing_in_ward_relationships.csv")[0]:
        lid = node_listing.get(r[":START_ID(Listing)"])
        if lid:
            ward_of[lid] = ward_canon(r[":END_ID(Ward)"], "old")
    for r in read_csv(OLD / "neo4j_listing_in_former_area_relationships.csv")[0]:
        lid = node_listing.get(r[":START_ID(Listing)"])
        if lid:
            former_of[lid] = former_canon(r[":END_ID(FormerAdminArea)"], "old")
    for r in read_csv(NEWG / "neo4j_listing_ward_edges.csv")[0]:
        ward_of[r[":START_ID(Listing)"]] = ward_canon(r[":END_ID(Ward)"], "new")
    for r in read_csv(NEWG / "neo4j_listing_former_area_edges.csv")[0]:
        former_of[r[":START_ID(Listing)"]] = former_canon(r[":END_ID(FormerAdminArea)"], "new")
    missing_ward = [i for i in rows if i not in ward_of]
    missing_former = [i for i in rows if i not in former_of]
    report["admin"] = {"listings_without_ward": len(missing_ward), "listings_without_former_area": len(missing_former),
                       "legacy_ward_ids": len(old_wards), "new_ward_ids": len(new_wards),
                       "ward_ids_merged_by_canonical_form": len({ward_canon(i, "old") for i in old_wards}
                                                                | {ward_canon(i, "new") for i in new_wards}),
                       "former_ids_merged_by_canonical_form": len({former_canon(i, "old") for i in old_former}
                                                                  | {former_canon(i, "new") for i in new_former})}
    old_ward_rows = {ward_canon(i, "old"): r for i, r in old_wards.items()}
    new_ward_rows = {ward_canon(i, "new"): r for i, r in new_wards.items()}
    old_former_rows = {former_canon(i, "old"): r for i, r in old_former.items()}
    new_former_rows = {former_canon(i, "new"): r for i, r in new_former.items()}
    return {"ward_of": ward_of, "former_of": former_of, "old_ward_rows": old_ward_rows,
            "new_ward_rows": new_ward_rows, "old_former_rows": old_former_rows, "new_former_rows": new_former_rows}


# --------------------------------------------------------------------------- route
def routing_groups(edges, rows_by_id, poi_xy):
    """Group legacy-only edges into bounded OSRM table requests (same scheme as the live package)."""
    by_listing = collections.defaultdict(list)
    for e in edges:
        by_listing[e["listing_node_id"]].append(e)
    origins, coord_of = {}, {}
    for lid in by_listing:
        r = rows_by_id[lid]
        c = (float(r["longitude"]), float(r["latitude"]))
        origins.setdefault(c, []).append(lid)
        coord_of[lid] = c

    def morton(c):
        x, y, v = int((c[0] - 106) * 100000), int((c[1] - 10) * 100000), 0
        for bit in range(20):
            v |= ((x >> bit) & 1) << (2 * bit)
            v |= ((y >> bit) & 1) << (2 * bit + 1)
        return v

    groups, src, dest = [], [], set()
    for c in sorted(origins, key=morton):
        target = {e["osm_id"] for lid in origins[c] for e in by_listing[lid]}
        merged = dest | target
        if src and (len(src) + 1 + len(merged) > OSRM_MAX_COORDS or len(src) >= OSRM_MAX_SOURCES):
            groups.append((src, sorted(dest)))
            src, dest, merged = [], set(), target
        src.append(c)
        dest = merged
    if src:
        groups.append((src, sorted(dest)))
    return groups, coord_of


def matrix_request(endpoint, src, dest, poi_xy):
    coords = src + [poi_xy[p] for p in dest]
    parts = ";".join("%.8f,%.8f" % (lo, la) for lo, la in coords)
    params = urllib.parse.urlencode({"sources": ";".join(map(str, range(len(src)))),
                                     "destinations": ";".join(map(str, range(len(src), len(coords)))),
                                     "annotations": "distance,duration", "generate_hints": "false"})
    url = endpoint.rstrip("/") + "/table/v1/driving/" + parts + "?" + params
    return url, CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")


class RateLimited(Exception):
    pass


USER_AGENT = "RealEstatePOIEnrichment/1.0 (one-off academic spatial analysis; cached sequential matrices)"


def fetch_json(url):
    """GET through curl: system Python on macOS (LibreSSL 2.8) cannot complete TLS with some hosts."""
    proc = subprocess.run(["curl", "-sS", "-m", "60", "-A", USER_AGENT, "-H", "Accept: application/json",
                           "-w", "\n%{http_code}", url], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("curl exit %d: %s" % (proc.returncode, proc.stderr.strip()[:200]))
    body, _, status = proc.stdout.rpartition("\n")
    if status in ("403", "429"):
        raise RateLimited("HTTP " + status)
    if status != "200":
        raise RuntimeError("HTTP %s: %s" % (status, body[:200]))
    return json.loads(body)


def load_assembled():
    with open(ASSEMBLED, "rb") as f:
        return pickle.load(f)


def route(args):
    state = load_assembled()
    rows_by_id = {r["listing_id"]: r for r in state["rows"]}
    poi_xy = {p["osm_id"]: (float(p["longitude"]), float(p["latitude"])) for p in state["pois"]}
    groups, _ = routing_groups(state["edges_legacy_only"], rows_by_id, poi_xy)
    host = urllib.parse.urlsplit(args.osrm_url).hostname
    print("matrix_batches", len(groups), "edges", len(state["edges_legacy_only"]), flush=True)
    if args.plan:
        return
    if host not in ("localhost", "127.0.0.1", "::1") and not args.allow_coordinate_transfer:
        raise SystemExit("External routing sends listing and POI coordinates to %s. "
                         "Re-run with --allow-coordinate-transfer once that is authorised." % host)
    CACHE.mkdir(parents=True, exist_ok=True)
    requested = cached = 0
    for gi, (src, dest) in enumerate(groups):
        url, fp = matrix_request(args.osrm_url, src, dest, poi_xy)
        if fp.exists():
            cached += 1
            continue
        if requested >= args.max_requests:
            break
        data = None
        for attempt in range(2):
            try:
                data = fetch_json(url)
                if data.get("code") != "Ok":
                    raise ValueError(str(data)[:200])
                break
            except Exception as exc:  # noqa: BLE001 - report and decide below
                print("matrix_error", gi + 1, "attempt", attempt + 1, repr(exc), flush=True)
                data = None
                if isinstance(exc, RateLimited):
                    break
                time.sleep(5)
        if data is None:
            print("Stopping after persistent service failure; completed matrices are cached.", flush=True)
            return
        record = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "endpoint": args.osrm_url, "response": data}
        tmp = fp.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False))
        tmp.replace(fp)
        requested += 1
        if requested % 10 == 0:
            print("progress", gi + 1, "/", len(groups), "new", requested, "cached", cached, flush=True)
        time.sleep(max(2.0, args.delay))
    print("done new_requests", requested, "cached", cached, "batches", len(groups), flush=True)


# --------------------------------------------------------------------------- finalize
def apply_routes(state, endpoint):
    rows_by_id = {r["listing_id"]: r for r in state["rows"]}
    poi_xy = {p["osm_id"]: (float(p["longitude"]), float(p["latitude"])) for p in state["pois"]}
    edges = state["edges_legacy_only"]
    groups, coord_of = routing_groups(edges, rows_by_id, poi_xy)
    answers, missing = {}, 0
    for src, dest in groups:
        _, fp = matrix_request(endpoint, src, dest, poi_xy)
        if not fp.exists():
            missing += 1
            continue
        record = json.loads(fp.read_text())
        data, stamp = record["response"], record["fetched_at"]
        for si, c in enumerate(src):
            for di, oid in enumerate(dest):
                dist, dur = data["distances"][si][di], data["durations"][si][di]
                s_snap, d_snap = data["sources"][si]["distance"], data["destinations"][di]["distance"]
                status = "unreachable" if dist is None or dur is None else "snapped_far" if max(s_snap, d_snap) > 500 else "ok"
                answers[(c, oid)] = {"driving_distance_km": round(dist / 1000, 6) if dist is not None else "",
                                     "driving_duration_min": round(dur / 60, 4) if dur is not None else "",
                                     "route_status": status, "route_source": "OSRM_driving_live_table",
                                     "source_snap_m": round(s_snap, 2), "destination_snap_m": round(d_snap, 2),
                                     "route_enriched_at": stamp}
    for e in edges:
        ans = answers.get((coord_of[e["listing_node_id"]], e["osm_id"]))
        if ans:
            e.update(ans)
    return missing, len(groups)


def fill_poi_fields(row, edges, poi_by, stamp):
    """Rank-1 summary columns of the master row, same definitions as the live package."""
    rank1 = {e["category"]: e for e in edges if int(e["rank"]) == 1}
    flags, times, present = [], [], []
    for cat in CATS:
        e = rank1.get(cat)
        row[cat + "_route_status"] = (e["route_status"] if e else "coordinate_review"
                                      if not valid_xy(row) else "no_poi_within_radius")
        row[cat + "_source_snap_m"] = e["source_snap_m"] if e else ""
        row[cat + "_destination_snap_m"] = e["destination_snap_m"] if e else ""
        if e:
            p = poi_by[e["osm_id"]]
            present.append(cat)
            for dest, key in [("name", "name"), ("osm_id", "osm_id"), ("latitude", "latitude"),
                              ("longitude", "longitude"), ("street", "street"), ("address_osm", "address"),
                              ("operator", "operator")]:
                row["nearest_%s_%s" % (cat, dest)] = p[key]
            row["nearest_%s_street_source" % cat] = "OpenStreetMap_live_tags" if p["street"] else ""
            row[cat + "_straight_line_km"] = e["straight_line_km"]
            row[cat + "_data_source"] = p["source"]
            if e["route_source"]:
                for key in ("driving_distance_km", "driving_duration_min", "route_source"):
                    row["%s_%s" % (cat, key)] = e[key]
                times.append(e["route_enriched_at"])
        if cat in LIMITS:
            field = "within_%s_%dkm_driving" % (cat, LIMITS[cat])
            row[field] = ""
            if e and e["route_status"] == "ok":
                row[field] = int(float(e["driving_distance_km"]) <= LIMITS[cat])
                flags.append(row[field])
    row["amenity_types_within_threshold_count"] = sum(flags) if len(flags) == len(LIMITS) else ""
    row["amenities_travel_enriched_at"] = row["travel_enriched_at"] = max(times) if times else ""
    row["nearby_category_count"] = len(present)
    row["nearby_categories"] = "|".join(present)
    row["poi_snapshot_at"] = stamp
    row["top5_basis"] = "haversine_within_category_radius"


def finalize(args):
    state = load_assembled()
    rows, fields, pois, stamp = state["rows"], state["fields"], state["pois"], state["stamp"]
    poi_by = {p["osm_id"]: p for p in pois}
    missing, batches = apply_routes(state, args.osrm_url)
    by_listing = collections.defaultdict(list)
    for e in state["edges_legacy_only"]:
        by_listing[e["listing_node_id"]].append(e)
    for row in rows:
        if row["source"] == "old":
            fill_poi_fields(row, by_listing.get(row["listing_id"], []), poi_by, stamp)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)

    # ---- edges: package edges verbatim for live listings, recomputed edges for legacy-only
    edge_fields = ["listing_node_id", "osm_id", "category", "rank", "straight_line_km", "driving_distance_km",
                   "driving_duration_min", "route_source", "route_status", "source_snap_m", "destination_snap_m",
                   "route_enriched_at", "poi_data_source", "osm_snapshot_at", "coordinate_status", "origin"]
    all_edges = [dict(e, origin="live_package") for e in state["new_edges"]]
    all_edges += [dict(e, origin="v3_recomputed") for e in state["edges_legacy_only"]]
    all_edges.sort(key=lambda e: (int(e["listing_node_id"]), e["category"], int(e["rank"])))

    write_csv(V3 / "master_v3.csv", rows, fields)
    write_csv(V3 / "listing_amenity_top5_edges.csv", all_edges, edge_fields)
    write_csv(V3 / "osm_poi_nodes.csv", pois, list(pois[0]))
    write_csv(V3 / "images_manifest.csv", state["manifest"],
              ["listing_id", "key", "group", "local_path", "detected_type", "size_bytes"])
    write_csv(REPORTS / "excluded_images.csv", [{"path": p, "reason": r} for p, r in state["excluded_images"]],
              ["path", "reason"])
    write_graph(state, rows, all_edges, pois)
    overlap_report(state, rows)
    write_report(state, rows, all_edges, missing, batches)


def write_graph(state, rows, all_edges, pois):
    admin = state["admin"]
    by_id = {r["listing_id"]: r for r in rows}

    # listings (header identical to the legacy node file so import_search_graph.cypher reads every property)
    header = read_csv(OLD / "neo4j_listing_nodes.csv")[1]
    nodes = []
    for r in rows:
        out = {}
        for h in header:
            col = h.split(":")[0]
            if h == "listing_node_id:ID(Listing)":
                out[h] = r["listing_id"]
            elif h == ":LABEL":
                out[h] = "Listing"
            elif h == "duplicate_index:int":
                out[h] = "1"
            elif h.endswith(":boolean"):
                out[h] = as_bool_text(r.get(col))
            elif h.endswith(":date"):
                out[h] = iso_date(r.get(col))
            else:
                out[h] = r.get(col, "")
        nodes.append(out)
    write_csv(GRAPH / "neo4j_listing_nodes.csv", nodes, header)

    amen_header = ["amenity_id:ID(Amenity)", "name:string", "category:string", "subtype:string", "latitude:float",
                   "longitude:float", "street:string", "address:string", "operator:string", "source:string",
                   "osm_snapshot_at:string", "coordinate_method:string", ":LABEL"]
    labels = dict(zip(CATS, ["Hospital", "School", "CollegeUniversity", "MetroStation", "Mall", "Market",
                             "Supermarket", "Park", "BusStop"]))
    amen = [{"amenity_id:ID(Amenity)": p["osm_id"], "name:string": p["name"], "category:string": p["category"],
             "subtype:string": p["subtype"], "latitude:float": p["latitude"], "longitude:float": p["longitude"],
             "street:string": p["street"], "address:string": p["address"], "operator:string": p["operator"],
             "source:string": p["source"], "osm_snapshot_at:string": p["osm_snapshot_at"],
             "coordinate_method:string": p["coordinate_method"],
             ":LABEL": ";".join(["Amenity"] + [labels[c] for c in p["category"].split("|")])} for p in pois]
    write_csv(GRAPH / "neo4j_amenity_nodes.csv", amen, amen_header)

    edge_header = [":START_ID(Listing)", ":END_ID(Amenity)", "category:string", "rank:int", "is_nearest:boolean",
                   "straight_line_km:float", "driving_distance_km:float", "driving_duration_min:float",
                   "within_threshold:boolean", "threshold_km:float", "route_source:string", "route_status:string",
                   "source_snap_m:float", "destination_snap_m:float", "route_enriched_at:string",
                   "osm_snapshot_at:string", ":TYPE"]
    rel = []
    for e in all_edges:
        limit = LIMITS.get(e["category"])
        within = ""
        if limit and e["route_status"] == "ok" and e["driving_distance_km"] != "":
            within = "true" if float(e["driving_distance_km"]) <= limit else "false"
        rel.append({":START_ID(Listing)": e["listing_node_id"], ":END_ID(Amenity)": e["osm_id"],
                    "category:string": e["category"], "rank:int": e["rank"],
                    "is_nearest:boolean": "true" if int(e["rank"]) == 1 else "false",
                    "straight_line_km:float": e["straight_line_km"], "driving_distance_km:float": e["driving_distance_km"],
                    "driving_duration_min:float": e["driving_duration_min"], "within_threshold:boolean": within,
                    "threshold_km:float": limit if limit else "", "route_source:string": e["route_source"],
                    "route_status:string": e["route_status"], "source_snap_m:float": e["source_snap_m"],
                    "destination_snap_m:float": e["destination_snap_m"], "route_enriched_at:string": e["route_enriched_at"],
                    "osm_snapshot_at:string": e["osm_snapshot_at"], ":TYPE": "NEAR_AMENITY"})
    write_csv(GRAPH / "neo4j_listing_near_amenity_relationships.csv", rel, edge_header)

    # wards / former areas
    ward_of, former_of = admin["ward_of"], admin["former_of"]
    used_wards = sorted({ward_of[i] for i in by_id if i in ward_of})
    exemplar = {}
    for r in rows:
        exemplar.setdefault(ward_of.get(r["listing_id"]), r)
    ward_header = ["ward_id:ID(Ward)", "name:string", "normalized_name:string", "aliases:string", "ward_type:string",
                   "city_province:string", ":LABEL"]
    ward_rows, generated_wards = [], 0
    for wid in used_wards:
        if wid in admin["old_ward_rows"]:
            o = admin["old_ward_rows"][wid]
            ward_rows.append({"ward_id:ID(Ward)": wid, "name:string": o["name:string"],
                              "normalized_name:string": o["normalized_name:string"], "aliases:string": o["aliases:string"],
                              "ward_type:string": o["ward_type:string"], "city_province:string": o["city_province:string"],
                              ":LABEL": "Ward"})
            continue
        generated_wards += 1
        r = exemplar[wid]
        name, kind, city = r["ward_commune_name"], r["ward_commune_type"], r["city_province"]
        nn = norm(name)
        aliases = list(dict.fromkeys([name, nn, nn.replace("d", "") if "đ" in name.lower() else nn,
                                      "%s, %s" % (name, city), "%s %s" % (nn, norm(city))]))
        ward_rows.append({"ward_id:ID(Ward)": wid, "name:string": name, "normalized_name:string": nn,
                          "aliases:string": "|".join(aliases), "ward_type:string": kind,
                          "city_province:string": city, ":LABEL": "Ward"})
    write_csv(GRAPH / "neo4j_ward_nodes.csv", ward_rows, ward_header)

    used_former = sorted({former_of[i] for i in by_id if i in former_of})
    listing_count = collections.Counter(former_of[i] for i in by_id if i in former_of)
    pair_count = collections.Counter((ward_of[i], former_of[i]) for i in by_id if i in ward_of and i in former_of)
    mapped_wards = collections.Counter(f for (_, f) in pair_count)
    former_header = ["former_area_id:ID(FormerAdminArea)", "name:string", "normalized_name:string", "area_type:string",
                     "former_city_province:string", "normalized_former_city_province:string", "old_address:string",
                     "aliases:string", "listing_count:int", "mapped_ward_count:int", ":LABEL"]
    former_rows, generated_former = [], 0
    for fid in used_former:
        if fid in admin["old_former_rows"]:
            o = dict(admin["old_former_rows"][fid])
        else:
            generated_former += 1
            n = admin["new_former_rows"][fid]
            name, prov = n["name:string"], n["former_city_province:string"]
            nn, np_ = norm(name), norm(prov)
            area_type = next((t for t in ("Thành Phố", "Thành phố", "Thị Xã", "Thị xã", "Quận", "Huyện", "Phường", "Xã")
                              if name.startswith(t)), "")
            old_addr = "%s, %s cũ" % (name, prov)
            aliases = [name, nn, name + " cũ", nn + " cu", "%s, %s" % (name, prov), "%s %s" % (nn, np_),
                       old_addr, "%s %s cu" % (nn, np_)]
            o = {"name:string": name, "normalized_name:string": nn, "area_type:string": area_type,
                 "former_city_province:string": prov, "normalized_former_city_province:string": np_,
                 "old_address:string": old_addr, "aliases:string": "|".join(dict.fromkeys(aliases))}
        o.update({"former_area_id:ID(FormerAdminArea)": fid, "listing_count:int": listing_count[fid],
                  "mapped_ward_count:int": mapped_wards[fid], ":LABEL": "FormerAdminArea"})
        former_rows.append(o)
    write_csv(GRAPH / "neo4j_former_admin_area_nodes.csv", former_rows, former_header)

    # streets (ids derived from canonical ward + normalised name, so the same street never splits)
    streets, on_street = {}, []
    for r in rows:
        wid, name = ward_of.get(r["listing_id"]), r["road_name_final"].strip()
        if not wid or not name:
            continue
        sid = "street|" + hashlib.sha1(("%s|%s" % (wid, norm(name))).encode()).hexdigest()[:14]
        streets.setdefault(sid, {"street_id:ID(Street)": sid, "name:string": name, "ward_id:string": wid,
                                 "city_province:string": r["city_province"], ":LABEL": "Street"})
        on_street.append({":START_ID(Listing)": r["listing_id"], ":END_ID(Street)": sid, ":TYPE": "ON_STREET"})
    write_csv(GRAPH / "neo4j_street_nodes.csv", list(streets.values()),
              ["street_id:ID(Street)", "name:string", "ward_id:string", "city_province:string", ":LABEL"])
    write_csv(GRAPH / "neo4j_listing_on_street_relationships.csv", on_street, [":START_ID(Listing)", ":END_ID(Street)", ":TYPE"])
    write_csv(GRAPH / "neo4j_street_in_ward_relationships.csv",
              [{":START_ID(Street)": s["street_id:ID(Street)"], ":END_ID(Ward)": s["ward_id:string"], ":TYPE": "IN_WARD"}
               for s in streets.values()], [":START_ID(Street)", ":END_ID(Ward)", ":TYPE"])

    # clusters
    write_csv(GRAPH / "neo4j_geo_cluster_nodes.csv",
              [{"cluster_id:ID(GeoCluster)": c["cluster_id"], "centroid_latitude:float": c["centroid_latitude"],
                "centroid_longitude:float": c["centroid_longitude"], "listing_count:int": c["listing_count"],
                "representative_geohash_6:string": c["representative_geohash_6"],
                "representative_geohash_7:string": c["representative_geohash_7"], ":LABEL": "GeoCluster"}
               for c in state["clusters"]],
              ["cluster_id:ID(GeoCluster)", "centroid_latitude:float", "centroid_longitude:float",
               "listing_count:int", "representative_geohash_6:string", "representative_geohash_7:string", ":LABEL"])
    write_csv(GRAPH / "neo4j_listing_in_cluster_relationships.csv",
              [{":START_ID(Listing)": r["listing_id"], ":END_ID(GeoCluster)": r["geo_cluster_150m"], ":TYPE": "IN_CLUSTER"}
               for r in rows if r["geo_cluster_150m"]], [":START_ID(Listing)", ":END_ID(GeoCluster)", ":TYPE"])

    write_csv(GRAPH / "neo4j_listing_in_ward_relationships.csv",
              [{":START_ID(Listing)": i, ":END_ID(Ward)": ward_of[i], ":TYPE": "IN_WARD"} for i in by_id if i in ward_of],
              [":START_ID(Listing)", ":END_ID(Ward)", ":TYPE"])
    write_csv(GRAPH / "neo4j_listing_in_former_area_relationships.csv",
              [{":START_ID(Listing)": i, ":END_ID(FormerAdminArea)": former_of[i], ":TYPE": "IN_FORMER_AREA"}
               for i in by_id if i in former_of], [":START_ID(Listing)", ":END_ID(FormerAdminArea)", ":TYPE"])
    write_csv(GRAPH / "neo4j_ward_mapped_from_former_area_relationships.csv",
              [{":START_ID(Ward)": w, ":END_ID(FormerAdminArea)": f, "supporting_listing_count:int": n,
                ":TYPE": "MAPPED_FROM"} for (w, f), n in sorted(pair_count.items())],
              [":START_ID(Ward)", ":END_ID(FormerAdminArea)", "supporting_listing_count:int", ":TYPE"])
    shutil.copyfile(Path(__file__).with_name("neo4j_post_import_setup.cypher"), GRAPH / "neo4j_post_import_setup.cypher")
    state["report"]["graph"] = {"listings": len(nodes), "amenities": len(amen), "near_amenity_edges": len(rel),
                                "wards": len(ward_rows), "wards_generated_for_new_only": generated_wards,
                                "former_areas": len(former_rows), "former_areas_generated_for_new_only": generated_former,
                                "streets": len(streets), "clusters": len(state["clusters"]),
                                "ward_former_mappings": len(pair_count)}


def overlap_report(state, rows):
    changed = []
    fields = ["posted_date", "expiry_date", "price_range", "area", "title", "description", "bedrooms", "bathrooms",
              "legal_status", "furnishing", "frontage", "access_road", "address", "latitude_longitude"]
    by_id = {r["listing_id"]: r for r in rows}
    for lid, old in state["legacy_prev"].items():
        new = by_id[lid]
        diff = [f for f in fields if (old.get(f, "") or "").strip() != (new.get(f, "") or "").strip()]
        changed.append({"listing_id": lid, "changed_fields": "|".join(diff),
                        "old_posted_date": old["posted_date"], "new_posted_date": new["posted_date"],
                        "old_expiry_date": old["expiry_date"], "new_expiry_date": new["expiry_date"],
                        "old_price_range": old["price_range"], "new_price_range": new["price_range"],
                        "old_area": old["area"], "new_area": new["area"]})
    write_csv(REPORTS / "overlap_changes.csv", changed, list(changed[0]))
    state["report"]["overlap"] = {"listings": len(changed),
                                  "price_changed": sum(c["old_price_range"] != c["new_price_range"] for c in changed),
                                  "area_changed": sum(c["old_area"] != c["new_area"] for c in changed)}


def write_report(state, rows, all_edges, missing, batches):
    report = state["report"]
    report["routes"] = {"legacy_only_batches": batches, "batches_without_cache": missing,
                        "edge_status": dict(collections.Counter(e["route_status"] for e in all_edges)),
                        "edges_by_origin": dict(collections.Counter(e["origin"] for e in all_edges))}
    report["listings_without_coordinates"] = sum(1 for r in rows if not valid_xy(r))
    report["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "merge_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- validate
def validate(_args):
    rows, _ = read_csv(V3 / "master_v3.csv")
    edges, _ = read_csv(V3 / "listing_amenity_top5_edges.csv")
    pois, _ = read_csv(V3 / "osm_poi_nodes.csv")
    manifest, _ = read_csv(V3 / "images_manifest.csv")
    checks = {}
    ids = [r["listing_id"] for r in rows]
    checks["listing_ids_unique"] = len(ids) == len(set(ids))
    poi_ids = {p["osm_id"] for p in pois}
    id_set = set(ids)
    checks["edge_endpoints_exist"] = all(e["listing_node_id"] in id_set and e["osm_id"] in poi_ids for e in edges)
    keys = [(e["listing_node_id"], e["osm_id"]) for e in edges]
    checks["no_duplicate_edges"] = len(keys) == len(set(keys))
    ranks = collections.defaultdict(list)
    for e in edges:
        ranks[(e["listing_node_id"], e["category"])].append(int(e["rank"]))
    checks["ranks_contiguous"] = all(sorted(v) == list(range(1, len(v) + 1)) for v in ranks.values())
    checks["edges_within_radius"] = all(float(e["straight_line_km"]) <= RADIUS[e["category"]] + 1e-6 for e in edges)
    checks["no_pending_routes"] = not any(e["route_status"] == "pending" for e in edges)
    checks["route_values_paired"] = all((e["driving_distance_km"] == "") == (e["driving_duration_min"] == "") for e in edges)
    xy = {r["listing_id"]: valid_xy(r) for r in rows}
    poi_xy = {p["osm_id"]: (float(p["latitude"]), float(p["longitude"])) for p in pois}
    bad = 0
    for e in edges:
        if e["origin"] != "v3_recomputed":
            continue
        a, b = xy[e["listing_node_id"]], poi_xy[e["osm_id"]]
        la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        bad += abs(12742 * math.asin(math.sqrt(h)) - float(e["straight_line_km"])) > 1e-3
    checks["recomputed_distances_match_haversine"] = bad == 0
    checks["images_exist_on_disk"] = all((REPO / m["local_path"]).exists() for m in manifest)
    checks["images_column_matches_manifest"] = sum(len(json.loads(r["images"])) for r in rows) == len(manifest)
    for name in ("neo4j_listing_nodes", "neo4j_ward_nodes", "neo4j_former_admin_area_nodes", "neo4j_street_nodes",
                 "neo4j_geo_cluster_nodes", "neo4j_amenity_nodes"):
        data, head = read_csv(GRAPH / (name + ".csv"))
        idcol = head[0]
        checks[name + "_ids_unique"] = len({r[idcol] for r in data}) == len(data)
    nodes = {r["listing_node_id:ID(Listing)"] for r in read_csv(GRAPH / "neo4j_listing_nodes.csv")[0]}
    wards = {r["ward_id:ID(Ward)"] for r in read_csv(GRAPH / "neo4j_ward_nodes.csv")[0]}
    former = {r["former_area_id:ID(FormerAdminArea)"] for r in read_csv(GRAPH / "neo4j_former_admin_area_nodes.csv")[0]}
    streets = {r["street_id:ID(Street)"] for r in read_csv(GRAPH / "neo4j_street_nodes.csv")[0]}
    clusters = {r["cluster_id:ID(GeoCluster)"] for r in read_csv(GRAPH / "neo4j_geo_cluster_nodes.csv")[0]}
    closure = {
        "listing_in_ward": ("neo4j_listing_in_ward_relationships.csv", nodes, wards),
        "listing_in_former": ("neo4j_listing_in_former_area_relationships.csv", nodes, former),
        "listing_on_street": ("neo4j_listing_on_street_relationships.csv", nodes, streets),
        "listing_in_cluster": ("neo4j_listing_in_cluster_relationships.csv", nodes, clusters),
        "street_in_ward": ("neo4j_street_in_ward_relationships.csv", streets, wards),
        "ward_from_former": ("neo4j_ward_mapped_from_former_area_relationships.csv", wards, former),
        "near_amenity": ("neo4j_listing_near_amenity_relationships.csv", nodes, poi_ids)}
    for key, (fname, left, right) in closure.items():
        data, head = read_csv(GRAPH / fname)
        checks["closure_" + key] = all(r[head[0]] in left and r[head[1]] in right for r in data)
    checks["every_listing_has_ward_and_former_area"] = (len(read_csv(GRAPH / "neo4j_listing_in_ward_relationships.csv")[0]) == len(ids)
                                                         and len(read_csv(GRAPH / "neo4j_listing_in_former_area_relationships.csv")[0]) == len(ids))
    result = {"passed": all(checks.values()), "checks": checks}
    (REPORTS / "validation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("assemble").set_defaults(func=assemble)
    r = sub.add_parser("route")
    r.add_argument("--osrm-url", default="http://localhost:5000")
    r.add_argument("--delay", type=float, default=2.0)
    r.add_argument("--max-requests", type=int, default=100000)
    r.add_argument("--plan", action="store_true", help="only print the number of OSRM requests needed")
    r.add_argument("--allow-coordinate-transfer", action="store_true")
    r.set_defaults(func=route)
    f = sub.add_parser("finalize")
    f.add_argument("--osrm-url", default="http://localhost:5000", help="must equal the endpoint used by 'route'")
    f.set_defaults(func=finalize)
    sub.add_parser("validate").set_defaults(func=validate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
