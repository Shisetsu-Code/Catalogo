#!/usr/bin/env python3
"""Probe public official Hacksaw demo entrypoints without reusing SlotsLaunch.
Only record URLs that load in an independent fresh context without credentials.
Never export login, token, session, signature or cookie parameters.
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse,parse_qsl,urlunparse,urlencode
from playwright.async_api import async_playwright

OUT = Path("data/hacksaw")
OUT.mkdir(parents=True,exist_ok=True)
GAMES = [
 ("Le Bandit","https://www.hacksawgaming.com/games/le-bandit"),
 ("Wanted Dead or a Wild","https://www.hacksawgaming.com/games/wanted-dead-or-a-wild"),
 ("Epic SixSixSix","https://www.hacksawgaming.com/games/epic-sixsixsix")
]
SENSITIVE = re.compile(r"token|session|authorization|auth|bearer|sig(nature)?|key|jwt|access|nonce|password|secret|hash|user|player|account|currency|login",re.I)
def safe_url(url):
 try:
  p=urlparse(url)
  if not p.scheme.startswith("http"):return None
  args=parse_qsl(p.query,keep_blank_values=True)
  if any(SENSITIVE.search(k) for k,v in args):return None
  return urlunparse((p.scheme,p.netloc,p.path,p.params,urlencode(args),''))[:1500]
 except Exception:return None

def game_url(url):
 try:
  u=urlparse(url)
  host=u.hostname or ""
  return (host=="hacksawgaming.com" or host.endswith(".hacksawgaming.com")) and (
   any(k in (u.path or "").lower() for k in ("index.html","game","play","launch","demo","/client","/lobby"))
   or "static" in host)
 except Exception:return False

async def probe_game(browser,name,official):
 context=await browser.new_context(viewport={"width":1440,"height":900},locale="en-GB")
 page=await context.new_page()
 urls=set()
 popups=[]
 errors=[]
 page.on("request",lambda r: urls.add(r.url) if game_url(r.url) else None)
 page.on("popup",lambda p: popups.append(p))
 try:
  response=await page.goto(official,wait_until="domcontentloaded",timeout=45000)
  await page.wait_for_timeout(2500)
  age_labels=["Yes, I am over 18","Yes, I'm over 18","Yes, I am 18","Accept","Ok"]
  for label in age_labels:
   try:
    b=page.get_by_text(label,exact=True)
    if await b.count() and await b.first.is_visible():
     await b.first.click(timeout=2500)
     await page.wait_for_timeout(800)
   except Exception as e:
    errors.append(f"age:{label} {str(e)[:100]}")
  before_frames=[safe_url(f.url) for f in page.frames]
  buttons=await page.locator("button").all_inner_texts()
  click_match=[]
  click_success=False
  for sel in ["text=/^Try it$/i","button:has-text('Try it')","a:has-text('Try it')",
              "[aria-label*='Try']","text=/^Play Demo$/i"]:
   try:
    loc=page.locator(sel)
    for i in range(min(await loc.count(),6)):
     if await loc.nth(i).is_visible():
      click_match.append({"selector":sel,"index":i})
      await loc.nth(i).click(timeout=5000)
      click_success=True
      break
    if click_success: break
   except Exception as e:errors.append(f"click:{sel} {str(e)[:140]}")
  await page.wait_for_timeout(7500)
  frames=[safe_url(f.url) for f in page.frames]
  iframes=await page.locator("iframe").evaluate_all("(els) => els.map(x => ({src:x.src,outer:x.outerHTML.slice(0,300)}))")
  popup_urls=[safe_url(p.url) for p in popups]
  observed=sorted(set(filter(None,[safe_url(x) for x in urls])))
  candidates=[u for u in set(frames+popup_urls+observed) if u and game_url(u) and not u.startswith(official)]
  # Prefer browser document/iframe over JS/assets.
  candidates=sorted(candidates,key=lambda u:(0 if u in frames or u in popup_urls else 1,len(u)))
  independent=[]
  for u in candidates[:5]:
   try:
    fresh=await browser.new_context(viewport={"width":1280,"height":720},locale="en-GB")
    tp=await fresh.new_page()
    resp=await tp.goto(u,wait_until="domcontentloaded",timeout=25000)
    await tp.wait_for_timeout(2500)
    independent.append({"url":u,
        "status":resp.status if resp else None,
        "title":(await tp.title())[:140],
        "frame_count":len(tp.frames),
        "main_content_len":len(await tp.locator("body").inner_text(timeout=4000)) if await tp.locator("body").count() else 0,
        "body_excerpt":(await tp.locator("body").inner_text(timeout=4000))[:200] if await tp.locator("body").count() else ""
    })
    await fresh.close()
   except Exception as e: independent.append({"url":u,"error":str(e)[:180]})
  return {
    "name":name,"official":official,"page_status":response.status if response else None,
    "after_url":safe_url(page.url),"before_frames":before_frames,"after_frames":frames,
    "iframes": [{"src":safe_url(i["src"]), "markup":i["outer"][:200] if not SENSITIVE.search(i["outer"]) else "[redacted]"} for i in iframes[:10]],
    "popups":popup_urls,"clicked":click_success,"click_match":click_match,
    "public_candidate_urls":candidates[:12],
    "independent_probes":independent,
    "request_urls_filtered":observed[:35],
    "buttons":[b.strip()[:70] for b in buttons[:15]],
    "errors":errors[:10],
    "page_tail":(await page.locator("body").inner_text())[:400],
  }

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
  games=[]
  for name,url in GAMES:
   print("Probing",name,flush=True)
   try: games.append(await probe_game(browser,name,url))
   except Exception as e: games.append({"name":name,"official":url,"error":str(e)[:500]})
  await browser.close()
 obj={"collected_at_utc":datetime.now(timezone.utc).isoformat(),"source":"Hacksaw Gaming official site", "games":games}
 (OUT/"direct_demo_probes.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(obj,ensure_ascii=False,indent=2)[:19000],flush=True)

if __name__=="__main__":asyncio.run(main())
