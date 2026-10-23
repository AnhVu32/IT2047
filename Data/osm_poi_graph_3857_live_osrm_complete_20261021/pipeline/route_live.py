#!/usr/bin/env python3
"""Cached spatial OSRM matrices. Sequential requests, >=2s delay, stop on service failure."""
import argparse,collections,datetime,hashlib,json,pathlib,time,urllib.request,urllib.error,urllib.parse
from build_live_graph import ROOT,OUT,CATS,read,write,export_graph_edges
CACHE=ROOT/'live_cache/osrm';CACHE.mkdir(parents=True,exist_ok=True)
def prepare(input_dir=None):
 source=ROOT/input_dir if input_dir else OUT
 master,_=read(source/'listings_osm_osrm_enriched.csv');pois,_=read(source/'osm_poi_nodes.csv');edges,_=read(source/'listing_amenity_top5_edges.csv')
 pm={p['osm_id']:(float(p['longitude']),float(p['latitude'])) for p in pois};lm={r['listing_id']:r for r in master}
 by=collections.defaultdict(list)
 for e in edges:by[e['listing_node_id']].append(e)
 origins={};lcoord={}
 for lid in by:
  r=lm[lid];c=(float(r['longitude']),float(r['latitude']));origins.setdefault(c,[]).append(lid);lcoord[lid]=c
 # Morton ordering keeps consecutive sources spatially close.
 def morton(c):
  x=int((c[0]-106)*100000);y=int((c[1]-10)*100000);v=0
  for bit in range(20):v|=((x>>bit)&1)<<(2*bit);v|=((y>>bit)&1)<<(2*bit+1)
  return v
 groups=[];src=[];dest=set()
 for c in sorted(origins,key=morton):
  target={e['osm_id'] for lid in origins[c] for e in by[lid]};merged=dest|target
  if src and (len(src)+1+len(merged)>100 or len(src)>=32):groups.append((src,sorted(dest)));src=[];dest=set();merged=target
  src.append(c);dest=merged
 if src:groups.append((src,sorted(dest)))
 return master,edges,pm,lcoord,groups
def main(a):
 master,edges,pm,lcoord,groups=prepare();print('matrix_batches',len(groups),'edges',len(edges),'max_coordinates',max(len(s)+len(d) for s,d in groups),flush=True)
 if a.plan:return
 if not a.osrm_url.startswith(('http://','https://')):raise SystemExit('OSRM URL must use HTTP(S)')
 if not a.cache_only and urllib.parse.urlsplit(a.osrm_url).hostname not in ('localhost','127.0.0.1','::1') and not a.allow_coordinate_transfer:
  raise SystemExit('External routing transmits listing and POI coordinates. Specify --allow-coordinate-transfer only after authorizing the selected endpoint, or use --cache-only/local OSRM.')
 answers={};failed=[];requested=0;cached=0
 for gi,(src,dest) in enumerate(groups):
  coords=src+[pm[p] for p in dest];parts=';'.join(f'{lo:.8f},{la:.8f}' for lo,la in coords)
  params=urllib.parse.urlencode({'sources':';'.join(map(str,range(len(src)))),'destinations':';'.join(map(str,range(len(src),len(coords)))),'annotations':'distance,duration','generate_hints':'false'})
  url=a.osrm_url.rstrip('/')+'/table/v1/driving/'+parts+'?'+params
  key=hashlib.sha256(url.encode()).hexdigest();fp=CACHE/(key+'.json');data=None;ts=''
  if fp.exists():
   record=json.loads(fp.read_text());data=record['response'];ts=record['fetched_at'];cached+=1
  else:
   if a.cache_only or requested>=a.max_requests:continue
   for attempt in range(2):
    try:
     req=urllib.request.Request(url,headers={'User-Agent':'RealEstatePOIEnrichment/1.0 (one-off academic spatial analysis; cached sequential matrices)','Accept':'application/json'})
     with urllib.request.urlopen(req,timeout=45) as r:data=json.load(r)
     if data.get('code')!='Ok':raise ValueError(str(data)[:200])
     ts=datetime.datetime.now(datetime.timezone.utc).isoformat();record={'fetched_at':ts,'endpoint':a.osrm_url,'response':data}
     fp.write_text(json.dumps(record,ensure_ascii=False));requested+=1;break
    except Exception as exc:
     print('matrix_error',gi+1,'attempt',attempt+1,repr(exc),flush=True)
     if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):break
     if attempt==0:time.sleep(5)
   if data is None or data.get('code')!='Ok':
    failed.append(gi);print('Stopping requests after persistent service failure; checkpoints retained',flush=True);break
   time.sleep(max(2,a.delay))
  assert len(data['distances'])==len(src) and len(data['durations'])==len(src)
  for si,c in enumerate(src):
   for di,oid in enumerate(dest):
    dd=data['distances'][si][di];tt=data['durations'][si][di]
    ss=data['sources'][si]['distance'];ds=data['destinations'][di]['distance']
    status='unreachable' if dd is None or tt is None else 'snapped_far' if max(ss,ds)>500 else 'ok'
    answers[(c,oid)]={'driving_distance_km':round(dd/1000,6) if dd is not None else '', 'driving_duration_min':round(tt/60,4) if tt is not None else '', 'route_status':status,'route_source':'OSRM_driving_live_table','source_snap_m':round(ss,2),'destination_snap_m':round(ds,2),'route_enriched_at':ts}
  if (gi+1)%10==0 or gi==len(groups)-1:print('matrix_progress',gi+1,'/',len(groups),'new_requests',requested,'cached',cached,flush=True)
  if (gi+1)%25==0:save(master,edges,lcoord,answers,groups,requested,cached,failed)
 save(master,edges,lcoord,answers,groups,requested,cached,failed)
def save(master,edges,lcoord,answers,groups,requested,cached,failed):
 for e in edges:
  ans=answers.get((lcoord[e['listing_node_id']],e['osm_id']))
  if ans:e.update(ans)
 write(OUT/'listing_amenity_top5_edges.csv',edges);export_graph_edges(edges)
 rank1={(e['listing_node_id'],e['category']):e for e in edges if int(e['rank'])==1}
 limits={'school':2,'college_university':5,'metro':3,'mall':5,'market':2,'supermarket':2,'park':5,'bus_stop':2}
 for r in master:
  flags=[];times=[]
  for cat in CATS:
   e=rank1.get((r['listing_id'],cat))
   r[cat+'_route_status']=e['route_status'] if e else 'coordinate_review' if not r['latitude'] else 'no_poi_within_radius'
   r[cat+'_source_snap_m']=e['source_snap_m'] if e else ''
   r[cat+'_destination_snap_m']=e['destination_snap_m'] if e else ''
   if e and e['route_source']:
    for key in ['driving_distance_km','driving_duration_min','route_source']:r[cat+'_'+key]=e[key]
    times.append(e['route_enriched_at'])
   if cat in limits:
    field=f'within_{cat}_{limits[cat]}km_driving';r[field]=''
    if e and e['route_status']=='ok':r[field]=int(float(e['driving_distance_km'])<=limits[cat]);flags.append(r[field])
  r['amenity_types_within_threshold_count']=sum(flags) if len(flags)==len(limits) else ''
  r['amenities_travel_enriched_at']=max(times) if times else '';r['travel_enriched_at']=r['amenities_travel_enriched_at']
 write(OUT/'listings_osm_osrm_enriched.csv',master)
 summary=json.loads((OUT/'summary.json').read_text());summary.update(route_status_counts=dict(collections.Counter(e['route_status'] for e in edges)),route_edges_computed=sum(e['route_status'] in ('ok','snapped_far') for e in edges),matrix_batch_count=len(groups),matrix_requests_this_run=requested,matrix_cache_hits=cached,matrix_failed=failed,route_status='complete' if all(e['route_status']!='pending' for e in edges) else 'partial',osrm_duration_semantics='profile car estimate; no real-time traffic; distance along OSRM fastest route')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print('saved_routes',summary['route_status_counts'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--osrm-url',default='http://localhost:5000');p.add_argument('--delay',type=float,default=2);p.add_argument('--max-requests',type=int,default=1000);p.add_argument('--plan',action='store_true');p.add_argument('--cache-only',action='store_true');p.add_argument('--allow-coordinate-transfer',action='store_true');main(p.parse_args())
