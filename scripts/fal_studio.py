#!/usr/bin/env python3
"""Server-side fal.ai Video & 2D Motion-Control CLI for Agentic Reels Studio.

Verified fal.ai model endpoints (schemas checked against fal.ai/models/<id>/llms.txt):
  - fal-ai/kling-video/v3/pro/motion-control        ($0.168/s) 2D/anime motion transfer + facial element binding
  - fal-ai/kling-video/v3/standard/motion-control   ($0.126/s) Cost-effective v3 motion transfer
  - fal-ai/kling-video/v2.6/pro/motion-control      ($0.112/s) Complex dance motion transfer
  - bria/video/background-removal/v3                ($0.050/s) Native VP9 alpha-transparent WebM matting
  - fal-ai/kling-video/v3/pro/image-to-video        ($0.112/s audio off / $0.168/s audio on) Moving camera backdrops
  - fal-ai/birefnet/v2                              Image foreground cutout / matting

Security & billing discipline:
  - FAL_KEY is loaded strictly server-side from environment or repo-root .env and never printed or logged.
  - Uses fal's Queue API (`fal_client.submit`) and saves `request_id` to `<out>.job.json` before polling.
  - Never auto-resubmits on ambiguous errors; use `resume` with the saved request_id to avoid double billing.
  - Handles HTTP 403 without retrying (distinguishes 'Exhausted balance' vs account lock reasons).
  - Every billable subcommand supports `--dry-run` to inspect the exact payload and cost estimate safely.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

CREDITS_URL = "https://fal.ai/dashboard/usage-billing/credits"

MOTION_MODELS = {
    "v3-pro": {
        "endpoint": "fal-ai/kling-video/v3/pro/motion-control",
        "price_per_sec": 0.168,
        "supports_elements": True,
        "notes": "Kling v3 Pro Motion Control (max 30s with character_orientation='video', supports @Element1 face binding)",
    },
    "v3-std": {
        "endpoint": "fal-ai/kling-video/v3/standard/motion-control",
        "price_per_sec": 0.126,
        "supports_elements": True,
        "notes": "Kling v3 Standard Motion Control (cost-effective v3, supports @Element1 face binding)",
    },
    "v2.6-pro": {
        "endpoint": "fal-ai/kling-video/v2.6/pro/motion-control",
        "price_per_sec": 0.112,
        "supports_elements": False,
        "notes": "Kling v2.6 Pro Motion Control (ideal for complex dance moves and gestures, max 30s)",
    },
    "v2.6-std": {
        "endpoint": "fal-ai/kling-video/v2.6/standard/motion-control",
        "price_per_sec": 0.07,
        "supports_elements": False,
        "notes": "Kling v2.6 Standard Motion Control (lowest-cost Kling motion transfer, $0.07/s, max 30s)",
    },
}

VIDEO_BG_REMOVE_ENDPOINT = "bria/video/background-removal/v3"
VIDEO_BG_REMOVE_PRICE_PER_SEC = 0.05

I2V_ENDPOINT = "fal-ai/kling-video/v3/pro/image-to-video"
I2V_PRICE_PER_SEC_NO_AUDIO = 0.112
I2V_PRICE_PER_SEC_AUDIO = 0.168

IMAGE_BG_REMOVE_ENDPOINT = "fal-ai/birefnet/v2"

DEFAULT_ANIME_DANCE_PROMPT = (
    "2D cel-shaded Japanese anime girl dancing fluidly matching every hip sway, body turn, and hand gesture "
    "from the reference dance, crisp anime linework, consistent dark school uniform blazer, loosened crimson tie, "
    "pleated skirt, and black leather backpack, smooth 24fps sakuga animation, clean framing"
)

GREEN_SCREEN_PROMPT_SUFFIX = (
    ", solid uniform neon chroma key green studio background (#00FF00), flat even studio lighting, "
    "no background objects, no shadows on background, full body visible from head to shoes"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.exists() or path.is_symlink():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def fal_key_state() -> str:
    load_dotenv()
    try:
        val = os.environ.get("FAL_KEY", "").strip()
    except Exception:
        return "Inaccessible"
    return "Present" if val else "Absent"


def require_fal_client() -> Any:
    load_dotenv()
    if not os.environ.get("FAL_KEY", "").strip():
        sys.exit(
            "Error: FAL_KEY is Absent. Configure FAL_KEY in .env (gitignored, chmod 600) "
            "or obtain one at https://fal.ai/dashboard/keys — never pass the key on the command line."
        )
    try:
        import fal_client  # type: ignore
    except ImportError:
        sys.exit("Error: fal-client is not installed. Run: python3 -m pip install -r requirements.txt")
    return fal_client


def probe_video_duration(path_or_url: str) -> float | None:
    if path_or_url.startswith(("http://", "https://")) or not shutil.which("ffprobe"):
        return None
    p = Path(path_or_url)
    if not p.exists():
        return None
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def resolve_input_media(fal_client: Any, source: str, dry_run: bool) -> str:
    """Return remote URL as-is or upload local file to fal storage when not in dry-run."""
    if source.startswith(("http://", "https://")):
        return source
    p = Path(source).expanduser().resolve()
    if not p.exists():
        sys.exit(f"Error: input file not found: {p}")
    if dry_run:
        return f"<fal-upload:{p.name}>"
    print(f"Uploading {p.name} to fal storage...", file=sys.stderr)
    try:
        return str(fal_client.upload_file(p))
    except Exception as exc:
        handle_fal_http_error(exc, "fal-storage-upload")
        raise


def validate_fal_origin_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed_suffixes = (".fal.media", ".fal.ai", ".fal.run", "fal.media", "fal.ai", "fal.run", "storage.googleapis.com")
    if parsed.scheme != "https" or not any(host == s or host.endswith(s) for s in allowed_suffixes):
        raise ValueError(f"Refusing to download from unexpected output origin: {parsed.scheme}://{host}")


def download_file(url: str, out_path: Path) -> int:
    validate_fal_origin_url(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-reels-studio/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, out_path.open("wb") as f:
        shutil.copyfileobj(resp, f)
    return out_path.stat().st_size


def save_job_record(out_path: Path, record: dict[str, Any]) -> Path:
    job_path = out_path.with_suffix(out_path.suffix + ".job.json")
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return job_path


def handle_fal_http_error(exc: Exception, endpoint: str) -> None:
    resp = getattr(exc, "response", None)
    status_code = getattr(exc, "status_code", None)
    if status_code is None and resp is not None:
        status_code = getattr(resp, "status_code", None)
    detail = ""
    if resp is not None:
        try:
            detail = resp.text.strip()
        except Exception:
            detail = ""
    msg = f"{exc}" + (f" | response: {detail}" if detail and detail not in str(exc) else "")
    if status_code == 403:
        if "exhausted balance" in msg.lower():
            sys.exit(
                f"HTTP 403 from {endpoint}: Exhausted balance. The integration is configured, "
                f"but the fal account needs credits. Top up at {CREDITS_URL} (do not retry until funded)."
            )
        sys.exit(
            f"HTTP 403 from {endpoint} (account/billing/policy block — do not retry or replace key): {msg}\n"
            f"Check credits or account locks at {CREDITS_URL}"
        )
    sys.exit(f"fal API error on {endpoint} (status {status_code}): {msg}")


def submit_and_wait(
    fal_client: Any,
    endpoint: str,
    arguments: dict[str, Any],
    out_path: Path,
    result_key: str = "video",
    poll_interval: float = 4.0,
) -> dict[str, Any]:
    """Submit a queued job, persist request_id immediately, poll until completed, and download output."""
    try:
        handle = fal_client.submit(endpoint, arguments=arguments)
    except Exception as exc:
        handle_fal_http_error(exc, endpoint)

    request_id = str(handle.request_id)
    job_record: dict[str, Any] = {
        "endpoint": endpoint,
        "request_id": request_id,
        "submitted_at": utc_now(),
        "status": "SUBMITTED",
        "output_path": str(out_path),
    }
    job_file = save_job_record(out_path, job_record)
    print(f"Submitted {endpoint} -> request_id={request_id} (saved to {job_file})", file=sys.stderr)
    return poll_and_download(fal_client, endpoint, request_id, out_path, result_key, poll_interval, job_record)


def poll_and_download(
    fal_client: Any,
    endpoint: str,
    request_id: str,
    out_path: Path,
    result_key: str = "video",
    poll_interval: float = 4.0,
    job_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = job_record or {
        "endpoint": endpoint,
        "request_id": request_id,
        "resumed_at": utc_now(),
        "output_path": str(out_path),
    }
    last_state = ""
    try:
        while True:
            st = fal_client.status(endpoint, request_id, with_logs=True)
            state_name = type(st).__name__
            if state_name != last_state:
                print(f"[{request_id}] status={state_name}", file=sys.stderr)
                last_state = state_name
            if isinstance(st, fal_client.Completed):
                break
            time.sleep(poll_interval)
        res = fal_client.result(endpoint, request_id)
    except Exception as exc:
        record["status"] = "POLL_ERROR"
        record["error"] = str(exc)
        save_job_record(out_path, record)
        print(
            f"\nPolling stopped for request_id={request_id}. Do NOT resubmit a duplicate job!\n"
            f"Resume with: python3 scripts/fal_studio.py resume --endpoint {endpoint} "
            f"--request-id {request_id} --out {out_path}",
            file=sys.stderr,
        )
        handle_fal_http_error(exc, endpoint)

    media_obj = res.get(result_key) if isinstance(res, dict) else None
    media_url = media_obj.get("url") if isinstance(media_obj, dict) else None
    if not media_url:
        record["status"] = "COMPLETED_NO_URL"
        record["raw_keys"] = list(res.keys()) if isinstance(res, dict) else []
        save_job_record(out_path, record)
        sys.exit(f"Error: fal job {request_id} completed without '{result_key}.url' in response.")

    size_bytes = download_file(str(media_url), out_path)
    record.update(
        {
            "status": "COMPLETED",
            "completed_at": utc_now(),
            "output_bytes": size_bytes,
            "content_type": media_obj.get("content_type") if isinstance(media_obj, dict) else None,
            "warning": res.get("warning") if isinstance(res, dict) else None,
        }
    )
    save_job_record(out_path, record)
    return {
        "endpoint": endpoint,
        "request_id": request_id,
        "output": str(out_path),
        "bytes": size_bytes,
        "warning": res.get("warning") if isinstance(res, dict) else None,
    }


def cmd_check(args: argparse.Namespace) -> int:
    try:
        import fal_client  # type: ignore

        sdk_version = getattr(fal_client, "__version__", "installed")
    except ImportError:
        sdk_version = None

    info = {
        "fal_key_state": fal_key_state(),
        "env_file_exists": ENV_FILE.exists(),
        "fal_client_sdk": sdk_version or "missing",
        "credits_url": CREDITS_URL,
        "endpoints": {
            "motion_control": {k: {"endpoint": v["endpoint"], "price_per_sec_usd": v["price_per_sec"]} for k, v in MOTION_MODELS.items()},
            "video_bg_removal": {"endpoint": VIDEO_BG_REMOVE_ENDPOINT, "price_per_sec_usd": VIDEO_BG_REMOVE_PRICE_PER_SEC},
            "image_to_video": {
                "endpoint": I2V_ENDPOINT,
                "price_per_sec_usd_no_audio": I2V_PRICE_PER_SEC_NO_AUDIO,
                "price_per_sec_usd_audio": I2V_PRICE_PER_SEC_AUDIO,
            },
            "image_bg_removal": {"endpoint": IMAGE_BG_REMOVE_ENDPOINT},
        },
        "api_call_made": False,
    }
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print("FAL.AI STUDIO CONFIGURATION")
        print("=" * 60)
        print(f"  FAL_KEY state  : {info['fal_key_state']} (value hidden)")
        print(f"  fal-client SDK : {info['fal_client_sdk']}")
        print(f"  Credits/billing: {CREDITS_URL}")
        print("\nVerified endpoints:")
        for key, spec in MOTION_MODELS.items():
            print(f"  motion [{key:<8}] -> {spec['endpoint']} (${spec['price_per_sec']:.3f}/s)")
        print(f"  video matting     -> {VIDEO_BG_REMOVE_ENDPOINT} (${VIDEO_BG_REMOVE_PRICE_PER_SEC:.3f}/s)")
        print(f"  image-to-video    -> {I2V_ENDPOINT} (${I2V_PRICE_PER_SEC_NO_AUDIO:.3f}/s audio off)")
        print(f"  image matting     -> {IMAGE_BG_REMOVE_ENDPOINT}")
    return 0


def cmd_motion_transfer(args: argparse.Namespace) -> int:
    spec = MOTION_MODELS[args.model]
    endpoint = spec["endpoint"]
    fal_client = None if args.dry_run else require_fal_client()

    if args.face_ref and not spec["supports_elements"]:
        sys.exit(f"Error: --face-ref element binding is only supported on v3 models, not {args.model}.")
    if args.face_ref and args.orientation != "video":
        sys.exit("Error: Kling v3 element binding requires --orientation video.")

    duration = probe_video_duration(args.dance)
    max_dur = 30.0 if args.orientation == "video" else 10.0
    if duration is not None and duration > max_dur + 0.5:
        sys.exit(
            f"Error: reference dance video is {duration:.1f}s, exceeding {max_dur:.0f}s limit "
            f"for character_orientation='{args.orientation}'. Trim it first with ffmpeg."
        )

    image_url = resolve_input_media(fal_client, args.character, args.dry_run)
    video_url = resolve_input_media(fal_client, args.dance, args.dry_run)

    prompt = args.prompt.strip()
    if args.green_screen and "#00FF00" not in prompt:
        prompt = prompt + GREEN_SCREEN_PROMPT_SUFFIX

    arguments: dict[str, Any] = {
        "image_url": image_url,
        "video_url": video_url,
        "character_orientation": args.orientation,
        "keep_original_sound": bool(args.keep_sound),
        "prompt": prompt,
    }
    if args.face_ref:
        face_url = resolve_input_media(fal_client, args.face_ref, args.dry_run)
        arguments["elements"] = [{"frontal_image_url": face_url}]
        if "@Element1" not in arguments["prompt"]:
            arguments["prompt"] = f"@Element1 {arguments['prompt']}"

    est_cost = round(duration * spec["price_per_sec"], 3) if duration is not None else None
    out_path = Path(args.out).resolve()

    if args.dry_run:
        preview = {
            "dry_run": True,
            "endpoint": endpoint,
            "model_alias": args.model,
            "detected_dance_seconds": round(duration, 2) if duration is not None else None,
            "estimated_cost_usd": est_cost,
            "output": str(out_path),
            "arguments": arguments,
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    result = submit_and_wait(fal_client, endpoint, arguments, out_path, result_key="video")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_remove_bg_video(args: argparse.Namespace) -> int:
    fal_client = None if args.dry_run else require_fal_client()
    duration = probe_video_duration(args.video)
    video_url = resolve_input_media(fal_client, args.video, args.dry_run)

    arguments: dict[str, Any] = {
        "video_url": video_url,
        "background_color": args.bg,
        "output_container_and_codec": args.codec,
        "preserve_audio": bool(args.preserve_audio),
        "auto_zoom": bool(args.auto_zoom),
    }
    est_cost = round(duration * VIDEO_BG_REMOVE_PRICE_PER_SEC, 3) if duration is not None else None
    out_path = Path(args.out).resolve()

    if args.dry_run:
        preview = {
            "dry_run": True,
            "endpoint": VIDEO_BG_REMOVE_ENDPOINT,
            "detected_video_seconds": round(duration, 2) if duration is not None else None,
            "estimated_cost_usd": est_cost,
            "output": str(out_path),
            "arguments": arguments,
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    result = submit_and_wait(fal_client, VIDEO_BG_REMOVE_ENDPOINT, arguments, out_path, result_key="video")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_animate_backdrop(args: argparse.Namespace) -> int:
    fal_client = None if args.dry_run else require_fal_client()
    dur_str = str(args.duration)
    if dur_str not in {str(d) for d in range(3, 16)}:
        sys.exit("Error: --duration must be an integer between 3 and 15 seconds.")

    start_image_url = resolve_input_media(fal_client, args.image, args.dry_run)
    arguments: dict[str, Any] = {
        "start_image_url": start_image_url,
        "prompt": args.prompt.strip(),
        "duration": dur_str,
        "generate_audio": bool(args.audio),
        "negative_prompt": args.negative_prompt,
        "cfg_scale": float(args.cfg_scale),
    }
    if args.end_image:
        arguments["end_image_url"] = resolve_input_media(fal_client, args.end_image, args.dry_run)

    rate = I2V_PRICE_PER_SEC_AUDIO if args.audio else I2V_PRICE_PER_SEC_NO_AUDIO
    est_cost = round(int(dur_str) * rate, 3)
    out_path = Path(args.out).resolve()

    if args.dry_run:
        preview = {
            "dry_run": True,
            "endpoint": I2V_ENDPOINT,
            "duration_seconds": int(dur_str),
            "estimated_cost_usd": est_cost,
            "output": str(out_path),
            "arguments": arguments,
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    result = submit_and_wait(fal_client, I2V_ENDPOINT, arguments, out_path, result_key="video")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_chroma_key(args: argparse.Namespace) -> int:
    """Free local FFmpeg chroma-key + despill to VP9 alpha-transparent WebM for Remotion."""
    if not shutil.which("ffmpeg"):
        sys.exit("Error: ffmpeg is required for local chroma-key.")
    src = Path(args.video).resolve()
    if not src.exists():
        sys.exit(f"Error: video file not found: {src}")
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    color = args.color.lstrip("#")
    vf = (
        f"colorkey=0x{color}:{args.similarity:.3f}:{args.blend:.3f},"
        f"despill=type=green:mix=0.55:expand=0.1,"
        f"format=yuva420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-auto-alt-ref",
        "0",
        "-b:v",
        "0",
        "-crf",
        "24",
        "-an",
        str(out_path),
    ]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "command": cmd, "output": str(out_path)}, indent=2))
        return 0

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"FFmpeg chroma-key failed ({proc.returncode}):\n{proc.stderr}")
    print(json.dumps({"output": str(out_path), "bytes": out_path.stat().st_size, "codec": "vp9-yuva420p"}, indent=2))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    fal_client = require_fal_client()
    out_path = Path(args.out).resolve()
    res = poll_and_download(fal_client, args.endpoint, args.request_id, out_path, result_key=args.result_key)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Server-side fal.ai 2D Motion-Control & Video Matting CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Check FAL_KEY state (never prints value), SDK, and verified endpoints")
    p_check.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_check.set_defaults(func=cmd_check)

    p_mt = sub.add_parser("motion-transfer", help="Transfer dance video motion onto a 2D anime character image")
    p_mt.add_argument("--character", required=True, help="Path or URL to 2D character reference image (e.g. Bandida Bella)")
    p_mt.add_argument("--dance", required=True, help="Path or URL to reference dance video (<=30s with video orientation)")
    p_mt.add_argument("--out", required=True, help="Output MP4 file path")
    p_mt.add_argument("--model", choices=list(MOTION_MODELS.keys()), default="v3-pro", help="Motion control model tier")
    p_mt.add_argument("--orientation", choices=["video", "image"], default="video", help="'video' for complex dances (max 30s)")
    p_mt.add_argument("--face-ref", help="Optional facial consistency image for Kling v3 @Element1 binding")
    p_mt.add_argument("--prompt", default=DEFAULT_ANIME_DANCE_PROMPT, help="2D anime motion prompt")
    p_mt.add_argument("--green-screen", action="store_true", help="Request solid #00FF00 chroma background for clean matting")
    p_mt.add_argument("--keep-sound", action="store_true", help="Keep original reference video audio (default off)")
    p_mt.add_argument("--dry-run", action="store_true", help="Print verified payload and cost estimate without calling fal")
    p_mt.set_defaults(func=cmd_motion_transfer)

    p_bg = sub.add_parser("remove-bg-video", help="Remove background from a video into transparent VP9 WebM (Bria VRMBG 3.0)")
    p_bg.add_argument("--video", required=True, help="Path or URL to dance video")
    p_bg.add_argument("--out", required=True, help="Output transparent .webm path")
    p_bg.add_argument(
        "--bg",
        default="Transparent",
        choices=["Transparent", "Black", "White", "Gray", "Red", "Green", "Blue", "Yellow", "Cyan", "Magenta", "Orange"],
    )
    p_bg.add_argument(
        "--codec",
        default="webm_vp9",
        choices=["webm_vp9", "mp4_h264", "mp4_h265", "mov_h265", "mov_proresks", "mkv_vp9", "gif"],
    )
    p_bg.add_argument("--preserve-audio", action="store_true", help="Preserve input audio (default muted for Remotion)")
    p_bg.add_argument("--auto-zoom", action="store_true", help="Crop output tightly around subject")
    p_bg.add_argument("--dry-run", action="store_true", help="Print payload and cost estimate without calling fal")
    p_bg.set_defaults(func=cmd_remove_bg_video)

    p_i2v = sub.add_parser("animate-backdrop", help="Animate a still night car photo into a handheld camera clip (Kling v3 Pro I2V)")
    p_i2v.add_argument("--image", required=True, help="Path or URL to start backdrop image")
    p_i2v.add_argument("--end-image", help="Optional end frame image path or URL")
    p_i2v.add_argument("--out", required=True, help="Output MP4 file path")
    p_i2v.add_argument(
        "--prompt",
        default="Handheld night automotive cinema shot, smooth slow push-in dolly around wet rain-slicked supercar, subtle neon reflections shimmering on asphalt, shallow depth of field, 4K film look",
    )
    p_i2v.add_argument("--negative-prompt", default="blur, distort, text, watermark, and low quality")
    p_i2v.add_argument("--duration", type=int, default=5, help="Clip duration in seconds (3..15)")
    p_i2v.add_argument("--cfg-scale", type=float, default=0.5, help="Prompt adherence 0..1")
    p_i2v.add_argument("--audio", action="store_true", help="Generate native audio ($0.168/s instead of $0.112/s)")
    p_i2v.add_argument("--dry-run", action="store_true", help="Print payload and cost estimate without calling fal")
    p_i2v.set_defaults(func=cmd_animate_backdrop)

    p_ck = sub.add_parser("chroma-key", help="Free local FFmpeg chroma-key + despill to VP9 alpha WebM")
    p_ck.add_argument("--video", required=True, help="Input green-screen MP4")
    p_ck.add_argument("--out", required=True, help="Output alpha-transparent .webm")
    p_ck.add_argument("--color", default="00FF00", help="Hex key color (default 00FF00)")
    p_ck.add_argument("--similarity", type=float, default=0.28, help="Color similarity threshold (0.01..1.0)")
    p_ck.add_argument("--blend", type=float, default=0.10, help="Edge feather blend (0.0..1.0)")
    p_ck.add_argument("--dry-run", action="store_true", help="Print FFmpeg command without executing")
    p_ck.set_defaults(func=cmd_chroma_key)

    p_res = sub.add_parser("resume", help="Resume polling/downloading an existing fal request_id without resubmitting")
    p_res.add_argument("--endpoint", required=True, help="Exact fal endpoint ID")
    p_res.add_argument("--request-id", required=True, help="Saved fal request_id")
    p_res.add_argument("--out", required=True, help="Output file path")
    p_res.add_argument("--result-key", default="video", help="Top-level output field containing {url}")
    p_res.set_defaults(func=cmd_resume)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
