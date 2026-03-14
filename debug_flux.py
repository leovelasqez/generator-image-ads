"""
Test rápido para verificar el formato exacto de la API FLUX.1 Kontext Pro en kie.ai.
Ejecuta: python debug_flux.py
"""
import os, json, time, requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NB2_API_KEY", "")
BASE    = "https://api.kie.ai/api/v1/flux/kontext"
CREATE  = f"{BASE}/generate"
STATUS  = f"{BASE}/record-info"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

print(f"API_KEY: {'OK (' + API_KEY[:8] + '...)' if API_KEY else 'MISSING'}")
print(f"Endpoint: {CREATE}\n")

# ─── TEST 1: 1:1 ─────────────────────────────────────────────
print("=" * 60)
print("TEST 1: aspect ratio 1:1")
print("=" * 60)
payload_1 = {
    "model": "flux-kontext-pro",
    "prompt": "Purple medical gloves on clean white background, product photography, professional studio lighting",
    "aspectRatio": "1:1",
    "outputFormat": "jpeg",
}
print(f"Payload: {json.dumps(payload_1, indent=2)}\n")

r1 = requests.post(CREATE, headers=HEADERS, json=payload_1, timeout=30)
print(f"HTTP {r1.status_code}")
result1 = r1.json()
print(f"Response: {json.dumps(result1, indent=2)}\n")

task_id_1 = result1.get("data", {}).get("taskId")

# ─── TEST 2: 4:5 ─────────────────────────────────────────────
print("=" * 60)
print("TEST 2: aspect ratio 4:5 (Meta Ads vertical)")
print("=" * 60)
payload_2 = {
    "model": "flux-kontext-pro",
    "prompt": "Purple medical gloves on clean white background, product photography, professional studio lighting",
    "aspectRatio": "4:5",
    "outputFormat": "jpeg",
}
print(f"Payload: {json.dumps(payload_2, indent=2)}\n")

r2 = requests.post(CREATE, headers=HEADERS, json=payload_2, timeout=30)
print(f"HTTP {r2.status_code}")
result2 = r2.json()
print(f"Response: {json.dumps(result2, indent=2)}\n")

task_id_2 = result2.get("data", {}).get("taskId")

# ─── POLL ambos ──────────────────────────────────────────────
print("=" * 60)
print("POLLING hasta completar (máx 90s)...")
print("=" * 60)

tasks = {k: v for k, v in {"1:1": task_id_1, "4:5": task_id_2}.items() if v}
done  = {}

for i in range(18):  # 18 × 5s = 90s
    time.sleep(5)
    for ratio, tid in list(tasks.items()):
        r = requests.get(f"{STATUS}?taskId={tid}", headers=HEADERS, timeout=30)
        data = r.json().get("data", {})
        flag = data.get("successFlag")
        print(f"  [{ratio}] taskId={tid[:16]}... successFlag={flag}")
        if flag == 1:
            print(f"  [{ratio}] EXITO — Full response:")
            print(f"  {json.dumps(data, indent=4)}")
            done[ratio] = data
            del tasks[ratio]
        elif flag in (2, 3):
            print(f"  [{ratio}] FALLO — {data.get('errorMessage','?')} (code={data.get('errorCode','?')})")
            del tasks[ratio]
    if not tasks:
        break

if tasks:
    print(f"\nTasks aun pendientes: {list(tasks.keys())} — prueba mas tiempo")

print("\n=== RESUMEN ===")
for ratio, d in done.items():
    url = d.get("response", {}).get("resultImageUrl", "N/A")
    print(f"  {ratio} -> URL: {url}")
