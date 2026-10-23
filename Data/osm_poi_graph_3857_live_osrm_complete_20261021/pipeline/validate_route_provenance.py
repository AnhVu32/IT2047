#!/usr/bin/env python3
"""Audit every exported route against the recorded raw OSRM matrix values."""
import collections,hashlib,json,urllib.parse
from route_live import ROOT,OUT,CACHE,prepare
from fill_route_cache_batched import url_for
def main():
 master,edges,pm,lcoord,groups=prepare();answers={};derived_count=0;matrix_count=0
 endpoint='https://router.project-osrm.org'
 for src,dest in groups:
  key=hashlib.sha256(url_for(endpoint,src,dest,pm).encode()).hexdigest();fp=CACHE/(key+'.json');assert fp.exists(),fp
  rec=json.loads(fp.read_text());data=rec['response'];matrix_count+=1
  if rec.get('derived_from_merged_response'):
   raw=json.loads((ROOT/'live_cache'/rec['derived_from_merged_response']).read_text());si={tuple(c):i for i,c in enumerate(raw['source_coordinates'])};di={p:i for i,p in enumerate(raw['destination_osm_ids'])};r=raw['response']
   for i,c in enumerate(src):
    for j,p in enumerate(dest):
     assert data['distances'][i][j]==r['distances'][si[c]][di[p]]
     assert data['durations'][i][j]==r['durations'][si[c]][di[p]]
    assert data['sources'][i]==r['sources'][si[c]]
   for j,p in enumerate(dest):assert data['destinations'][j]==r['destinations'][di[p]]
   derived_count+=1
  for i,c in enumerate(src):
   for j,p in enumerate(dest):answers[c,p]=(data['distances'][i][j],data['durations'][i][j],data['sources'][i]['distance'],data['destinations'][j]['distance'])
 for e in edges:
  dd,tt,ss,ds=answers[lcoord[e['listing_node_id']],e['osm_id']]
  if dd is None or tt is None:assert e['route_status']=='unreachable' and e['driving_distance_km']=='' and e['driving_duration_min']==''
  else:
   assert abs(float(e['driving_distance_km'])-round(dd/1000,6))<1e-9
   assert abs(float(e['driving_duration_min'])-round(tt/60,4))<1e-9
   assert e['route_status']==('snapped_far' if max(ss,ds)>500 else 'ok')
   assert abs(float(e['source_snap_m'])-round(ss,2))<1e-9 and abs(float(e['destination_snap_m'])-round(ds,2))<1e-9
 result={'passed':True,'original_matrices_checked':matrix_count,'submatrices_checked_against_raw_merged_responses':derived_count,'exported_route_edges_checked':len(edges),'status_counts':dict(collections.Counter(e['route_status'] for e in edges))}
 (OUT/'route_provenance_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
