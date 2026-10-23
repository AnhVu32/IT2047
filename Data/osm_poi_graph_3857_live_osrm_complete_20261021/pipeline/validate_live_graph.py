#!/usr/bin/env python3
"""Validate ID closure, schema types, route coverage and independent exact Top-5."""
import collections,json,math,pathlib,random
from build_live_graph import OUT,ROOT,CATS,RADIUS,read,write
def hav(a,b):
 la,lo,lb,lob=map(math.radians,(*a,*b));q=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin((lob-lo)/2)**2
 return 12742*math.asin(min(1,math.sqrt(q)))
def main():
 checks={};master,mf=read(OUT/'listings_osm_osrm_enriched.csv');edges,ef=read(OUT/'listing_amenity_top5_edges.csv');pois,pf=read(OUT/'osm_poi_nodes.csv')
 lm={r['listing_id']:r for r in master};pm={r['osm_id']:r for r in pois};checks['all_3857_listing_ids_unique']=len(lm)==len(master)==3857
 checks['all_poi_ids_unique']=len(pm)==len(pois)
 checks['all_live_poi_sources']=all(p['source']=='OpenStreetMap_Overpass_live' for p in pois)
 checks['no_api_keys_in_export']=all('key=' not in r.get('location_link','') for r in master)
 checks['no_duplicate_edges']=len({(e['listing_node_id'],e['category'],e['osm_id']) for e in edges})==len(edges)
 grouped=collections.defaultdict(list)
 for e in edges:grouped[(e['listing_node_id'],e['category'])].append(e)
 checks['top5_ranks_unique_contiguous']=all(sorted(int(e['rank']) for e in es)==list(range(1,len(es)+1)) and len(es)<=5 for es in grouped.values())
 checks['edges_within_category_radius']=all(float(e['straight_line_km'])<=RADIUS[e['category']]+1e-6 for e in edges)
 checks['edges_use_valid_coordinates']=all(lm[e['listing_node_id']]['latitude'] and lm[e['listing_node_id']]['longitude'] for e in edges)
 checks['poi_category_matches_edge']=all(e['category'] in pm[e['osm_id']]['category'].split('|') for e in edges)
 checks['route_values_paired']=all((e['driving_distance_km']=='')==(e['driving_duration_min']=='') for e in edges)
 checks['route_values_nonnegative']=all(float(e['driving_distance_km'])>=0 and float(e['driving_duration_min'])>=0 for e in edges if e['driving_distance_km']!='')
 checks['unreachable_or_pending_routes_empty']=all(e['driving_distance_km']=='' for e in edges if e['route_status'] in ('unreachable','pending'))
 checks['ok_snap_within_500m']=all(max(float(e['source_snap_m']),float(e['destination_snap_m']))<=500 for e in edges if e['route_status']=='ok')
 checks['rank1_matches_master']=all(str(lm[lid]['nearest_'+cat+'_osm_id'])==next(e for e in es if int(e['rank'])==1)['osm_id'] for (lid,cat),es in grouped.items())
 # Independent scalar Haversine over every POI for deterministic sample origins.
 rng=random.Random(3857);valid=[r for r in master if r['latitude']];sample=rng.sample(valid,12);independent=True;tested=0
 cp={cat:[p for p in pois if cat in p['category'].split('|')] for cat in CATS}
 for r in sample:
  a=(float(r['latitude']),float(r['longitude']))
  for cat in CATS:
   dist=sorted((hav(a,(float(p['latitude']),float(p['longitude']))),p['osm_id']) for p in cp[cat]);want=[x for x in dist[:5] if x[0]<=RADIUS[cat]];got=sorted(grouped.get((r['listing_id'],cat),[]),key=lambda e:int(e['rank']))
   independent &= len(want)==len(got) and all(abs(d-float(e['straight_line_km']))<1e-6 for (d,oid),e in zip(want,got))
   # Equal-distance ties may be returned in any order by the spatial index.
   independent &= all(abs(hav(a,(float(pm[e['osm_id']]['latitude']),float(pm[e['osm_id']]['longitude'])))-float(e['straight_line_km']))<1e-6 for e in got);tested+=1
 checks['independent_haversine_top5_108_groups']=bool(independent)
 # Neo4j node IDs are scoped to their declared groups.
 ids={};rows_count={};numeric_errors=[]
 for f in sorted(OUT.glob('neo4j_*_nodes.csv')):
  rows,fields=read(f);idfield=next(k for k in fields if ':ID(' in k);grp=idfield.split(':ID(')[1].split(')')[0];ids[grp]={r[idfield] for r in rows};checks[f.name+'_unique_ids']=len(ids[grp])==len(rows);rows_count[f.name]=len(rows)
 for f in sorted(OUT.glob('neo4j_*.csv')):
  rows,fields=read(f);rows_count[f.name]=len(rows)
  for k in fields:
   if k.startswith((':START_ID(',':END_ID(')):
    grp=k.split('(')[1].split(')')[0];checks[f.name+'_'+k+'_closure']=all(r[k] in ids[grp] for r in rows)
   elif k.endswith((':int',':float')):
    for i,r in enumerate(rows):
     if r[k]=='':continue
     try:
      val=float(r[k]);assert math.isfinite(val)
      if k.endswith(':int'):assert str(int(r[k]))==r[k]
     except (ValueError,AssertionError):numeric_errors.append([f.name,i+2,k,r[k]])
 checks['neo4j_numeric_columns_valid']=not numeric_errors
 graph_edges,_=read(OUT/'neo4j_listing_amenity_edges.csv');checks['graph_edge_count_matches']=len(graph_edges)==len(edges)
 lookup={(e['listing_node_id'],e['category'],e['osm_id']):e for e in edges}
 checks['graph_edge_route_values_match']=all(all(str(g[k+':'+typ])==str(lookup[(g[':START_ID(Listing)'],g['category:string'],g[':END_ID(Amenity)'])][k]) for k,typ in [('rank','int'),('driving_distance_km','float'),('driving_duration_min','float'),('route_status','string')]) for g in graph_edges)
 source,_=read(ROOT/'inputs/phân tích hệ thống bds/cleaned_master_data.csv')
 checks['current_input_fields_preserved_except_key_redaction']=all(all(r[k]==lm[r['listing_id']][k] for k in r if k!='location_link') for r in source)
 coverage=[]
 for r in master:
  for cat in CATS:
   es=grouped.get((r['listing_id'],cat),[])
   coverage.append(dict(listing_id=r['listing_id'],category=cat,top5_count=len(es),routes_ok=sum(e['route_status']=='ok' for e in es),routes_snapped_far=sum(e['route_status']=='snapped_far' for e in es),routes_unreachable=sum(e['route_status']=='unreachable' for e in es),routes_pending=sum(e['route_status']=='pending' for e in es),selection_radius_km=RADIUS[cat],coverage_status='coordinate_review' if not r['latitude'] else 'no_poi_within_radius' if not es else 'five_candidates' if len(es)==5 else 'fewer_than_five'))
 write(OUT/'listing_category_coverage.csv',coverage)
 result={'passed':all(checks.values()),'checks':checks,'independent_groups_checked':tested,'neo4j_file_rows':rows_count,'route_status_counts':dict(collections.Counter(e['route_status'] for e in edges)),'numeric_errors':numeric_errors[:10]}
 (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));assert result['passed']
if __name__=='__main__':main()
