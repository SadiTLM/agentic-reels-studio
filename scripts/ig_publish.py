#!/usr/bin/env python3
"""Official Meta Instagram Graph API Publisher & Bundle Verifier.

Supports:
  - Bundle verification (--verify / verify subcommand) without any API credentials
  - Checking 24-hour publishing rate limit (check-limit)
  - Publishing Reels via public HTTPS video_url OR direct local binary upload
    using Meta's Resumable Upload protocol (upload_type=resumable -> rupload.facebook.com)
  - Container status_code polling (IN_PROGRESS -> FINISHED) before media_publish
  - Archiving published records into pipeline/06_published/posts.json

Environment variables (.env or shell):
  IG_USER_ID         Instagram Professional (Business/Creator) Account ID
  IG_ACCESS_TOKEN    Long-lived User Access Token with instagram_business_content_publish
                     (or instagram_content_publish on graph.facebook.com)
  IG_API_HOST        graph.instagram.com (default) or graph.facebook.com
  IG_GRAPH_VERSION   v25.0 (default)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_LOG = ROOT / "pipeline" / "06_published" / "posts.json"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_bundle(bundle_dir: Path) -> tuple[dict, Path, Path | None, str]:
    manifest_path = bundle_dir / "post_manifest.json"
    if not manifest_path.exists():
        sys.exit(f"Error: post_manifest.json not found in {bundle_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    video_path = bundle_dir / manifest.get("video_file", "reel.mp4")
    if not video_path.exists():
        sys.exit(f"Error: video file missing: {video_path}")
    cover_name = manifest.get("cover_file")
    cover_path = (bundle_dir / cover_name) if cover_name and (bundle_dir / cover_name).exists() else None
    caption = manifest.get("caption", "")
    if not caption and (bundle_dir / "caption.txt").exists():
        caption = (bundle_dir / "caption.txt").read_text(encoding="utf-8").strip()
    return manifest, video_path, cover_path, caption


def probe_mp4(video_path: Path) -> dict:
    if not shutil.which("ffprobe"):
        sys.exit("Error: ffprobe is required to validate MP4 specs.")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v_stream:
        sys.exit(f"Error: no video stream in {video_path}")
    duration = float(info.get("format", {}).get("duration", 0.0))
    return {
        "width": int(v_stream.get("width", 0)),
        "height": int(v_stream.get("height", 0)),
        "vcodec": v_stream.get("codec_name"),
        "pix_fmt": v_stream.get("pix_fmt"),
        "acodec": a_stream.get("codec_name") if a_stream else None,
        "duration_s": round(duration, 2),
        "bytes": video_path.stat().st_size,
    }


def verify_bundle(bundle_dir: Path) -> tuple[dict, dict]:
    manifest, video_path, cover_path, caption = load_bundle(bundle_dir)
    probe = probe_mp4(video_path)
    errors = []
    if probe["vcodec"] not in ("h264", "hevc"):
        errors.append(f"video codec '{probe['vcodec']}' must be h264 or hevc")
    if probe["acodec"] and probe["acodec"] != "aac":
        errors.append(f"audio codec '{probe['acodec']}' must be aac")
    if probe["duration_s"] < 3 or probe["duration_s"] > 900:
        errors.append(f"duration {probe['duration_s']}s out of Reel range (3s-900s)")
    if probe["bytes"] > 300 * 1024 * 1024:
        errors.append(f"file size {probe['bytes']} exceeds 300MB limit")
    if len(caption) > 2200:
        errors.append(f"caption length {len(caption)} exceeds 2200 chars")
    hashtags = [w for w in caption.split() if w.startswith("#")]
    if len(hashtags) > 5:
        errors.append(f"{len(hashtags)} hashtags exceeds Instagram limit of 5")
    if not manifest.get("approved"):
        errors.append("bundle is not marked approved=true")

    if errors:
        sys.exit("Verification FAILED:\n  - " + "\n  - ".join(errors))

    print("VERIFICATION PASSED")
    print(f"  ID        : {manifest.get('id')}")
    print(f"  Video     : {video_path.name} ({probe['width']}x{probe['height']}, {probe['vcodec']}/{probe['acodec']}, {probe['duration_s']}s, {probe['bytes']} bytes)")
    print(f"  Cover     : {cover_path.name if cover_path else 'none (first frame)'}")
    print(f"  Caption   : {len(caption)}/2200 chars, {len(hashtags)} hashtags")
    return manifest, probe


def api_request(method: str, url: str, params: dict | None = None, headers: dict | None = None, data: bytes | None = None) -> dict:
    if params and method == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        body = None
    elif params and data is None:
        body = urllib.parse.urlencode(params).encode("utf-8")
    else:
        body = data

    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Meta Graph API HTTP {e.code} on {url}:\n{err_body}")


def get_credentials() -> tuple[str, str, str, str]:
    load_dotenv(ROOT / ".env")
    user_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    host = os.environ.get("IG_API_HOST", "graph.instagram.com").strip()
    ver = os.environ.get("IG_GRAPH_VERSION", "v25.0").strip()
    if not user_id or not token:
        sys.exit(
            "Missing Meta credentials. Set IG_USER_ID and IG_ACCESS_TOKEN in .env "
            "(see .env.example). Run 'verify' to test bundles offline."
        )
    return user_id, token, host, ver


def cmd_verify(args: argparse.Namespace) -> int:
    verify_bundle(Path(args.bundle).resolve())
    return 0


def cmd_check_limit(_args: argparse.Namespace) -> int:
    user_id, token, host, ver = get_credentials()
    url = f"https://{host}/{ver}/{user_id}/content_publishing_limit"
    res = api_request("GET", url, params={"fields": "config,quota_usage", "access_token": token})
    print(json.dumps(res, indent=2))
    return 0


def cmd_publish_reel(args: argparse.Namespace) -> int:
    bundle_dir = Path(args.bundle).resolve()
    manifest, probe = verify_bundle(bundle_dir)
    _, video_path, _, caption = load_bundle(bundle_dir)

    if args.dry_run:
        mode = f"video_url={args.video_url}" if args.video_url else "upload_type=resumable (rupload.facebook.com)"
        print("\n[DRY RUN] Would execute 3-step Meta Instagram Graph API Reel flow:")
        print(f"  1. POST /{os.environ.get('IG_GRAPH_VERSION', 'v25.0')}/{{IG_USER_ID}}/media ({mode})")
        print(f"     media_type=REELS, share_to_feed=true, caption_chars={len(caption)}")
        print("  2. Poll GET /{container_id}?fields=status_code until FINISHED")
        print("  3. POST /{IG_USER_ID}/media_publish creation_id={container_id}")
        return 0

    user_id, token, host, ver = get_credentials()
    base = f"https://{host}/{ver}"

    # Step 1: Create container
    create_params = {
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true" if manifest.get("share_to_feed", True) else "false",
        "access_token": token,
    }
    if args.video_url:
        create_params["video_url"] = args.video_url
        if args.cover_url:
            create_params["cover_url"] = args.cover_url
        container = api_request("POST", f"{base}/{user_id}/media", params=create_params)
        container_id = container["id"]
    else:
        create_params["upload_type"] = "resumable"
        container = api_request("POST", f"{base}/{user_id}/media", params=create_params)
        container_id = container["id"]
        upload_uri = container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{ver}/{container_id}"
        video_bytes = video_path.read_bytes()
        print(f"Uploading {len(video_bytes)} bytes via Resumable Upload -> {upload_uri}")
        up_res = api_request(
            "POST",
            upload_uri,
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(len(video_bytes)),
                "Content-Type": "application/octet-stream",
            },
            data=video_bytes,
        )
        print("Upload response:", up_res)

    # Step 2: Poll container status_code until FINISHED
    print(f"Polling container {container_id}...")
    wait_s = 10
    for attempt in range(1, 20):
        status = api_request(
            "GET",
            f"{base}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
        )
        code = status.get("status_code")
        print(f"  Attempt {attempt}: status_code={code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"Container processing failed: {status}")
        time.sleep(wait_s)
        wait_s = min(wait_s + 5, 30)
    else:
        sys.exit(f"Timed out waiting for container {container_id} to finish.")

    # Step 3: Publish container
    pub = api_request(
        "POST",
        f"{base}/{user_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
    )
    media_id = pub.get("id")
    print(f"PUBLISHED! Instagram Media ID: {media_id}")

    # Archive to pipeline/06_published/posts.json
    PUBLISHED_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(PUBLISHED_LOG.read_text(encoding="utf-8")) if PUBLISHED_LOG.exists() else {"posts": []}
    log["posts"].append({
        "id": manifest.get("id"),
        "title": manifest.get("title"),
        "media_id": media_id,
        "container_id": container_id,
        "published_at": utc_now(),
        "video_bytes": probe["bytes"],
        "duration_s": probe["duration_s"],
    })
    PUBLISHED_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Meta Instagram Graph API Publisher")
    sub = p.add_subparsers(dest="command", required=True)

    pv = sub.add_parser("verify", help="Verify ready-to-post bundle locally (offline)")
    pv.add_argument("bundle")

    sub.add_parser("check-limit", help="Check 24h Meta Graph API publishing quota")

    pr = sub.add_parser("publish-reel", help="Publish a Reel bundle via Meta Graph API")
    pr.add_argument("bundle")
    pr.add_argument("--video-url", help="Optional public HTTPS URL for video")
    pr.add_argument("--cover-url", help="Optional public HTTPS URL for cover")
    pr.add_argument("--dry-run", action="store_true", help="Validate and print steps without network calls")

    args = p.parse_args()
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "check-limit":
        return cmd_check_limit(args)
    if args.command == "publish-reel":
        return cmd_publish_reel(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
