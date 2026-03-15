"""
Test rápido para Nano Banana Pro en kie.ai.
Ejecuta: python debug_nbpro.py
"""
import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("NB2_API_KEY", "")
CREATE     = "https://api.kie.ai/api/v1/jobs/createTask"
STATUS     = "https://api.kie.ai/api/v1/jobs/recordInfo"
HEADERS    = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
REF_IMAGE  = os.getenv("NB2_REFERENCE_IMAGE_PATH", "")

print(f"API_KEY: {'OK (' + API_KEY[:8] + '...)' if API_KEY else 'MISSING'}")
print(f"Ref image: {REF_IMAGE!r}  exists={Path(REF_IMAGE).exists() if REF_IMAGE else False}\n")

# ── TEST 1: text-to-image 1:1 ─────────────────────────────
print("=" * 60)
print("TEST 1: text-to-image 1:1")
print("=" * 60)
payload1 = {
    "model": "nano-banana-pro",
    "input": {
        "prompt": "Professional Meta Ad for PROVI Kit Lila. Purple nitrile gloves, purple surgical mask, purple hair cap arranged on white marble background. Text overlay: 'Kit Lila Completo $41.950 COP'. WhatsApp button. Clean product photography.",
        "aspect_ratio": "1:1",
        "resolution": "1K",
        "output_format": "jpg",
    }
}
print(f"Payload: {json.dumps(payload1, indent=2)}\n")
r1 = requests.post(CREATE, headers=HEADERS, json=payload1, timeout=30)
res1 = r1.json()
print(f"HTTP {r1.status_code} → {json.dumps(res1, indent=2)}\n")
task1 = res1.get("data", {}).get("taskId")

# ── TEST 2: text-to-image 4:5 ─────────────────────────────
print("=" * 60)
print("TEST 2: text-to-image 4:5 (Meta Ads vertical)")
print("=" * 60)
payload2 = {
    "model": "nano-banana-pro",
    "input": {
        "prompt": "Professional Meta Ad for PROVI Kit Lila. Purple nitrile gloves, purple surgical mask, purple hair cap arranged on white marble background. Text overlay: 'Kit Lila Completo $41.950 COP'. WhatsApp button. Clean product photography.",
        "aspect_ratio": "4:5",
        "resolution": "1K",
        "output_format": "jpg",
    }
}
r2 = requests.post(CREATE, headers=HEADERS, json=payload2, timeout=30)
res2 = r2.json()
print(f"HTTP {r2.status_code} → {json.dumps(res2, indent=2)}\n")
task2 = res2.get("data", {}).get("taskId")

# ── TEST 3: img2img con referencia ─────────────────────────
task3 = None
if REF_IMAGE and Path(REF_IMAGE).exists():
    print("=" * 60)
    print("TEST 3: img2img con imagen de referencia")
    print("=" * 60)
    import base64, io
    from PIL import Image as PILImage
    img = PILImage.open(REF_IMAGE).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload3 = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": "Professional Meta Ad. Use the reference product image. Purple medical kit on clean white background with text 'Kit Lila PROVI $41.950 COP'. WhatsApp CTA button.",
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "output_format": "jpg",
            "image_input": [f"data:image/jpeg;base64,{b64}"],
        }
    }
    r3 = requests.post(CREATE, headers=HEADERS, json=payload3, timeout=30)
    res3 = r3.json()
    print(f"HTTP {r3.status_code} → {json.dumps(res3, indent=2)}\n")
    task3 = res3.get("data", {}).get("taskId")

# ── POLLING ───────────────────────────────────────────────
tasks = {k: v for k, v in {"1:1": task1, "4:5": task2, "img2img": task3}.items() if v}
done  = {}

print("=" * 60)
print(f"Polling {len(tasks)} tasks (máx 90s)...")
print("=" * 60)

for i in range(18):
    time.sleep(5)
    for label, tid in list(tasks.items()):
        r = requests.get(f"{STATUS}?taskId={tid}", headers=HEADERS, timeout=30)
        data = r.json().get("data", {})
        state = data.get("state", "?")
        print(f"  [{label}] state={state!r}")
        if state == "success":
            result_json = json.loads(data.get("resultJson", "{}"))
            url = (result_json.get("resultUrls") or ["N/A"])[0]
            print(f"  [{label}] EXITO — URL: {url}")
            done[label] = url
            del tasks[label]
        elif state in ("failed", "error"):
            print(f"  [{label}] FALLO — {data}")
            del tasks[label]
    if not tasks:
        break

print("\n=== RESUMEN ===")
for label, url in done.items():
    print(f"  {label}: {url}")
