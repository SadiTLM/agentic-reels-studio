---
name: agentic-reels-pipeline
description: >-
  Orquestador completo del sistema Agentic Reels Studio (SadiTLM/agentic-reels-studio).
  Gestiona el ciclo completo de contenido para Instagram Reels y Carruseles:
  (1) buscar tendencias (last30days + ig-viral), (2) generar ideas y guiones con
  hookscore/beats, (3) validar con revisión Goldfish y aprobación humana,
  (4) producir video 9:16 H.264/AAC con Remotion o FFmpeg/Pillow y revisar zonas seguras,
  (5) escribir, humanizar y lintear copys, y (6) empaquetar y publicar vía Meta Instagram Graph API.
---

# Agentic Reels Pipeline — Orquestador de Sistema

Usa este flujo cuando el usuario quiera operar el sistema completo de contenido de `SadiTLM/agentic-reels-studio`.

## Etapa 1: Tendencias e Investigación (`pipeline/01_trends/`)
1. Ejecuta `last30days` con Python 3.12 (`uv run --python 3.12 python skills/last30days/scripts/last30days.py "<tema>" --emit brief`) para recopilar conversaciones y tendencias reales de los últimos 30 días.
2. Usa `skills/ig-viral/SKILL.md` y `skills/ig-viral/swipe.py` para registrar formatos ganadores y ángulos en `pipeline/01_trends/`.

## Etapa 2: Creación de Ideas + Revisión Goldfish (`pipeline/02_ideas/`)
1. Crea una idea nueva:
   ```bash
   python3 scripts/studio.py new-idea --title "<Título>" --topic "<Tema>" --project "<id_en_brand_projects>" --format reel
   ```
2. Genera 3 opciones de gancho usando las 26 fórmulas de `skills/ig-reel/hooks.json` y puntúalas con `skills/ig-reel/hookscore.py` (o `studio.py score-hooks <id>`).
3. Mide el ritmo y duración hablada con `skills/ig-reel/beats.py` (o `studio.py time-script <id>`).
4. **Revisión Goldfish obligatoria**: Lanza un subagente fresco (sin historial previo de la sesión) para auditar la idea en `pipeline/02_ideas/<id>.json` verificando: ¿el gancho promete algo verificable?, ¿la idea aporta valor concreto sin relleno de IA?, ¿cabe en 15–45 segundos? Registra su dictamen con:
   ```bash
   python3 scripts/studio.py review-goldfish <id> --score <0-100> --verdict pass --notes "<hallazgos>"
   ```

## Etapa 3: Compuerta de Aprobación Humana (`pipeline/03_approved/`)
Nunca produzcas el video final ni publiques sin aprobación explícita del usuario. Muestra el resumen (gancho ganador, guion por escenas, veredicto Goldfish) y espera confirmación para ejecutar:
```bash
python3 scripts/studio.py approve <id>
```

## Etapa 4: Producción Local 9:16 (`pipeline/04_production/`)
1. Para Reels animados / texto cinético / presentación de proyectos técnicos: genera `short.json` siguiendo `skills/remotion-shorts-skill/references/short-json.md` y renderiza con `remotion-studio/render.mjs` (primero `--stills`, inspecciona `sheet.jpg` y `cuts.jpg`, luego el MP4).
2. Para clips reales grabados o carruseles 1080x1350: usa `skills/instagram-skill/scripts/reel.py` y `render_slides.py`.
3. Ejecuta las validaciones obligatorias (`studio.py produce <id>` automatiza el pipeline):
   - `skills/instagram-skill/scripts/ig_check.py` (códec H.264/AAC, 9:16, duración, caption <= 2200, <= 5 hashtags).
   - `skills/instagram-skill/scripts/reel.py zones` (verifica que el texto no quede tapado por la UI de Reels: 14% arriba, 35% abajo, 6% lados).
   - `skills/instagram-skill/scripts/preview.py` (genera vista previa HTML de feed + grid 3:4).

## Etapa 5: Copy, Humanización y Empaquetado (`pipeline/05_ready_to_post/`)
1. Redacta el caption siguiendo `brand/voice.md` y `skills/ig-caption/SKILL.md` (los primeros 125 caracteres deben sobrevivir al corte "... más").
2. Valida con `skills/ig-caption/caption.py` y `skills/ig-human/detect.py` (0 slop de IA, 0 em-dashes).
3. Empaqueta el entregable final:
   ```bash
   python3 scripts/studio.py package <id>
   ```

## Etapa 6: Publicación vía Meta Instagram Graph API (`pipeline/06_published/`)
1. Previsualiza y verifica el payload sin enviar nada:
   ```bash
   python3 scripts/ig_publish.py verify pipeline/05_ready_to_post/<id>
   ```
2. Cuando el usuario tenga configurados `IG_USER_ID` e `IG_ACCESS_TOKEN` en `.env` y confirme publicar:
   ```bash
   python3 scripts/ig_publish.py publish-reel pipeline/05_ready_to_post/<id>
   ```
3. Tras publicar, sincroniza la landing page si el Reel o proyecto debe mostrarse públicamente:
   ```bash
   python3 scripts/studio.py sync-site
   ```
