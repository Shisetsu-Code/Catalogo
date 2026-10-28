#!/usr/bin/env python3
"""Finite public DEMO launcher ID test.
No login, payment, provider sessions, guessing passwords, or gameplay.
Tests HTTP + browser runtime; an HTML 200 is not 'game loaded'.
"""
import asyncio, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
BASE="https://static-stg.hacksawgaming.com/launcher/static-launcher.html"
IDS={
  2480:"Candidate 2480",
  2484:"Candidate 2484",
  2488:"Candidate 2488",
  2492:"Candidate 2492",
  2496:"Candidate 2496",
  2500:"Candidate 2500",
  2504:"Candidate 2504",
  2508:"Candidate 2508",
  2512:"Candidate 2512",
  2516:"Candidate 2516",
  2520:"Candidate 2520",
  2524:"Candidate 2524",
  2528:"Candidate 2528",
  2532:"Candidate 2532",
  2536:"Candidate 2536",
  2540:"Candidate 2540",
  2544:"Candidate 2544",
  2548:"Candidate 2548",
  2552:"Candidate 2552",
  2556:"Candidate 2556",
  2560:"Candidate 2560",
  2564:"Candidate 2564",
  2568:"Candidate 2568",
  2572:"Candidate 2572",
  2576:"Candidate 2576",
  2580:"Candidate 2580",
  2584:"Candidate 2584",
  2588:"Candidate 2588",
  2592:"Candidate 2592",
  2604:"Candidate 2604",
  2608:"Candidate 2608",
  2624:"Candidate 2624",
  2640:"Candidate 2640",
  2660:"Candidate 2660",
  2680:"Candidate 2680",
  2704:"Candidate 2704",
  2720:"Candidate 2720",
}
OUT=Path("data/hacksaw")
OUT.mkdir(parents=True,exist_ok=True)
def url(id):
 return BASE+"?"+urlencode(dict(gameid=id,channel="desktop",language="en",partner="stg",mode="demo",token="123"))
SENSITIVE_RE = re.compile(r'token|authorization|cookie|session|signature|password|secret',re.I)
def scrub(s):
 return re.sub(r'(token|session|signature|password|secret)=([^&# ]+)',r'\1=[REDACTED]',str(s),flags=re.I)[:350]
async def test(browser,gameid,name,sem):
 async with sem:
  ctx=await browser.new_context(viewport={"width":1280,"height":720},locale="en-GB")
  page=await ctx.new_page()
  calls=[]
  errors=[]
  console=[]
  page.on("response",lambda r:calls.append({"status":r.status, "host":r.url.split("/")[2] if "://" in r.url else "",
                   "path":r.url.split("?")[0].split("/")[-1][:80]}) if len(calls)<100 else None)
  page.on("pageerror",lambda e:errors.append(scrub(e)) if len(errors)<8 else None)
  page.on("console",lambda m:console.append(scrub(m.text)) if m.type=="error" and len(console)<8 else None)
  result={"id":gameid,"expected_game":name,"host":BASE,"navigation_status":None,
          "page_title":"","elapsed_s":None,"main_frame":False,"canvas_count":0,
          "iframe_count":0,"observed_runtime":False,"load_result":"unknown",
          "responses":[],"errors":[]}
  start=time.monotonic()
  try:
   r=await page.goto(url(gameid),wait_until="domcontentloaded",timeout=20000)
   result["navigation_status"]=r.status if r else None
   await page.wait_for_timeout(8500)
   result["page_title"]=(await page.title())[:130]
   result["canvas_count"]=await page.locator("canvas").count()
   result["iframe_count"]=await page.locator("iframe").count()
   result["main_frame"]=page.url.startswith(BASE)
   try:
    body=(await page.locator("body").inner_text(timeout=3500))[:450]
   except: body=""
   result["visible_text"]=body
   try:
    frameurl=page.frames[-1].url
    result["last_frame_host"]=frameurl.split("/")[2] if "://" in frameurl else ""
   except: pass
   result["version_requests"]=[x for x in calls if x["path"]=="version.json"]
   result["observed_runtime"]=(result["canvas_count"]>0 or result["iframe_count"]>0 or len(calls)>8)
   errish=bool(re.search(r"invalid|unavailable|expired|unauthorized|not found|forbidden|game not|unknown game",body,re.I))
   if not r or r.status>=400: result["load_result"]="http_error"
   elif errish:result["load_result"]="visible_error"
   elif result["version_requests"] and all(x["status"]>=400 for x in result["version_requests"]):result["load_result"]="version_rejected"
   elif result["observed_runtime"]:result["load_result"]="runtime_resources_loaded_not_gameplay_verified"
   else:result["load_result"]="html_shell_only"
  except Exception as e:result["load_result"]="navigation_exception";result["exception"]=scrub(e)
  finally:
   result["elapsed_s"]=round(time.monotonic()-start,1)
   result["responses"]=calls[:50]
   result["errors"]=errors[:8]
   result["console_errors"]=console[:8]
   print(json.dumps({k:result.get(k) for k in ["id","expected_game","navigation_status","load_result","elapsed_s","page_title","exception"]},ensure_ascii=False),flush=True)
   await ctx.close()
  return result

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
  sem=asyncio.Semaphore(3)
  tests=await asyncio.gather(*(test(browser,k,v,sem) for k,v in IDS.items()))
  await browser.close()
 out={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"launcher":BASE,
     "test_params":{"channel":"desktop","language":"en","partner":"stg","mode":"demo",
       "token":"public example placeholder, not proof of authorization"},
     "interpretation":"An HTTP 200 or runtime assets do NOT prove a game initialized or is playable. Tests are public demo-only.",
     "tests":sorted(tests,key=lambda x:x["id"])}
 (OUT/"id_tests_batch2.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("OUTPUT",str(OUT/"id_tests_batch2.json"),flush=True)

if __name__=="__main__":asyncio.run(main())
