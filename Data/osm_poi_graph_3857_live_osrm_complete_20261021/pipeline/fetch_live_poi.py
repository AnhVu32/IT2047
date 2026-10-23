#!/usr/bin/env python3
"""Fetch one bounded, auditable Overpass query. No listing IDs/addresses are sent."""
import argparse,json,pathlib,urllib.request,urllib.parse,datetime,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
if ROOT.name=='pipeline':ROOT=ROOT.parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--endpoint',default='https://overpass-api.de/api/interpreter');p.add_argument('--user-agent',required=True);p.add_argument('--refresh',action='store_true');a=p.parse_args()
 cache=ROOT/'live_cache';cache.mkdir(exist_ok=True);output=cache/'overpass_de_live.json';query=(cache/'overpass_query.ql').read_text()
 if output.exists() and not a.refresh:print('Using existing snapshot',output);return
 req=urllib.request.Request(a.endpoint,data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':a.user_agent,'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=150) as r:raw=r.read()
 payload=json.loads(raw)
 if payload.get('remark') or not isinstance(payload.get('elements'),list):raise RuntimeError('Incomplete/error response; existing snapshot preserved: '+str(payload.get('remark')))
 meta={'endpoint':a.endpoint,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'osm_snapshot_at':payload.get('osm3s',{}).get('timestamp_osm_base'),'elements':len(payload['elements']),'sha256':hashlib.sha256(raw).hexdigest()}
 output.write_bytes(raw);(cache/'overpass_download_metadata.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
