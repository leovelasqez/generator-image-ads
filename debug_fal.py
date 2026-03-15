"""
Test rápido para Nano Banana 2 en fal.ai.
Ejecuta: python debug_fal.py

Requisitos:
    pip install fal-client python-dotenv Pillow
"""
import os, json, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FAL_KEY = os.getenv("FAL_KEY", "")
REF_IMAGE = os.getenv("NB2_REFERENCE_IMAGE_PATH", "")
FAL_MODEL = "fal-ai/nano-banana-pro"

print(f"FAL_KEY: {'OK (' + FAL_KEY[:8] + '...)' if FAL_KEY else 'MISSING'}")
print(f"Ref image: {REF_IMAGE!r}  exists={Path(REF_IMAGE).exists() if REF_IMAGE else False}\n")

if not FAL_KEY:
    print("ERROR: FAL_KEY no configurada en .env")
    raise SystemExit(1)

os.environ["FAL_KEY"] = FAL_KEY
import fal_client

PROMPT = (
    "IMPORTANT: All text visible in the image must be written exclusively in Spanish. "
    "No brand logos, no icons, no social media symbols anywhere in the image. "
    "All CTAs are plain text on a solid colored bar only — no icons. "
    "Anuncio estatico de producto. "
    "Guantes de nitrilo lilas, tapabocas lila y gorro oruga lila sobre fondo blanco. "
    "Texto en negro: 'Kit Lila Completo $55.000 COP'. "
    "Fotografia limpia de producto."
)
NEGATIVE_PROMPT = (
    "blurry, watermark, english text, logo, brand logo, no PROVI logo, "
    "no META logo, no META ADS badge, no social media watermarks, "
    "no WhatsApp logo, no WhatsApp icon, no green WhatsApp bubble"
)

# ── TEST 1: text-to-image 1:1 ─────────────────────────────
print("=" * 60)
print("TEST 1: text-to-image 1:1")
print("=" * 60)
try:
    result1 = fal_client.subscribe(FAL_MODEL, arguments={
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "aspect_ratio": "1:1",
        "limit_generations": False,
    })
    url1 = result1["images"][0]["url"]
    print(f"EXITO — URL: {url1}\n")
except Exception as e:
    print(f"FALLO: {e}\n")
    url1 = None

# ── TEST 2: text-to-image 4:5 ─────────────────────────────
print("=" * 60)
print("TEST 2: text-to-image 4:5 (Meta Ads vertical)")
print("=" * 60)
try:
    result2 = fal_client.subscribe(FAL_MODEL, arguments={
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "aspect_ratio": "4:5",
        "limit_generations": False,
    })
    url2 = result2["images"][0]["url"]
    print(f"EXITO — URL: {url2}\n")
except Exception as e:
    print(f"FALLO: {e}\n")
    url2 = None

# ── TEST 3: img2img con imagen de referencia ─────────────────
url3 = None
if REF_IMAGE and Path(REF_IMAGE).exists():
    print("=" * 60)
    print("TEST 3: img2img con imagen de referencia")
    print("=" * 60)
    try:
        ref_url = fal_client.upload_file(REF_IMAGE)
        print(f"Referencia subida: {ref_url}")
        result3 = fal_client.subscribe(FAL_MODEL, arguments={
            "prompt": PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "aspect_ratio": "1:1",
            "limit_generations": False,
            "image_urls": [ref_url],
        })
        url3 = result3["images"][0]["url"]
        print(f"EXITO — URL: {url3}\n")
    except Exception as e:
        print(f"FALLO: {e}\n")
else:
    print("TEST 3: Omitido (NB2_REFERENCE_IMAGE_PATH no configurado o no existe)\n")

# ── RESUMEN ─────────────────────────────────────────────────
print("=" * 60)
print("RESUMEN")
print("=" * 60)
for label, url in [("1:1", url1), ("4:5", url2), ("img2img", url3)]:
    if url:
        print(f"  {label}: {url}")
    else:
        print(f"  {label}: FALLO o no ejecutado")
