#!/usr/bin/env python3
"""Errata v3.1 for Data/v3 — data errors found while building the HCMRE-Q v2 benchmark.

Run from anywhere (paths are relative to this file):
    python Data/v3/pipeline/fix_v3_quality.py            # dry run: writes the report, changes no data
    python Data/v3/pipeline/fix_v3_quality.py --apply    # also patches the CSVs in place

Fixes (deterministic; every changed cell is listed in reports/v3_1_corrections.csv with its evidence):
  1. property_type  The 2026 crawl uses 5 fine-grained names; the app filters and ranks on the two
                    group names (backend/src/services/inference/normalization.py PROPERTY_TYPE_GROUP_MAP).
                    Mapped: Căn hộ chung cư -> Căn hộ; Nhà riêng, Nhà mặt phố, Nhà biệt thự, liền kề,
                    Shophouse, nhà phố thương mại -> Nhà đất. The fine name stays readable in `Folder`.
  2. ward swap      8 rows of the 2026 crawl hold the former district in `district` and the new ward in
                    `former_admin_area` (their ward_commune is the pre-2025 ward). Swapped back; the graph
                    rows of these listings (ward, former area, street) are rebuilt with build_v3.py's ids.
  3. area           '1.038' style thousands separator (= 1038 m²) when the text states that area;
                    one non-numeric value replaced by the area stated in the title.
  4. price_range    The 2026 crawler stored the FIRST amount of the title — also when it is a discount
                    ("Giảm 1 tỷ"), a rent ("HĐT 70 triệu"), a unit price ("53 triệu/m²") or an old price
                    ("18 tỷ về 15,7 tỷ") — and dropped the tail of "1 tỷ 750". Only rows of the 2026
                    crawl (source new/both) are audited; legacy prices agree with their own text (99.2%).
       R1 recover   stored price == crawler reading (price_text.crawler_value) of a non-price amount or of a
                    price whose tail was dropped AND the text states another price (price_text.stated_price)
                    AND that price is plausible -> the stated price.
       R2 unknown   stored price == crawler reading of a non-price amount (rent, unit price, discount,
                    down payment) AND the text states no price at all -> empty (NULL). When the text
                    states several prices the listing is decided by hand instead.
       manual       listings the rules cannot decide, read by hand (MANUAL_PRICE, with reasons).

Outputs (only when there is something to fix):
  reports/v3_1_corrections.csv     listing_id, field, old, new, rule, evidence
  patches/v3_1_postgres.sql        same changes for an already-loaded PostgreSQL (clears search_text and
                                   embedding of the changed rows; then run build_search_index.py backfill)
  patches/v3_1_neo4j.cypher        same changes for an already-loaded Neo4j
  with --apply: master_v3.csv, postgres/properties_v3.csv and graph/*.csv patched cell by cell (all other
  bytes unchanged). A second run finds nothing to fix and writes nothing.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_text import crawler_value, stated_price  # noqa: E402

csv.field_size_limit(sys.maxsize)
V3 = Path(__file__).resolve().parents[1]
GRAPH = V3 / "graph"

SHA256 = {  # master_v3.csv as published (commit 06741a2) and after this script
    "original": "d98518e74586e592aae7ff8533086f25e54a72a6c4311d416a7f7dea826014bd",
    "fixed": "5b65c94dabd25a89f4b878c7b8e84948bf86b51da4394513f1bda19e5e82942d",
}

PROPERTY_TYPE_GROUP = {
    "Căn hộ chung cư": "Căn hộ",
    "Nhà riêng": "Nhà đất",
    "Nhà mặt phố": "Nhà đất",
    "Nhà biệt thự, liền kề": "Nhà đất",
    "Shophouse, nhà phố thương mại": "Nhà đất",
}

STRONG_NON_PRICE = {"per_time", "per_area", "rent", "downpay", "promo"}
PLAUSIBLE_TRIEU_PER_M2 = (8.0, 2500.0)   # 0.1% / 99.9% of legacy listings: 13 / 2531
MIN_PRICE = 0.3                            # tỷ

# Decided by reading the listing. value None = price unknown (NULL); value "keep" = stored value is right.
MANUAL_PRICE = {
    46082917: (17.5, 'title "HĐT: 22tr/th, giá: 20 tỷ về 17,5 tỷ": 20 tỷ is the price before the cut'),
    46281578: (1.69, 'title "lỗ 400tr giá chỉ 1tỷ690": stored 1.0 drops the 690 triệu tail'),
    46325566: (1.7, 'title "giá gốc 2,1 tỷ bán còn 1,7 tỷ": 2,1 tỷ is the original price'),
    46330089: (5.55, 'title "giá còn 5 tỷ 550 TL": stored 5.0 drops the 550 triệu tail'),
    46334896: (4.99, 'title "giá 4 tỷ 990 TL": stored 4.0 drops the 990 triệu tail'),
    46281984: (13.7, 'description "Giá: 16.5 tỷ (còn TL) giảm 13,7 tỷ"; title "Giảm gần 3 tỷ" = 16.5 - 13.7'),
    45854337: (70.0, 'title "giá tốt hơn thị trường 5 tỷ" is a discount; description "30% là 21 tỷ ... tức 70 tỷ '
                     'cho lịch thanh toán vay" (65 tỷ only with accelerated payment)'),
    45569896: ("keep", 'title "Giảm sốc 7.9 tỷ - nhà HXH Tô Hiến Thành ... 68m2": 7.9 tỷ (116 triệu/m²) '
                       'is the price, not a 7.9 tỷ discount'),
    46054887: ("keep", 'title "Giảm sâu 135 tỷ! Tòa nhà ... hầm 10 tầng, 168,7 m²": 135 tỷ is the price'),
    43919030: (2.4, 'description "Giá cắt lỗ 400 triệu so với giá mua vào. Giá 2.4 tỷ (giá hời toà)"'),
    46320807: ("keep", 'title "chỉ từ 15,9 tỷ" (project starting price); "50 triệu" in the text is not a price'),
}

SWAP_FIELDS = ("district", "former_admin_area", "ward_commune", "ward_commune_type", "ward_commune_name",
               "location_graph_key")


# --------------------------------------------------------------------------- csv io (byte-preserving)
def read_table(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def write_table(path, header, rows):
    buf = io.StringIO(newline="")
    csv.writer(buf).writerows([header] + rows)          # default dialect == how build_v3.py wrote them
    Path(path).write_bytes(buf.getvalue().encode("utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fnum(value):
    return "" if value is None else repr(float(round(value, 4)))


def to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


# build_v3.py helpers (copied; checked below to reproduce every existing street id)
def norm_ascii(text):
    text = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(text):
    return norm_ascii(text).replace(" ", "-")


def street_id(ward_id, road_name):
    return "street|" + hashlib.sha1(("%s|%s" % (ward_id, norm_ascii(road_name))).encode()).hexdigest()[:14]


# --------------------------------------------------------------------------- audit
def area_from_text(text):
    """Areas stated as 'N m²' in the text; '1.038m²' also read as 1038."""
    out = []
    for m in re.finditer(r"(\d{1,5}(?:[.,]\d{1,3})?)\s*(?:m2|m²|mét vuông)", text or "", re.IGNORECASE):
        raw = m.group(1)
        out.append(float(raw.replace(",", ".")))
        if re.fullmatch(r"\d{1,3}[.,]\d{3}", raw):
            out.append(float(raw.replace(",", "").replace(".", "")))
    return out


def audit(header, rows):
    col = {h: i for i, h in enumerate(header)}
    fixes, review = [], []

    def add(lid, field, old, new, rule, evidence):
        fixes.append(dict(listing_id=lid, field=field, old=old, new=new, rule=rule, evidence=evidence))

    # spelling of each former district as the other listings write it ("Thành Phố Thủ Đức")
    spellings = collections.defaultdict(collections.Counter)
    for r in rows:
        spellings[slug(r[col["former_admin_area"]])][r[col["former_admin_area"]]] += 1

    for r in rows:
        lid = int(r[col["listing_id"]])
        source, title, desc = r[col["source"]], r[col["title"]], r[col["description"]]

        # 1. property_type
        pt = r[col["property_type"]]
        if pt in PROPERTY_TYPE_GROUP:
            add(lid, "property_type", pt, PROPERTY_TYPE_GROUP[pt], "property_type_group",
                "backend PROPERTY_TYPE_GROUP_MAP")

        # 2. ward / former district swapped
        district, former = r[col["district"]], r[col["former_admin_area"]]
        if not re.match(r"^(Phường|Xã|Đặc khu) ", district) and re.match(r"^(Phường|Xã|Đặc khu) ", former):
            kind, name = former.split(" ", 1)
            usual = spellings[slug(district)].most_common(1)
            new = {"district": former, "former_admin_area": usual[0][0] if usual else district, "ward_commune": former,
                   "ward_commune_type": kind, "ward_commune_name": name,
                   "location_graph_key": former + "|" + r[col["geohash_7"]]}
            for f in SWAP_FIELDS:
                if r[col[f]] != new[f]:
                    add(lid, f, r[col[f]], new[f], "ward_swap",
                        f"district held '{district}' (former district) and former_admin_area held '{former}' (ward)")

        # 3. area
        area_raw = r[col["area"]]
        area = to_float(area_raw)
        stated_areas = area_from_text(f"{title} . {desc}")
        if area is None and area_raw.strip():
            counts = collections.Counter(stated_areas)
            if counts:
                best = max(counts, key=lambda v: (counts[v], -v))
                add(lid, "area", area_raw, fnum(best), "area_non_numeric", f"area '{area_raw}'; text states {best} m²")
                area = best
        elif area is not None and area < 10 and any(abs(a - area * 1000) < 0.5 for a in stated_areas):
            add(lid, "area", area_raw, fnum(area * 1000), "area_thousands_separator",
                f"area {area_raw}; text states {area * 1000:g} m²")
            area *= 1000

        # 4. price
        if source not in ("new", "both"):
            continue
        p_raw = r[col["price_range"]]
        p = to_float(p_raw)
        tp, how, snip = stated_price(title, desc)
        cv, cv_field, cv_amount = crawler_value(title, desc)
        explained = cv is not None and p is not None and abs(cv - p) <= 0.0005 * max(p, 0.01) + 1e-9
        ppm2 = (lambda v: v * 1000 / area if (v is not None and area) else None)
        plausible = (lambda v: v is not None and v >= MIN_PRICE and
                     (ppm2(v) is None or PLAUSIBLE_TRIEU_PER_M2[0] <= ppm2(v) <= PLAUSIBLE_TRIEU_PER_M2[1]))
        if lid in MANUAL_PRICE:
            value, reason = MANUAL_PRICE[lid]
            if value == "keep":
                continue
            if (value is None) != (p is None) or (value is not None and abs(value - p) > 1e-9):
                add(lid, "price_range", p_raw, fnum(value), "price_manual", reason)
            continue
        if p is None:
            continue
        stated = cv_amount is not None and cv_amount["cls"] == "positive" and abs(cv_amount["value"] - p) < 1e-6
        if explained and stated:
            pass                                   # the crawler read a price the text does state: keep it
        elif explained and tp is not None and abs(tp - p) / p > 0.01:
            evidence = (f"stored {p:g} = crawler reading of '{cv_amount['raw']}' ({cv_amount['cls']}) in the "
                        f"{cv_field}; text states {tp:g} [{how}]: «{snip.strip()}»")
            if plausible(tp):
                add(lid, "price_range", p_raw, fnum(tp), "price_R1_recover", evidence)
            else:
                review.append((lid, "implausible stated price", evidence))
        elif explained and tp is None and how == "ambiguous" and cv_amount["cls"] in STRONG_NON_PRICE | {"discount"}:
            review.append((lid, "stored price is a non-price amount and the text states several prices",
                           f"stored {p:g} = '{cv_amount['raw']}' ({cv_amount['cls']}): «{cv_amount['snippet'].strip()}»"))
        elif explained and tp is None and cv_amount["cls"] in STRONG_NON_PRICE | {"discount"}:
            evidence = (f"stored {p:g} = '{cv_amount['raw']}' in the {cv_field}, a {cv_amount['cls']} amount: "
                        f"«{cv_amount['snippet'].strip()}»; no price stated")
            if cv_amount["cls"] in STRONG_NON_PRICE or p < 1 or not plausible(p):
                add(lid, "price_range", p_raw, "", "price_R2_unknown", evidence)
            else:
                review.append((lid, "discount-worded amount that may be the price", evidence))
        elif not explained and tp is not None and abs(tp - p) / p > 0.10:
            review.append((lid, "stored price differs from the stated price, crawler error not identified",
                           f"stored {p:g}; text states {tp:g} [{how}]: «{snip.strip()}»"))
    return fixes, review


# --------------------------------------------------------------------------- apply
def patch_rows(header, rows, key, changes, rename=None):
    """changes: {key value: {column: new}}; rename maps master column -> this file's column."""
    col = {h: i for i, h in enumerate(header)}
    k = col[key]
    hit = collections.Counter()
    for r in rows:
        for field, new in changes.get(r[k], {}).items():
            c = (rename or {}).get(field, field)
            if c in col:
                r[col[c]] = new
                hit[c] += 1
    return hit


def graph_admin(fixed_master_header, fixed_master_rows, swapped_ids):
    """Rebuild the ward / former-area / street rows of the swapped listings exactly as build_v3.py would."""
    mcol = {h: i for i, h in enumerate(fixed_master_header)}
    by_id = {r[mcol["listing_id"]]: r for r in fixed_master_rows}
    files = {name: read_table(GRAPH / name) for name in (
        "neo4j_ward_nodes.csv", "neo4j_former_admin_area_nodes.csv", "neo4j_street_nodes.csv",
        "neo4j_listing_in_ward_relationships.csv", "neo4j_listing_in_former_area_relationships.csv",
        "neo4j_listing_on_street_relationships.csv", "neo4j_street_in_ward_relationships.csv",
        "neo4j_ward_mapped_from_former_area_relationships.csv")}
    ward_of = {r[0]: r[1] for r in files["neo4j_listing_in_ward_relationships.csv"][1]}
    former_of = {r[0]: r[1] for r in files["neo4j_listing_in_former_area_relationships.csv"][1]}
    street_of = {r[0]: r[1] for r in files["neo4j_listing_on_street_relationships.csv"][1]}
    ward_nodes = {r[0]: r for r in files["neo4j_ward_nodes.csv"][1]}
    former_hdr, former_rows = files["neo4j_former_admin_area_nodes.csv"]
    former_nodes = {r[0]: r for r in former_rows}
    street_hdr, street_rows = files["neo4j_street_nodes.csv"]
    streets = {r[0]: r for r in street_rows}

    # the copied id formula must reproduce every existing street id
    bad = [lid for lid, sid in street_of.items() if street_id(ward_of[lid], by_id[lid][mcol["road_name_final"]]) != sid]
    if bad:
        raise SystemExit(f"street id formula does not reproduce build_v3.py for {len(bad)} listings, e.g. {bad[:3]}")
    if set(ward_nodes) != set(ward_of.values()) or set(former_nodes) != set(former_of.values()):
        raise SystemExit("ward/former-area node files contain unused nodes; this script expects build_v3.py output")

    log = []
    fc = {h: i for i, h in enumerate(former_hdr)}
    for lid in sorted(swapped_ids):
        r = by_id[lid]
        new_ward = "ward|%s|%s" % (slug(r[mcol["city_province"]]), slug(r[mcol["ward_commune_type"]] + " " +
                                                                        r[mcol["ward_commune_name"]]))
        if new_ward not in ward_nodes:
            raise SystemExit(f"{lid}: ward node {new_ward} does not exist")
        fid = "former-area|%s|%s" % (slug(r[mcol["city_province"]]), slug(r[mcol["former_admin_area"]]))  # build_v3 id
        if fid not in former_nodes:
            raise SystemExit(f"{lid}: former area node {fid} does not exist")
        cands = [fid]
        entry = dict(listing_id=lid, ward=(ward_of[lid], new_ward), former=(former_of[lid], cands[0]), street=None)
        ward_of[lid], former_of[lid] = new_ward, cands[0]
        road = r[mcol["road_name_final"]].strip()
        if lid in street_of and road:
            new_sid = street_id(new_ward, road)
            entry["street"] = (street_of[lid], new_sid)
            if new_sid not in streets:
                streets[new_sid] = [new_sid, road, new_ward, r[mcol["city_province"]], "Street"]
            street_of[lid] = new_sid
        log.append(entry)

    used_wards, used_former, used_streets = set(ward_of.values()), set(former_of.values()), set(street_of.values())
    out = {}
    hdr, rows = files["neo4j_ward_nodes.csv"]
    out["neo4j_ward_nodes.csv"] = (hdr, [r for r in rows if r[0] in used_wards])
    listing_count = collections.Counter(former_of.values())
    pair_count = collections.Counter((ward_of[i], former_of[i]) for i in ward_of if i in former_of)
    mapped = collections.Counter(f for (_, f) in pair_count)
    new_former = []
    for r in former_rows:
        if r[0] in used_former:
            r = list(r)
            r[fc["listing_count:int"]] = str(listing_count[r[0]])
            r[fc["mapped_ward_count:int"]] = str(mapped[r[0]])
            new_former.append(r)
    out["neo4j_former_admin_area_nodes.csv"] = (former_hdr, new_former)
    out["neo4j_street_nodes.csv"] = (street_hdr, [s for s in streets.values() if s[0] in used_streets])
    for name, mapping, typ in (("neo4j_listing_in_ward_relationships.csv", ward_of, "IN_WARD"),
                               ("neo4j_listing_in_former_area_relationships.csv", former_of, "IN_FORMER_AREA"),
                               ("neo4j_listing_on_street_relationships.csv", street_of, "ON_STREET")):
        hdr, rows = files[name]
        out[name] = (hdr, [[r[0], mapping[r[0]], typ] for r in rows])
    hdr, _ = files["neo4j_street_in_ward_relationships.csv"]
    out["neo4j_street_in_ward_relationships.csv"] = (hdr, [[s[0], s[2], "IN_WARD"] for s in out["neo4j_street_nodes.csv"][1]])
    hdr, _ = files["neo4j_ward_mapped_from_former_area_relationships.csv"]
    out["neo4j_ward_mapped_from_former_area_relationships.csv"] = (
        hdr, [[w, f, str(n), "MAPPED_FROM"] for (w, f), n in sorted(pair_count.items())])
    return out, files, log


# --------------------------------------------------------------------------- patches for loaded databases
def sql_literal(value):
    return "NULL" if value in ("", None) else "'" + str(value).replace("'", "''") + "'"


def write_sql(path, fixes):
    by_id = collections.defaultdict(dict)
    for f in fixes:
        if f["field"] in ("property_type", "price_range", "area", "district", "former_admin_area"):
            by_id[f["listing_id"]][f["field"]] = f["new"]
    lines = ["-- Errata v3.1 for a PostgreSQL loaded from Data/v3 (generated by Data/v3/pipeline/fix_v3_quality.py).",
             "-- psql -v ON_ERROR_STOP=1 -d real_estate -f v3_1_postgres.sql",
             "-- then rebuild search_text + embedding of the cleared rows:",
             "--   python scripts/build_search_index.py --skip-catalog-import --skip-graph-metadata",
             "BEGIN;"]
    for lid in sorted(by_id):
        sets = []
        for field, new in sorted(by_id[lid].items()):
            cast = "::double precision" if field in ("price_range", "area") and new != "" else ""
            sets.append(f"{field} = {sql_literal(new)}{cast}")
        sets += ["search_text = NULL", "search_text_version = NULL", "embedding = NULL", "embedding_model = NULL",
                 "updated_at = now()"]
        lines.append(f"UPDATE properties SET {', '.join(sets)} WHERE listing_id = {lid};")
    lines += ["COMMIT;", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return len(by_id)


def cypher_value(field, new):
    if new == "":
        return "null"
    if field in ("price_range", "area"):
        return repr(float(new))
    return json.dumps(new, ensure_ascii=False)


def write_cypher(path, fixes, admin_log):
    node_fields = {"property_type": "property_type", "price_range": "price_range", "area": "area",
                   "ward_commune": "ward_commune", "ward_commune_type": "ward_commune_type",
                   "ward_commune_name": "ward_commune_name", "former_admin_area": "former_admin_area"}
    groups = collections.defaultdict(list)
    for f in fixes:
        if f["field"] in node_fields and f["field"] != "property_type":
            groups[f["field"]].append((str(f["listing_id"]), f["new"]))
    lines = ["// Errata v3.1 for a Neo4j loaded from Data/v3/graph (generated by fix_v3_quality.py).",
             "// cypher-shell -f v3_1_neo4j.cypher   — idempotent; a fresh import of the patched CSVs needs none of it.",
             ""]
    for old, new in sorted(PROPERTY_TYPE_GROUP.items()):
        lines.append(f"MATCH (l:Listing) WHERE l.property_type = {json.dumps(old, ensure_ascii=False)} "
                     f"SET l.property_type = {json.dumps(new, ensure_ascii=False)};")
    for field in ("price_range", "area", "ward_commune", "ward_commune_type", "ward_commune_name", "former_admin_area"):
        items = groups.get(field, [])
        for start in range(0, len(items), 200):
            chunk = ", ".join(f"{{id: {json.dumps(i)}, v: {cypher_value(field, v)}}}" for i, v in items[start:start + 200])
            lines.append(f"UNWIND [{chunk}] AS r MATCH (l:Listing {{listing_id: r.id}}) SET l.{node_fields[field]} = r.v;")
    lines.append("")
    lines.append("// ward / former area / street of the listings whose ward and former district were swapped")
    for e in admin_log:
        lid = json.dumps(str(e["listing_id"]))
        lines += [
            f"MATCH (l:Listing {{listing_id: {lid}}})-[r:IN_WARD|IN_FORMER_AREA|ON_STREET]->() DELETE r;",
            f"MATCH (l:Listing {{listing_id: {lid}}}), (w:Ward {{ward_id: {json.dumps(e['ward'][1])}}}) MERGE (l)-[:IN_WARD]->(w);",
            f"MATCH (l:Listing {{listing_id: {lid}}}), (f:FormerAdminArea {{former_area_id: {json.dumps(e['former'][1])}}}) "
            f"MERGE (l)-[:IN_FORMER_AREA]->(f);",
        ]
        if e["street"]:
            lines.append(
                f"MATCH (l:Listing {{listing_id: {lid}}}), (w:Ward {{ward_id: {json.dumps(e['ward'][1])}}}) "
                f"MERGE (s:Street {{street_id: {json.dumps(e['street'][1])}}}) "
                f"ON CREATE SET s.name = l.road_name_final, s.ward_id = w.ward_id, s.city_province = l.city_province "
                f"MERGE (l)-[:ON_STREET]->(s) MERGE (s)-[:IN_WARD]->(w);")
    old_nodes = sorted({e["ward"][0] for e in admin_log} | {e["street"][0] for e in admin_log if e["street"]} |
                       {e["former"][0] for e in admin_log})
    lines += ["// remove the nodes only the swapped rows had created (kept if anything else still uses them)",
              f"UNWIND {json.dumps(old_nodes, ensure_ascii=False)} AS id "
              "MATCH (n) WHERE ((n:Ward AND n.ward_id = id) OR (n:Street AND n.street_id = id) "
              "OR (n:FormerAdminArea AND n.former_area_id = id)) "
              "AND NOT EXISTS { MATCH (n)<-[:IN_WARD|IN_FORMER_AREA|ON_STREET]-(:Listing) } DETACH DELETE n;",
              "// recount ward <- former area mappings and former-area counters",
              "MATCH (:Ward)-[m:MAPPED_FROM]->(:FormerAdminArea) DELETE m;",
              "MATCH (w:Ward)<-[:IN_WARD]-(l:Listing)-[:IN_FORMER_AREA]->(f:FormerAdminArea) "
              "WITH w, f, count(l) AS n MERGE (w)-[m:MAPPED_FROM]->(f) SET m.supporting_listing_count = n;",
              "MATCH (f:FormerAdminArea) SET f.listing_count = COUNT { (f)<-[:IN_FORMER_AREA]-(:Listing) }, "
              "f.mapped_ward_count = COUNT { (f)<-[:MAPPED_FROM]-(:Ward) };", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="patch the CSVs in place (default: dry run)")
    args = ap.parse_args()

    master_path = V3 / "master_v3.csv"
    before = sha256(master_path)
    state = {SHA256["original"]: "published v3", SHA256["fixed"]: "already v3.1"}.get(before, "unknown version")
    print(f"master_v3.csv sha256 {before[:16]}… ({state})")
    header, rows = read_table(master_path)
    fixes, review = audit(header, rows)
    if not fixes:
        print("Nothing to fix — the data is already at v3.1. No file written.")
        return 0

    counts = collections.Counter((f["field"], f["rule"]) for f in fixes)
    listings = len({f["listing_id"] for f in fixes})
    print(f"{len(fixes)} cell corrections in {listings} listings:")
    for (field, rule), n in sorted(counts.items()):
        print(f"  {field:18} {rule:26} {n:5}")
    if review:
        print(f"\n{len(review)} listings need a decision (add them to MANUAL_PRICE):")
        for lid, why, ev in review:
            print(f"  {lid}  {why}\n      {ev}")

    reports, patches = V3 / "reports", V3 / "patches"
    reports.mkdir(exist_ok=True)
    patches.mkdir(exist_ok=True)
    with open(reports / "v3_1_corrections.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["listing_id", "field", "old", "new", "rule", "evidence"])
        w.writeheader()
        w.writerows(sorted(fixes, key=lambda x: (x["listing_id"], x["field"])))

    # master
    changes = collections.defaultdict(dict)
    for f in fixes:
        changes[str(f["listing_id"])][f["field"]] = f["new"]
    patch_rows(header, rows, "listing_id", changes)
    swapped = {str(f["listing_id"]) for f in fixes if f["rule"] == "ward_swap"}
    admin_out, admin_in, admin_log = graph_admin(header, rows, swapped)

    n_sql = write_sql(patches / "v3_1_postgres.sql", fixes)
    write_cypher(patches / "v3_1_neo4j.cypher", fixes, admin_log)
    print(f"\nwrote reports/v3_1_corrections.csv, patches/v3_1_postgres.sql ({n_sql} rows), patches/v3_1_neo4j.cypher")

    if not args.apply:
        print("Dry run — no data file changed. Review the report, then run again with --apply.")
        return 0

    write_table(master_path, header, rows)
    ph, pr = read_table(V3 / "postgres" / "properties_v3.csv")
    hit_pg = patch_rows(ph, pr, "listing_id", changes)
    write_table(V3 / "postgres" / "properties_v3.csv", ph, pr)
    gh, gr = read_table(GRAPH / "neo4j_listing_nodes.csv")
    hit_g = patch_rows(gh, gr, "listing_id:string", changes, rename={
        "property_type": "property_type:string", "price_range": "price_range:float", "area": "area:float",
        "ward_commune": "ward_commune:string", "ward_commune_type": "ward_commune_type:string",
        "ward_commune_name": "ward_commune_name:string", "former_admin_area": "former_admin_area:string"})
    write_table(GRAPH / "neo4j_listing_nodes.csv", gh, gr)
    for name, (hdr, new_rows) in admin_out.items():
        old_hdr, old_rows = admin_in[name]
        if new_rows != old_rows:
            write_table(GRAPH / name, hdr, new_rows)
    after = sha256(master_path)
    print(f"patched master_v3.csv, postgres/properties_v3.csv {dict(hit_pg)}, graph/neo4j_listing_nodes.csv "
          f"{dict(hit_g)}, {sum(admin_out[n][1] != admin_in[n][1] for n in admin_out)} graph admin files")
    print(f"master_v3.csv sha256 {after[:16]}…" + ("  (= expected v3.1)" if after == SHA256["fixed"] else
                                                   "  (expected " + SHA256["fixed"][:16] + "…)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
