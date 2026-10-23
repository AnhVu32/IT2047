#!/usr/bin/env python3
"""Build exact spherical Top-5 from the successful live Overpass snapshot."""
import csv,json,math,collections,pathlib,shutil,re,datetime
import numpy as np
from scipy.spatial import cKDTree
ROOT=pathlib.Path(__file__).resolve().parent
if ROOT.name=='pipeline':ROOT=ROOT.parent
OUT=ROOT/'graph_live';OUT.mkdir(exist_ok=True)
CATS=['hospital','school','college_university','metro','mall','market','supermarket','park','bus_stop']
RADIUS=dict(zip(CATS,[7,3,7,5,7,3,3,5,2]))
LABELS=dict(zip(CATS,['Hospital','School','CollegeUniversity','MetroStation','Mall','Market','Supermarket','Park','BusStop']))
def read(p):
 with open(p,encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);return list(r),r.fieldnames
def write(p,rows,fields=None):
 with open(p,'w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fields or list(rows[0]),extrasaction='ignore');w.writeheader();w.writerows(rows)
def sphere(a):
 a=np.radians(np.asarray(a,float));lat,lon=a[:,0],a[:,1]
 return np.column_stack((np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)))
def build():
 payload=json.loads((ROOT/'live_cache/overpass_de_live.json').read_text())
 assert 'remark' not in payload and payload.get('elements')
 stamp=payload['osm3s']['timestamp_osm_base'];pois=[];excluded=[]
 for e in payload['elements']:
  t=e.get('tags',{});c=e.get('center',e);cats=[];am=t.get('amenity');rw=t.get('railway');oid=f"{e['type']}/{e['id']}"
  if any(t.get(k) in ('yes','construction','proposed') for k in ['disused','abandoned','construction','proposed']):
   excluded.append({'osm_id':oid,'name':t.get('name',''),'reason':'non_operational_tag'});continue
  if am in ('hospital','clinic'):cats.append('hospital')
  if am in ('school','kindergarten'):cats.append('school')
  if am in ('college','university'):cats.append('college_university')
  if t.get('shop')=='mall':cats.append('mall')
  if t.get('shop')=='supermarket':cats.append('supermarket')
  if am=='marketplace':cats.append('market')
  if t.get('leisure')=='park':cats.append('park')
  if t.get('highway')=='bus_stop' or (t.get('public_transport')=='platform' and t.get('bus')=='yes'):cats.append('bus_stop')
  if rw=='subway_entrance':
   excluded.append({'osm_id':oid,'name':t.get('name',''),'reason':'metro_entrance_not_distinct_station'})
  elif (rw=='station' and t.get('station')=='subway') or (t.get('public_transport')=='station' and t.get('subway')=='yes'):
   if t.get('network')=='Ho Chi Minh City Metro' and t.get('name'):
    cats.append('metro')
   else:excluded.append({'osm_id':oid,'name':t.get('name',''),'reason':'metro_station_network_or_operation_unverified'})
  if not cats or c.get('lat') is None or c.get('lon') is None:continue
  name=t.get('name:vi') or t.get('name') or t.get('name:en') or ''
  pois.append(dict(osm_id=oid,name=name,category='|'.join(cats),subtype=am or t.get('shop') or rw or t.get('leisure') or t.get('public_transport') or t.get('highway',''),latitude=c['lat'],longitude=c['lon'],street=t.get('addr:street',''),address=t.get('addr:full') or ', '.join(t[k] for k in ['addr:housenumber','addr:street','addr:suburb','addr:city'] if t.get(k)),operator=t.get('operator',''),source='OpenStreetMap_Overpass_live',osm_snapshot_at=stamp,coordinate_method='osm_node' if e['type']=='node' else 'osm_bbox_center',osm_url='https://www.openstreetmap.org/'+oid,tags_json=json.dumps(t,ensure_ascii=False,separators=(',',':'))))
 pois.sort(key=lambda p:p['osm_id']);assert len({p['osm_id'] for p in pois})==len(pois)
 write(OUT/'osm_poi_nodes.csv',pois);write(OUT/'excluded_poi_review.csv',excluded)
 master,mfields=read(ROOT/'prior/listings_209cols_osm_cache_enriched.csv')
 latest,lfields=read(ROOT/'inputs/phân tích hệ thống bds/cleaned_master_data.csv');latest={r['listing_id']:r for r in latest}
 assert set(latest)=={r['listing_id'] for r in master}
 for r in master:
  for f in lfields:r[f]=latest[r['listing_id']][f]
  for cat in CATS:
   for f in list(r):
    if f.startswith('nearest_'+cat+'_') or f.startswith(cat+'_'):r[f]=''
  for f in list(r):
   if f.startswith('within_') or f in ['travel_enriched_at','amenities_travel_enriched_at','amenity_types_within_threshold_count']:r[f]=''
  # Do not reproduce an embedded API credential in a generated deliverable.
  r['location_link']=re.sub(r'([?&])key=[^&]*',r'\1',r.get('location_link','')).rstrip('?&')
  r['poi_snapshot_at']=stamp
  r['top5_basis']='haversine_within_category_radius'
 valid=[r for r in master if r['latitude'] and r['longitude']]
 xyz=sphere([[float(r['latitude']),float(r['longitude'])] for r in valid]);edges=[]
 for cat in CATS:
  arr=[p for p in pois if cat in p['category'].split('|')];tree=cKDTree(sphere([[p['latitude'],p['longitude']] for p in arr]))
  dd,ii=tree.query(xyz,k=min(5,len(arr)));dd=np.atleast_2d(dd);ii=np.atleast_2d(ii)
  for i,r in enumerate(valid):
   for rank,(chord,idx) in enumerate(zip(dd[i],ii[i]),1):
    km=12742*math.asin(min(1,float(chord)/2));p=arr[int(idx)]
    if km>RADIUS[cat]:continue
    edges.append(dict(listing_node_id=r['listing_id'],osm_id=p['osm_id'],category=cat,rank=rank,straight_line_km=round(km,6),driving_distance_km='',driving_duration_min='',route_source='',route_status='pending',source_snap_m='',destination_snap_m='',route_enriched_at='',poi_data_source=p['source'],osm_snapshot_at=stamp,coordinate_status=r['coordinate_status']))
    if rank==1:
     for dest,src in [('name','name'),('osm_id','osm_id'),('latitude','latitude'),('longitude','longitude'),('street','street'),('address_osm','address'),('operator','operator')]:r['nearest_'+cat+'_'+dest]=p[src]
     r['nearest_'+cat+'_street_source']='OpenStreetMap_live_tags' if p['street'] else ''
     r[cat+'_straight_line_km']=round(km,6);r[cat+'_data_source']=p['source']
 counts=collections.Counter(e['listing_node_id'] for e in edges)
 for r in master:
  present=[cat for cat in CATS if r['nearest_'+cat+'_osm_id']]
  r['nearby_category_count']=len(present);r['nearby_categories']='|'.join(present)
 write(OUT/'listings_osm_osrm_enriched.csv',master,list(dict.fromkeys(mfields+lfields+['poi_snapshot_at','top5_basis'])))
 write(OUT/'listing_amenity_top5_edges.csv',edges)
 # Preserve known administrative/cluster graph structure from the supplied package.
 for f in (ROOT/'prior').glob('neo4j_*.csv'):
  if f.name not in ('neo4j_amenity_nodes.csv','neo4j_listing_amenity_edges.csv'):shutil.copyfile(f,OUT/f.name)
 for name in ['needs_coordinate_review.csv','coordinate_quality.csv','post_import_indexes.cypher']:shutil.copyfile(ROOT/'prior'/name,OUT/name)
 qa,qf=read(OUT/'coordinate_quality.csv')
 for r in qa:r['edge_count']=counts[r['listing_id']]
 write(OUT/'coordinate_quality.csv',qa,qf)
 pc=['osm_id:ID(Amenity)','name:string','category:string','subtype:string','latitude:float','longitude:float','street:string','address:string','operator:string','source:string','osm_snapshot_at:string','coordinate_method:string',':LABEL']
 write(OUT/'neo4j_amenity_nodes.csv',[dict(zip(pc,[p['osm_id'],p['name'],p['category'],p['subtype'],p['latitude'],p['longitude'],p['street'],p['address'],p['operator'],p['source'],p['osm_snapshot_at'],p['coordinate_method'],';'.join(['Amenity']+[LABELS[c] for c in p['category'].split('|')])])) for p in pois],pc)
 export_graph_edges(edges)
 stats=dict(listings=len(master),safe_coordinate_listings=len(valid),coordinate_review=len(master)-len(valid),osm_raw_elements=len(payload['elements']),poi_nodes=len(pois),poi_by_category=dict(collections.Counter(c for p in pois for c in p['category'].split('|'))),edges=len(edges),edges_by_category=dict(collections.Counter(e['category'] for e in edges)),listings_with_edges=len(counts),radius_km=RADIUS,osm_snapshot_at=stamp,ranking='exact spherical nearest five within per-category radius; not road-distance ranking',fresh_poi_only=True,route_status='pending')
 (OUT/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2));print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)
def export_graph_edges(edges):
 ec=[':START_ID(Listing)',':END_ID(Amenity)','category:string','rank:int','straight_line_km:float','driving_distance_km:float','driving_duration_min:float','route_source:string','route_status:string','source_snap_m:float','destination_snap_m:float','route_enriched_at:string','osm_snapshot_at:string',':TYPE']
 write(OUT/'neo4j_listing_amenity_edges.csv',[dict(zip(ec,[e['listing_node_id'],e['osm_id'],e['category'],e['rank'],e['straight_line_km'],e['driving_distance_km'],e['driving_duration_min'],e['route_source'],e['route_status'],e['source_snap_m'],e['destination_snap_m'],e['route_enriched_at'],e['osm_snapshot_at'],'NEAR_AMENITY'])) for e in edges],ec)
if __name__=='__main__':build()
