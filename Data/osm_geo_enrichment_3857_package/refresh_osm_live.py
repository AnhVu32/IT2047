#!/usr/bin/env python3
"""Incrementally refresh OSM POIs using Overpass, with persistent tile responses.
Run this ONLY on a host with internet access and respect Overpass rate limits.
Afterwards rerun build_from_osm_cache.py with --extra-poi refreshed_osm_poi_nodes.csv.
"""
import argparse,csv,json,math,re,time
from pathlib import Path
import requests

TYPES=('hospital','school','college_university','metro','mall','market','supermarket','park','bus_stop')
TAGS=[
 'nwr["amenity"~"^(hospital|clinic)$"]',
 'nwr["amenity"~"^(school|kindergarten|college|university)$"]',
 'nwr["shop"~"^(mall|supermarket)$"]',
 'nwr["amenity"="marketplace"]',
 'nwr["leisure"="park"]',
 'nwr["highway"="bus_stop"]',
 'nwr["railway"="station"]["station"="subway"]',
 'nwr["railway"="subway_entrance"]',
 'nwr["public_transport"="station"]["subway"="yes"]',
 'nwr["public_transport"="platform"]["bus"="yes"]'
]

def classify(t):
 cats=[];am=t.get('amenity','');sh=t.get('shop','');rw=t.get('railway','')
 if am in {'hospital','clinic'}:cats.append('hospital')
 if am in {'school','kindergarten'}:cats.append('school')
 if am in {'college','university'}:cats.append('college_university')
 if sh=='mall':cats.append('mall')
 if am=='marketplace':cats.append('market')
 if sh=='supermarket':cats.append('supermarket')
 if t.get('leisure')=='park':cats.append('park')
 if t.get('highway')=='bus_stop' or (t.get('public_transport')=='platform' and t.get('bus')=='yes'):cats.append('bus_stop')
 if (rw=='station' and t.get('station')=='subway') or rw=='subway_entrance' or (t.get('public_transport')=='station' and t.get('subway')=='yes'):cats.append('metro')
 return cats

def read_rows(path):
 with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write_rows(path,rows):
 fields=['osm_id','name','category','latitude','longitude','street','address','operator','source']
 with open(path,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main(a):
 cache=Path(a.cache_dir);cache.mkdir(parents=True,exist_ok=True)
 origin=read_rows(a.master);base={r['osm_id']:r for r in read_rows(a.base_poi)}
 coords=[]
 for r in origin:
  try:
   lat=float(r['latitude']);lon=float(r['longitude'])
   if 9.5<=lat<=11.5 and 105.8<=lon<=107.6:coords.append((lat,lon))
  except (ValueError,KeyError):pass
 # Tile IDs deterministically cover the listing point; bbox includes 7km pad,
 # enough to fetch local amenities around an entire tile.
 tiles=sorted(set((math.floor(lat/a.tile_degree),math.floor(lon/a.tile_degree)) for lat,lon in coords))
 succeeded=0
 for ilat,ilon in tiles:
  key=f'{ilat}_{ilon}'
  fp=cache/(key+'.json')
  if fp.exists():
   try:payload=json.loads(fp.read_text(encoding='utf8'))
   except (ValueError,OSError):fp.unlink();payload=None
  else:payload=None
  if payload is None:
   if succeeded>=a.max_tiles:continue
   pad=a.radius_km/111
   lat0=ilat*a.tile_degree-pad;lat1=(ilat+1)*a.tile_degree+pad
   lon_pad=a.radius_km/(111*math.cos(math.radians((lat0+lat1)/2)))
   lon0=ilon*a.tile_degree-lon_pad;lon1=(ilon+1)*a.tile_degree+lon_pad
   bbox=f'({lat0:.5f},{lon0:.5f},{lat1:.5f},{lon1:.5f})'
   query='[out:json][timeout:180];('+''.join(t+bbox+';' for t in TAGS)+');out center tags;'
   try:
    res=requests.post(a.overpass_url,data={'data':query},headers={'User-Agent':a.user_agent},timeout=(20,200))
    res.raise_for_status();payload=res.json()
    if not isinstance(payload.get('elements'),list):raise ValueError('No elements field')
    fp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    succeeded+=1;print('Downloaded tile',key,'POIs',len(payload['elements']),flush=True)
    time.sleep(a.sleep_seconds)
   except (requests.RequestException,ValueError) as exc:
    print('Failed tile',key,repr(exc),flush=True)
    continue
  for element in payload.get('elements',[]):
   tags=element.get('tags') or {};cats=classify(tags)
   if not cats:continue
   cc=element.get('center',element)
   lat=cc.get('lat');lon=cc.get('lon')
   if lat is None or lon is None:continue
   oid=f"{element['type']}/{element['id']}"
   old=base.get(oid,{})
   merged=set(cats)|set(x for x in str(old.get('category','')).split('|') if x)
   base[oid]={
    'osm_id':oid,'name':tags.get('name') or old.get('name',''),
    'category':'|'.join(sorted(merged)),'latitude':lat,'longitude':lon,
    'street':tags.get('addr:street') or old.get('street',''),
    'address':', '.join(x for x in [tags.get('addr:housenumber'),tags.get('addr:street'),tags.get('addr:city')] if x) or old.get('address',''),
    'operator':tags.get('operator') or old.get('operator',''),
    'source':'OpenStreetMap_Overpass_live'}
 write_rows(a.output,[v for k,v in sorted(base.items())]);print('Saved',len(base),'POIs to',a.output,flush=True)
 print('Processed',len(list(cache.glob('*.json'))),'of',len(tiles),'tiles, new requests this run',succeeded,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--master',required=True,help='Previously built listings_209cols...csv')
 p.add_argument('--base-poi',required=True)
 p.add_argument('--output',required=True)
 p.add_argument('--cache-dir',required=True)
 p.add_argument('--overpass-url',default='https://overpass.kumi.systems/api/interpreter')
 p.add_argument('--tile-degree',type=float,default=.10)
 p.add_argument('--radius-km',type=float,default=7)
 p.add_argument('--max-tiles',type=int,default=3)
 p.add_argument('--sleep-seconds',type=float,default=12)
 p.add_argument('--user-agent',required=True,help='Identify your organization/contact per OSM API etiquette')
 main(p.parse_args())
