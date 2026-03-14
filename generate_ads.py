"""
PROVI — Kit Lila Ad Generator
Pipeline automatizado de generación de anuncios para Meta Ads via Nano Banana 2

Uso:
    python generate_ads.py

Requisitos:
    pip install requests Pillow tqdm python-dotenv

Variables de entorno (.env):
    NB2_API_KEY=tu_api_key_aqui
    NB2_REFERENCE_IMAGE_PATH=./assets/kit_lila_referencia.jpg  (opcional)
"""

import json
import os
import sys
import time
import logging
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from tqdm import tqdm

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv opcional

# Forzar UTF-8 en stdout/stderr para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────
# CONFIGURACIÓN — Ajusta estos valores
# ─────────────────────────────────────────────

API_KEY: str = os.getenv("NB2_API_KEY", "TU_API_KEY_AQUI")

# Endpoints de kie.ai — FLUX.1 Kontext Pro
# Confirmado via debug_flux.py
KIE_BASE_URL: str = "https://api.kie.ai/api/v1/flux/kontext"
NB2_GENERATE_ENDPOINT: str = f"{KIE_BASE_URL}/generate"      # POST — crea el task
NB2_STATUS_ENDPOINT: str = f"{KIE_BASE_URL}/record-info"     # GET  — ?taskId=<id>

# Modelo activo
FLUX_MODEL: str = "flux-kontext-pro"  # "flux-kontext-pro" | "flux-kontext-max"

# Carpeta raíz de salida
OUTPUT_DIR: Path = Path("./output/provi/kit_lila")

# Variaciones por prompt (2 variaciones × 20 prompts = 40 imágenes)
VARIATIONS_PER_PROMPT: int = 2

# Formatos Meta Ads — FLUX Kontext Pro soporta: 1:1, 3:4, 9:16, 4:3, 16:9
# 4:5 no está soportado → se mapea a 3:4 (portrait más cercano para Meta Feed)
ASPECT_RATIOS: dict = {
    "1:1": "1:1",   # 1080×1080 — Feed cuadrado
    "4:5": "3:4",   # 1080×1350 aprox → 3:4 es lo más cercano disponible
}

# Resolución de salida (no aplica en FLUX Kontext, se ignora)
OUTPUT_RESOLUTION: str = "2K"

# Formato de imagen de salida — FLUX Kontext acepta "jpeg" o "png" (no "jpg")
OUTPUT_FORMAT: str = "jpeg"

# Rate limiting — kie.ai permite hasta 20 requests por 10 segundos
DELAY_BETWEEN_REQUESTS: float = 0.6   # 20 req/10s → 1 cada 0.5s + margen
MAX_RETRIES: int = 3                   # reintentos por fallo
RETRY_BACKOFF_BASE: float = 2.0       # base del backoff exponencial (seg)
POLL_INTERVAL: float = 5.0            # segundos entre polls de estado del task
MAX_POLL_ATTEMPTS: int = 60           # máx intentos de polling (5 min total)

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "generation.log" if OUTPUT_DIR.exists() else "generation.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def setup_output_dirs() -> dict[str, Path]:
    """Crea la estructura de carpetas de salida."""
    dirs = {}
    for ratio_key in ASPECT_RATIOS:
        folder_name = f"formato_{ratio_key.replace(':', 'x')}"
        path = OUTPUT_DIR / folder_name
        path.mkdir(parents=True, exist_ok=True)
        dirs[ratio_key] = path
    log.info(f"Carpetas creadas en: {OUTPUT_DIR}")
    return dirs


def load_prompts(path: str = "provi_ad_prompts.json") -> list[dict]:
    """Carga y valida el JSON de prompts."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data.get("prompts", [])
    log.info(f"Prompts cargados: {len(prompts)}")
    return prompts


def build_headers() -> dict:
    """Headers de autenticación para Nano Banana 2."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def build_payload(prompt_data: dict, aspect_ratio: str, variation_seed: int) -> dict:
    """
    Construye el payload para FLUX.1 Kontext Pro en kie.ai.

    Estructura confirmada via debug_flux.py:
      {
        "model": "flux-kontext-pro",
        "prompt": "...",
        "aspectRatio": "1:1" | "4:5" | ...,
        "outputFormat": "jpeg"
      }
    """
    ratio_value = ASPECT_RATIOS[aspect_ratio]
    return {
        "model": FLUX_MODEL,
        "prompt": prompt_data["prompt"],
        "aspectRatio": ratio_value,
        "outputFormat": OUTPUT_FORMAT,
    }


def request_with_retry(
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response:
    """Ejecuta una petición HTTP con reintentos y backoff exponencial."""
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, timeout=30, **kwargs)

            if response.status_code == 429:  # Rate limit
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(f"Rate limit alcanzado. Esperando {wait:.1f}s (intento {attempt}/{max_retries})")
                time.sleep(wait)
                continue

            if response.status_code >= 500:  # Error de servidor
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(f"Error del servidor ({response.status_code}). Reintentando en {wait:.1f}s")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            wait = RETRY_BACKOFF_BASE ** attempt
            log.warning(f"Timeout en intento {attempt}/{max_retries}. Esperando {wait:.1f}s")
            time.sleep(wait)
        except requests.exceptions.ConnectionError as e:
            wait = RETRY_BACKOFF_BASE ** attempt
            log.warning(f"Error de conexión: {e}. Reintentando en {wait:.1f}s")
            time.sleep(wait)

    raise RuntimeError(f"Falló después de {max_retries} intentos: {method} {url}")


def submit_generation_job(payload: dict) -> str:
    """
    Envía un job de generación a kie.ai — FLUX.1 Kontext Pro.

    Respuesta confirmada:
        {"code": 200, "msg": "success", "data": {"taskId": "abc123"}}
    """
    response = request_with_retry("POST", NB2_GENERATE_ENDPOINT, headers=build_headers(), json=payload)
    result = response.json()

    if result.get("code") != 200:
        raise ValueError(f"API error {result.get('code')}: {result.get('msg')} — {result}")

    task_id = result.get("data", {}).get("taskId")
    if not task_id:
        raise ValueError(f"No se encontro taskId en la respuesta: {result}")

    return task_id


def poll_job_status(task_id: str) -> str:
    """
    Hace polling al endpoint GET /record-info?taskId=<id> de kie.ai (FLUX Kontext).

    Respuesta confirmada al completar:
        {
          "code": 200, "msg": "success",
          "data": {
            "taskId": "...",
            "successFlag": 1,          -- 0=generando, 1=exito, 2/3=fallo
            "response": {
              "resultImageUrl": "https://..."
            }
          }
        }
    """
    url = f"{NB2_STATUS_ENDPOINT}?taskId={task_id}"
    for attempt in range(MAX_POLL_ATTEMPTS):
        response = request_with_retry("GET", url, headers=build_headers())
        result = response.json()
        data = result.get("data", {})
        flag = data.get("successFlag")

        if flag == 1:
            image_url = data.get("response", {}).get("resultImageUrl")
            if not image_url:
                raise ValueError(f"Task exitoso pero sin URL de imagen: {data}")
            return image_url

        if flag in (2, 3):
            err = data.get("errorMessage") or data.get("errorCode") or "Error desconocido"
            raise RuntimeError(f"Task {task_id} fallo (flag={flag}): {err}")

        log.debug(f"Task {task_id} — successFlag={flag} (poll {attempt + 1}/{MAX_POLL_ATTEMPTS})")
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Task {task_id} no completo en {MAX_POLL_ATTEMPTS * POLL_INTERVAL:.0f}s")


def download_image(image_url: str, dest_path: Path) -> Path:
    """Descarga una imagen desde una URL y la guarda en dest_path."""
    response = request_with_retry("GET", image_url, stream=True)

    # Detectar extensión desde Content-Type o URL
    content_type = response.headers.get("Content-Type", "image/png")
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".png"
    ext = ext.replace(".jpe", ".jpg")  # normalizar

    final_path = dest_path.with_suffix(ext)
    with open(final_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return final_path


def generate_single_ad(
    prompt_data: dict,
    aspect_ratio: str,
    variation_idx: int,
    output_dirs: dict,
) -> Optional[Path]:
    """
    Genera una imagen individual: submit → poll → download.
    Retorna la ruta del archivo descargado, o None si falla.
    """
    # Seed reproducible pero único por variación
    seed_source = f"{prompt_data['id']}-{aspect_ratio}-{variation_idx}"
    seed = int(hashlib.md5(seed_source.encode()).hexdigest()[:8], 16)

    payload = build_payload(prompt_data, aspect_ratio, seed)

    ratio_key = aspect_ratio
    output_dir = output_dirs[ratio_key]
    filename = f"provi_p{prompt_data['id']:02d}_{prompt_data['angle']}_{ratio_key.replace(':', 'x')}_v{variation_idx}"
    dest_path = output_dir / filename

    try:
        log.info(f"  >> ID:{prompt_data['id']} | {aspect_ratio} | v{variation_idx} | {prompt_data['angle']}")
        job_id = submit_generation_job(payload)
        image_url = poll_job_status(job_id)
        saved_path = download_image(image_url, dest_path)
        log.info(f"  OK Guardado: {saved_path.name}")
        return saved_path

    except Exception as e:
        log.error(f"  FALLO ID:{prompt_data['id']} v{variation_idx} [{aspect_ratio}]: {e}")
        return None


# ─────────────────────────────────────────────
# GALERÍA HTML
# ─────────────────────────────────────────────

def generate_gallery(output_dirs: dict, all_results: list[dict]) -> Path:
    """
    Genera una galería HTML moderna, responsiva y filtrable con Tailwind CSS.
    Agrupa los anuncios por formato (1:1 / 4:5).
    """
    gallery_path = OUTPUT_DIR / "index.html"

    # Agrupar imágenes por ratio
    by_ratio: dict[str, list] = {ratio: [] for ratio in ASPECT_RATIOS}
    for result in all_results:
        if result.get("path") and result["path"].exists():
            ratio = result["aspect_ratio"]
            rel_path = result["path"].relative_to(OUTPUT_DIR)
            by_ratio[ratio].append({
                "rel_path": str(rel_path).replace("\\", "/"),
                "prompt_id": result["prompt_id"],
                "angle": result["angle"],
                "angle_label": result["angle_label"],
                "headline": result["headline"],
                "cta": result["cta"],
                "variation": result["variation"],
                "format": ratio,
            })

    total_images = sum(len(v) for v in by_ratio.values())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Generar cards HTML por ratio
    def build_cards(items: list, ratio: str) -> str:
        if not items:
            return '<p class="text-gray-400 col-span-full text-center py-10">Sin imágenes generadas para este formato.</p>'
        cards = []
        for item in items:
            angle_color = {
                "nosotros_vs_ellos": "bg-blue-100 text-blue-700",
                "desglose_valor": "bg-green-100 text-green-700",
                "ugc_estatico": "bg-yellow-100 text-yellow-700",
                "urgencia_whatsapp": "bg-red-100 text-red-700",
                "bioseguridad_estetica": "bg-purple-100 text-purple-700",
            }.get(item["angle"], "bg-gray-100 text-gray-700")

            cards.append(f"""
            <div class="bg-white rounded-2xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300 group">
              <div class="overflow-hidden bg-gray-50">
                <img
                  src="{item['rel_path']}"
                  alt="{item['headline']}"
                  loading="lazy"
                  class="w-full object-cover group-hover:scale-105 transition-transform duration-500"
                  onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 400 400%22><rect fill=%22%23f3f4f6%22 width=%22400%22 height=%22400%22/><text x=%22200%22 y=%22200%22 text-anchor=%22middle%22 fill=%22%23d1d5db%22 font-size=%2220%22>Sin imagen</text></svg>'"
                />
              </div>
              <div class="p-4">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-semibold px-2 py-1 rounded-full {angle_color}">{item['angle_label']}</span>
                  <span class="text-xs text-gray-400 font-mono">#{item['prompt_id']:02d} · v{item['variation']} · {item['format']}</span>
                </div>
                <p class="text-sm font-semibold text-gray-800 leading-snug mb-1">"{item['headline']}"</p>
                <p class="text-xs text-teal-600 font-medium">📲 {item['cta']}</p>
              </div>
            </div>""")
        return "\n".join(cards)

    tabs_content = ""
    tab_buttons = ""
    first = True
    for ratio, items in by_ratio.items():
        ratio_id = ratio.replace(":", "x")
        active_tab = "tab-active" if first else "tab-inactive"
        active_panel = "" if first else 'hidden'
        count = len(items)
        cols = "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4" if ratio == "1:1" else "grid-cols-2 sm:grid-cols-3 lg:grid-cols-3"

        tab_buttons += f"""
        <button
          onclick="switchTab('{ratio_id}')"
          id="btn-{ratio_id}"
          class="tab-btn px-6 py-2.5 rounded-full text-sm font-semibold transition-all duration-200 {active_tab}"
        >
          {ratio} <span class="ml-1 opacity-70">({count})</span>
        </button>"""

        tabs_content += f"""
        <div id="panel-{ratio_id}" class="tab-panel {active_panel}">
          <div class="grid {cols} gap-5">
            {build_cards(items, ratio)}
          </div>
        </div>"""
        first = False

    # Estadísticas por ángulo
    angle_stats = {}
    for result in all_results:
        if result.get("path") and result["path"].exists():
            a = result["angle_label"]
            angle_stats[a] = angle_stats.get(a, 0) + 1

    stats_html = "".join([
        f'<div class="bg-white rounded-xl p-4 text-center shadow-sm"><p class="text-2xl font-bold text-purple-600">{count}</p><p class="text-xs text-gray-500 mt-1">{angle}</p></div>'
        for angle, count in angle_stats.items()
    ])

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PROVI — Galería Kit Lila Ads</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {{
      --lila: #A855F7;
      --teal: #2CB1BC;
      --navy: #0F2A43;
    }}
    body {{ font-family: 'Inter', system-ui, sans-serif; background: #F5F7FA; }}
    .tab-active {{ background: var(--lila); color: white; }}
    .tab-inactive {{ background: white; color: #6B7280; border: 1px solid #E5E7EB; }}
    .tab-inactive:hover {{ background: #F3E8FF; color: var(--lila); }}
    .brand-gradient {{ background: linear-gradient(135deg, var(--navy) 0%, #1e3a5f 50%, #2CB1BC 100%); }}
    img {{ display: block; width: 100%; }}
    .hidden {{ display: none !important; }}
  </style>
</head>
<body class="min-h-screen">

  <!-- Header -->
  <header class="brand-gradient text-white py-10 px-6 shadow-lg">
    <div class="max-w-7xl mx-auto">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <div class="w-3 h-3 rounded-full bg-purple-400"></div>
            <span class="text-purple-300 text-sm font-medium uppercase tracking-widest">Meta Ads Campaign</span>
          </div>
          <h1 class="text-3xl md:text-4xl font-black tracking-tight">PROVI — Kit Lila</h1>
          <p class="text-teal-300 mt-1 text-sm">Galería de revisión · {total_images} anuncios generados</p>
        </div>
        <div class="text-right">
          <p class="text-white/60 text-xs">Generado el</p>
          <p class="text-white font-semibold">{timestamp}</p>
          <p class="text-teal-300 text-xs mt-1">Nano Banana 2 · {VARIATIONS_PER_PROMPT} variaciones/prompt</p>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 mt-8">
        {stats_html}
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 py-8">

    <!-- Filters / Tabs -->
    <div class="flex items-center gap-3 mb-8 flex-wrap">
      <span class="text-sm font-semibold text-gray-500 mr-2">Formato:</span>
      {tab_buttons}
    </div>

    <!-- Tab Panels -->
    {tabs_content}

  </main>

  <!-- Footer -->
  <footer class="text-center py-6 text-gray-400 text-xs border-t border-gray-200 mt-10">
    PROVI · Kit Lila · Pipeline generado con Claude Code + Nano Banana 2
  </footer>

  <script>
    function switchTab(ratioId) {{
      // Ocultar todos los paneles
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
      // Desactivar todos los botones
      document.querySelectorAll('.tab-btn').forEach(b => {{
        b.classList.remove('tab-active');
        b.classList.add('tab-inactive');
      }});
      // Activar panel y botón seleccionado
      document.getElementById('panel-' + ratioId).classList.remove('hidden');
      const btn = document.getElementById('btn-' + ratioId);
      btn.classList.add('tab-active');
      btn.classList.remove('tab-inactive');
    }}

    // Lightbox simple al hacer click en imagen
    document.addEventListener('DOMContentLoaded', () => {{
      const overlay = document.createElement('div');
      overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;cursor:zoom-out;justify-content:center;align-items:center;padding:20px';
      overlay.innerHTML = '<img id="lb-img" style="max-height:90vh;max-width:90vw;border-radius:12px;object-fit:contain;box-shadow:0 25px 60px rgba(0,0,0,0.5)">';
      document.body.appendChild(overlay);

      document.querySelectorAll('.tab-panel img').forEach(img => {{
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', () => {{
          document.getElementById('lb-img').src = img.src;
          overlay.style.display = 'flex';
        }});
      }});
      overlay.addEventListener('click', () => overlay.style.display = 'none');
      document.addEventListener('keydown', e => {{ if(e.key === 'Escape') overlay.style.display = 'none'; }});
    }});
  </script>
</body>
</html>"""

    with open(gallery_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Galería generada: {gallery_path}")
    return gallery_path


# ─────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────

def validate_config():
    """Valida la configuración antes de ejecutar el pipeline."""
    errors = []
    if API_KEY in ("TU_API_KEY_AQUI", "", None):
        errors.append("ERROR: API_KEY no configurada. Agrega NB2_API_KEY en tu .env o edita el script.")
    if errors:
        print("\n".join(errors))
        print("\nEdita el script o crea un archivo .env con NB2_API_KEY=tu_clave")
        raise SystemExit(1)


def run_pipeline():
    """Ejecuta el pipeline completo de generación."""
    validate_config()

    log.info("=" * 60)
    log.info(f"PROVI Kit Lila — Iniciando pipeline ({FLUX_MODEL})")
    log.info(f"Variaciones por prompt: {VARIATIONS_PER_PROMPT}")
    log.info(f"Formatos: {list(ASPECT_RATIOS.keys())}")
    log.info("=" * 60)

    output_dirs = setup_output_dirs()
    prompts = load_prompts()

    # Calcular total de generaciones
    total_jobs = len(prompts) * VARIATIONS_PER_PROMPT
    log.info(f"Total de imágenes a generar: {total_jobs}")

    all_results: list[dict] = []
    failed_jobs: list[dict] = []

    with tqdm(total=total_jobs, desc="Generando anuncios", unit="img") as pbar:
        for prompt_data in prompts:
            aspect_ratio = prompt_data.get("format", "1:1")

            for variation_idx in range(1, VARIATIONS_PER_PROMPT + 1):
                saved_path = generate_single_ad(
                    prompt_data=prompt_data,
                    aspect_ratio=aspect_ratio,
                    variation_idx=variation_idx,
                    output_dirs=output_dirs,
                )

                result = {
                    "prompt_id": prompt_data["id"],
                    "angle": prompt_data["angle"],
                    "angle_label": prompt_data.get("angle_label", prompt_data["angle"]),
                    "headline": prompt_data.get("headline", ""),
                    "cta": prompt_data.get("cta", ""),
                    "aspect_ratio": aspect_ratio,
                    "variation": variation_idx,
                    "path": saved_path,
                }
                all_results.append(result)

                if saved_path is None:
                    failed_jobs.append(result)

                pbar.update(1)
                # Rate limiting
                time.sleep(DELAY_BETWEEN_REQUESTS)

    # Resumen
    successful = sum(1 for r in all_results if r["path"] is not None)
    log.info("=" * 60)
    log.info(f"Pipeline completado: {successful}/{total_jobs} imágenes generadas")
    if failed_jobs:
        log.warning(f"Fallidas: {len(failed_jobs)} — revisa generation.log para detalles")

    # Generar galería HTML
    gallery_path = generate_gallery(output_dirs, all_results)
    log.info(f"Galería disponible en: {gallery_path.resolve()}")
    log.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
