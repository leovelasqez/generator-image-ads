"""
Script de diagnóstico para la API de kie.ai — Nano Banana 2.
Ejecuta: python debug_api.py
"""
import os, json, mimetypes, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NB2_API_KEY", "")
REFERENCE_IMAGE = os.getenv("NB2_REFERENCE_IMAGE_PATH", "")
ENDPOINT = "https://api.kie.ai/api/v1/jobs/createTask"

print(f"API_KEY loaded: {'YES (' + API_KEY[:8] + '...)' if API_KEY else 'NO — MISSING'}")
print(f"Reference image: {REFERENCE_IMAGE!r}  exists={Path(REFERENCE_IMAGE).exists() if REFERENCE_IMAGE else False}")
print()

# --- TEST 1: texto puro (text-to-image) ---
print("=" * 60)
print("TEST 1: Text-to-image (sin imagen de referencia)")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
payload_t2i = {
    "model": "nano-banana-2",
    "input": {
        "prompt": "A simple test image: white background, purple medical gloves",
        "aspect_ratio": "1:1",
    },
}
print(f"Payload enviado: {json.dumps(payload_t2i, indent=2)}")
print(f"Headers: Authorization=Bearer {API_KEY[:8]}...")
print()

try:
    r = requests.post(ENDPOINT, headers=headers, json=payload_t2i, timeout=30)
    print(f"HTTP Status Code: {r.status_code}")
    print(f"Response headers: {dict(r.headers)}")
    print(f"Response body:\n{json.dumps(r.json(), indent=2)}")
except Exception as e:
    print(f"ERROR: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response text: {e.response.text}")

print()

# --- TEST 2: con imagen de referencia (img2img) si existe ---
if REFERENCE_IMAGE and Path(REFERENCE_IMAGE).exists():
    print("=" * 60)
    print("TEST 2: Img2img (con imagen de referencia)")
    print("=" * 60)

    headers_img = {"Authorization": f"Bearer {API_KEY}"}
    mime_type = mimetypes.guess_type(REFERENCE_IMAGE)[0] or "image/webp"
    # Intento A: input como JSON string + image_input como campo separado
    input_obj = {
        "prompt": "A simple test image: white background, purple medical gloves",
        "aspect_ratio": "1:1",
    }
    data_fields_a = {
        "model": "nano-banana-2",
        "input": json.dumps(input_obj),
    }
    print(f"[A] Form data: {data_fields_a}")
    print(f"[A] File field: image_input ({mime_type})")
    print()

    with open(REFERENCE_IMAGE, "rb") as f:
        files_a = [("image_input", (Path(REFERENCE_IMAGE).name, f, mime_type))]
        try:
            r2a = requests.post(ENDPOINT, headers=headers_img, files=files_a, data=data_fields_a, timeout=30)
            print(f"[A] HTTP Status: {r2a.status_code}")
            print(f"[A] Response:\n{json.dumps(r2a.json(), indent=2)}")
        except Exception as e:
            print(f"[A] ERROR: {e}")

    print()
    # Intento B: JSON body con imagen JPEG (convertida de WEBP) en base64
    import base64, io
    from PIL import Image as PILImage
    img_pil = PILImage.open(REFERENCE_IMAGE).convert("RGB")
    buf = io.BytesIO()
    img_pil.save(buf, format="JPEG", quality=90)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"[B] JSON body con imagen JPEG base64 (convertida de WEBP, {len(buf.getvalue())} bytes)")
    payload_b_real = {
        "model": "nano-banana-2",
        "input": {
            "prompt": "A simple test image: white background, purple medical gloves",
            "aspect_ratio": "1:1",
            "image_input": f"data:image/jpeg;base64,{img_b64}",
        },
    }
    try:
        r2b = requests.post(ENDPOINT, headers={**headers_img, "Content-Type": "application/json"},
                            json=payload_b_real, timeout=30)
        print(f"[B] HTTP Status: {r2b.status_code}")
        print(f"[B] Response:\n{json.dumps(r2b.json(), indent=2)}")
    except Exception as e:
        print(f"[B] ERROR: {e}")

    print()
    # Intento C: multipart con imagen JPEG convertida
    buf.seek(0)
    data_fields_c = {
        "model": "nano-banana-2",
        "input": json.dumps({
            "prompt": "A simple test image: white background, purple medical gloves",
            "aspect_ratio": "1:1",
        }),
    }
    print(f"[C] Multipart con imagen JPEG convertida, field=image_input")
    try:
        files_c = [("image_input", ("reference.jpg", buf.getvalue(), "image/jpeg"))]
        r2c = requests.post(ENDPOINT, headers=headers_img, files=files_c, data=data_fields_c, timeout=30)
        print(f"[C] HTTP Status: {r2c.status_code}")
        print(f"[C] Response:\n{json.dumps(r2c.json(), indent=2)}")
    except Exception as e:
        print(f"[C] ERROR: {e}")
else:
    print("TEST 2 omitido: no hay imagen de referencia configurada o no existe.")
