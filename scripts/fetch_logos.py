#!/usr/bin/env python3
"""Descarga miniaturas de sitios de proveedores y genera respaldo visual explícito.

Uso:
    python -m pip install pillow
    python scripts/fetch_logos.py

El archivo proveedores.json controla nombre, id, dominio y opcionalmente logo_url.
Los logos obtenidos corresponden a favicons públicos; no se generan logos falsos.
En caso de fallo se genera una miniatura textual, identificada como placeholder.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "logos"
SOURCE = ROOT / "proveedores.json"
SIZE = 96
MAX_BYTES = 512_000


def icon_url(provider: dict) -> str:
    explicit = provider.get("logo_url", "").strip()
    if explicit:
        parsed = urllib.parse.urlparse(explicit)
        if parsed.scheme == "https" and parsed.hostname:
            return explicit
        raise ValueError("logo_url debe utilizar HTTPS")
    domain = provider.get("domain", "").strip()
    if not domain or "/" in domain or " " in domain:
        return ""
    return "https://www.google.com/s2/favicons?domain=" + urllib.parse.quote(domain) + "&sz=128"


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CatalogoProveedores/1.0)", "Accept": "image/png,image/jpeg,image/webp,image/x-icon,*/*"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("Imagen supera el límite de tamaño")
        return content


def placeholder(name: str, identifier: str) -> Image.Image:
    seed = hashlib.sha256(identifier.encode("utf-8")).digest()
    bg = (48 + seed[0] // 3, 54 + seed[1] // 3, 65 + seed[2] // 3, 255)
    canvas = Image.new("RGBA", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(canvas)
    tokens = name.strip().split()
    initial = "".join(token[:1].upper() for token in tokens[:2]) or "?"
    if len(initial) > 2:
        initial = initial[:2]
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), initial, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    draw.text(((SIZE-width)/2-box[0], (SIZE-height)/2-box[1]), initial,
              fill=(255,255,255), font=font)
    return canvas


def convert_image(source: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(source))
    img.load()
    if img.width < 16 or img.height < 16:
        raise ValueError("Icono demasiado pequeño")
    img = img.convert("RGBA")
    img.thumbnail((SIZE-10, SIZE-10), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    result.alpha_composite(img, ((SIZE-img.width)//2, (SIZE-img.height)//2))
    return result


def fetch_one(provider: dict, fallback_signature: str | None) -> dict:
    identifier = provider["id"]
    name = provider["name"]
    url = ""
    status = "placeholder"
    reason = ""
    try:
        url = icon_url(provider)
        if not url:
            raise ValueError("Falta dominio/logo_url")
        data = download(url)
        if fallback_signature and hashlib.sha256(data).hexdigest() == fallback_signature:
            raise ValueError("Servicio devolvió icono genérico, no el del proveedor")
        image = convert_image(data)
        status = "favicon"
    except (ValueError, urllib.error.URLError, OSError, UnidentifiedImageError) as error:
        image = placeholder(name, identifier)
        reason = str(error)
    image.save(OUTPUT / (identifier + ".png"), "PNG", optimize=True)
    return {"id": identifier, "name": name, "status": status, "source": url if status == "favicon" else "", "reason": reason}


def main() -> int:
    catalog = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not all(isinstance(row, dict) and "id" in row and "name" in row for row in catalog):
        print("El catálogo debe contener objetos con id y name", file=sys.stderr)
        return 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    signature = None
    try:
        fake = download("https://www.google.com/s2/favicons?domain=not-a-real-domain-for-icon-check.invalid&sz=128")
        signature = hashlib.sha256(fake).hexdigest()
    except Exception as e:
        print("Advertencia: no se pudo detectar el favicon genérico:", str(e)[:120])
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_one, row, signature) for row in catalog]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['status']:12} {result['name']}")
    results.sort(key=lambda result: result["name"].lower())
    (OUTPUT / "fuentes.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    acquired = sum(row["status"] == "favicon" for row in results)
    print(f"Miniaturas creadas: {len(results)}. Favicons descargados: {acquired}. Respaldos de texto: {len(results) - acquired}.")
    return 0 if len(results) == len(catalog) else 1


if __name__ == "__main__":
    raise SystemExit(main())
