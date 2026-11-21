const FALLBACK_PORTFOLIO = {
  brand: {
    owner: "Josué D.",
    alias: "SadiTLM",
    email: "contacto@saditlm.dev",
  },
  projects: [
    {
      id: "harness2",
      name: "Harness² — Recursive Agent Harnessing",
      category: "Optimización Agéntica",
      status: "Fork Integrado",
      repo: "https://github.com/SadiTLM/harness2",
      summary:
        "Framework que optimiza automáticamente prompts, herramientas, memoria, guardrails y subagentes alrededor de un modelo sin reentrenar sus pesos.",
      highlights: [
        "Recursión a nivel de tarea (Propose-Probe-Compose) sin respuestas de referencia",
        "Recursión entre tareas que acumula lecciones verificadas",
        "Hasta +11.8 pts en LAB y +11.5 pts en WorkBuddy-Bench",
      ],
      stack: ["Python 3.12", "OpenCode", "Codex", "Vertex AI"],
    },
    {
      id: "elephant-goldfish-model",
      name: "Elephant-Goldfish Model (EGM)",
      category: "Arquitectura & Revisión Spec-Driven",
      status: "Fork Integrado",
      repo: "https://github.com/SadiTLM/elephant-goldfish-model",
      summary:
        "Metodología dual donde un agente Elephant con contexto profundo redacta diseños y subagentes Goldfish sin memoria detectan puntos ciegos antes de programar.",
      highlights: [
        "Separación estricta entre diseño y auditoría sin sesgos",
        "Revisión en 5 etapas con compuertas de decisión humanas",
        "Compatible con Antigravity, Claude Code, Codex y OpenCode",
      ],
      stack: ["Multi-Agent", "Skills", "GitHub Actions", "Astro"],
    },
    {
      id: "agentic-reels-studio",
      name: "Agentic Reels Studio",
      category: "Automatización de Contenido & Growth",
      status: "Activo en Producción",
      repo: "https://github.com/SadiTLM/agentic-reels-studio",
      summary:
        "Sistema completo de punta a punta: minería de tendencias, ideación con score de hooks, revisión Goldfish, render 9:16 con Remotion/FFmpeg y publicación Meta Graph API.",
      highlights: [
        "20 skills especializadas (last30days, ig-reel, remotion-shorts, ig-human)",
        "Renderizado 1080x1920 H.264/AAC local con validación de zonas seguras",
        "Conector oficial Meta Instagram Graph API",
      ],
      stack: ["Python 3.11/3.12", "Remotion", "FFmpeg", "Meta Graph API"],
    },
  ],
  showcase_reels: [],
};

let portfolioData = FALLBACK_PORTFOLIO;
let currentFilter = "all";
let currentReelIndex = 0;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function renderProjects() {
  const grid = document.getElementById("projects-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const list = portfolioData.projects.filter((p) => {
    return currentFilter === "all" || p.category === currentFilter;
  });

  for (const project of list) {
    const card = el("article", "project-card");

    const top = el("div");
    const meta = el("div", "project-meta");
    meta.append(el("span", "project-cat", project.category));
    meta.append(el("span", "project-status", project.status));

    const title = el("h3", "", project.name);
    const summary = el("p", "project-summary", project.summary);

    const ul = el("ul", "project-highlights");
    for (const h of project.highlights || []) {
      ul.append(el("li", "", h));
    }
    top.append(meta, title, summary, ul);

    const bottom = el("div");
    const stackRow = el("div", "stack-row");
    for (const tech of project.stack || []) {
      stackRow.append(el("span", "stack-tag", tech));
    }

    const link = el("a", "project-link", "Ver repositorio en GitHub ->");
    link.href = project.repo;
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    bottom.append(stackRow, link);
    card.append(top, bottom);
    grid.append(card);
  }
}

function renderReels() {
  const selector = document.getElementById("reel-selector");
  const title = document.getElementById("reel-title");
  const hook = document.getElementById("reel-hook");
  const hookScore = document.getElementById("reel-hook-score");
  const gfScore = document.getElementById("reel-goldfish-score");
  const duration = document.getElementById("reel-duration");
  const caption = document.getElementById("reel-caption");
  const player = document.getElementById("reel-player");
  const source = document.getElementById("reel-source");

  const reels = portfolioData.showcase_reels || [];
  selector.innerHTML = "";

  if (!reels.length) {
    title.textContent = "Aún no hay Reels sincronizados";
    hook.textContent =
      "Ejecuta `python3 scripts/studio.py produce <id>` y `python3 scripts/studio.py sync-site` para publicar un Reel aquí.";
    caption.textContent = "Sin caption disponible.";
    return;
  }

  reels.forEach((reel, idx) => {
    const btn = el(
      "button",
      `reel-pill${idx === currentReelIndex ? " active" : ""}`,
      reel.title
    );
    btn.type = "button";
    btn.id = `reel-select-${idx}`;
    btn.addEventListener("click", () => {
      currentReelIndex = idx;
      renderReels();
    });
    selector.append(btn);
  });

  const active = reels[currentReelIndex] || reels[0];
  title.textContent = active.title;
  hook.textContent = active.hook ? `Hook principal: "${active.hook}"` : active.topic;
  hookScore.textContent = active.hook_score != null ? `${active.hook_score}/100` : "N/A";
  gfScore.textContent = active.goldfish_score != null ? `${active.goldfish_score}/100` : "N/A";
  duration.textContent = active.duration_seconds ? `${active.duration_seconds}s` : "9:16";
  caption.textContent = active.caption || "";

  if (active.cover_url) {
    player.poster = active.cover_url;
  }
  if (active.video_url && source.getAttribute("src") !== active.video_url) {
    source.setAttribute("src", active.video_url);
    player.load();
  }
}

function setupFilters() {
  const container = document.getElementById("project-filters");
  if (!container) return;
  container.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".filter-btn");
    if (!btn) return;
    currentFilter = btn.dataset.filter || "all";
    for (const node of container.querySelectorAll(".filter-btn")) {
      node.classList.toggle("active", node === btn);
    }
    renderProjects();
  });
}

function setupForm() {
  const form = document.getElementById("brief-form");
  const copyBtn = document.getElementById("copy-json-btn");
  const status = document.getElementById("form-status");
  if (!form) return;

  function buildPayload() {
    const data = new FormData(form);
    return {
      recipient: "Josué D. (SadiTLM)",
      name: String(data.get("name") || "").trim(),
      contact: String(data.get("contact") || "").trim(),
      scope: String(data.get("scope") || "").trim(),
      notes: String(data.get("notes") || "").trim(),
      created_at: new Date().toISOString(),
    };
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const payload = buildPayload();
    if (!payload.name || !payload.contact || !payload.notes) {
      status.style.color = "#e05a36";
      status.textContent = "Completa nombre, contacto y objetivo antes de enviar.";
      return;
    }
    const email = (portfolioData.brand && portfolioData.brand.email) || "contacto@saditlm.dev";
    const subject = encodeURIComponent(`[SadiTLM Brief] ${payload.scope} - ${payload.name}`);
    const body = encodeURIComponent(
      `Nombre: ${payload.name}\nContacto: ${payload.contact}\nAlcance: ${payload.scope}\n\nObjetivo:\n${payload.notes}`
    );
    status.style.color = "#3fa876";
    status.textContent = "Brief validado. Abriendo cliente de correo...";
    window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
  });

  copyBtn.addEventListener("click", async () => {
    const payload = buildPayload();
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      status.style.color = "#3fa876";
      status.textContent = "Brief JSON copiado al portapapeles.";
    } catch {
      status.style.color = "#e05a36";
      status.textContent = "No se pudo acceder al portapapeles en este navegador.";
    }
  });
}

async function init() {
  const yearEl = document.getElementById("footer-year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  try {
    const resp = await fetch("data/portfolio.json", { cache: "no-store" });
    if (resp.ok) {
      portfolioData = await resp.json();
    }
  } catch {
    // Fallback works cleanly even when opened locally over file://
  }

  const metricProj = document.getElementById("metric-projects");
  if (metricProj && portfolioData.projects) {
    metricProj.textContent = String(portfolioData.projects.length);
  }

  setupFilters();
  setupForm();
  renderProjects();
  renderReels();
}

init();
