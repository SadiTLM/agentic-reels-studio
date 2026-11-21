---
name: fal-ai-video
description: Flujo server-side con fal.ai para generar bailes 2D anime fluidos a 24-30fps (Kling Motion Control v3/v2.6), recorte transparente VP9 alfa (Bria VRMBG 3.0 o FFmpeg chroma-key) y fondos cinematográficos en movimiento (Kling v3 Image-to-Video) listos para componer en Remotion dentro de Agentic Reels Studio.
---

# fal-ai-video — Pipeline 2D Anime Motion-Control & Video Matting

Usa esta skill cuando necesites producir movimiento real fluido (caderas, giros 360°, manos, cabello) manteniendo la estética 2D anime de **Agentic Reels Studio** (`brand/assets/chibi-bandida/`) y componiéndolo con humo, desvanecimientos y glitch en Remotion.

## Reglas de Seguridad y Facturación

1. **Solo servidor / CLI**: `FAL_KEY` vive únicamente en `.env` (ignorado por git, permisos `600`). Nunca lo imprimas ni lo expongas en `site/`, bundles de Remotion, argumentos CLI o logs.
2. **Siempre `--dry-run` antes de gastar créditos**: Inspecciona duración detectada, payload exacto y costo estimado en USD antes de confirmar con el usuario.
3. **Nunca reenviar un trabajo dudoso**: `scripts/fal_studio.py` usa la Queue API (`fal_client.submit`) y guarda inmediatamente `request_id` en `<salida>.job.json`. Si el polling se corta, usa `resume` en lugar de volver a enviar.
4. **HTTP 403**: Si devuelve `"Exhausted balance"`, la integración funciona pero faltan créditos (`https://fal.ai/dashboard/usage-billing/credits`). No reintentar automáticamente.

## Endpoints Verificados

| Paso | Subcomando | Endpoint fal.ai | Costo oficial |
|---|---|---|---|
| Verificar entorno | `check` | *(local, 0 llamadas)* | \$0 |
| Copiar baile 2D (Pro v3 + face binding) | `motion-transfer --model v3-pro` | `fal-ai/kling-video/v3/pro/motion-control` | \$0.168 / s |
| Copiar baile 2D (Pro v2.6 económico) | `motion-transfer --model v2.6-pro` | `fal-ai/kling-video/v2.6/pro/motion-control` | \$0.112 / s |
| Copiar baile 2D (Standard v2.6 ultra-económico) | `motion-transfer --model v2.6-std` | `fal-ai/kling-video/v2.6/standard/motion-control` | \$0.070 / s |
| Copiar baile 2D (Standard v3) | `motion-transfer --model v3-std` | `fal-ai/kling-video/v3/standard/motion-control` | \$0.126 / s |
| Recorte de video transparente VP9 | `remove-bg-video` | `bria/video/background-removal/v3` | \$0.050 / s |
| Recorte local gratis (pantalla verde) | `chroma-key` | *(FFmpeg local `colorkey` + `despill`)* | \$0 |
| Animar foto de auto (cámara en mano) | `animate-backdrop` | `fal-ai/kling-video/v3/pro/image-to-video` | \$0.112 / s (sin audio) |

## Flujo Recomendado (2D Bandida Bella + Autos Nocturnos)

### 1. Revisar configuración (sin llamadas pagadas)
```bash
python3 scripts/fal_studio.py check
```

### 2. Transferir baile de referencia a 2D anime (primero `--dry-run`)
```bash
python3 scripts/fal_studio.py motion-transfer \
  --character brand/assets/chibi-bandida/pose_01.png \
  --dance /ruta/al/baile_referencia.mp4 \
  --model v3-pro \
  --orientation video \
  --green-screen \
  --out pipeline/04_production/<id>/bandida_dance_raw.mp4 \
  --dry-run
```
*(Quita `--dry-run` únicamente después de confirmar presupuesto con el usuario.)*

### 3. Extraer canal alfa transparente (`.webm` VP9 `yuva420p`)
- **Máxima precisión (Bria VRMBG 3.0, \$0.05/s):**
  ```bash
  python3 scripts/fal_studio.py remove-bg-video \
    --video pipeline/04_production/<id>/bandida_dance_raw.mp4 \
    --bg Transparent --codec webm_vp9 \
    --out pipeline/04_production/<id>/bandida_dance_alpha.webm
  ```
- **Alternativa local gratis (si usaste `--green-screen`):**
  ```bash
  python3 scripts/fal_studio.py chroma-key \
    --video pipeline/04_production/<id>/bandida_dance_raw.mp4 \
    --out pipeline/04_production/<id>/bandida_dance_alpha.webm
  ```

### 4. Componer en Remotion con humo, desvanecimientos, glitch y exportación dual
En el `short_spec` de la idea (`pipeline/02_ideas/<id>.json`), apunta `chibi.video` al `.webm` transparente y activa `glitch: { intensity: 0.72, smoke: true, dissolve: true, scanlines: true, grain: true }`. Después corre `scripts/studio.py produce <id>` para generar `reel_con_audio.mp4`, `reel_sin_sonido.mp4` y `AUDIO_SYNC.md`.
