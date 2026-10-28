#!/usr/bin/env python3
"""Catalogo de demos de Hacksaw Gaming desde el listado público de SlotsLaunch.
No reconstruye ni inventa URL internas de juego: conserva los href reales del DOM.
"""
import asyncio
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

from playwright.async_api import async_playwright

BASE = "https://slotslaunch.com"
URL = BASE + "/hacksaw-gaming"
OUT = Path("data/hacksaw")
OUT.mkdir(parents=True, exist_ok=True)

JS_READ = r"""() => {
  const links = Array.from(document.querySelectorAll('a[href]'));
  return links.filter(a => {
      try {
        const u = new URL(a.getAttribute('href'), location.href);
        return u.hostname === 'slotslaunch.com'
            && /^\/hacksaw-gaming\/[^\/?#]+\/?$/.test(u.pathname);
      } catch { return false; }
    }).map(a => {
      const u = new URL(a.getAttribute('href'), location.href);
      let name = '';
      let text = a.textContent.trim().replace(/\s+/g, ' ');
      if (a.querySelector('h3,h2,h4')) name = a.querySelector('h3,h2,h4').textContent.trim();
      for (let p = a.parentElement, n=0; p && n<5 && !name; p=p.parentElement,n++) {
        let title=p.querySelector('h3');
        if(title) name=title.textContent.trim();
      }
      const img=a.querySelector('img') || a.parentElement?.querySelector('img');
      if (!name && img) name=(img.alt || '').replace(/\s+Demo Slot$/i,'').trim();
      if(!name && text && !/^(Launch Demo|Coming Soon|Play|Free Play)$/i.test(text)) name=text;
      return {
        url: u.origin + u.pathname,
        name,
        text,
        upcoming: /Coming Soon/i.test((a.parentElement?.parentElement?.textContent||'').slice(0,250))
      };
    });
}"""

def as_title(slug):
    return unquote(slug).replace('-', ' ').title()

def normalized(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())

async def collect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, locale="en-US")
        errors=[]
        page.on("pageerror", lambda err: errors.append(str(err)[:240]))
        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(3500)
        for accept in ("button:has-text('Accept All')", "button:has-text('Accept')", "button:has-text('I Agree')"):
            try:
                if await page.locator(accept).count():
                    await page.locator(accept).first.click(timeout=1600)
                    break
            except Exception:
                pass
        expected=None
        text=await page.locator('body').inner_text()
        m=re.search(r"Add all\s+([\d,]+)\s+demo slots from Hacksaw",text,re.I)
        if m: expected=int(m.group(1).replace(",",""))

        # El proveedor tiene una sección "All ..." con carga perezosa (50 por lote).
        # Desplazar hasta abajo, esperar solicitudes y repetir; no limitar a la primera pantalla.
        max_seen=0
        stale=0
        for i in range(130):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1250 if i%6 == 0 else 650)
            raw=await page.evaluate(JS_READ)
            count=len({x['url'] for x in raw})
            if count>max_seen:
                max_seen=count
                stale=0
                print(f"Scroll {i}: {count} URL unicas / anunciado={expected}", flush=True)
            else:
                stale+=1
            if expected and count>=expected: break
            if stale>=17:
                # Intento adicional para disparar observer ubicado en el footer.
                await page.mouse.wheel(0,-850)
                await page.wait_for_timeout(300)
                await page.mouse.wheel(0,1500)
                await page.wait_for_timeout(1000)
                if stale>=24: break
        raw=await page.evaluate(JS_READ)
        await page.screenshot(path=str(OUT / "pagina_final.png"),full_page=False)
        await browser.close()

    games={}
    for x in raw:
        slug=urlparse(x['url']).path.rstrip('/').split('/')[-1]
        name=x['name'].strip() if x['name'] else as_title(slug)
        if name in ('Launch Demo','Coming Soon','Play','Free Play'):
            name=as_title(slug)
        score = (4 if x['name'] and x['name'] not in ('Launch Demo','Coming Soon') else 0)
        v=games.get(x['url'])
        if v is None:
            games[x['url']]={"name":name,"page_url":x['url'],"slug":slug,
                "source":"SlotsLaunch","status":"listado_para_demo",
                "direct_client_url":"","official_url":"","title_score":score}
        elif score>v["title_score"]:
            v["name"]=name
            v["title_score"]=score

    all_games=list(games.values())
    # Los anunciados como Coming Soon que no figuran en la lista de demos
    # no se pueden etiquetar como lanzables sin verificar.
    for g in all_games:
        if re.search(r"^(?:donny-and-danny-og|toxic-city-hold-and-win|gold-baron-777-hold-and-win|epic-hand-of-anubis|tasty-teddy|suspect-noir|3-red-hoods|hacked-wanted-dead-or-a-wild|feeling-froggy|magic-piggy-3x3|lucky-ling-golden-treasures|throne-of-gold-hold-and-win|lead-for-lunch|eclipse-princess|hacked-hand-of-anubis|red-hot-chili-clovers|skybound-bail2win|the-luxe-dice|marlin-masters-3x3|3-arcane-cauldron-hg)$",g["slug"]):
            g["status"]="anunciado_sin_demo_confirmada"

    all_games.sort(key=lambda x: x["name"].casefold())
    for g in all_games: g.pop("title_score",None)
    meta={"source_url":URL,
          "collected_at_utc":datetime.now(timezone.utc).isoformat(),
          "source_claimed_demo_count":expected,
          "unique_page_links_collected":len(all_games),
          "complete_against_site_claim":expected is not None and
              len([x for x in all_games if x["status"]=="listado_para_demo"])>=expected,
          "notes":"Enlaces a páginas con demo; no son URL de API del fabricante ni sesiones/iframes permanentes.",
          "page_javascript_errors":errors[:15]}
    (OUT / "catalogo.json").write_text(json.dumps(
        {"metadata":meta, "games":all_games},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUT / "catalogo.csv").open("w",newline="",encoding="utf-8-sig") as f:
        fieldnames=["name","page_url","slug","status","source","direct_client_url","official_url"]
        writer=csv.DictWriter(f,fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_games)
    print(json.dumps(meta,ensure_ascii=False,indent=2),flush=True)
    print("Primeros 10:",all_games[:10],flush=True)

if __name__ == "__main__":
    asyncio.run(collect())
