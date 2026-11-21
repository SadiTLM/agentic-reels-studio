#!/usr/bin/env python3
"""Chibi / Cartoon Sprite Prep & Dance Pose Extractor for Agentic Reels Studio.

Supports Option B ("monas chinas / monos chidos" + dance choreography transfer):
  1. `cutout`        — Remove solid/chroma background via border flood-fill (preserves white eyes/highlights).
  2. `split-sheet`   — Split a multi-pose sprite sheet (e.g. 2x2) into foot-aligned transparent PNG poses.
  3. `extract-dance` — Extract timed reference dance keyframes + contact sheet from any MP4 dance video.

Uses stdlib + Pillow + ffmpeg.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _color_dist(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def remove_bg_floodfill(
    img: Image.Image,
    bg_mode: str = "auto",
    tolerance: float = 44.0,
) -> Image.Image:
    """Remove exterior background using 4-neighbor BFS flood-fill from image borders.

    Unlike naive global color keying, flood-fill never eats interior white highlights
    (eyes, hair sheen, sneakers) enclosed by character outlines.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    if bg_mode == "white":
        bg_ref = (255, 255, 255)
    elif bg_mode == "black":
        bg_ref = (0, 0, 0)
    elif bg_mode == "green":
        bg_ref = (0, 255, 0)
    else:
        # Median of 4 corner samples
        corners = [px[1, 1][:3], px[w - 2, 1][:3], px[1, h - 2][:3], px[w - 2, h - 2][:3]]
        bg_ref = tuple(sorted(c[i] for c in corners)[1] for i in range(3))

    visited = bytearray(w * h)
    bg_mask = bytearray(w * h)
    q: collections.deque[tuple[int, int]] = collections.deque()

    def try_seed(x: int, y: int) -> None:
        idx = y * w + x
        if visited[idx]:
            return
        if _color_dist(px[x, y][:3], bg_ref) <= tolerance * 1.15:
            visited[idx] = 1
            bg_mask[idx] = 1
            q.append((x, y))

    for x in range(w):
        try_seed(x, 0)
        try_seed(x, h - 1)
    for y in range(h):
        try_seed(0, y)
        try_seed(w - 1, y)

    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not visited[nidx]:
                    visited[nidx] = 1
                    if _color_dist(px[nx, ny][:3], bg_ref) <= tolerance:
                        bg_mask[nidx] = 1
                        q.append((nx, ny))

    # Apply alpha: clear background pixels & softly feather 1px fringe bordering background
    soft_tol = tolerance * 1.65
    for y in range(h):
        row_off = y * w
        for x in range(w):
            idx = row_off + x
            if bg_mask[idx]:
                r, g, b, _ = px[x, y]
                px[x, y] = (r, g, b, 0)
            else:
                # Check if touching a background pixel for gentle anti-alias defringing
                touches_bg = False
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and bg_mask[ny * w + nx]:
                        touches_bg = True
                        break
                if touches_bg:
                    r, g, b, a = px[x, y]
                    d = _color_dist((r, g, b), bg_ref)
                    if d < soft_tol:
                        new_a = int(a * max(0.0, (d - tolerance * 0.7) / max(1.0, soft_tol - tolerance * 0.7)))
                        px[x, y] = (r, g, b, max(0, min(255, new_a)))

    return rgba


def remove_trapped_white_holes(rgba: Image.Image) -> Image.Image:
    """Clear pure-white background pockets trapped inside hair strands/limbs while protecting face & shirt core."""
    w, h = rgba.size
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    px = rgba.load()
    bx0, by0, bx1, by1 = bbox
    bw, bh = bx1 - bx0, by1 - by0
    prot_x0, prot_x1 = bx0 + bw * 0.34, bx0 + bw * 0.66
    prot_y0, prot_y1 = by0 + bh * 0.18, by0 + bh * 0.57
    visited = bytearray(w * h)
    to_clear: list[tuple[int, int]] = []
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            idx = y * w + x
            if visited[idx]:
                continue
            r, g, b, a = px[x, y]
            if a > 200 and r >= 246 and g >= 246 and b >= 246:
                q: collections.deque[tuple[int, int]] = collections.deque([(x, y)])
                visited[idx] = 1
                comp = []
                in_prot = False
                while q:
                    cx, cy = q.popleft()
                    comp.append((cx, cy))
                    if prot_x0 <= cx <= prot_x1 and prot_y0 <= cy <= prot_y1:
                        in_prot = True
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if bx0 <= nx < bx1 and by0 <= ny < by1:
                            nidx = ny * w + nx
                            if not visited[nidx]:
                                nr, ng, nb, na = px[nx, ny]
                                if na > 150 and nr >= 238 and ng >= 238 and nb >= 238:
                                    visited[nidx] = 1
                                    q.append((nx, ny))
                if not in_prot and len(comp) >= 12:
                    to_clear.extend(comp)
    clear_set = set(to_clear)
    for cx, cy in clear_set:
        r, g, b, _ = px[cx, cy]
        px[cx, cy] = (r, g, b, 0)
    return rgba


def trim_and_pad(rgba: Image.Image, pad: int = 12) -> Image.Image:
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    cropped = rgba.crop(bbox)
    cw, ch = cropped.size
    out = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
    out.paste(cropped, (pad, pad), cropped)
    return out


def cmd_cutout(args: argparse.Namespace) -> int:
    src = Path(args.input)
    dst = Path(args.output)
    if not src.exists():
        sys.exit(f"Error: input image not found: {src}")
    with Image.open(src) as im:
        w, h = im.size
        if args.inset > 0:
            dx, dy = int(w * args.inset), int(h * args.inset)
            im = im.crop((dx, dy, w - dx, h - dy))
        cleaned = remove_bg_floodfill(im, bg_mode=args.bg, tolerance=args.tolerance)
        final = trim_and_pad(cleaned, pad=args.pad)
    dst.parent.mkdir(parents=True, exist_ok=True)
    final.save(dst, "PNG")
    print(f"Saved transparent sprite -> {dst} ({final.width}x{final.height})")
    return 0


def cmd_split_sheet(args: argparse.Namespace) -> int:
    src = Path(args.sheet)
    out_dir = Path(args.out)
    if not src.exists():
        sys.exit(f"Error: sprite sheet not found: {src}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        sw, sh = im.size
        cw = sw / args.cols
        ch = sh / args.rows
        raw_poses: list[Image.Image] = []
        for r in range(args.rows):
            for c in range(args.cols):
                x0 = int(round(c * cw))
                y0 = int(round(r * ch))
                x1 = int(round((c + 1) * cw))
                y1 = int(round((r + 1) * ch))
                cell = im.crop((x0, y0, x1, y1))
                # Trim inset margin so grid divider borders never bleed into cells
                ix = int(cell.width * args.inset)
                iy = int(cell.height * args.inset)
                if ix > 0 or iy > 0:
                    cell = cell.crop((ix, iy, cell.width - ix, cell.height - iy))
                if args.remove_bg:
                    cell = remove_bg_floodfill(cell, bg_mode=args.bg, tolerance=args.tolerance)
                    if args.bg in ("auto", "white"):
                        cell = remove_trapped_white_holes(cell)
                    cell = trim_and_pad(cell, pad=10)
                else:
                    cell = cell.convert("RGBA")
                raw_poses.append(cell)

    # Normalize all poses to identical canvas dimensions with feet bottom-aligned
    max_w = max(p.width for p in raw_poses)
    max_h = max(p.height for p in raw_poses)
    pad = 16
    norm_w, norm_h = max_w + pad * 2, max_h + pad * 2
    saved_paths: list[str] = []

    preview_cols = min(4, len(raw_poses))
    preview_rows = (len(raw_poses) + preview_cols - 1) // preview_cols
    thumb = 320
    preview = Image.new("RGB", (preview_cols * thumb + (preview_cols + 1) * 16, preview_rows * thumb + (preview_rows + 1) * 16), "#12151C")

    for i, pose in enumerate(raw_poses, 1):
        canvas = Image.new("RGBA", (norm_w, norm_h), (0, 0, 0, 0))
        px = (norm_w - pose.width) // 2
        py = norm_h - pad - pose.height  # foot-aligned baseline
        canvas.paste(pose, (px, py), pose)
        out_path = out_dir / f"{args.prefix}_{i:02d}.png"
        canvas.save(out_path, "PNG")
        saved_paths.append(out_path.name)

        # Paste onto dark-checker preview so alpha cleanliness is easy to inspect
        p_copy = canvas.copy()
        p_copy.thumbnail((thumb, thumb), Image.LANCZOS)
        r, c = divmod(i - 1, preview_cols)
        ox = 16 + c * (thumb + 16) + (thumb - p_copy.width) // 2
        oy = 16 + r * (thumb + 16) + (thumb - p_copy.height) // 2
        preview.paste(p_copy, (ox, oy), p_copy)

    preview_path = out_dir / "poses_preview.jpg"
    preview.save(preview_path, "JPEG", quality=90)
    manifest = {
        "source_sheet": str(src),
        "cols": args.cols,
        "rows": args.rows,
        "canvas_size": [norm_w, norm_h],
        "poses": saved_paths,
        "preview": preview_path.name,
    }
    (out_dir / "sprites.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Split {len(saved_paths)} foot-aligned sprites -> {out_dir} ({norm_w}x{norm_h})")
    return 0


def cmd_extract_dance(args: argparse.Namespace) -> int:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        sys.exit("Error: ffmpeg and ffprobe are required.")
    src = Path(args.video)
    out_dir = Path(args.out)
    if not src.exists():
        sys.exit(f"Error: video not found: {src}")
    out_dir.mkdir(parents=True, exist_ok=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(src)],
        capture_output=True, text=True, check=True,
    )
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    total = min(args.max_frames, max(4, int(round(dur * args.fps))))
    frames_meta = []
    thumbs = []

    for i in range(total):
        t = (dur - 0.15) * i / max(1, total - 1) if total > 1 else 0.0
        out_jpg = out_dir / f"dance_{i + 1:02d}_{t:.2f}s.jpg"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{t:.3f}", "-i", str(src),
                "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "3",
                str(out_jpg),
            ],
            check=True,
            capture_output=True,
        )
        frames_meta.append({"index": i + 1, "time_s": round(t, 2), "file": out_jpg.name})
        thumbs.append((t, Image.open(out_jpg).convert("RGB")))

    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    tw, th = 270, 480
    pad, lab = 12, 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (th + lab + pad) + pad), "#101216")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    for idx, (t, im) in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + lab + pad)
        im.thumbnail((tw, th), Image.LANCZOS)
        sheet.paste(im, (x + (tw - im.width) // 2, y))
        draw.text((x + 4, y + th + 4), f"#{idx + 1:02d} @ {t:.2f}s", fill="#FFD60A", font=font)

    sheet_path = out_dir / "dance_poses_sheet.jpg"
    sheet.save(sheet_path, "JPEG", quality=88)
    manifest = {
        "source_video": src.name,
        "duration_s": round(dur, 2),
        "extracted_count": len(frames_meta),
        "sheet": sheet_path.name,
        "frames": frames_meta,
    }
    (out_dir / "dance_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(frames_meta)} dance reference poses -> {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chibi sprite cutout & dance pose extractor")
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("cutout", help="Remove solid background from a single character image")
    pc.add_argument("input")
    pc.add_argument("output")
    pc.add_argument("--bg", default="auto", choices=["auto", "white", "green", "black"])
    pc.add_argument("--tolerance", type=float, default=44.0)
    pc.add_argument("--inset", type=float, default=0.01)
    pc.add_argument("--pad", type=int, default=12)

    ps = sub.add_parser("split-sheet", help="Split grid sprite sheet into foot-aligned transparent PNG poses")
    ps.add_argument("sheet")
    ps.add_argument("--cols", type=int, default=2)
    ps.add_argument("--rows", type=int, default=2)
    ps.add_argument("--out", required=True)
    ps.add_argument("--prefix", default="pose")
    ps.add_argument("--bg", default="auto", choices=["auto", "white", "green", "black"])
    ps.add_argument("--tolerance", type=float, default=44.0)
    ps.add_argument("--inset", type=float, default=0.025, help="Fraction to trim from each cell border")
    ps.add_argument("--no-remove-bg", dest="remove_bg", action="store_false")

    pe = sub.add_parser("extract-dance", help="Extract dance choreography keyframes from a reference video")
    pe.add_argument("video")
    pe.add_argument("--out", required=True)
    pe.add_argument("--fps", type=float, default=2.0)
    pe.add_argument("--max-frames", type=int, default=16)
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "cutout":
        return cmd_cutout(args)
    if args.command == "split-sheet":
        return cmd_split_sheet(args)
    if args.command == "extract-dance":
        return cmd_extract_dance(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
