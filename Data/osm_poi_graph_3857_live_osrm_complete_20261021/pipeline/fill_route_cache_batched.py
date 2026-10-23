#!/usr/bin/env python3
"""Compute bounded merged OSRM matrices and retain exact original-group caches.
Submatrix values are copied unchanged from the actual OSRM response; raw merged
responses and their provenance are retained. Uses immutable input seed files.
"""
import argparse,collections,concurrent.futures,datetime,hashlib,json,pathlib,threading,time,urllib.request,urllib.parse,urllib.error
from route_live import ROOT,CACHE,prepare
def url_for(endpoint,src,dest,pm):
 coords=src+[pm[p] for p in dest];parts=';'.join(f'{lo:.8f},{la:.8f}' for lo,la in coords)
 params=urllib.parse.urlencode({'sources':';'.join(map(str,range(len(src)))),'destinations':';'.join(map(str,range(len(src),len(coords)))),'annotations':'distance,duration','generate_hints':'false'})
 return endpoint.rstrip('/')+'/table/v1/driving/'+parts+'?'+params
def main():
 p=argparse.ArgumentParser();p.add_argument('--osrm-url',required=True);p.add_argument('--allow-coordinate-transfer',action='store_true');p.add_argument('--input-dir',default='graph_live');a=p.parse_args()
 if not a.allow_coordinate_transfer:raise SystemExit('Explicit user authorization for coordinate transfer required')
 _,_,pm,_,groups=prepare(a.input_dir)
 def file_for(src,dest):return CACHE/(hashlib.sha256(url_for(a.osrm_url,src,dest,pm).encode()).hexdigest()+'.json')
 rawcache=ROOT/'live_cache/osrm_merged';rawcache.mkdir(exist_ok=True)
 jobs=[];members=[];ss=[];dd=set()
 for gi in reversed(range(len(groups))):
  src,dest=groups[gi]
  if file_for(src,dest).exists():continue
  ms=ss+src;md=sorted(dd|set(dest));u=url_for(a.osrm_url,ms,md,pm)
  if members and (len(ms)*len(md)>8000 or len(ms)+len(md)>240 or len(u)>7400):
   jobs.append((members,ss,sorted(dd)));members=[];ss=[];dd=set()
  members.append(gi);ss+=src;dd.update(dest)
 if members:jobs.append((members,ss,sorted(dd)))
 print('immutable_input_original_groups',len(groups),'missing_groups',sum(len(j[0]) for j in jobs),'merged_requests',len(jobs),flush=True)
 lock=threading.Lock();last=[0.];stop=threading.Event();done=[0]
 def split_record(members,src,dest,record,rawkey):
  data=record['response'];si={c:i for i,c in enumerate(src)};di={oid:i for i,oid in enumerate(dest)}
  for gi in members:
   gs,gd=groups[gi];fp=file_for(gs,gd)
   if fp.exists():continue
   rows=[si[c] for c in gs];cols=[di[d] for d in gd]
   response={'code':'Ok','distances':[[data['distances'][i][j] for j in cols] for i in rows],'durations':[[data['durations'][i][j] for j in cols] for i in rows],'sources':[data['sources'][i] for i in rows],'destinations':[data['destinations'][j] for j in cols]}
   if 'data_version' in data:response['data_version']=data['data_version']
   value={'fetched_at':record['fetched_at'],'endpoint':a.osrm_url,'derived_from_merged_response':'osrm_merged/'+rawkey+'.json','response':response}
   tmp=fp.with_suffix('.submatrix.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False));tmp.replace(fp)
 def worker(job):
  members,src,dest=job
  if stop.is_set() or all(file_for(*groups[i]).exists() for i in members):return
  url=url_for(a.osrm_url,src,dest,pm);rawkey=hashlib.sha256(url.encode()).hexdigest();rawfile=rawcache/(rawkey+'.json');record=None
  if rawfile.exists():record=json.loads(rawfile.read_text())
  for attempt in range(2):
   if record:break
   if stop.is_set():return
   with lock:
    pause=3-(time.monotonic()-last[0])
    if pause>0:time.sleep(pause)
    if stop.is_set():return
    last[0]=time.monotonic()
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'RealEstatePOIEnrichment/1.0 (user-authorized cached bounded matrices)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as res:data=json.load(res)
    if data.get('code')!='Ok':raise ValueError(str(data)[:200])
    assert len(data['distances'])==len(src) and all(len(r)==len(dest) for r in data['distances'])
    record={'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'endpoint':a.osrm_url,'source_coordinates':src,'destination_osm_ids':dest,'original_group_indices':members,'response':data}
    tmp=rawfile.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False));tmp.replace(rawfile)
   except Exception as exc:
    print('merged_error',members,'attempt',attempt+1,repr(exc),flush=True)
    if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):stop.set();return
    if attempt==0:time.sleep(5)
  if not record:stop.set();return
  split_record(members,src,dest,record,rawkey)
  with lock:
   done[0]+=1
   if done[0]%5==0:print('merged_done',done[0],'/',len(jobs),'last_original_groups',[i+1 for i in members],flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,jobs))
 hits=sum(file_for(src,dest).exists() for src,dest in groups)
 print('batched_finished','covered_original_groups',hits,'/',len(groups),'stopped',stop.is_set(),flush=True)
if __name__=='__main__':main()
