# Agentic Reels Studio — Josué D. (`SadiTLM`)

Sistema automatizado de producción de contenido para Instagram Reels y Carruseles, investigación de tendencias, revisión agéntica **Elephant-Goldfish** y portafolio público de automatizaciones.

---

## Arquitectura del Sistema (6 Etapas)

```
01_trends  ──▶  02_ideas + Goldfish  ──▶  03_approved  ──▶  04_production  ──▶  05_ready_to_post  ──▶  06_published
(last30days     (hookscore + beats +      (Compuerta         (Remotion 9:16      (Bundle validado +    (Meta Graph API +
 + ig-viral)     revisión Goldfish)        humana)            + FFmpeg + zones)   ig-human + caption)   ig-audit)
```

### Skills Instaladas (`skills/`)
- **Orquestador:** `agentic-reels-pipeline`
- **Tendencias:** `last30days` (Reddit, HN, GitHub, X, YouTube, Web) + `ig-viral` (`swipe.py`)
- **Guiones, Hooks y Estrategia IG:** `ig-reel` (26 fórmulas, `hookscore.py`, `beats.py`), `ig-plan`, `ig-carousel`, `ig-story`, `ig-repurpose`, `ig-audit`, `ig-profile`, `ig-comment`, `ig-reply`, `ig-dm`
- **Copy & Humanización:** `ig-caption` (`caption.py`), `ig-human` (`detect.py`, `humanize.py`, `slop.json`), `copywriting`, `content-strategy`, `social`
- **Producción Visual 9:16 & 4:5:** `instagram-skill` (`reel.py`, `render_slides.py`, `ig_check.py`, `preview.py`) + `remotion-shorts-skill` (React/Remotion 1080×1920 H.264/AAC con SFX y zonas seguras)

---

## Uso Rápido

```bash
# 1. Ver el estado del sistema
python3 scripts/studio.py status

# 2. Investigar tendencias (requiere Python 3.12 vía uv)
python3 scripts/studio.py trends "AI agents automation" --quick

# 3. Crear idea, puntuar ganchos y medir ritmo
python3 scripts/studio.py new-idea --title "Mi proyecto" --topic "Agentes" --project harness2
python3 scripts/studio.py score-hooks <idea_id>
python3 scripts/studio.py time-script <idea_id> --target 30

# 4. Revisión Goldfish (subagente sin historial) + Aprobación humana
python3 scripts/studio.py review-goldfish <idea_id> --score 88 --verdict pass --notes "Gancho específico y sin relleno"
python3 scripts/studio.py approve <idea_id>

# 5. Producir video 1080x1920 + portada + zonas seguras + humanizar copy
python3 scripts/studio.py lint-copy <idea_id> --fix
python3 scripts/studio.py produce <idea_id>
python3 scripts/studio.py package <idea_id>

# 6. Verificar o publicar vía Meta Instagram Graph API
python3 scripts/ig_publish.py verify pipeline/05_ready_to_post/<idea_id>
python3 scripts/ig_publish.py publish-reel pipeline/05_ready_to_post/<idea_id> --dry-run

# 7. Sincronizar proyectos y Reels al portafolio web
python3 scripts/studio.py sync-site
```

---

## Configurar Meta Instagram Graph API (Publicación Automática)

1. Convierte tu cuenta de Instagram a **Profesional (Creator o Business)**.
2. Copia `.env.example` a `.env` y agrega `IG_USER_ID` e `IG_ACCESS_TOKEN` con permiso `instagram_business_content_publish` (o agrega esos secretos en GitHub → Settings → Secrets → Actions para usar `.github/workflows/publish-reel.yml`).
3. `scripts/ig_publish.py` soporta tanto URL pública (`--video-url`) como **subida binaria resumable** directa a `rupload.facebook.com`.

---

## Portafolio Público (`site/`)

Página estática funcional diseñada para **Josué D. · SadiTLM** mostrando los proyectos agénticos integrados (`Harness²`, `Elephant-Goldfish Model`, `Agentic Reels Studio`), reproductor de Reels generados por el pipeline, calculadora interactiva de ahorro y formulario funcional de contacto/brief.
