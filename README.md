# 🎯 Generator Image Ads — PROVI Kit Lila

Pipeline automatizado de generación de anuncios estáticos para **Meta Ads**, usando **FLUX.1 Kontext Pro** vía [kie.ai](https://kie.ai). Toma una marca y un producto, genera prompts de diseño publicitario de alta conversión y los envía a la API para producir imágenes listas para campañas.

---

## ¿Qué hace este proyecto?

1. **Investiga la marca** — extrae paleta de colores, tipografía, tono de voz y datos clave del producto
2. **Genera 20 prompts** — redactados para Meta Ads con 5 ángulos de conversión distintos
3. **Llama a la API** — envía cada prompt a FLUX.1 Kontext Pro (2 variaciones por prompt = 40 imágenes)
4. **Organiza las imágenes** — guardadas por formato en `./output/provi/kit_lila/`
5. **Genera una galería HTML** — interfaz visual con Tailwind CSS para revisar todos los anuncios

---

## Marca y producto

| Campo | Valor |
|-------|-------|
| Marca | **PROVI** |
| Producto | **Kit Lila Completo** |
| Contenido | Tapabocas x50 + Gorro Oruga x50 + Guantes Nitrilo x100 |
| Precio | $41.950 COP |
| Nicho | Insumos médicos, belleza, odontología, estética |
| CTA | WhatsApp Business (`3126786075`) |
| Objetivo | Meta Ads — conversión directa vía WhatsApp |

---

## Ángulos de los anuncios

| Ángulo | Descripción |
|--------|-------------|
| `nosotros_vs_ellos` | Comparación Kit vs. compra individual (ahorro 29%) |
| `desglose_valor` | Presentación del kit ítem por ítem con precio desglosado |
| `ugc_estatico` | Estilo contenido de usuario — testimonial visual |
| `urgencia_whatsapp` | CTA de escasez y urgencia hacia WhatsApp |
| `bioseguridad_estetica` | Color lila como diferenciador de bioseguridad premium |

---

## Stack técnico

| Componente | Tecnología |
|------------|------------|
| Modelo de imagen | [FLUX.1 Kontext Pro](https://kie.ai/features/flux1-kontext) |
| API | [kie.ai](https://kie.ai) — `api.kie.ai/api/v1/flux/kontext` |
| Script | Python 3.12 |
| Dependencias | `requests`, `tqdm`, `python-dotenv` |
| Galería | HTML + Tailwind CSS (CDN) |

---

## Estructura del proyecto

```
generator-image-ads/
├── generate_ads.py          # Script principal del pipeline
├── provi_ad_prompts.json    # 20 prompts estructurados por ángulo
├── provi_brand_dna.md       # Identidad visual y datos de la marca
├── .env.example             # Plantilla de variables de entorno
├── .gitignore
└── output/                  # Imágenes generadas (excluido de git)
    └── provi/kit_lila/
        ├── formato_1x1/     # Anuncios 1:1 (Feed cuadrado)
        ├── formato_4x5/     # Anuncios 3:4 (Feed vertical)
        └── index.html       # Galería de revisión
```

---

## Instalación y uso

### 1. Clonar el repositorio

```bash
git clone https://github.com/leovelasqez/generator-image-ads.git
cd generator-image-ads
```

### 2. Instalar dependencias

```bash
pip install requests tqdm python-dotenv
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
NB2_API_KEY=tu_api_key_de_kie_ai
```

> Obtén tu API key en [kie.ai](https://kie.ai) → Dashboard → API Keys

### 4. Ejecutar el pipeline

```bash
python generate_ads.py
```

El script generará **40 imágenes** (20 prompts × 2 variaciones) organizadas por formato y creará una galería HTML en `./output/provi/kit_lila/index.html`.

---

## API de kie.ai — FLUX.1 Kontext Pro

El script usa el modelo asíncrono de kie.ai:

```
POST https://api.kie.ai/api/v1/flux/kontext/generate
GET  https://api.kie.ai/api/v1/flux/kontext/record-info?taskId=<id>
```

**Payload de ejemplo:**

```json
{
  "model": "flux-kontext-pro",
  "prompt": "...",
  "aspectRatio": "1:1",
  "outputFormat": "jpeg"
}
```

**Respuesta de estado:**

```json
{
  "data": {
    "successFlag": 1,
    "response": {
      "resultImageUrl": "https://..."
    }
  }
}
```

| `successFlag` | Estado |
|---|---|
| `0` | Generando |
| `1` | Exitoso |
| `2` / `3` | Fallido |

---

## Formatos de salida

| Formato | Ratio API | Uso Meta Ads |
|---------|-----------|-------------|
| `formato_1x1` | `1:1` | Feed cuadrado |
| `formato_4x5` | `3:4` | Feed vertical (mayor alcance orgánico) |

---

## Configuración avanzada

Edita las constantes al inicio de `generate_ads.py`:

```python
FLUX_MODEL            = "flux-kontext-pro"  # o "flux-kontext-max"
VARIATIONS_PER_PROMPT = 2                   # variaciones por prompt
DELAY_BETWEEN_REQUESTS = 0.6               # segundos entre requests
MAX_RETRIES           = 3                   # reintentos por fallo
POLL_INTERVAL         = 5.0                # segundos entre polls
```

---

## Reutilizar para otra marca

1. Edita `provi_brand_dna.md` con los datos de la nueva marca
2. Reemplaza `provi_ad_prompts.json` con prompts adaptados al nuevo producto
3. Ajusta `OUTPUT_DIR` en `generate_ads.py`
4. Ejecuta el pipeline

---

## Licencia

MIT
