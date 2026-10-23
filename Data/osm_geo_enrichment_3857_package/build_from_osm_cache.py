#!/usr/bin/env python3
"""Spatial enrichment of listings using verified OSM POIs cached in a historical dataset.
Does NOT call live APIs; route metrics only transfer when both listing ID and
OSM feature match, and source and target coordinates are within 30 metres.

Usage:
 python build_from_osm_cache.py --input cleaned_master_data_50cols_enriched.csv \
   --historical Final_Data_full_amenities_enriched.csv --output output_dir
Use refresh_osm_live.py to update the OSM POI catalog from Overpass on a networked machine.
"""
import argparse, csv, math, re, unicodedata, hashlib, json, sys
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

CATEGORIES = ['hospital','school','college_university','metro','mall','market','supermarket','park','bus_stop']
RADIUS_KM={'hospital':7,'school':3,'college_university':7,'metro':5,'mall':7,'market':3,'supermarket':3,'park':5,'bus_stop':2}
BEN_THANH=(10.772,106.6983)
ALPHABET='0123456789bcdefghjkmnpqrstuvwxyz'

def clean(s):return str(s or '').strip()
def norm(s):
 s=unicodedata.normalize('NFD',clean(s).lower().replace('đ','d'))
 s=''.join(c for c in s if unicodedata.category(c)!='Mn')
 return ' '.join(re.findall(r'[a-z0-9]+',s))
def fnum(s):
 try:return float(s)
 except (ValueError,TypeError):return None
def latlon(v):
 m=re.search(r'(?:q=)?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)',clean(v))
 return (float(m.group(1)),float(m.group(2))) if m else None
def in_area(c):return c is not None and 9.5<=c[0]<=11.5 and 105.8<=c[1]<=107.6
def dist_m(a,b):
 lat1,lon1,lat2,lon2=map(math.radians,(*a,*b))
 dlat=lat2-lat1;dlon=lon2-lon1
 q=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
 return 12742000*math.asin(min(1,math.sqrt(q)))
def to_local(coords):
 coords=np.asarray(coords,dtype=float)
 return np.column_stack(((coords[:,0]-10.8)*111195,(coords[:,1]-106.7)*111195*math.cos(math.radians(10.8))))
def geohash(lat,lon,precision=7):
 lat_range=[-90.,90.];lon_range=[-180.,180.];is_even=True;bits=[16,8,4,2,1];s='';ch=0;bit=0
 while len(s)<precision:
  rg=lon_range if is_even else lat_range;mid=sum(rg)/2.;v=lon if is_even else lat
  if v>=mid:ch|=bits[bit];rg[0]=mid
  else:rg[1]=mid
  is_even=not is_even
  if bit==4:s+=ALPHABET[ch];ch=0;bit=0
  else:bit+=1
 return s
def csv_read(p):
 with open(p,encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);return list(reader),reader.fieldnames
def csv_write(p,cols,rows):
 with open(p,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
def common(values):
 items=[clean(x) for x in values if clean(x)]
 return Counter(items).most_common(1)[0][0] if items else ''
def parse_admin(address):
 a=[x.strip() for x in clean(address).split(',')]
 ward=next((x for x in reversed(a) if re.match(r'^(?:Phường|Xã|Thị trấn)\b',x,re.I)),'')
 if a and ward in a:
  start=a.index(ward)
  street=a[start-1] if start>=1 else ''
  label=', '.join(a[:start-1]).strip() if start>=2 else (a[0] if a else '')
 else:
  street=a[-2] if len(a)>1 else ''
  label=a[0] if a else ''
 return ward,street,label

def build(args):
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 fresh,h50=csv_read(args.input)
 historical,h209=csv_read(args.historical)
 # Existing OSM IDs/coordinates are the only verified POI evidence.
 poi=defaultdict(lambda:defaultdict(list))
 hist_by_id=defaultdict(list)
 address_candidates=defaultdict(list)
 for x in historical:
  hist_by_id[x['listing_id']].append(x)
  cc=(fnum(x.get('latitude')),fnum(x.get('longitude')))
  if in_area(cc) and (fnum(x.get('coordinate_confidence')) or 0)>=0.8:
   address_candidates[norm(x.get('address'))].append((cc,'historical'))
  for category in CATEGORIES:
   p='nearest_'+category+'_'
   osm=clean(x.get(p+'osm_id'))
   point=(fnum(x.get(p+'latitude')),fnum(x.get(p+'longitude')))
   if not osm or not re.match(r'^(node|way|relation)/\d+$',osm) or not in_area(point):continue
   rr=poi[osm]
   rr['categories'].append(category)
   rr['name'].append(x.get(p+'name'))
   rr['latitude'].append(point[0]);rr['longitude'].append(point[1])
   for k,field in [('street','street'),('address','address_osm'),('operator','operator')]:rr[k].append(x.get(p+field))
 # Fresh valid listing coordinates are an additional exact-address imputation signal.
 for x in fresh:
  c=latlon(x.get('latitude_longitude'))
  if in_area(c):address_candidates[norm(x.get('address'))].append((c,'new_valid_listing'))

 nodes=[]
 for oid,agg in sorted(poi.items()):
  cats=sorted(set(agg['categories']))
  nodes.append(dict(osm_id=oid,name=common(agg['name']),category='|'.join(cats),latitude=round(float(np.median(agg['latitude'])),8),longitude=round(float(np.median(agg['longitude'])),8),street=common(agg['street']),address=common(agg['address']),operator=common(agg['operator']),source='OpenStreetMap_Overpass_historical_cache'))
 if args.extra_poi and Path(args.extra_poi).exists():
  external,_=csv_read(args.extra_poi)
  byid={r['osm_id']:r for r in nodes}
  for r in external:
   if re.match(r'^(node|way|relation)/\d+$',r.get('osm_id','')) and in_area((fnum(r.get('latitude')),fnum(r.get('longitude')))):
    byid[r['osm_id']]=r
  nodes=sorted(byid.values(),key=lambda x:x['osm_id'])
 poi_file=out/'osm_poi_nodes.csv'
 csv_write(poi_file,['osm_id','name','category','latitude','longitude','street','address','operator','source'],nodes)
 cat_nodes={k:[] for k in CATEGORIES}
 for node in nodes:
  for cat in node['category'].split('|'):
   if cat in cat_nodes:cat_nodes[cat].append(node)
 cat_trees={}
 for cat,arr in cat_nodes.items():
  coord=np.array([[float(x['latitude']),float(x['longitude'])] for x in arr],float)
  cat_trees[cat]=(cKDTree(to_local(coord)),arr) if len(arr) else (None,[])
 # For each bad source coordinate, use high-confidence exact address or exact
 # listing ID; never substitute arbitrary ward centroids for POI search.
 geo=[];review=[];counts=Counter()
 for x in fresh:
  original=latlon(x.get('latitude_longitude'))
  coord=original if in_area(original) else None
  status='original_valid' if coord else ('original_out_of_region' if original else 'missing_original')
  source='new_listing_latitude_longitude' if coord else ''
  confidence=1.0 if coord else None
  if coord is None:
   prev=[r for r in hist_by_id.get(x['listing_id'],[]) if in_area((fnum(r.get('latitude')),fnum(r.get('longitude')))) and (fnum(r.get('coordinate_confidence')) or 0)>=.9]
   if prev:
    coords=[(float(r['latitude']),float(r['longitude'])) for r in prev]
    if max(dist_m(coords[0],v) for v in coords)<150:
     coord=coords[0];status='imputed_same_listing_id';source='historical_matching_listing_id';confidence=.92
  if coord is None:
   candidates=[c for c,s in address_candidates.get(norm(x.get('address')),[]) if in_area(c)]
   if candidates:
    # Find the strongest <=250m cluster. Reject split/ambiguous addresses.
    pts=to_local(candidates);tree=cKDTree(pts)
    neighbors=[tree.query_ball_point(v,r=250) for v in pts]
    best=max(neighbors,key=len)
    if len(best)>=max(1,math.ceil(.6*len(candidates))):
     cluster=np.array([candidates[i] for i in best]);candidate=(float(np.median(cluster[:,0])),float(np.median(cluster[:,1])))
     if max(dist_m(candidate,tuple(z)) for z in cluster)<250:
      coord=candidate;status='imputed_exact_address';source='historical_or_new_listing_exact_address';confidence=.76 if len(best)>=2 else .65
   if coord is None:
    counts['unresolved_coordinates']+=1
    review.append(dict(listing_id=x['listing_id'],issue='invalid_coordinate_no_safe_replacement',latitude_longitude=x.get('latitude_longitude',''),address=x.get('address',''),detail='Requires manual geocoding; no POI edges created'))
  counts[status]+=1
  geo.append(dict(coord=coord,orig=original,status=status,source=source,confidence=confidence))

 valid_idx=[i for i,z in enumerate(geo) if z['coord'] is not None]
 valid_coords=[geo[i]['coord'] for i in valid_idx]
 xyz=to_local(valid_coords) if valid_coords else np.zeros((0,2))
 tree=cKDTree(xyz) if len(xyz) else None
 n=len(fresh)
 densities=[None]*n;nearest_dist=[None]*n;labels=['']*n; sizes=['']*n
 if tree:
  nearest_d,inds=tree.query(xyz,k=2 if len(xyz)>1 else 1)
  # Spatial clusters use single-link connected components with 150m adjacency.
  pairs=tree.query_pairs(r=150)
  parent=list(range(len(valid_idx)))
  def root(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  for a,b in pairs:
   ra=root(a);rb=root(b)
   if ra!=rb:parent[rb]=ra
  comps=defaultdict(list)
  for j in range(len(valid_idx)):comps[root(j)].append(j)
  sorted_comps=sorted(comps.values(),key=lambda c:(round(float(np.mean(xyz[c,0])),3),round(float(np.mean(xyz[c,1])),3)))
  for k,cluster in enumerate(sorted_comps,1):
   cluster_label=f'G{k:04d}'
   for j in cluster:labels[valid_idx[j]]=cluster_label;sizes[valid_idx[j]]=len(cluster)
  for j,orig_i in enumerate(valid_idx):
   densities[orig_i]=len(tree.query_ball_point(xyz[j],r=1000))-1
   nearest_dist[orig_i]=round(float(nearest_d[j,1]),2) if len(xyz)>1 else None

 # Batch all category nearest-neighbor searches in SciPy/NumPy.
 # The original per-row implementation is prohibitively slow on low-CPU servers.
 nearby_by_idx=[{} for _ in range(n)]
 if len(valid_idx):
  for cat,(ptree,arr) in cat_trees.items():
   if ptree is None:continue
   count=min(12,len(arr))
   candidate_dist, candidate_idx=ptree.query(xyz,k=count)
   candidate_idx=np.asarray(candidate_idx)
   if candidate_idx.ndim==1:candidate_idx=candidate_idx[:,None]
   poi_lats=np.radians(np.array([float(v['latitude']) for v in arr]))
   poi_lons=np.radians(np.array([float(v['longitude']) for v in arr]))
   lats=np.radians(np.array([v[0] for v in valid_coords]))[:,None]
   lons=np.radians(np.array([v[1] for v in valid_coords]))[:,None]
   a_lat=poi_lats[candidate_idx];a_lon=poi_lons[candidate_idx]
   hav=np.sin((a_lat-lats)/2)**2+np.cos(lats)*np.cos(a_lat)*np.sin((a_lon-lons)/2)**2
   distances=12742*np.arcsin(np.minimum(1,np.sqrt(np.maximum(0,hav))))
   ordered=np.argsort(distances,axis=1)
   for row_idx,source_idx in enumerate(valid_idx):
    nearby_by_idx[source_idx][cat]=[(float(distances[row_idx,j]),arr[int(candidate_idx[row_idx,j])]) for j in ordered[row_idx]]
 edges=[]; full=[];score_data={};no_poi=Counter();invalid_for_poi=0
 for i,(x,z) in enumerate(zip(fresh,geo)):
  cc=z['coord'];row={k:clean(x.get(k)) for k in h50}
  for col in h209:
   if col not in row:row[col]=''
  row['latitude_original']=z['orig'][0] if z['orig'] else ''
  row['longitude_original']=z['orig'][1] if z['orig'] else ''
  row['latitude']=round(cc[0],8) if cc else ''
  row['longitude']=round(cc[1],8) if cc else ''
  row['coordinate_status']=z['status'];row['coordinate_source']=z['source'];row['coordinate_confidence']=z['confidence'] or ''
  row['latitude_longitude_enriched']=f'q={row["latitude"]},{row["longitude"]}' if cc else ''
  row['map_link_enriched']=f'https://www.openstreetmap.org/?mlat={row["latitude"]}&mlon={row["longitude"]}#map=16/{row["latitude"]}/{row["longitude"]}' if cc else ''
  ward,street,label=parse_admin(x.get('address'))
  row['ward_commune']=ward;row['ward_commune_name']=re.sub(r'^(Phường|Xã|Thị trấn)\s+','',ward,flags=re.I);row['ward_commune_type']=ward.split(' ')[0] if ward else ''
  row['street_name']=street;row['road_name_final']=street;row['road_name_source']='parsed_address_not_osm_road_snap' if street else ''
  row['location_label']=label;row['former_admin_area']=clean(x.get('old_address')).split(',')[0].strip()
  row['geo_cluster_150m']=labels[i];row['geo_cluster_size']=sizes[i]
  row['nearest_listing_distance_m']=nearest_dist[i] if nearest_dist[i] is not None else ''
  row['listing_density_1km']=densities[i] if densities[i] is not None else ''
  if cc:
   row['geohash_6']=geohash(*cc,6);row['geohash_7']=geohash(*cc,7)
   row['location_graph_key']=ward+'|'+row['geohash_7']
   d=dist_m(cc,BEN_THANH)/1000;row['distance_to_ben_thanh_km']=round(d,3)
   row['distance_band_ben_thanh']='0-5km' if d<5 else '5-10km' if d<10 else '10-20km' if d<20 else '20km+'
  else:invalid_for_poi+=1
  cat_present=[];within_known_count=0
  matching=hist_by_id.get(x['listing_id'],[])
  for cat in CATEGORIES:
   if not cc:continue
   dist_candidates=nearby_by_idx[i].get(cat,[])
   if not dist_candidates:continue
   firstd,first=dist_candidates[0];p='nearest_'+cat+'_'
   for col,suffix in [('name','name'),('osm_id','osm_id'),('latitude','latitude'),('longitude','longitude'),('street','street'),('address_osm','address'),('operator','operator')]:
    row[p+col]=first.get(suffix,'')
   row[p+'street_source']='OpenStreetMap_cached_tags' if first.get('street') else ''
   row[cat+'_straight_line_km']=round(firstd,3)
   row[cat+'_data_source']='OpenStreetMap_Overpass_historical_cache'
   # Retain an old OSRM route only when listing ID and OSM ID match,
   # and coordinates are within 30 metres of the original listing.
   route_from=None
   for h in matching:
    previous=(fnum(h.get('latitude')),fnum(h.get('longitude')))
    if not in_area(previous) or dist_m(cc,previous)>30:continue
    if h.get(p+'osm_id')==first['osm_id'] and fnum(h.get(cat+'_driving_distance_km')) is not None and fnum(h.get(cat+'_driving_duration_min')) is not None:
     route_from=h;break
   if route_from:
    row[cat+'_driving_distance_km']=route_from[cat+'_driving_distance_km']
    row[cat+'_driving_duration_min']=route_from[cat+'_driving_duration_min']
    row[cat+'_route_source']='historical_OSRM_same_listing_same_osm_id_within_30m'
   threshold_col={'school':('within_school_2km_driving',2),'college_university':('within_college_university_5km_driving',5),'metro':('within_metro_3km_driving',3),'mall':('within_mall_5km_driving',5),'market':('within_market_2km_driving',2),'supermarket':('within_supermarket_2km_driving',2),'park':('within_park_5km_driving',5),'bus_stop':('within_bus_stop_2km_driving',2)}.get(cat)
   if threshold_col and route_from:
    field,lim=threshold_col;matchbool=float(row[cat+'_driving_distance_km'])<=lim
    row[field]='1' if matchbool else '0';within_known_count+=int(matchbool)
   # Top K edges: only local POIs. No distant edges pretending to be 'near'.
   top=0
   for d,obj in dist_candidates:
    if d>RADIUS_KM[cat] or top>=5:break
    top+=1
    edge=dict(listing_node_id=x['listing_id'],osm_id=obj['osm_id'],category=cat,rank=top,straight_line_km=round(d,3),driving_distance_km='',driving_duration_min='',route_source='',poi_data_source='OpenStreetMap_Overpass_historical_cache',coordinate_status=z['status'])
    if top==1 and route_from:
     edge.update(driving_distance_km=row[cat+'_driving_distance_km'],driving_duration_min=row[cat+'_driving_duration_min'],route_source=row[cat+'_route_source'])
    edges.append(edge)
   if top==0:no_poi[cat]+=1
   else:cat_present.append(cat)
  row['nearby_category_count']=len(cat_present);row['nearby_categories']='|'.join(cat_present)
  # Null unless all 8 threshold categories have route measurements. The historical
  # dataset used route metrics for every category, but this new dataset does not.
  if sum(bool(row.get(cat+'_driving_distance_km')) for cat in CATEGORIES if cat!='hospital')==8:
   row['amenity_types_within_threshold_count']=within_known_count
  full.append(row)
 # Keep exact 209 original schema; extra QA in a separate CSV.
 csv_write(out/'listings_209cols_osm_cache_enriched.csv',h209,full)
 csv_write(out/'listing_amenity_top5_edges.csv',['listing_node_id','osm_id','category','rank','straight_line_km','driving_distance_km','driving_duration_min','route_source','poi_data_source','coordinate_status'],edges)
 geo_review=[]
 for i,(x,z) in enumerate(zip(fresh,geo)):
  geo_review.append(dict(listing_id=x['listing_id'],address=x.get('address',''),original_latitude=z['orig'][0] if z['orig'] else '',original_longitude=z['orig'][1] if z['orig'] else '',latitude=z['coord'][0] if z['coord'] else '',longitude=z['coord'][1] if z['coord'] else '',coordinate_status=z['status'],coordinate_source=z['source'],coordinate_confidence=z['confidence'] or '',edge_count=sum(1 for ee in [])))
 csv_write(out/'coordinate_quality.csv',list(geo_review[0]),geo_review)
 csv_write(out/'needs_coordinate_review.csv', ['listing_id','issue','latitude_longitude','address','detail'],review)
 # Make Neo4j import files; keep listing schema intentionally compact, 50-cols original
 # plus normalized location properties. Let users attach semantic features later.
 listcols=['listing_node_id:ID(Listing)','listing_id:string','title:string','description:string','price_range:float','area:float','bedrooms:int','bathrooms:int','property_type:string','legal_status:string','address_new:string','address_old:string','former_admin_area:string','ward_commune:string','road_name_final:string','latitude:float','longitude:float','geohash_6:string','geohash_7:string','geo_cluster_150m:string','coordinate_status:string',':LABEL']
 lrows=[]
 for r in full:
  lrows.append(dict(zip(listcols,[r['listing_id'],r['listing_id'],r['title'],r['description'],r['price_range'] if fnum(r['price_range']) is not None else '',r['area'] if fnum(r['area']) is not None else '',str(int(float(r['bedrooms']))) if fnum(r['bedrooms']) is not None and float(r['bedrooms']).is_integer() else '',str(int(float(r['bathrooms']))) if fnum(r['bathrooms']) is not None and float(r['bathrooms']).is_integer() else '',r['property_type'],r['legal_status'],r['address'],r['old_address'],r['former_admin_area'],r['ward_commune'],r['road_name_final'],r['latitude'],r['longitude'],r['geohash_6'],r['geohash_7'],r['geo_cluster_150m'],r['coordinate_status'],'Listing'])))
 csv_write(out/'neo4j_listing_nodes.csv',listcols,lrows)
 pc=['osm_id:ID(Amenity)','name:string','category:string','latitude:float','longitude:float','street:string','address:string','operator:string',':LABEL']
 catlabels={'hospital':'Hospital','school':'School','college_university':'CollegeUniversity','metro':'MetroStation','mall':'Mall','market':'Market','supermarket':'Supermarket','park':'Park','bus_stop':'BusStop'}
 csv_write(out/'neo4j_amenity_nodes.csv',pc,[dict(zip(pc,[r['osm_id'],r['name'],r['category'],r['latitude'],r['longitude'],r['street'],r['address'],r['operator'],';'.join(['Amenity']+[catlabels[x] for x in r['category'].split('|') if x in catlabels])])) for r in nodes])
 ec=[':START_ID(Listing)',':END_ID(Amenity)','category:string','rank:int','straight_line_km:float','driving_distance_km:float','driving_duration_min:float','route_source:string',':TYPE']
 csv_write(out/'neo4j_listing_amenity_edges.csv',ec,[dict(zip(ec,[r['listing_node_id'],r['osm_id'],r['category'],r['rank'],r['straight_line_km'],r['driving_distance_km'],r['driving_duration_min'],r['route_source'],'NEAR_AMENITY'])) for r in edges])
 cnodecols=['cluster_id:ID(GeoCluster)','centroid_latitude:float','centroid_longitude:float','listing_count:int',':LABEL']
 cluster_coordinates=defaultdict(list)
 for r in full:
  if r['geo_cluster_150m'] and r['latitude']!='':cluster_coordinates[r['geo_cluster_150m']].append((float(r['latitude']),float(r['longitude'])))
 csv_write(out/'neo4j_cluster_nodes.csv',cnodecols,[dict(zip(cnodecols,[key,round(float(np.mean(vals,axis=0)[0]),8),round(float(np.mean(vals,axis=0)[1]),8),len(vals),'GeoCluster'])) for key,vals in sorted(cluster_coordinates.items())])
 csv_write(out/'neo4j_listing_cluster_edges.csv',[':START_ID(Listing)',':END_ID(GeoCluster)',':TYPE'],[{':START_ID(Listing)':r['listing_id'],':END_ID(GeoCluster)':r['geo_cluster_150m'],':TYPE':'IN_CLUSTER'} for r in full if r['geo_cluster_150m']])
 # Administrative graph: preserve both current ward and former district/city.
 ward_dict={};former_dict={};listing_ward=[];listing_former=[];ward_former=Counter()
 for row in full:
  ward=clean(row['ward_commune']);former=clean(row['former_admin_area']);city=clean(row['city_province'])
  oldprov=clean(row['old_address'].split(',')[-1]).removesuffix(' cũ').strip()
  if ward:
   wid='ward|'+norm(city).replace(' ','-')+'|'+norm(ward).replace(' ','-')
   ward_dict[wid]=(ward,city)
   listing_ward.append({':START_ID(Listing)':row['listing_id'],':END_ID(Ward)':wid,':TYPE':'IN_WARD'})
  if former:
   fid='former-area|'+norm(oldprov).replace(' ','-')+'|'+norm(former).replace(' ','-')
   former_dict[fid]=(former,oldprov)
   listing_former.append({':START_ID(Listing)':row['listing_id'],':END_ID(FormerAdminArea)':fid,':TYPE':'IN_FORMER_AREA'})
   if ward:ward_former[(wid,fid)]+=1
 csv_write(out/'neo4j_ward_nodes.csv',['ward_id:ID(Ward)','name:string','city_province:string',':LABEL'],[{'ward_id:ID(Ward)':k,'name:string':v[0],'city_province:string':v[1],':LABEL':'Ward'} for k,v in sorted(ward_dict.items())])
 csv_write(out/'neo4j_former_admin_area_nodes.csv',['former_area_id:ID(FormerAdminArea)','name:string','former_city_province:string',':LABEL'],[{'former_area_id:ID(FormerAdminArea)':k,'name:string':v[0],'former_city_province:string':v[1],':LABEL':'FormerAdminArea'} for k,v in sorted(former_dict.items())])
 csv_write(out/'neo4j_listing_ward_edges.csv',[':START_ID(Listing)',':END_ID(Ward)',':TYPE'],listing_ward)
 csv_write(out/'neo4j_listing_former_area_edges.csv',[':START_ID(Listing)',':END_ID(FormerAdminArea)',':TYPE'],listing_former)
 csv_write(out/'neo4j_ward_former_area_edges.csv',[':START_ID(Ward)',':END_ID(FormerAdminArea)','supporting_listing_count:int',':TYPE'],[{':START_ID(Ward)':k[0],':END_ID(FormerAdminArea)':k[1],'supporting_listing_count:int':v,':TYPE':'MAPPED_FROM'} for k,v in sorted(ward_former.items())])
 summary={'input_listings':len(fresh),'input_columns':len(h50),'output_master_columns':len(h209),'unique_osm_poi':len(nodes),'poi_by_category':{k:len(v) for k,v in cat_nodes.items()},'edges_top5_in_radius':len(edges),'edges_by_category':dict(Counter(x['category'] for x in edges)),'listings_with_any_amenity':len(set(x['listing_node_id'] for x in edges)),'listings_without_safe_coordinates':invalid_for_poi,'coordinate_status_counts':dict(counts),'edge_route_reuse_count':sum(1 for x in edges if x['route_source']),'hard_radius_km':RADIUS_KM,'no_nearby_poi_cached_by_category':dict(no_poi),'geo_cluster_nodes':len(cluster_coordinates),'ward_nodes':len(ward_dict),'former_area_nodes':len(former_dict),'ward_former_area_mappings':len(ward_former),'cache_provenance':'POIs from historical Final_Data_full_amenities_enriched.csv where source is OpenStreetMap_Overpass; no new OSM fetch.','distance_scope':'straight_line_km is computed haversine, not route distance; no fabricated driving values','created_from':Path(args.input).name}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True);p.add_argument('--historical',required=True);p.add_argument('--output',required=True);p.add_argument('--extra-poi',default=None)
 build(p.parse_args())
