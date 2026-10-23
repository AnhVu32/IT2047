#!/usr/bin/env python3
"""Populate driving distance and duration for local OSM edges via your own OSRM server.
Requires a properly built OSRM graph for southern Vietnam; do not run this
mass dataset workload against the public OSRM demo endpoint.

Usage:
python compute_osrm_routes.py --master listings_209cols_osm_cache_enriched.csv \
 --edges listing_amenity_top5_edges.csv --poi osm_poi_nodes.csv \
 --osrm-url http://localhost:5000 --output-dir routed --max-listings 100

Stores a JSONL checkpoint, supporting restart. Default routes rank 1 only;
--top-k 5 will route all 5 edges per category in one OSRM Table call per listing.
"""
import argparse,csv,json,time
from pathlib import Path
import requests

LIMITS={'school':2,'college_university':5,'metro':3,'mall':5,'market':2,'supermarket':2,'park':5,'bus_stop':2}
CATS=['hospital','school','college_university','metro','mall','market','supermarket','park','bus_stop']

def read(path):
 with open(path,encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);return list(r),r.fieldnames

def write(path,rows,fields):
 with open(path,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main(a):
 if 'router.project-osrm.org' in a.osrm_url:
  raise SystemExit('Refusing mass routing against public demo server: use your own OSRM instance.')
 if not a.osrm_url.startswith(('http://','https://')):raise SystemExit('Invalid OSRM URL')
 out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 master,fields=read(a.master);edges,efields=read(a.edges);pois,_=read(a.poi)
 poi_by_id={p['osm_id']:p for p in pois}
 by_listing={}
 for e in edges:
  if int(e['rank'])<=a.top_k:by_listing.setdefault(e['listing_node_id'],[]).append(e)
 cachefile=out/'osrm_checkpoint.jsonl';completed={}
 if cachefile.exists():
  with open(cachefile,encoding='utf8') as f:
   for line in f:
    try:r=json.loads(line);completed[r['listing_id']]=r['results']
    except (json.JSONDecodeError,KeyError):pass
 requested=0;good=0
 with open(cachefile,'a',encoding='utf8') as checkpoint:
  for listing in master:
   lid=listing['listing_id']
   if lid in completed:continue
   dest=[e for e in by_listing.get(lid,[]) if e['osm_id'] in poi_by_id]
   if not dest:continue
   try:
    lat=float(listing['latitude']);lon=float(listing['longitude'])
   except ValueError:continue
   if requested>=a.max_listings:break
   coords=[(lon,lat)]+[(float(poi_by_id[e['osm_id']]['longitude']),float(poi_by_id[e['osm_id']]['latitude'])) for e in dest]
   route=';'.join(f'{lo:.7f},{la:.7f}' for lo,la in coords)
   params={'sources':'0','destinations':';'.join(str(i) for i in range(1,len(coords))),'annotations':'distance,duration'}
   try:
    resp=requests.get(a.osrm_url.rstrip('/')+'/table/v1/driving/'+route,params=params,timeout=(10,90))
    resp.raise_for_status();data=resp.json()
    if data.get('code')!='Ok':raise ValueError(str(data.get('message',data.get('code'))))
    dd=data['distances'][0];tt=data['durations'][0]
    answers={}
    for edge,meters,seconds in zip(dest,dd,tt):
     if meters is None or seconds is None:continue
     key=edge['category']+'|'+edge['osm_id']
     answers[key]={'driving_distance_km':round(meters/1000,3),'driving_duration_min':round(seconds/60,2)}
    completed[lid]=answers
    checkpoint.write(json.dumps({'listing_id':lid,'results':answers},ensure_ascii=False)+'\n');checkpoint.flush()
    requested+=1;good+=1
   except (requests.RequestException,ValueError,KeyError,IndexError) as exc:
    requested+=1;print('OSRM failed',lid,str(exc)[:150],flush=True)
   time.sleep(a.sleep_seconds)
 # Update all edges for successful listing-id/OSM-id/category routes.
 for edge in edges:
  key=edge['category']+'|'+edge['osm_id'];info=completed.get(edge['listing_node_id'],{}).get(key)
  if info:
   edge.update(info);edge['route_source']='OSRM_driving_self_hosted'
 write(out/'listing_amenity_top5_edges_routed.csv',edges,efields)
 # The 209-column master has rank-1 fields only.
 rank1={(e['listing_node_id'],e['category']):e for e in edges if int(e['rank'])==1}
 for row in master:
  nmatch=0;nin=0
  for cat in CATS:
   edge=rank1.get((row['listing_id'],cat))
   if edge and edge['driving_distance_km']!='' and edge['driving_duration_min']!='':
    row[cat+'_driving_distance_km']=edge['driving_distance_km']
    row[cat+'_driving_duration_min']=edge['driving_duration_min']
    row[cat+'_route_source']=edge['route_source']
   field=f'within_{cat}_'+('2km' if cat in {'school','market','supermarket','bus_stop'} else '3km' if cat=='metro' else '5km')+'_driving'
   if cat in LIMITS:
    if row[cat+'_driving_distance_km']!='':
     is_in=float(row[cat+'_driving_distance_km'])<=LIMITS[cat]
     row[field]='1' if is_in else '0'
     nmatch+=1;nin+=int(is_in)
    else:row[field]=''
  row['amenity_types_within_threshold_count']=nin if nmatch==len(LIMITS) else ''
 write(out/'listings_209cols_osm_osrm_enriched.csv',master,fields)
 print('Successful listing routes this run',good,'cached',len(completed),'saved to',out)

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--master',required=True);p.add_argument('--edges',required=True);p.add_argument('--poi',required=True)
 p.add_argument('--osrm-url',required=True);p.add_argument('--output-dir',required=True)
 p.add_argument('--top-k',type=int,choices=[1,2,3,4,5],default=1)
 p.add_argument('--max-listings',type=int,default=100);p.add_argument('--sleep-seconds',type=float,default=0.05)
 main(p.parse_args())
