import json, re, time, urllib.request, urllib.parse, html
from html.parser import HTMLParser
from pathlib import Path

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.data={}; self.links=[]; self.meta={}
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='meta': self.meta[a.get('property',a.get('name',''))]=a.get('content','')
        for k in ('data-tralbum','data-band','data-blob'):
            if a.get(k):
                try: self.data[k]=json.loads(a[k])
                except ValueError: pass

def get(url):
    time.sleep(2)
    req=urllib.request.Request(url,headers={'User-Agent':'BlackUnicornCatalogue/1.0 (label catalogue sync)'})
    with urllib.request.urlopen(req,timeout=25) as r:
        if urllib.parse.urlparse(r.url).hostname not in ('larrylush.bandcamp.com','quietmanmusic.bandcamp.com','friendsloversandfamily.bandcamp.com'): raise ValueError('Unexpected redirect')
        p=Page(); p.feed(r.read(4000000).decode('utf-8','replace')); return p

def canonical(url):
    u=urllib.parse.urlparse(url)
    return 'https://'+u.netloc+u.path.rstrip('/')

path=Path('catalogue.json')
records=json.loads(path.read_text())
known={canonical(r['url']):r for r in records}
urls=set(known)
for host in ('larrylush.bandcamp.com','quietmanmusic.bandcamp.com','friendsloversandfamily.bandcamp.com'):
    try:
        base='https://'+host+'/music'
        p=get(base)
        for link in p.links:
            u=urllib.parse.urljoin(base,link); parts=urllib.parse.urlparse(u)
            if parts.hostname==host and parts.path.startswith('/album/'): urls.add(canonical(u))
        print('Discovery:',host,len(urls))
    except Exception as e: print('Discovery failed:',host,e)
seen_ids={int(r['embed']):r for r in records if r.get('embed')}
updated=0
for url in sorted(urls):
    old=known.get(url)
    if old and old.get('embed'): continue
    try:
        p=get(url); t=p.data.get('data-tralbum',{}); c=t.get('current') or {}
        aid=c.get('id') or t.get('id')
        if not aid:
            m=re.search(r'album=(\d+)',p.meta.get('og:video','')+' '+p.meta.get('og:video:secure_url',''))
            aid=int(m.group(1)) if m else None
        if not aid or not str(aid).isdigit(): raise ValueError('No album ID found')
        if old:
            old['embed']=int(aid)
            seen_ids[int(aid)]=old
        elif int(aid) in seen_ids:
            print('Duplicate album ID:',url,aid); continue
        else:
            title=c.get('title') or p.meta.get('og:title')
            artist=t.get('artist') or c.get('artist') or p.meta.get('og:site_name')
            art=p.meta.get('og:image')
            if not all(isinstance(x,str) and x for x in (title,artist,art)): raise ValueError('Incomplete metadata')
            records.append(dict(title=title,artist=artist,genre='Unclassified',img=art,url=url,embed=int(aid),description=c.get('about') or ''))
            seen_ids[int(aid)]=records[-1]
        updated+=1; print('Imported:',url,aid)
    except Exception as e: print('Skipped:',url,e)
if updated:
    path.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('Updated releases:',updated)
if not updated and any(not r.get('embed') for r in records): raise SystemExit('No updates; missing IDs remain. Review logs.')
