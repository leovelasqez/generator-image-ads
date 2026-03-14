Actúa como un AI Engineer y experto en automatización de marketing. Tu objetivo es construir y ejecutar un pipeline automatizado de creación de anuncios estáticos para Meta Ads, integrando web scraping, redacción publicitaria y llamadas a la API de Nano Banana 2.

[INSTRUCCIÓN DE SKILLS]
Antes de comenzar, evalúa los requerimientos de este proyecto. Tienes total libertad para invocar y utilizar cualquier Skill de tu entorno (como los provenientes de skills.sh) que consideres necesario para optimizar el resultado. Considera proactivamente usar skills de navegación web, diseño frontend (para la galería), revisión de código o depuración sistemática (systematic-debugging) según los bloqueos o necesidades de cada etapa.

[CONTEXTO DEL SISTEMA]
Quiero replicar un sistema que toma una marca y un producto, investiga su identidad visual, genera 40 prompts de diseño publicitario de alta conversión y los envía a Nano Banana 2 para generar las imágenes finales, organizándolas en una galería HTML.

[DATOS DE LA MARCA Y PRODUCTO]
- Nombre de la marca: PROVI
- Sitio web: https://provi.tienda/
- Instagram: https://www.instagram.com/provi.tienda/
- Producto a promocionar: "Kit Lila" (Incluye: Tapabocas x50 + Gorro Oruga x50 + Guantes Nitrilo x100).
- Objetivo de la campaña: Meta Ads enfocados en conversión directa, llevando tráfico a WhatsApp Business. El llamado a la acción (CTA) debe ser siempre hacia WhatsApp (ej. "Pídelo por WhatsApp", "Escríbenos para asesoría").
- Nicho: Insumos médicos, de belleza, odontológicos o estética.

[INSTRUCCIONES DE EJECUCIÓN - PASO A PASO]

PASO 1: INVESTIGACIÓN Y BRAND DNA
Usa tus herramientas y skills de navegación para visitar la URL de la página web y el Instagram proporcionados. Extrae la paleta de colores predominante (códigos HEX), tipografías, estilo de fotografía y el tono de voz de la marca. Crea un archivo local llamado `provi_brand_dna.md` con esta información.

PASO 2: GENERACIÓN DE 40 PROMPTS DE ANUNCIOS
Basado en el `provi_brand_dna.md` y los detalles del "Kit Lila", redacta 20 prompts optimizados para el modelo de imagen Nano Banana 2. 
Los ángulos deben incluir: "Nosotros vs. Ellos", Desglose de valor del kit, UGC estático, Urgencia para comprar por WhatsApp, y enfoque en bioseguridad/estética (color lila como diferenciador). Guarda esto en un archivo JSON estructurado llamado `provi_ad_prompts.json`.

PASO 3: SCRIPT DE INTEGRACIÓN CON NANO BANANA 2
Escribe un script (Python o Node.js) robusto y de calidad de producción llamado `generate_ads.py` que:
1. Lea el JSON de prompts.
2. Haga llamadas a la API de Nano Banana 2 pidiendo 2 variaciones por prompt (40 imágenes totales). Configura el aspect ratio para Meta Ads (1:1 y 4:5). Deja variables claras para mi API Key y la ruta de la imagen de referencia del producto.
3. Descargue y guarde las imágenes en `./output/provi/kit_lila/formato_X/`. Implementa manejo de errores, control de rate limits de la API y reintentos.

PASO 4: GALERÍA DE REVISIÓN
Dentro del script, incluye una función que genere un archivo `index.html` en la carpeta principal de salida al finalizar las descargas. Usa tus skills de frontend para que esta galería no sea una tabla básica, sino una interfaz limpia, responsiva y moderna (puedes inyectar Tailwind si lo prefieres) donde pueda visualizar rápidamente los 160 anuncios agrupados por formato.

Por favor, planifica tu enfoque, indícame qué skills vas a activar para cada fase y comienza ejecutando el PASO 1.