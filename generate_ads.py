"""
PROVI — Kit Lila Ad Generator
Pipeline automatizado de generación de anuncios para Meta Ads via fal.ai — Nano Banana 2

Uso:
    python generate_ads.py

Requisitos:
    pip install fal-client tqdm python-dotenv requests

Variables de entorno (.env):
    FAL_KEY=tu_api_key_de_fal.ai
    NB2_REFERENCE_IMAGE_PATH=./assets/kit_lila_referencia.jpg  (opcional — activa img2img)
"""

import json
import os
import sys
import time
import logging
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Optional

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

FAL_KEY: str = os.getenv("FAL_KEY", "TU_FAL_KEY_AQUI")

# Modelo fal.ai — Nano Banana 2 (Gemini 2.0 Flash Image)
FAL_MODEL: str = "fal-ai/nano-banana-pro"

# Imagen de referencia del producto (opcional — activa img2img)
REFERENCE_IMAGE_PATH: str = os.getenv("NB2_REFERENCE_IMAGE_PATH", "")

# Carpeta raíz de salida
OUTPUT_DIR: Path = Path("./output/provi/kit_lila")

# Variaciones por prompt (2 variaciones × 20 prompts = 40 imágenes)
VARIATIONS_PER_PROMPT: int = 2

# Formatos Meta Ads
ASPECT_RATIOS: dict = {
    "1:1": "1:1",   # 1080×1080 — Feed cuadrado
    "4:5": "4:5",   # 1080×1350 — Feed vertical (mayor alcance)
}

# Reintentos por fallo
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 2.0  # segundos base del backoff exponencial

# Delay entre requests para respetar rate limits de fal.ai
DELAY_BETWEEN_REQUESTS: float = 0.5


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

def setup_logging():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(stream=sys.stdout),
            logging.FileHandler(OUTPUT_DIR / "generation.log", encoding="utf-8"),
        ],
    )

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FAL CLIENT SETUP
# ─────────────────────────────────────────────

def init_fal_client():
    """Configura el cliente fal.ai con la API key."""
    import fal_client  # noqa: F401 — verifica instalación
    os.environ["FAL_KEY"] = FAL_KEY

init_fal_client()
import fal_client


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
    log.info(f"Carpetas de salida: {OUTPUT_DIR}")
    return dirs


def load_prompts(path: str = "provi_ad_prompts.json") -> list[dict]:
    """Carga y valida el JSON de prompts."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data.get("prompts", [])
    log.info(f"Prompts cargados: {len(prompts)}")
    return prompts


def upload_reference_image() -> Optional[str]:
    """
    Sube la imagen de referencia del producto a fal.ai y retorna su URL pública.
    Esta URL se reutiliza en todos los prompts para activar img2img.
    Retorna None si no hay imagen de referencia configurada.
    """
    ref_path = Path(REFERENCE_IMAGE_PATH) if REFERENCE_IMAGE_PATH else None

    if not ref_path or not ref_path.exists():
        if REFERENCE_IMAGE_PATH:
            log.warning(f"Imagen de referencia no encontrada: {REFERENCE_IMAGE_PATH}")
        else:
            log.info("Sin imagen de referencia — generación text-to-image")
        return None

    log.info(f"Subiendo imagen de referencia a fal.ai: {ref_path.name}")
    url = fal_client.upload_file(str(ref_path))
    log.info(f"Referencia disponible en: {url}")
    return url


def build_arguments(prompt_data: dict, aspect_ratio: str, ref_url: Optional[str]) -> dict:
    """
    Construye los argumentos para fal_client.subscribe().

    Documentación fal.ai — Nano Banana 2:
      https://fal.ai/models/fal-ai/nano-banana-2/api
    """
    args = {
        "prompt": prompt_data["prompt"],
        "aspect_ratio": ASPECT_RATIOS[aspect_ratio],
        "limit_generations": False,  # requerido para múltiples variaciones del mismo prompt
    }

    # Negative prompt si está definido en el JSON
    if prompt_data.get("negative_prompt"):
        args["negative_prompt"] = prompt_data["negative_prompt"]

    # img2img — pasa la URL de referencia si está disponible
    if ref_url:
        args["image_urls"] = [ref_url]

    return args


def generate_single_ad(
    prompt_data: dict,
    aspect_ratio: str,
    variation_idx: int,
    output_dirs: dict,
    ref_url: Optional[str],
) -> Optional[Path]:
    """
    Genera una imagen individual via fal_client.subscribe() (síncrono, sin polling).
    Retorna la ruta del archivo descargado, o None si falla.
    """
    ratio_key = aspect_ratio
    output_dir = output_dirs[ratio_key]
    safe_angle = prompt_data["angle"].replace(" ", "_")[:30]
    filename = f"provi_p{prompt_data['id']:02d}_{safe_angle}_{ratio_key.replace(':', 'x')}_v{variation_idx}"
    dest_path = output_dir / filename

    args = build_arguments(prompt_data, aspect_ratio, ref_url)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"  >> ID:{prompt_data['id']:02d} | {aspect_ratio} | v{variation_idx} | {prompt_data['angle']}"
                     + (" [img2img]" if ref_url else ""))

            result = fal_client.subscribe(FAL_MODEL, arguments=args)

            # Extraer URL de la imagen generada
            images = result.get("images") or []
            if not images:
                raise ValueError(f"Respuesta sin imágenes: {result}")
            image_url = images[0]["url"]

            # Descargar la imagen
            saved_path = download_image(image_url, dest_path)
            log.info(f"  OK {saved_path.name}")
            return saved_path

        except Exception as e:
            wait = RETRY_BACKOFF_BASE ** attempt
            if attempt < MAX_RETRIES:
                log.warning(f"  Intento {attempt}/{MAX_RETRIES} fallido: {e}. Reintentando en {wait:.0f}s")
                time.sleep(wait)
            else:
                log.error(f"  FALLO ID:{prompt_data['id']} v{variation_idx} [{aspect_ratio}]: {e}")
                return None


def download_image(image_url: str, dest_path: Path) -> Path:
    """Descarga una imagen desde una URL y la guarda en dest_path."""
    response = requests.get(image_url, timeout=60, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "image/jpeg")
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
    ext = ext.replace(".jpe", ".jpg")

    final_path = dest_path.with_suffix(ext)
    with open(final_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return final_path


# ─────────────────────────────────────────────
# GALERÍA HTML
# ─────────────────────────────────────────────

def generate_gallery(output_dirs: dict, all_results: list[dict], used_img2img: bool) -> Path:
    """
    Genera una galería HTML moderna, responsiva y filtrable con Tailwind CSS.
    Agrupa los anuncios por formato (1:1 / 4:5).
    """
    gallery_path = OUTPUT_DIR / "index.html"

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
    model_badge = "fal.ai · Nano Banana 2" + (" · img2img" if used_img2img else "")

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
        active_panel = "" if first else "hidden"
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
          <p class="text-teal-300 text-xs mt-1">{model_badge} · {VARIATIONS_PER_PROMPT} variaciones/prompt</p>
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
    PROVI · Kit Lila · Pipeline generado con Claude Code + fal.ai Nano Banana 2
  </footer>

  <script>
    function switchTab(ratioId) {{
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(b => {{
        b.classList.remove('tab-active');
        b.classList.add('tab-inactive');
      }});
      document.getElementById('panel-' + ratioId).classList.remove('hidden');
      const btn = document.getElementById('btn-' + ratioId);
      btn.classList.add('tab-active');
      btn.classList.remove('tab-inactive');
    }}

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
    if FAL_KEY in ("TU_FAL_KEY_AQUI", "", None):
        print("ERROR: FAL_KEY no configurada.")
        print("Crea un archivo .env con: FAL_KEY=tu_clave_de_fal.ai")
        print("Obtén tu clave en: https://fal.ai/dashboard/keys")
        raise SystemExit(1)


def run_pipeline():
    """Ejecuta el pipeline completo de generación."""
    validate_config()
    setup_logging()

    log.info("=" * 60)
    log.info(f"PROVI Kit Lila — Pipeline iniciado ({FAL_MODEL})")
    log.info(f"Variaciones por prompt: {VARIATIONS_PER_PROMPT}")
    log.info(f"Formatos: {list(ASPECT_RATIOS.keys())}")
    log.info("=" * 60)

    output_dirs = setup_output_dirs()
    prompts = load_prompts()

    # Subir imagen de referencia una sola vez (reutilizar en todos los prompts)
    ref_url = upload_reference_image()
    used_img2img = ref_url is not None

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
                    ref_url=ref_url,
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
                time.sleep(DELAY_BETWEEN_REQUESTS)

    successful = sum(1 for r in all_results if r["path"] is not None)
    log.info("=" * 60)
    log.info(f"Pipeline completado: {successful}/{total_jobs} imágenes generadas")
    if failed_jobs:
        log.warning(f"Fallidas: {len(failed_jobs)} — revisa generation.log")

    gallery_path = generate_gallery(output_dirs, all_results, used_img2img)
    log.info(f"Galería: {gallery_path.resolve()}")
    log.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
