from pathlib import Path
from collections import Counter,defaultdict
import csv,json,sys
P=Path(__file__).parent

def load(filename):
 with open(P/filename,encoding='utf-8-sig',newline='') as f:
  c=csv.DictReader(f);return list(c),c.fieldnames
m,mc=load('listings_209cols_osm_cache_enriched.csv')
l,lc=load('neo4j_listing_nodes.csv')
a,ac=load('neo4j_amenity_nodes.csv')
e,ec=load('neo4j_listing_amenity_edges.csv')
p,pc=load('osm_poi_nodes.csv')
review,_=load('needs_coordinate_review.csv')
quality,_=load('coordinate_quality.csv')
assert len(m)==3857 and len(mc)==209
assert len(l)==3857 and len({r['listing_id'] for r in m})==3857
assert len(a)==len(p)==1896
assert len(e)==143411
assert len(review)==27
assert sum(bool(row['latitude']) for row in m)==3830
assert all(row['osm_id'].startswith(('node/','way/','relation/')) for row in p)
assert set(x['osm_id:ID(Amenity)'] for x in a)==set(x['osm_id'] for x in p)
lids=set(x['listing_node_id:ID(Listing)'] for x in l)
aids=set(x['osm_id:ID(Amenity)'] for x in a)
assert all(x[':START_ID(Listing)'] in lids and x[':END_ID(Amenity)'] in aids for x in e)
assert all(1<=int(x['rank:int'])<=5 for x in e)
assert len({(x[':START_ID(Listing)'],x['category:string'],x['rank:int']) for x in e})==len(e)
for col in ['price_range:float','area:float','bedrooms:int','bathrooms:int','latitude:float','longitude:float']:
 for x in l:
  if x[col]:
   if col.endswith(':int'):int(x[col])
   else:float(x[col])
limits={'hospital':7,'school':3,'college_university':7,'metro':5,'mall':7,'market':3,'supermarket':3,'park':5,'bus_stop':2}
assert all(float(x['straight_line_km:float'])<=limits[x['category:string']]+.002 for x in e)
with open('/mnt/data/real_estate_50cols_enriched/cleaned_master_data_50cols_enriched.csv',encoding='utf-8-sig') as f:
 original=list(csv.DictReader(f))
assert all(all(a[k]==b[k] for k in list(a)[:50]) for a,b in zip(original,m))
checks={'master_rows':len(m),'master_columns':len(mc),'input_50_columns_preserved':True,'unique_listing_ids':len(lids),'amenity_nodes':len(aids),'top5_edges':len(e),'invalid_coord_unresolved':len(review),'coordinates_valid_or_imputed':sum(bool(x['latitude']) for x in m),'routed_edges_count':sum(bool(x['driving_distance_km:float']) for x in e),'ready_for_neo4j_import':True}
(P/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(checks,ensure_ascii=False,indent=2))
