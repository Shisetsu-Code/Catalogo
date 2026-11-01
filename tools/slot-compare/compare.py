#!/usr/bin/env python3
"""Collect public game catalogs from SlotCatalog and SlotsTemple; never start a game."""
import argparse
import csv
import json
import logging
import math
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

PROVIDERS = {
    "3 Oaks": ("3 Oaks", "3 Oaks Gaming", "3Oaks"),
    "BGaming": ("BGaming", "B Gaming"),
    "ELK Studios": ("ELK Studios", "Elk"),
    "Endorphina": ("Endorphina",),
    "Hacksaw Gaming": ("Hacksaw Gaming", "Hacksaw"),
    "KA Gaming": ("KA Gaming", "KAGaming"),
    "NetEnt": ("NetEnt", "Net Ent"),
    "Nolimit City": ("Nolimit City", "NoLimit City"),
    "Play'n GO": ("Play'n GO", "Play N Go", "Play and Go"),
    "Playson": ("Playson",),
    "Playtech": ("Playtech",),
    "Pragmatic Play": ("Pragmatic Play",),
}
CATALOG_FALLBACK = {
    "3 Oaks": "3-Oaks-Gaming",
    "BGaming": "BGAMING",
    "ELK Studios": "ELK-Studios",
    "Endorphina": "Endorphina",
    "Hacksaw Gaming": "Hacksaw-Gaming",
    "KA Gaming": "KA-Gaming",
    "NetEnt": "NetEnt",
    "Nolimit City": "Nolimit-City",
    "Play'n GO": "Play-n-GO",
    "Playson": "Playson",
    "Playtech": "Playtech",
    "Pragmatic Play": "Pragmatic-Play",
}
TEMPLE_FALLBACK = {
    "3 Oaks": "3-oaks",
    "BGaming": "bgaming",
    "ELK Studios": "elk-studios",
    "Endorphina": "endorphina",
    "Hacksaw Gaming": "hacksaw-gaming",
    "KA Gaming": "ka-gaming",
    "NetEnt": "net-ent",
    "Nolimit City": "nolimit-city",
    "Play'n GO": "play-n-go",
    "Playson": "playson",
    "Playtech": "playtech",
    "Pragmatic Play": "pragmatic-play",
}
BASE_C = "https://slotcatalog.com/en"
BASE_T = "https://www.slotstemple.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CatalogComparison/1.0; research; contact via GitHub Shisetsu-Code/Catalogo)",
           "Accept-Language": "en-US,en;q=0.9"}
LOG = logging.getLogger("catalog-compare")
FIELDS = ["proveedor","juego","nombre_normalizado","slotcatalog_url","slotstemple_url","fuentes","estado"]

def normalize(value):
    s = unicodedata.normalize("NFKD", value or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

def alias_match(a, b):
    return normalize(a) == normalize(b)

def game_url(url, site):
    p = urlparse(url)
    path = p.path.rstrip("/")
    if site == "slotcatalog":
        return (p.hostname or "").endswith("slotcatalog.com") and bool(re.match(r"^/en/slots/[^/]+$",path,re.I))
    if not (p.hostname or "").endswith("slotstemple.com"):
        return False
    return bool(re.match(r"^/(?:free-slots|slots)/[^/]+$",path,re.I)) and not path.endswith(("by-maker","free-slots"))

def title_from_anchor(a, url, site):
    t = a.get_text(" ", strip=True)
    # Alt text may be the only text on image cards.
    if not t:
        img = a.find("img")
        if img: t = img.get("alt") or img.get("title") or ""
    t = re.sub(r"^(more details|play (?:for )?free|play demo|read review)\s*:?\s*", "", t,flags=re.I).strip()
    if not t or t.lower() in {"go to casino","more details","play","details","play free","play now"}:
        slug = unquote(urlparse(url).path.strip("/").split("/")[-1])
        t = slug.replace("-"," ").replace("_"," ")
    return re.sub(r"\s+"," ",t).strip()

def links_from_html(html, url, site, provider_url=None):
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.select("a[href]"):
        dest = urljoin(url, a.get("href","")).split("#")[0]
        if not game_url(dest, site):
            continue
        if provider_url and dest.rstrip("/") == provider_url.rstrip("/"):
            continue
        title = title_from_anchor(a,dest,site)
        if len(title) < 2 or len(title) > 140: continue
        # URL uniquely identifies a listing entry on each site.
        found.setdefault(dest.rstrip("/"), title)
    return found

def fetch(session, url, *, delay=0.35):
    time.sleep(delay)
    r=session.get(url,timeout=35,headers=HEADERS)
    if r.status_code == 429 or r.status_code >= 500:
        raise RuntimeError(f"HTTP {r.status_code} {url}")
    r.raise_for_status()
    if "text/html" not in r.headers.get("content-type","text/html"):
        raise RuntimeError(f"not HTML at {url}")
    return r.text, r.url

def index_links(session, index, site):
    html, actual=fetch(session,index)
    soup=BeautifulSoup(html,"html.parser")
    entries=[]
    for a in soup.select("a[href]"):
        url=urljoin(actual,a.get("href",""))
        path=urlparse(url).path
        if site=="slotcatalog" and not re.search(r"/en/soft/[^/]+/?$",path,re.I): continue
        if site=="slotstemple" and not re.search(r"/free-slots/[^/]+/?$",path,re.I): continue
        # On the makers index, the link often says "See all N Games"; the maker
        # is in the previous sibling/parent.
        label=a.get_text(" ",strip=True)
        parent=a.parent
        for _ in range(3):
            if parent is not None:
                label += " " + parent.get_text(" ",strip=True)[:100]
                parent=parent.parent
        entries.append((url,label))
    return entries

def pick_index(entries, aliases, site):
    choices=[]
    for url, label in entries:
        slug=unquote(urlparse(url).path.rstrip("/").split("/")[-1]).replace("-"," ")
        for alias in aliases:
            if alias_match(slug,alias):
                return url
        for alias in aliases:
            if re.search(r"(?:^|\W)"+re.escape(alias)+r"(?:\W|$)",label,re.I):
                choices.append(url)
                break
    return choices[0] if choices else None

def browser_page(page, url):
    r=page.goto(url,wait_until="domcontentloaded",timeout=45000)
    page.wait_for_timeout(1800)
    code=r.status if r else None
    if code in (403,429):
        raise RuntimeError(f"HTTP {code} {url} (access restricted)")
    return page.content(), page.url

def slotcatalog(session, page, provider_url, max_pages=160):
    records={}
    pages=[]
    error=""
    try:
        html,actual=fetch(session, provider_url)
        # Prefer server-rendered HTML. A JS fallback runs if cards are missing.
        if len(links_from_html(html,actual,"slotcatalog"))<3:
            html,actual=browser_page(page,provider_url)
        match=re.search(r"Items:\s*([0-9,]+)\s*/\s*Displaying\s*\d+\s*[-–]\s*(\d+)",BeautifulSoup(html,"html.parser").get_text(" ",strip=True),re.I)
        expected=int(match.group(1).replace(",","")) if match else None
        per_page=int(match.group(2)) if match else 12
        n_pages=min(max_pages, math.ceil(expected/per_page)) if expected else max_pages
        # Collect the site's actual pagination URLs, not guessed request parameters.
        soup=BeautifulSoup(html,"html.parser")
        choices={}
        for a in soup.select("a[href]"):
            u=urljoin(actual,a.get("href",""))
            if not u.startswith(provider_url.rstrip("/")+"/"): continue
            n=u.rstrip("/").split("/")[-1]
            if n.isdigit(): choices[int(n)]=u
        for n in range(1,n_pages+1):
            target=actual if n==1 else choices.get(n,f"{provider_url.rstrip('/')}/{n}")
            try:
                if n==1: h, landed=html,actual
                else:
                    h,landed=fetch(session,target)
                    if len(links_from_html(h,landed,"slotcatalog"))<3:
                        h,landed=browser_page(page,target)
                items=links_from_html(h,landed,"slotcatalog",provider_url)
                fresh=0
                for link,name in items.items():
                    if link not in records:
                        records[link]=name; fresh+=1
                pages.append({"page":n,"url":target,"found":len(items),"new":fresh})
                LOG.info("SlotCatalog %s page %d/%d new=%d total=%d",provider_url,n,n_pages,fresh,len(records))
                # Guard against redirect loops / inaccessible pagination.
                if n>1 and fresh==0:
                    error=f"pagination ceased at {n}; check subsequent pages"
                    break
                if not expected and n>1 and len(items)<3:
                    break
                if not expected and n>=2 and len(items)<per_page:
                    break
            except Exception as ex:
                error=f"page {n}: {ex}"
                LOG.warning("SlotCatalog %s %s",provider_url,error)
                break
        if expected and len(records)!=expected:
            error=(error+"; " if error else "")+f"extracted {len(records)} != advertised {expected}"
            if len(records)>expected:
                # Entries from navigation/related-games are contaminating the listing.
                records={}
        return records,{"count":len(records),"advertised":expected,"pages":pages,"complete":not bool(error),"error":error,"url":provider_url}
    except Exception as ex:
        return {},{"count":0,"advertised":None,"pages":pages,"complete":False,"error":str(ex),"url":provider_url}

def slotstemple(page, url, max_scroll=120):
    records={}
    error=""
    try:
        html,actual=browser_page(page,url)
        # Many SlotTemple maker listings are populated by client-side JS.
        text=BeautifulSoup(html,"html.parser").get_text(" ",strip=True)
        pat=re.search(r"(?:games\s+)?([0-9,]+)\s+Results",text,re.I)
        expected=int(pat.group(1).replace(",","")) if pat else None
        stable=0
        for step in range(max_scroll):
            items=links_from_html(page.content(),actual,"slotstemple",url)
            before=len(records)
            records.update(items)
            if len(records)==before: stable+=1
            else: stable=0
            if expected and len(records)>=expected:break
            # Try explicit "Load more" when present, otherwise scroll.
            btn=page.get_by_role("button",name=re.compile(r"load more|show more|view more",re.I))
            if btn.count() and btn.first.is_visible():
                try: btn.first.click(timeout=1200)
                except Exception: pass
            page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
            page.wait_for_timeout(900)
            if stable>=8: break
        if not records: error="no game cards found in rendered page"
        if expected and len(records)!=expected:
            error=(error+"; " if error else "")+f"extracted {len(records)} != advertised {expected}"
            if len(records)>expected:
                # More links than the advertised provider games means unrelated navigation links.
                records={}
        return records,{"count":len(records),"advertised":expected,"steps":step+1,"complete":not bool(error),"error":error,"url":url}
    except Exception as ex:
        return records,{"count":len(records),"advertised":None,"complete":False,"error":str(ex),"url":url}

def combine(data):
    merged={}
    collisions=[]
    for provider, sites in data.items():
        for site in ("slotcatalog","slotstemple"):
            for url,title in sites[site].items():
                key=(provider,normalize(title))
                if not key[1]:continue
                row=merged.get(key)
                if row is None:
                    row={"proveedor":provider,"juego":title,"nombre_normalizado":key[1],
                         "slotcatalog_url":"","slotstemple_url":"","fuentes":"","estado":"detectado"}
                    merged[key]=row
                field=site+"_url"
                if row[field] and row[field]!=url:collisions.append({"provider":provider,"title":title,"url":url,"existing_url":row[field]})
                elif not row[field]:row[field]=url
    for row in merged.values():
        a=bool(row["slotcatalog_url"]); b=bool(row["slotstemple_url"])
        row["fuentes"]="ambas" if a and b else ("slotcatalog" if a else "slotstemple")
    return sorted(merged.values(),key=lambda x:(x["proveedor"].casefold(),x["nombre_normalizado"])),collisions

def write_csv(path,records,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="results")
    ap.add_argument("--providers",nargs="*",default=list(PROVIDERS))
    args=ap.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    output=Path(args.out)
    session=requests.Session()
    index={}
    for site,url in (("slotcatalog",BASE_C+"/Providers"),("slotstemple",BASE_T+"/slots-by-maker/")):
        try: index[site]=index_links(session,url,site);LOG.info("index %s: %d links",site,len(index[site]))
        except Exception as ex:LOG.warning("Index %s inaccessible: %s",site,ex); index[site]=[]
    all_data={}
    report={"started_utc":datetime.now(timezone.utc).isoformat(),"providers":{}}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        page=browser.new_page(user_agent=HEADERS["User-Agent"],viewport={"width":1280,"height":900},locale="en-US")
        page.set_default_timeout(5000)
        for name in args.providers:
            if name not in PROVIDERS:raise SystemExit(f"unknown provider {name}")
            aliases=PROVIDERS[name]
            catalog_url=pick_index(index["slotcatalog"],aliases,"slotcatalog") or BASE_C+"/soft/"+CATALOG_FALLBACK[name]
            temple_url=pick_index(index["slotstemple"],aliases,"slotstemple") or BASE_T+"/free-slots/"+TEMPLE_FALLBACK[name]+"/"
            LOG.info("START %s | %s | %s",name,catalog_url,temple_url)
            c,cs=slotcatalog(session,page,catalog_url)
            t,ts=slotstemple(page,temple_url)
            all_data[name]={"slotcatalog":c,"slotstemple":t}
            report["providers"][name]={"slotcatalog":cs,"slotstemple":ts}
            LOG.info("FINISH %s: C=%d T=%d",name,len(c),len(t))
        browser.close()
    unique,duplicates=combine(all_data)
    write_csv(output/"juegos_unicos.csv",unique,FIELDS)
    rows=[]
    for provider,sources in all_data.items():
        for site in ("slotcatalog","slotstemple"):
            for url,name in sources[site].items():
                rows.append({"proveedor":provider,"fuente":site,"juego":name,"url":url,"nombre_normalizado":normalize(name)})
    write_csv(output/"juegos_por_fuente.csv",sorted(rows,key=lambda x:(x["proveedor"],x["fuente"],x["nombre_normalizado"])),
              ["proveedor","fuente","juego","url","nombre_normalizado"])
    write_csv(output/"colisiones.csv",duplicates,["provider","title","url","existing_url"])
    report["finished_utc"]=datetime.now(timezone.utc).isoformat()
    report["unique_count"]=len(unique)
    report["source_count"]=len(rows)
    report["all_complete"]=all(s["complete"] for p in report["providers"].values() for s in p.values())
    report["collisions"]=len(duplicates)
    output.mkdir(parents=True,exist_ok=True)
    (output/"reporte.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    LOG.info("FINAL unique=%d source=%d complete=%s",len(unique),len(rows),report["all_complete"])
    if not report["all_complete"]:
        LOG.error("INCOMPLETE: see reporte.json; do not publish this CSV as a complete catalog")
        raise SystemExit(2)
    if not unique:raise SystemExit("No games extracted. Check access and selectors.")
if __name__=="__main__":main()
