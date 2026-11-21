#!/usr/bin/env python3
"""Agentic Reels Studio — End-to-End Content Pipeline CLI.

Manages the 6-stage workflow for Instagram Reels & Carousels:
  01_trends       -> Trend discovery (last30days + ig-viral)
  02_ideas        -> Ideation, hook scoring, script timing, Goldfish review
  03_approved     -> Human-approved ideas cleared for production
  04_production   -> Rendered 9:16 MP4 / 4:5 slides, covers, safe zones, linted copy
  05_ready_to_post-> Verified post bundles ready for Meta Graph API or manual upload
  06_published    -> Published log & audit data

Stdlib only (delegates media rendering/checks to installed skill scripts).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline"
SKILLS = ROOT / "skills"
BRAND = ROOT / "brand"
REMOTION_STUDIO = ROOT / "remotion-studio"
SITE_DATA = ROOT / "site" / "data"

STAGES = {
    "trends": PIPELINE / "01_trends",
    "ideas": PIPELINE / "02_ideas",
    "approved": PIPELINE / "03_approved",
    "production": PIPELINE / "04_production",
    "ready": PIPELINE / "05_ready_to_post",
    "published": PIPELINE / "06_published",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "reel-idea"


def find_idea(idea_id: str) -> tuple[str, Path]:
    """Locate an idea JSON across ideas/approved/production/ready."""
    for stage in ("ideas", "approved"):
        candidate = STAGES[stage] / f"{idea_id}.json"
        if candidate.exists():
            return stage, candidate
    for stage in ("production", "ready"):
        candidate = STAGES[stage] / idea_id / "idea.json"
        if candidate.exists():
            return stage, candidate
    sys.exit(f"Error: idea '{idea_id}' not found in pipeline.")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_json_tool(cmd: list[str], stdin_text: str | None = None) -> dict:
    proc = subprocess.run(
        cmd,
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if proc.returncode not in (0, 1, 2):
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError(f"Empty JSON output from {' '.join(cmd)}: {proc.stderr}")
    return json.loads(out)


def cmd_status(_args: argparse.Namespace) -> int:
    print("\nAGENTIC REELS STUDIO — PIPELINE STATUS")
    print("=" * 64)
    counts = {}
    for key, folder in STAGES.items():
        if key in ("ideas", "approved"):
            items = sorted(p.stem for p in folder.glob("*.json"))
        elif key in ("production", "ready"):
            items = sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
        elif key == "trends":
            items = sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
        else:
            posts_file = folder / "posts.json"
            items = [f"{len(load_json(posts_file).get('posts', []))} logged post(s)"] if posts_file.exists() else []
        counts[key] = len(items)
        label = folder.name
        summary = ", ".join(items[:6]) if items else "(empty)"
        if len(items) > 6:
            summary += f" (+{len(items) - 6} more)"
        print(f"  {label:<18} [{len(items):>2}]  {summary}")
    print("=" * 64)
    return 0


def cmd_trends(args: argparse.Namespace) -> int:
    """Run last30days research using uv Python 3.12 and archive in pipeline/01_trends/."""
    script = SKILLS / "last30days" / "scripts" / "last30days.py"
    if not script.exists():
        sys.exit(f"Missing trend script: {script}")
    out_file = STAGES["trends"] / f"{datetime.now().strftime('%Y-%m-%d')}_{slugify(args.topic)}.md"
    cmd = [
        "uv", "run", "--python", "3.12", "python", str(script),
        args.topic, "--emit", "md", "--quick" if args.quick else "--search",
    ]
    if args.quick:
        cmd = [
            "uv", "run", "--python", "3.12", "python", str(script),
            args.topic, "--emit", "md", "--quick", "--web-backend", "keyless",
        ]
    else:
        cmd = [
            "uv", "run", "--python", "3.12", "python", str(script),
            args.topic, "--emit", "md", "--web-backend", "keyless",
        ]
    print(f"Running trend scan for '{args.topic}'...")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=180)
    content = proc.stdout.strip() or proc.stderr.strip()
    if proc.returncode != 0 and not proc.stdout.strip():
        sys.exit(f"Trend scan failed:\n{proc.stderr}")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content + "\n", encoding="utf-8")
    print(f"Saved trend brief -> {out_file.relative_to(ROOT)}")
    return 0


def cmd_new_idea(args: argparse.Namespace) -> int:
    idea_id = args.id or f"{datetime.now().strftime('%Y%m%d')}-{slugify(args.title)}"
    target = STAGES["ideas"] / f"{idea_id}.json"
    if target.exists() and not args.force:
        sys.exit(f"Idea '{idea_id}' already exists at {target}. Use --force to overwrite.")

    projects_data = load_json(BRAND / "projects.json") if (BRAND / "projects.json").exists() else {"projects": []}
    project_meta = next((p for p in projects_data.get("projects", []) if p["id"] == args.project), None)
    handle = projects_data.get("brand", {}).get("handle", "@saditlm")

    hooks = args.hooks or [
        f"Nadie te dice por qué tus agentes fallan antes de escribir código.",
        f"Cómo {args.title.lower()} en 3 pasos desde la terminal.",
        f"Perdí 4 horas revisando código IA hasta usar este flujo.",
    ]

    idea = {
        "id": idea_id,
        "title": args.title,
        "topic": args.topic,
        "format": args.format,
        "project_ref": args.project,
        "handle": handle,
        "created_at": utc_now(),
        "status": "idea",
        "hooks": [{"text": h, "score": None, "verdict": None} for h in hooks],
        "selected_hook_index": 0,
        "spoken_script": args.script or "",
        "caption": args.caption or "",
        "keywords": [k.strip() for k in (args.keywords or "").split(",") if k.strip()],
        "short_spec": {
            "theme": {
                "bg": "#0E1014",
                "fg": "#F5F3EE",
                "accent": "#E05A36",
                "accentText": "#FFFFFF",
                "font": "Inter",
                "uppercase": False,
            },
            "footer": f"Repo: {project_meta['repo']}" if project_meta else "SadiTLM · Josué D.",
            "handle": handle,
            "scenes": [],
        },
        "goldfish_review": {
            "status": "pending",
            "score": None,
            "verdict": None,
            "notes": "",
            "reviewed_at": None,
        },
        "approval": {
            "approved": False,
            "approved_by": None,
            "approved_at": None,
        },
    }
    save_json(target, idea)
    md_path = STAGES["ideas"] / f"{idea_id}.md"
    md_path.write_text(
        f"# {args.title}\n\n"
        f"- **ID:** `{idea_id}`\n"
        f"- **Formato:** `{args.format}`\n"
        f"- **Proyecto:** `{args.project or 'general'}`\n"
        f"- **Tema:** {args.topic}\n\n"
        f"## Ganchos candidatos\n"
        + "\n".join(f"- {h}" for h in hooks)
        + "\n",
        encoding="utf-8",
    )
    print(f"Created idea -> {target.relative_to(ROOT)}")
    return 0


def cmd_score_hooks(args: argparse.Namespace) -> int:
    stage, path = find_idea(args.idea_id)
    idea = load_json(path)
    hookscore = SKILLS / "ig-reel" / "hookscore.py"

    scored = []
    for item in idea.get("hooks", []):
        text = item["text"] if isinstance(item, dict) else str(item)
        res = run_json_tool(["python3", str(hookscore), "--hook", text, "--json"])
        scored.append({
            "text": text,
            "score": res["score"],
            "verdict": res["verdict"],
            "weakest": res["weakest"],
            "flags": res.get("flags", []),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    idea["hooks"] = scored
    idea["selected_hook_index"] = 0
    save_json(path, idea)

    print(f"\nHOOK SCORES ({args.idea_id} in {stage}):")
    for idx, h in enumerate(scored):
        marker = "->" if idx == 0 else "  "
        print(f"  {marker} [{h['score']:>5.1f} {h['verdict']:<6}] (weakest: {h['weakest']}) {h['text']}")
    return 0


def cmd_time_script(args: argparse.Namespace) -> int:
    _, path = find_idea(args.idea_id)
    idea = load_json(path)
    script_text = idea.get("spoken_script", "").strip()
    if not script_text:
        sys.exit(f"Error: 'spoken_script' is empty in {path}.")
    beats = SKILLS / "ig-reel" / "beats.py"
    res = run_json_tool(
        ["python3", str(beats), "-", "--target", str(args.target), "--json"],
        stdin_text=script_text,
    )
    idea["beat_timing"] = {
        "total_seconds": res["total_seconds"],
        "total_words": res["total_words"],
        "target_seconds": res["target"],
        "beats_count": len(res["beats"]),
        "notes": res.get("notes", []),
    }
    save_json(path, idea)
    print(f"Script timing: {res['total_seconds']}s ({res['total_words']} words, {len(res['beats'])} beats)")
    for note in res.get("notes", []):
        print(f"  - {note}")
    return 0


def cmd_review_goldfish(args: argparse.Namespace) -> int:
    stage, path = find_idea(args.idea_id)
    if stage != "ideas":
        sys.exit(f"Error: idea '{args.idea_id}' is in '{stage}', expected 'ideas'.")
    idea = load_json(path)
    idea["goldfish_review"] = {
        "status": "reviewed",
        "score": args.score,
        "verdict": args.verdict,
        "notes": args.notes,
        "reviewed_at": utc_now(),
    }
    save_json(path, idea)
    print(f"Recorded Goldfish review for '{args.idea_id}': {args.verdict.upper()} ({args.score}/100)")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    stage, path = find_idea(args.idea_id)
    if stage != "ideas":
        sys.exit(f"Error: idea '{args.idea_id}' is in '{stage}', expected 'ideas'.")
    idea = load_json(path)
    gr = idea.get("goldfish_review", {})
    if not args.skip_goldfish and gr.get("verdict") != "pass":
        sys.exit(
            f"Approval blocked: Goldfish review verdict is '{gr.get('verdict')}' (expected 'pass'). "
            f"Run review-goldfish first or pass --skip-goldfish explicitly."
        )
    idea["status"] = "approved"
    idea["approval"] = {
        "approved": True,
        "approved_by": args.by,
        "approved_at": utc_now(),
    }
    dst_json = STAGES["approved"] / f"{args.idea_id}.json"
    save_json(dst_json, idea)
    path.unlink()

    src_md = STAGES["ideas"] / f"{args.idea_id}.md"
    if src_md.exists():
        shutil.move(str(src_md), str(STAGES["approved"] / f"{args.idea_id}.md"))

    print(f"Approved '{args.idea_id}' -> {dst_json.relative_to(ROOT)}")
    return 0


def cmd_lint_copy(args: argparse.Namespace) -> int:
    _, path = find_idea(args.idea_id)
    idea = load_json(path)
    caption = idea.get("caption", "").strip()
    if not caption:
        sys.exit(f"Error: 'caption' is empty in {path}.")

    humanize_py = SKILLS / "ig-human" / "humanize.py"
    detect_py = SKILLS / "ig-human" / "detect.py"
    caption_py = SKILLS / "ig-caption" / "caption.py"

    if args.fix:
        proc = subprocess.run(
            ["python3", str(humanize_py), "-"],
            input=caption,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            caption = proc.stdout.strip()
            idea["caption"] = caption

    detect_res = run_json_tool(["python3", str(detect_py), "-", "--json"], stdin_text=caption)
    kw_arg = ",".join(idea.get("keywords", []))
    cap_cmd = ["python3", str(caption_py), "-", "--json"]
    if kw_arg:
        cap_cmd.extend(["--keywords", kw_arg])
    cap_res = run_json_tool(cap_cmd, stdin_text=caption)

    idea["copy_audit"] = {
        "human_score": detect_res["human_score"],
        "human_verdict": detect_res["verdict"],
        "caption_verdict": cap_res["verdict"],
        "caption_chars": cap_res["characters"],
        "hashtags": cap_res["hashtags"],
        "visible_125": cap_res["visible"],
        "audited_at": utc_now(),
    }
    save_json(path, idea)

    print(f"\nCOPY AUDIT ({args.idea_id}):")
    print(f"  Humanizer : {detect_res['human_score']}/100 ({detect_res['verdict']})")
    print(f"  Caption   : {cap_res['characters']}/2200 chars, {len(cap_res['hashtags'])} tags ({cap_res['verdict']})")
    print(f"  125-fold  : {cap_res['visible']!r}")
    for chk in cap_res["checks"]:
        if chk["status"] != "PASS":
            print(f"    [{chk['status']}] {chk['check']}: {chk['detail']}")
    return 0


def cmd_produce(args: argparse.Namespace) -> int:
    stage, path = find_idea(args.idea_id)
    if stage not in ("approved", "production"):
        sys.exit(f"Error: '{args.idea_id}' must be approved first (currently in '{stage}').")
    idea = load_json(path)

    prod_dir = STAGES["production"] / args.idea_id
    prod_dir.mkdir(parents=True, exist_ok=True)
    short_json_path = prod_dir / "short.json"

    short_spec = json.loads(json.dumps(idea.get("short_spec", {})))
    if not short_spec.get("scenes"):
        sys.exit("Error: 'short_spec.scenes' is empty; add scenes before producing.")

    def _resolve_asset(rel_or_abs: str | None) -> str | None:
        if not rel_or_abs or rel_or_abs.startswith(("http://", "https://")):
            return rel_or_abs
        p = Path(rel_or_abs)
        if p.is_absolute():
            return str(p)
        from_root = (ROOT / p).resolve()
        if from_root.exists():
            return os.path.relpath(from_root, prod_dir)
        return rel_or_abs

    if short_spec.get("background"):
        short_spec["background"] = _resolve_asset(short_spec["background"])
    if isinstance(short_spec.get("music"), dict) and short_spec["music"].get("src"):
        short_spec["music"]["src"] = _resolve_asset(short_spec["music"]["src"])
    if isinstance(short_spec.get("chibi"), dict) and isinstance(short_spec["chibi"].get("poses"), list):
        short_spec["chibi"]["poses"] = [_resolve_asset(x) for x in short_spec["chibi"]["poses"]]
    for sc in short_spec.get("scenes", []):
        if sc.get("image"):
            sc["image"] = _resolve_asset(sc["image"])

    save_json(short_json_path, short_spec)

    render_mjs = REMOTION_STUDIO / "render.mjs"
    if not render_mjs.exists():
        sys.exit(f"Error: Remotion studio not found at {render_mjs}.")

    # Step 1: Render stills & review sheets first
    stills_cmd = ["node", str(render_mjs), str(short_json_path), "--stills", "--out", str(prod_dir)]
    print("Rendering Remotion review stills & cover...")
    r_stills = subprocess.run(stills_cmd, cwd=str(REMOTION_STUDIO), capture_output=True, text=True)
    print(r_stills.stdout)
    if r_stills.returncode not in (0, 2):
        sys.exit(f"Remotion stills failed ({r_stills.returncode}):\n{r_stills.stderr}")
    if r_stills.returncode == 2 and not args.force:
        sys.exit("Remotion returned warnings (exit 2). Inspect report.json or pass --force.")

    if not args.stills_only:
        video_cmd = ["node", str(render_mjs), str(short_json_path), "--out", str(prod_dir)]
        if args.force:
            video_cmd.append("--force")
        print("Rendering 1080x1920 H.264/AAC MP4 video...")
        r_vid = subprocess.run(video_cmd, cwd=str(REMOTION_STUDIO), capture_output=True, text=True)
        print(r_vid.stdout)
        if r_vid.returncode != 0:
            sys.exit(f"Remotion render failed ({r_vid.returncode}):\n{r_vid.stderr}")

        mp4_src = prod_dir / "short.mp4"
        mp4_dst = prod_dir / "reel.mp4"
        if mp4_src.exists():
            shutil.move(str(mp4_src), str(mp4_dst))

        # Optional Dual-Export Audio Sync (reel_con_audio.mp4 + reel_sin_sonido.mp4 + AUDIO_SYNC.md)
        audio_sync_cfg = idea.get("audio_sync") or {}
        audio_sync_py = ROOT / "scripts" / "audio_sync.py"
        if audio_sync_cfg.get("song") and audio_sync_py.exists() and mp4_dst.exists():
            report_path = prod_dir / "report.json"
            cuts_arg = ""
            if report_path.exists():
                rep = load_json(report_path)
                cuts_arg = ",".join(
                    f"{sc.get('start', 0)}:{sc.get('type', 'cut')} #{i + 1}"
                    for i, sc in enumerate(rep.get("scenes", []))
                )
            sync_cmd = [
                "python3", str(audio_sync_py), "dual-export", str(mp4_dst),
                "--out", str(prod_dir),
                "--song", str(audio_sync_cfg["song"]),
                "--artist", str(audio_sync_cfg.get("artist", "")),
                "--start", str(audio_sync_cfg.get("start_second", 0.0)),
            ]
            if audio_sync_cfg.get("bpm"):
                sync_cmd.extend(["--bpm", str(audio_sync_cfg["bpm"])])
            if audio_sync_cfg.get("ig_query"):
                sync_cmd.extend(["--ig-query", str(audio_sync_cfg["ig_query"])])
            if audio_sync_cfg.get("ref_audio"):
                ref_p = Path(audio_sync_cfg["ref_audio"])
                if not ref_p.is_absolute():
                    ref_p = ROOT / ref_p
                if ref_p.exists():
                    sync_cmd.extend(["--audio", str(ref_p)])
                    if audio_sync_cfg.get("ref_audio_offset_s"):
                        sync_cmd.extend(["--audio-offset", str(audio_sync_cfg["ref_audio_offset_s"])])
            if cuts_arg:
                sync_cmd.extend(["--cuts", cuts_arg])
            sync_res = subprocess.run(sync_cmd, cwd=str(ROOT), capture_output=True, text=True)
            print(sync_res.stdout)
            if sync_res.returncode != 0:
                print(sync_res.stderr)
                sys.exit("audio_sync.py dual-export failed.")

        # Safe-zone verification via instagram-skill/scripts/reel.py
        reel_py = SKILLS / "instagram-skill" / "scripts" / "reel.py"
        if reel_py.exists() and mp4_dst.exists():
            subprocess.run(
                ["python3", str(reel_py), "zones", str(mp4_dst), "--out", str(prod_dir / "zones.jpg")],
                check=False,
                cwd=str(ROOT),
            )

        # Build plan.json and validate via ig_check.py + preview.py
        caption = idea.get("caption", "")
        plan = {
            "brand": {"name": "Josué D. · SadiTLM", "handle": idea.get("handle", "@saditlm")},
            "timezone": "America/Mexico_City",
            "accounts": {
                "main": {
                    "handle": idea.get("handle", "@saditlm"),
                    "timezone": "America/Mexico_City",
                    "times": ["19:00"],
                }
            },
            "posts": [
                {
                    "id": args.idea_id,
                    "format": "reel",
                    "media": ["reel.mp4"],
                    "cover": "cover.jpg",
                    "caption": caption,
                    "targets": [{"account": "main"}],
                }
            ],
        }
        plan_path = prod_dir / "plan.json"
        save_json(plan_path, plan)

        ig_check = SKILLS / "instagram-skill" / "scripts" / "ig_check.py"
        chk = subprocess.run(["python3", str(ig_check), str(plan_path)], cwd=str(prod_dir), capture_output=True, text=True)
        print(chk.stdout)
        if chk.returncode != 0:
            print(chk.stderr)
            sys.exit("ig_check.py failed on produced Reel.")

        preview_py = SKILLS / "instagram-skill" / "scripts" / "preview.py"
        subprocess.run(
            ["python3", str(preview_py), str(plan_path), "--out", str(prod_dir / "preview")],
            cwd=str(prod_dir),
            check=False,
        )

    idea["status"] = "production"
    idea["production"] = {
        "dir": str(prod_dir.relative_to(ROOT)),
        "video": "reel.mp4" if (prod_dir / "reel.mp4").exists() else None,
        "video_with_audio": "reel_con_audio.mp4" if (prod_dir / "reel_con_audio.mp4").exists() else None,
        "video_without_audio": "reel_sin_sonido.mp4" if (prod_dir / "reel_sin_sonido.mp4").exists() else None,
        "audio_sync_guide": "AUDIO_SYNC.md" if (prod_dir / "AUDIO_SYNC.md").exists() else None,
        "cover": "cover.jpg" if (prod_dir / "cover.jpg").exists() else None,
        "sheet": "sheet.jpg" if (prod_dir / "sheet.jpg").exists() else None,
        "zones": "zones.jpg" if (prod_dir / "zones.jpg").exists() else None,
        "produced_at": utc_now(),
    }
    save_json(prod_dir / "idea.json", idea)
    if stage == "approved" and path.exists():
        path.unlink()
        approved_md = STAGES["approved"] / f"{args.idea_id}.md"
        if approved_md.exists():
            shutil.move(str(approved_md), str(prod_dir / "brief.md"))

    print(f"Production complete -> {prod_dir.relative_to(ROOT)}")
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    stage, path = find_idea(args.idea_id)
    if stage != "production":
        sys.exit(f"Error: '{args.idea_id}' must be in 'production' before packaging (currently in '{stage}').")
    prod_dir = path.parent
    idea = load_json(path)

    for required in ("reel.mp4", "cover.jpg", "plan.json"):
        if not (prod_dir / required).exists():
            sys.exit(f"Missing required artifact in production: {required}")

    bundle_dir = STAGES["ready"] / args.idea_id
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    shutil.copytree(prod_dir, bundle_dir)

    caption_txt = bundle_dir / "caption.txt"
    caption_txt.write_text(idea.get("caption", "").strip() + "\n", encoding="utf-8")

    audio_sync_meta = load_json(bundle_dir / "audio_sync.json") if (bundle_dir / "audio_sync.json").exists() else None
    manifest = {
        "id": idea["id"],
        "title": idea["title"],
        "format": idea["format"],
        "project_ref": idea.get("project_ref"),
        "handle": idea.get("handle", "@saditlm"),
        "video_file": "reel.mp4",
        "video_with_audio": "reel_con_audio.mp4" if (bundle_dir / "reel_con_audio.mp4").exists() else None,
        "video_without_audio": "reel_sin_sonido.mp4" if (bundle_dir / "reel_sin_sonido.mp4").exists() else None,
        "audio_sync_guide": "AUDIO_SYNC.md" if (bundle_dir / "AUDIO_SYNC.md").exists() else None,
        "audio_sync": audio_sync_meta,
        "cover_file": "cover.jpg",
        "caption_file": "caption.txt",
        "caption": idea.get("caption", ""),
        "share_to_feed": True,
        "packaged_at": utc_now(),
        "approved": bool(idea.get("approval", {}).get("approved")),
        "copy_audit": idea.get("copy_audit", {}),
        "goldfish_review": idea.get("goldfish_review", {}),
    }
    save_json(bundle_dir / "post_manifest.json", manifest)
    idea["status"] = "ready_to_post"
    save_json(bundle_dir / "idea.json", idea)
    shutil.rmtree(prod_dir)

    print(f"Packaged ready-to-post bundle -> {bundle_dir.relative_to(ROOT)}")
    return 0


def cmd_sync_site(_args: argparse.Namespace) -> int:
    """Export projects, pipeline counters, and produced showcase Reels into site/data/."""
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    site_media = ROOT / "site" / "assets" / "reels"
    site_media.mkdir(parents=True, exist_ok=True)

    projects = load_json(BRAND / "projects.json") if (BRAND / "projects.json").exists() else {}
    reels = []

    for stage in ("ready", "production"):
        for bundle in sorted(STAGES[stage].iterdir()):
            if not bundle.is_dir() or bundle.name.startswith("."):
                continue
            idea_file = bundle / "idea.json"
            if not idea_file.exists():
                continue
            idea = load_json(idea_file)
            mp4 = bundle / "reel.mp4"
            cover = bundle / "cover.jpg"
            entry = {
                "id": idea["id"],
                "title": idea["title"],
                "topic": idea.get("topic", ""),
                "project_ref": idea.get("project_ref", ""),
                "status": idea.get("status", stage),
                "hook": (idea.get("hooks") or [{}])[0].get("text", ""),
                "hook_score": (idea.get("hooks") or [{}])[0].get("score"),
                "goldfish_score": idea.get("goldfish_review", {}).get("score"),
                "duration_seconds": idea.get("beat_timing", {}).get("total_seconds"),
                "caption": idea.get("caption", ""),
                "video_url": None,
                "cover_url": None,
            }
            if mp4.exists():
                dst_mp4 = site_media / f"{idea['id']}.mp4"
                shutil.copy2(mp4, dst_mp4)
                entry["video_url"] = f"assets/reels/{idea['id']}.mp4"
            if cover.exists():
                dst_cov = site_media / f"{idea['id']}-cover.jpg"
                shutil.copy2(cover, dst_cov)
                entry["cover_url"] = f"assets/reels/{idea['id']}-cover.jpg"
            reels.append(entry)

    payload = {
        "generated_at": utc_now(),
        "brand": projects.get("brand", {}),
        "projects": projects.get("projects", []),
        "showcase_reels": reels,
    }
    save_json(SITE_DATA / "portfolio.json", payload)
    print(f"Synced portfolio data -> {(SITE_DATA / 'portfolio.json').relative_to(ROOT)} ({len(reels)} reel(s))")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agentic Reels Studio Pipeline CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current pipeline status across all 6 stages")

    p_tr = sub.add_parser("trends", help="Run last30days trend research and save brief")
    p_tr.add_argument("topic", help="Topic to research")
    p_tr.add_argument("--quick", action="store_true", help="Faster trend scan")

    p_new = sub.add_parser("new-idea", help="Create a new content idea in pipeline/02_ideas/")
    p_new.add_argument("--id", help="Optional custom slug ID")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--topic", required=True)
    p_new.add_argument("--project", default="agentic-reels-studio")
    p_new.add_argument("--format", default="reel", choices=["reel", "carousel", "story"])
    p_new.add_argument("--hooks", nargs="*", help="Candidate hook lines")
    p_new.add_argument("--script", default="")
    p_new.add_argument("--caption", default="")
    p_new.add_argument("--keywords", default="")
    p_new.add_argument("--force", action="store_true")

    p_sh = sub.add_parser("score-hooks", help="Score candidate hooks using hookscore.py")
    p_sh.add_argument("idea_id")

    p_ts = sub.add_parser("time-script", help="Measure script duration and beats using beats.py")
    p_ts.add_argument("idea_id")
    p_ts.add_argument("--target", type=float, default=30.0)

    p_gf = sub.add_parser("review-goldfish", help="Record independent zero-context Goldfish review")
    p_gf.add_argument("idea_id")
    p_gf.add_argument("--score", type=int, required=True)
    p_gf.add_argument("--verdict", required=True, choices=["pass", "revise", "reject"])
    p_gf.add_argument("--notes", required=True)

    p_ap = sub.add_parser("approve", help="Approve idea and promote to pipeline/03_approved/")
    p_ap.add_argument("idea_id")
    p_ap.add_argument("--by", default="Josué D.")
    p_ap.add_argument("--skip-goldfish", action="store_true")

    p_lc = sub.add_parser("lint-copy", help="Humanize and lint Instagram caption")
    p_lc.add_argument("idea_id")
    p_lc.add_argument("--fix", action="store_true", help="Apply automatic humanize.py cleanup")

    p_pr = sub.add_parser("produce", help="Render 9:16 Reel, check safe zones, and validate specs")
    p_pr.add_argument("idea_id")
    p_pr.add_argument("--stills-only", action="store_true")
    p_pr.add_argument("--force", action="store_true")

    p_pk = sub.add_parser("package", help="Package verified production artifacts into 05_ready_to_post/")
    p_pk.add_argument("idea_id")

    sub.add_parser("sync-site", help="Sync projects & rendered Reels into site/data/portfolio.json")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "status": cmd_status,
        "trends": cmd_trends,
        "new-idea": cmd_new_idea,
        "score-hooks": cmd_score_hooks,
        "time-script": cmd_time_script,
        "review-goldfish": cmd_review_goldfish,
        "approve": cmd_approve,
        "lint-copy": cmd_lint_copy,
        "produce": cmd_produce,
        "package": cmd_package,
        "sync-site": cmd_sync_site,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
