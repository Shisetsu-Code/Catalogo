#!/usr/bin/env python3
"""Find game client URLs for slots that are absent from Hacksaw's main catalog.
Source: verified page slugs in data/hacksaw/catalogo.json.
A candidate is NOT a verified direct game unless it opens separately without a token.
No cookies, tokens, authenticated endpoints, or query secrets are exported.
"""
import asyncio,csv,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,parse_qsl
from playwright.async_api import async_playwright

OUT=Path("data/hacksaw");OUT.mkdir(parents=True,exist_ok=True)
EARLY={"3-adventures-of-alice-hold-win","le-clubber","supernova-shooting-stars",
"buried-by-night","willy-wildwing","marlin-masters-frozen-frenzy","ghost-vision",
"croco-clover","le-gift-grabber","hellmageddon","le-santa-hold-win"}
TARGETS={
"3-adventures-of-alice-hold-win","3-magic-piggy-banks","aliens-among-us",
"buried-by-night","cash-crooks","croco-clover","donny-dough-og","ghost-vision",
"hellmageddon","le-bruno","le-clubber","le-gift-grabber","le-granny",
"le-santa-hold-win","marlin-masters-frozen-frenzy","mines-supreme","secret-order",
"shadows-inc","spicy-sixsixsix","supernova-galaxy-orbs","supernova-shooting-stars",
"the-lord","the-luxe-prestige","tres-pinatas","wanted-salvation","willy-wildwing",
"3-arcane-cauldron-hg","3-red-hoods","donny-danny-og","eclipse-princess",
"epic-hand-of-anubis","feeling-froggy","gold-baron-777-hold-win",
"hacked-hand-of-anubis","hacked-wanted-dead-or-a-wild","lead-for-lunch",
"lucky-ling-golden-treasures","magic-piggy-33","marlin-masters-3x3",
"red-hot-chili-clovers","skybound-bail2win","suspect-noir","tasty-teddy",
"the-luxe-dice","throne-of-gold-hold-win","toxic-city-hold-win"}
UPCOMING={"3-arcane-cauldron-hg","3-red-hoods","donny-danny-og","eclipse-princess",
"epic-hand-of-anubis","feeling-froggy","gold-baron-777-hold-win",
"hacked-hand-of-anubis","hacked-wanted-dead-or-a-wild","lead-for-lunch",
"lucky-ling-golden-treasures","magic-piggy-33","marlin-masters-3x3",
"red-hot-chili-clovers","skybound-bail2win","suspect-noir","tasty-teddy",
"the-luxe-dice","throne-of-gold-hold-win","toxic-city-hold-win",
"donny-dough-og","le-santa-hold-win"}
SENSITIVE=re.compile(r"(?:^|[?&])(token|signature|session|auth|jwt|key|hash|nonce|password|secret|playerid|userid|launchcode)=",re.I)
GAMEDOMAIN=re.compile(r"(^|\.)hacksawgaming\.com$|(^|\.)hacksawgaming\.net$",re.I)

def safe(url):
 if not url or not url.startswith(("http://","https://")):return ""
 if SENSITIVE.search(url):return ""
 return url[:2048]
def title_guess(slug):return slug.replace("-"," ").title()
def isgame(url):
 try:
  u=urlparse(url)
  return bool(GAMEDOMAIN.search(u.hostname or "")) and "hacksawgaming.com/games/" not in url
 except: return False

async def inspect(browser,slug):
 urls=set(); redirects=set();popups=[]
 ctx=await browser.new_context(locale="en-US",viewport={"width":1360,"height":880})
 page=await ctx.new_page()
 page.on("request",lambda r:urls.add(r.url) if isgame(r.url) else None)
 page.on("popup",lambda p:popups.append(p))
 path=f"https://slotslaunch.com/hacksaw-gaming/{slug}"
 logs={"slug":slug,"source":path,"observed":False,"direct_url":"","direct_verification":"no_confirmado",
       "candidate_urls":[],"slotlaunch_iframes":[],"buttons":[],"page_status":None}
 try:
  resp=await page.goto(path,wait_until="domcontentloaded",timeout=42000)
  logs["page_status"]=resp.status if resp else None
  await page.wait_for_timeout(2500)
  # Some game launchers require explicit Play Free or image click
  for selector in ["button:has-text('Free Play')","button:has-text('Play Free')",
   "button:has-text('Play Demo')","button:has-text('Play Now')",
   "[data-testid*=play]","button:has-text('Play')",
   "img[alt*='Play Free Demo']"]:
   try:
    loc=page.locator(selector)
    if await loc.count() and await loc.first.is_visible():
     await loc.first.click(timeout=1600);break
   except Exception:pass
  await page.wait_for_timeout(5000)
  frames=[f.url for f in page.frames]
  iframes=await page.locator("iframe").evaluate_all("(items)=>items.map(e=>e.src)")
  logs["slotlaunch_iframes"]=[safe(u) for u in iframes if safe(u)][:8]
  for u in frames+[p.url for p in popups]+list(urls):
   if safe(u) and isgame(u):
    redirects.add(u)
  logs["candidate_urls"]=sorted(redirects,key=len)[:12]
  # Standalone client test, completely new browser context and no inherited cookies
  for link in list(logs["candidate_urls"])[:3]:
   fresh=await browser.new_context(locale="en-US")
   test=await fresh.new_page()
   try:
    result=await test.goto(link,wait_until="domcontentloaded",timeout=19000)
    await test.wait_for_timeout(1600)
    ok=result is not None and result.status in (200,206)
    script_count=await test.locator("script").count()
    frame_count=len(test.frames)
    if ok and (script_count>1 or frame_count>1):
     logs["direct_url"]=link
     logs["direct_verification"]="documento_independiente_cargado_sin_cookies_no_jugabilidad_verificada"
     break
   except Exception:pass
   finally:await fresh.close()
  logs["observed"]=True
 except Exception as e:
  logs["error"]=str(e)[:180]
 finally: await ctx.close()
 return logs

async def main():
 data=json.loads((OUT/"catalogo.json").read_text(encoding="utf8"))
 from_source={g["slug"]:g for g in data["games"]}
 targets=[x for x in sorted(TARGETS) if x in from_source]
 results={x:{"slug":x,"source":from_source[x]["page_url"],
             "name":from_source[x].get("name") or title_guess(x),
             "group":("anunciado" if x in UPCOMING else "demo_listada"),
             "direct_url":"","direct_verification":"no_procesado",
             "observed":False} for x in targets}
 # Prioritize early demos, try a representative subset and avoid unbounded runs.
 probe=[x for x in sorted(targets,key=lambda x:(x not in EARLY,x)) if x in EARLY or x in
       {"secret-order","shadows-inc","aliens-among-us","mines-supreme","spicy-sixsixsix"}]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
  sem=asyncio.Semaphore(3)
  async def worker(slug):
   async with sem:
    info=await inspect(browser,slug)
    results[slug].update(info)
    print(slug,info["page_status"],len(info["candidate_urls"]),info["direct_verification"],flush=True)
  await asyncio.gather(*[worker(x) for x in probe])
  await browser.close()
 rows=list(results.values())
 (OUT/"solo_faltantes_directos.json").write_text(json.dumps({
  "created_utc":datetime.now(timezone.utc).isoformat(),
  "scope":"46 titles absent from partial official baseline, not an exhaustive 305 vs official audit",
  "notes":"No URL internal is reported as verified without a fresh context check; loading does not guarantee playability.",
  "games":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 with (OUT/"solo_faltantes_directos.csv").open("w",newline="",encoding="utf-8-sig") as f:
  fields=["name","group","slug","direct_url","direct_verification","source","observed"]
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
 print("TOTAL",len(rows),"PROBED",sum(bool(x["observed"]) for x in rows),
       "DIRECT",sum(bool(x["direct_url"]) for x in rows),flush=True)

if __name__=="__main__":asyncio.run(main())
