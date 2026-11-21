---
name: ig-muestras-remixer
description: 'Flujo especializado para producir Reels limpios, estéticos ("fancy") y sin texto de ventas, inspirados en la carpeta Muestras (personajes chibi/anime originales bailando al beat sobre cortes rápidos de deportivos/escenas con reflejo, speed-ramp RGB y VFX de impacto), con exportación dual obligatoria (reel_con_audio.mp4 + reel_sin_sonido.mp4 + AUDIO_SYNC.md con canción y segundo exacto para audio nativo en Instagram).'
---
# ig-muestras-remixer — Producción Visual Limpia + Sincronización Dual

Usa esta skill para producir Reels orgánicos, limpios y estéticos ("fancy") para crecer seguidores y lucir en portafolio (**sin** CTAs tipo *"Comenta X"*, *"Manda DM"*, cursos ni ganchos de venta).

## 1. Analizar Audio de Referencia (BPM y Golpes Exactos)
```bash
python3 scripts/audio_sync.py analyze <clip_referencia.mp4> --extract-audio /tmp/ref_audio.mp3 --json
```
Identifica el **BPM real**, los cortes exactos al beat y el segundo exacto del impacto (`bang` / drop).

## 2. Modo Cine Limpio (`type: "visual"`, `exactTiming: true`) + Chibi Dance
1. **Preparar sprites transparentes desde hoja de poses (ej. 2×2):**
   ```bash
   python3 scripts/sprite_prep.py split-sheet hoja_poses.png --cols 2 --rows 2 --inset 0.03 --out brand/assets/mi-chibi
   ```
   Flood-fill desde bordes conserva ojos blancos y brillos sin halos, alineando pies en la misma base.
2. **Opcional — Extraer poses de un baile real:**
   ```bash
   python3 scripts/sprite_prep.py extract-dance baile_ref.mp4 --fps 3 --max-frames 16 --out /tmp/baile_poses
   ```
   - Para **chibi sobre cortes rápidos** (estilo `@shotbykusa` / `@sinnerm3` / `@d2_shots`): usa escenas `type: "visual"` sin texto invasivo, `exactTiming: true`, `backdropDim: 0`, transiciones RGB speed-ramp automáticas y `chibi` con `bangScenes` (pose finger-gun + impacto de cristal + camera recoil shake).
   - Para **transferencia fluida 30fps de baile completo** (estilo `@gamstergaming`): conecta un motor V2V con GPU externa (Viggle AI / Kling Motion Control / ComfyUI OpenPose) y pasa el resultado por `audio_sync.py dual-export`.

## 3. Exportación Dual Obligatoria (Con Sonido + Sin Sonido + Canción y Segundo)
```bash
python3 scripts/audio_sync.py dual-export pipeline/04_production/<id>/reel.mp4 \
  --out pipeline/04_production/<id> \
  --song "9mm" \
  --artist "Memphis Cult, Groove Dealers, SPLYXER" \
  --start 0.0 \
  --bpm 155 \
  --audio /tmp/ref35_audio.mp3 \
  --cuts "0.0:Intro GT3 RS,1.85:Drop BMW M4,3.95:BANG #1 Ferrari F8,5.05:Skyline R34,8.05:Drop #2 GT3 RS,9.95:BANG #2 BMW M4,11.15:Final Ferrari F8"
```
Genera:
- `reel_con_audio.mp4` — Revisión local con sonido sincronizado al milisegundo.
- `reel_sin_sonido.mp4` — 1080×1920 H.264 con pista AAC silenciosa para subir a IG y elegir el audio nativo.
- `AUDIO_SYNC.md` + `audio_sync.json` — Canción exacta, artista, búsqueda en IG, segundo exacto y mapa de cortes.

## 4. Guardrails de Estilo (`brand/voice.md`)
- **Cero texto comercial en pantalla:** sin banners gigantes ni frases de venta. Solo visual limpio + firma discreta opcional (`watermark: "saditlm"`).
- **Caption minimalista:** 1 línea corta de vibra/estética + 2–4 hashtags limpios (sin `#viral`, `#fyp`, `#parati`).
- **Activos 100% originales:** nunca reutilizar video ni marcas de agua de otros creadores.
