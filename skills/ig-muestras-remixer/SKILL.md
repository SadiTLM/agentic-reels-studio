---
name: ig-muestras-remixer
description: 'Flujo especializado para producir Reels de alto alcance inspirados en referencias visuales y musicales (Opción A: visuales hipnóticos/partículas/geometría/timeline al beat; Opción B: personajes chibi/anime bailando sobre cortes rápidos con reflejo y VFX de impacto), con exportación dual obligatoria (reel_con_audio.mp4 para revisión + reel_sin_sonido.mp4 + AUDIO_SYNC.md con canción y segundo exacto para audio nativo en Instagram).'
---
# ig-muestras-remixer — Motor Visual A/B + Sincronización Dual de Audio

Usa esta skill cuando el usuario quiera producir Reels de alto impacto visual basados en referencias de estilo (`Muestras`), con sincronización exacta a canciones tendencia de Instagram o personajes caricaturizados ("monas chinas / monos chidos").

## 1. Analizar Audio de Referencia (BPM y Cortes)
```bash
python3 scripts/audio_sync.py analyze <clip_referencia.mp4> --extract-audio tmp_ref.mp3 --json
```
Esto detecta el **BPM real**, el intervalo entre beats y los picos fuertes (`peaks_s`) donde deben caer los cortes o el golpe `"bang!"`.

## 2. Elegir Motor Visual en `short_spec` (`remotion-studio/`)

### Opción A — Alto Alcance Visual + Tech/Agentes
Configura en `short_spec`:
- `"visualMode": "particles"` — Red oscura de partículas y nodos reactivos al BPM (estilo `@sniper600news`).
- `"visualMode": "ellipse"` — Geometría láser hipnótica con cuerdas iridiscentes al beat.
- `"visualMode": "timeline"` — Partículas + barra animada de timeline con playhead y barras de audio al ritmo del BPM (estilo `@cal1star`).
- `"bpm": 115` (o el BPM detectado de la canción) para ajustar cortes al compás.

### Opción B — Caricaturizado / Chibi Anime Dance ("Monas Chinas / Monos Chidos")
1. **Preparar sprites transparentes desde hoja de poses (ej. 2×2):**
   ```bash
   python3 scripts/sprite_prep.py split-sheet sheet.png --cols 2 --rows 2 --inset 0.03 --out brand/assets/mi-chibi
   ```
   Usa flood-fill desde los bordes para conservar ojos blancos, brillo y tenis sin halos, alineando automáticamente todos los pies a la misma línea base.
2. **Opcional — Extraer coreografía de un video de baile real:**
   ```bash
   python3 scripts/sprite_prep.py extract-dance baile_ref.mp4 --fps 3 --max-frames 16 --out /tmp/baile_poses
   ```
   - Para **estilo chibi sobre cortes rápidos** (como `@shotbykusa` / `9mm bang`): usa 4–8 poses limpias en `short_spec.chibi` con `"bangScene"` para activar la pose de impacto + destello radial + reflejo en el suelo.
   - Para **transferencia fluida 30fps de baile completo** (como `@gamstergaming`): usa los keyframes/video con un motor V2V externo con GPU (Viggle AI, Kling Motion Control o ComfyUI OpenPose+AnimateDiff) y luego pásalo por `audio_sync.py dual-export` e `ig_check.py`.
3. **Configurar `chibi` en `short_spec`:**
   ```json
   "backdropDim": 0.28,
   "chibi": {
     "poses": ["../../brand/assets/chibi-racer/pose_01.png", "..."],
     "x": 0.52,
     "y": 0.75,
     "scale": 0.96,
     "bpm": 148,
     "shadow": true,
     "bangScene": 1
   }
   ```

## 3. Exportación Dual Obligatoria (Con Sonido + Sin Sonido + Ficha Canción/Segundo)
Siempre que el usuario suba el audio manualmente en Instagram para aprovechar audios en tendencia:
```bash
python3 scripts/audio_sync.py dual-export pipeline/04_production/<id>/reel.mp4 \
  --out pipeline/04_production/<id> \
  --song "9mm" \
  --artist "Memphis Cult, Groove Dealers, SPLYXER" \
  --start 14.0 \
  --bpm 148 \
  --audio /ruta/al/audio_ref.mp3 \
  --cuts "0.0:Hook,3.6:Bang Drop,7.2:Cambio Escena"
```
Genera 4 archivos:
- `reel_con_audio.mp4` — Revisión local con sonido sincronizado.
- `reel_sin_sonido.mp4` — Video 1080×1920 H.264 con pista AAC silenciosa, listo para subir a IG y elegir la canción nativa.
- `AUDIO_SYNC.md` — Instrucciones exactas (canción, artista, búsqueda en IG, segundo exacto `MM:SS` y mapa de cortes).
- `audio_sync.json` — Metadatos estructurados consumidos por `studio.py package`.

## 4. Guardrails
- Nunca reutilizar video ni marcas de agua de otros creadores; usar fondos propios, procedurales o generados originalmente.
- Nunca auto-aprobar ni auto-publicar sin confirmación explícita del usuario.
- Validar siempre `reel_sin_sonido.mp4` y `reel_con_audio.mp4` con `ig_check.py` y `reel.py zones`.
