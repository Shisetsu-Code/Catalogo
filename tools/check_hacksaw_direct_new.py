#!/usr/bin/env python3
"""Check public direct client for newly identified Hacksaw demo IDs.
Does not use accounts, wallet transactions or non-public session tokens.
Final browser URLs from staging are saved only as paths (never query tokens).
"""
import asyncio,json,re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse,urlencode
from playwright.async_api import async_playwright
OUT=Path("data/hacksaw");OUT.mkdir(exist_ok=True,parents=True)
IDS={1126:"Mines (positive control)",1392:"Dark Summoning",2524:"Hellmageddon",2528:"Ghost Vision",999999:"Invalid (negative control)"}
STG="https://static-stg.hacksawgaming.com/launcher/static-launcher.html"
LIVE="https://static-live.hacksawgaming.com"
def stg_url(i):
 return STG+"?"+urlencode(dict(gameid=i,channel="desktop",language="en",partner="stg",mode="demo",token="123"))
def live_query(i):
 return urlencode(dict(channel="desktop",currency="EUR",env="https://rgs-demo.hacksawgaming.com/api",
 gameid=i,language="en",lobbyurl="https://www.hacksawgaming.com",mode=2,partner="demo",
 realmoneyenv="https://rgs-demo.hacksawgaming.com/api",token="123131"))
def redact(t):
 return re.sub(r"(?i)(token|session|auth|signature|key)=([^&\s]+)",r"\1=[REDACTED]",str(t))[:300]
async def nav(ctx,url):
 p=await ctx.new_page()
 network=[]
 errors=[]
 p.on("response",lambda r: network.append({"status":r.status,"host":(urlparse(r.url).hostname or ""), "path":urlparse(r.url).path[:150]}) if len(network)<150 else None)
 p.on("console",lambda m: errors.append(redact(m.text)) if m.type=="error" and len(errors)<10 else None)
 result={}
 try:
  res=await p.goto(url,wait_until="domcontentloaded",timeout=28000)
  await p.wait_for_timeout(6500)
  result={"http_status":res.status if res else None,
     "final_path":urlparse(p.url).path,
     "final_host":urlparse(p.url).hostname,
     "title":(await p.title())[:100],
     "text":(await p.locator("body").inner_text(timeout=4000))[:250] if await p.locator("body").count() else "",
     "canvas_count":await p.locator("canvas").count(),
     "iframe_count":await p.locator("iframe").count()}
 except Exception as e:result={"error":redact(e)}
 result["network"]=network
 result["errors"]=errors
 return result
async def test(browser,i,name,sem):
 async with sem:
  c1=await browser.new_context(viewport={"width":1280,"height":720})
  staging=await nav(c1,stg_url(i))
  await c1.close()
  pth=staging.get("final_path") or ""
  found=bool(re.match(r"^/\d+/.+/index\.html$",pth)) and staging.get("final_host")=="static-stg.hacksawgaming.com"
  live={}
  if found:
   candidate=LIVE+pth+"?"+live_query(i)
   c2=await browser.new_context(viewport={"width":1280,"height":720})
   live=await nav(c2,candidate)
   await c2.close()
   live["url"]=candidate
  print(json.dumps({"id":i,"stage_title":staging.get("title"),"stage_path":pth,
      "live_title":live.get("title"),"live_status":live.get("http_status"),
      "live_text":live.get("text")},ensure_ascii=False),flush=True)
  return {"id":i,"expected":name,"staging":staging,"candidate_formed":found,"live":live}
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
  sem=asyncio.Semaphore(2)
  tests=await asyncio.gather(*[test(b,i,n,sem) for i,n in IDS.items()])
  await b.close()
 out={"collected_at_utc":datetime.now(timezone.utc).isoformat(),"tests":tests,
      "rule":"A candidate is not a confirmed working demo without successful live assets AND demo backend initialization."}
 (OUT/"direct_missing_id_checks.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
if __name__=="__main__":asyncio.run(main())
