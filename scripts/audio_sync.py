#!/usr/bin/env python3
"""Audio Sync & Dual-Export Engine for Agentic Reels Studio.

Supports Josué's native Instagram audio sync workflow:
  1. `analyze`     — Detect BPM, top bass-drop onset peaks, and optionally extract clean audio from a reference clip.
  2. `dual-export` — Produce BOTH:
       - reel_con_audio.mp4   (preview with synced reference track to verify beat alignment)
       - reel_sin_sonido.mp4  (same H.264 video with silent AAC track for manual trending IG audio)
       - AUDIO_SYNC.md + audio_sync.json (exact song name, artist, IG search query, start second & beat cuts)

Zero external Python dependencies (stdlib + ffmpeg/ffprobe).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


def require_ffmpeg() -> None:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        sys.exit("Error: ffmpeg and ffprobe must be installed and on PATH.")


def fmt_mmss(seconds: float) -> str:
    sec = max(0.0, float(seconds))
    mins = int(sec // 60)
    rem = sec - mins * 60
    if abs(rem - round(rem)) < 0.05:
        return f"{mins}:{int(round(rem)):02d}"
    return f"{mins}:{rem:04.1f}"


def probe_media(path: Path) -> dict:
    require_ffmpeg()
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration") or 0.0)
    return {
        "duration_s": round(dur, 2),
        "width": int(v.get("width", 0)) if v else 0,
        "height": int(v.get("height", 0)) if v else 0,
        "vcodec": v.get("codec_name") if v else None,
        "acodec": a.get("codec_name") if a else None,
        "has_audio": a is not None,
    }


def analyze_audio(media_path: Path, max_seconds: float = 35.0) -> dict:
    """Estimate BPM and strongest beat/drop onset timestamps via energy flux autocorrelation."""
    require_ffmpeg()
    meta = probe_media(media_path)
    if not meta["has_audio"]:
        return {
            "source": str(media_path),
            "duration_s": meta["duration_s"],
            "has_audio": False,
            "bpm": None,
            "beat_interval_s": None,
            "peaks_s": [],
        }

    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "mono.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(media_path),
                "-ac", "1", "-ar", "22050",
                "-t", str(max_seconds),
                str(wav_path),
            ],
            check=True,
            capture_output=True,
        )
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

    if n_frames < 2048:
        return {
            "source": str(media_path),
            "duration_s": meta["duration_s"],
            "has_audio": True,
            "bpm": None,
            "beat_interval_s": None,
            "peaks_s": [],
        }

    samples = struct.unpack(f"<{n_frames}h", raw)
    hop = 512
    energies = []
    for i in range(0, len(samples) - hop, hop):
        chunk = samples[i : i + hop]
        energies.append(sum(x * x for x in chunk) / hop)

    onsets = [max(0.0, energies[i] - energies[i - 1]) for i in range(1, len(energies))]
    max_onset = max(onsets) if onsets else 0.0
    if max_onset <= 0.0:
        return {
            "source": str(media_path),
            "duration_s": meta["duration_s"],
            "has_audio": True,
            "bpm": None,
            "beat_interval_s": None,
            "peaks_s": [],
        }

    fps_e = sr / hop
    best_bpm = 120
    best_score = -1.0
    for bpm in range(80, 177):
        lag = round(fps_e * 60.0 / bpm)
        if lag <= 0 or lag >= len(onsets):
            continue
        score = sum(onsets[i] * onsets[i - lag] for i in range(lag, len(onsets))) / (len(onsets) - lag)
        if score > best_score:
            best_score = score
            best_bpm = bpm

    peaks: list[float] = []
    last_t = -1.0
    threshold = max_onset * 0.42
    for idx, val in enumerate(onsets):
        t = idx / fps_e
        if val >= threshold and (t - last_t) >= 0.38:
            peaks.append(round(t, 2))
            last_t = t

    return {
        "source": str(media_path),
        "duration_s": meta["duration_s"],
        "has_audio": True,
        "bpm": best_bpm,
        "beat_interval_s": round(60.0 / best_bpm, 3),
        "peaks_s": peaks[:16],
    }


def extract_clean_audio(source_path: Path, out_audio: Path, start_s: float = 0.0, duration_s: float | None = None) -> Path:
    require_ffmpeg()
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start_s > 0:
        cmd.extend(["-ss", f"{start_s:.3f}"])
    cmd.extend(["-i", str(source_path), "-vn"])
    if duration_s and duration_s > 0:
        cmd.extend(["-t", f"{duration_s:.3f}"])
    ext = out_audio.suffix.lower()
    if ext == ".wav":
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2"])
    elif ext in (".m4a", ".aac"):
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "2"])
    cmd.append(str(out_audio))
    subprocess.run(cmd, check=True, capture_output=True)
    return out_audio


def dual_export(
    video_path: Path,
    out_dir: Path,
    song: str,
    artist: str,
    start_s: float,
    bpm: float | None = None,
    ref_audio: Path | None = None,
    ref_audio_offset_s: float = 0.0,
    audio_volume: float = 0.9,
    ig_query: str | None = None,
    cuts: list[dict] | None = None,
) -> dict:
    """Create both audio-synced preview MP4 and silent IG-ready MP4 + sync guide."""
    require_ffmpeg()
    if not video_path.exists():
        sys.exit(f"Error: video not found: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    meta = probe_media(video_path)
    dur = meta["duration_s"]

    out_silent = out_dir / "reel_sin_sonido.mp4"
    out_with_audio = out_dir / "reel_con_audio.mp4"

    # 1. Export silent version with clean silent AAC track (100% compatible with IG & ig_check.py)
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(video_path),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            str(out_silent),
        ],
        check=True,
        capture_output=True,
    )

    # 2. Export preview version WITH synced audio
    if ref_audio and ref_audio.exists():
        fade_out_start = max(0.0, dur - 0.55)
        af = (
            f"volume={audio_volume:.2f},"
            f"afade=t=in:st=0:d=0.12,"
            f"afade=t=out:st={fade_out_start:.2f}:d=0.55"
        )
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video_path)]
        if ref_audio_offset_s > 0:
            cmd.extend(["-ss", f"{ref_audio_offset_s:.3f}"])
        cmd.extend([
            "-i", str(ref_audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-af", af,
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(out_with_audio),
        ])
        subprocess.run(cmd, check=True, capture_output=True)
        audio_source_note = str(ref_audio.name)
    elif meta["has_audio"]:
        shutil.copy2(video_path, out_with_audio)
        audio_source_note = f"embedded ({video_path.name})"
    else:
        shutil.copy2(out_silent, out_with_audio)
        audio_source_note = "none (silent placeholder)"

    query = ig_query or f"{song} {artist}".strip()
    sync_payload = {
        "song": song,
        "artist": artist,
        "instagram_audio_search": query,
        "start_second": round(float(start_s), 2),
        "start_timestamp": fmt_mmss(start_s),
        "bpm": bpm,
        "video_duration_s": dur,
        "files": {
            "preview_with_audio": out_with_audio.name,
            "upload_without_audio": out_silent.name,
        },
        "reference_audio_used": audio_source_note,
        "cuts": cuts or [],
    }
    sync_json_path = out_dir / "audio_sync.json"
    sync_json_path.write_text(json.dumps(sync_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Guía de Sincronización de Audio — {song}",
        "",
        "## Datos exactos para Instagram Reels",
        f"- **Canción:** {song}",
        f"- **Artista:** {artist}",
        f"- **Buscar en Audio de Instagram:** `{query}`",
        f"- **Segundo exacto de inicio:** `{fmt_mmss(start_s)}` ({round(float(start_s), 2)} s)",
        f"- **BPM del ritmo:** `{bpm if bpm else 'N/A'}`",
        f"- **Duración del Reel:** `{dur} s`",
        "",
        "## Archivos entregados",
        f"1. `{out_with_audio.name}` — **Para revisar antes de subir:** incluye el audio sincronizado para validar ritmo y cortes.",
        f"2. `{out_silent.name}` — **Para subir a Instagram:** mismo video 1080×1920 H.264 sin sonido para añadir el audio oficial en la app sin choque de pistas.",
        "",
        "## Pasos rápidos al subir en Instagram",
        f"1. Sube `{out_silent.name}` como nuevo Reel.",
        f"2. Toca el ícono de **Audio / Música** y busca `{query}`.",
        f"3. Desliza la barra del audio exactamente al segundo **`{fmt_mmss(start_s)}`**.",
        "4. Verifica en la previsualización que el primer beat fuerte coincida con el corte principal y publica.",
    ]
    if cuts:
        lines.extend(["", "## Mapa de cortes al beat", "| Segundo | Escena / Golpe |", "|---|---|"])
        for c in cuts:
            lines.append(f"| `{c.get('at', 0.0):.2f}s` | {c.get('label', '')} |")

    sync_md_path = out_dir / "AUDIO_SYNC.md"
    sync_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sync_payload


def parse_cuts(raw: str | None) -> list[dict]:
    if not raw:
        return []
    cuts = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        t_str, label = chunk.split(":", 1)
        try:
            cuts.append({"at": round(float(t_str.strip()), 2), "label": label.strip()})
        except ValueError:
            continue
    return cuts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Audio beat analyzer & dual-export sync engine for Instagram Reels")
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("analyze", help="Detect BPM and beat drop timestamps from a video or audio file")
    pa.add_argument("media", help="Input video or audio file")
    pa.add_argument("--extract-audio", help="Optional output path (.mp3/.wav/.m4a) to extract audio track")
    pa.add_argument("--start", type=float, default=0.0, help="Optional start offset when extracting audio")
    pa.add_argument("--duration", type=float, default=None, help="Optional max duration when extracting audio")
    pa.add_argument("--json", action="store_true", help="Output JSON")

    pd = sub.add_parser("dual-export", help="Create reel_con_audio.mp4 + reel_sin_sonido.mp4 + AUDIO_SYNC.md")
    pd.add_argument("video", help="Rendered 9:16 MP4 video")
    pd.add_argument("--out", required=True, help="Output directory")
    pd.add_argument("--song", required=True, help="Track title")
    pd.add_argument("--artist", required=True, help="Artist name")
    pd.add_argument("--start", type=float, required=True, help="Exact start second in the official Instagram track")
    pd.add_argument("--bpm", type=float, default=None, help="Track BPM")
    pd.add_argument("--audio", default=None, help="Reference audio or MP4 clip to mux into reel_con_audio.mp4")
    pd.add_argument("--audio-offset", type=float, default=0.0, help="Start offset inside the --audio reference file")
    pd.add_argument("--volume", type=float, default=0.9, help="Audio volume for preview video (0.0-1.5)")
    pd.add_argument("--ig-query", default=None, help="Exact text to search in Instagram audio picker")
    pd.add_argument("--cuts", default=None, help='Optional beat cuts e.g. "0.0:Hook,3.6:Bang Drop,7.2:CTA"')
    pd.add_argument("--json", action="store_true", help="Output JSON")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "analyze":
        src = Path(args.media)
        if not src.exists():
            sys.exit(f"Error: file not found: {src}")
        res = analyze_audio(src)
        if args.extract_audio:
            extracted = extract_clean_audio(src, Path(args.extract_audio), start_s=args.start, duration_s=args.duration)
            res["extracted_audio"] = str(extracted)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"File: {src.name} ({res['duration_s']}s)")
            print(f"  Estimated BPM : {res['bpm']} (beat every {res['beat_interval_s']}s)")
            print(f"  Top Peaks (s) : {res['peaks_s'][:10]}")
            if "extracted_audio" in res:
                print(f"  Extracted     : {res['extracted_audio']}")
        return 0

    if args.command == "dual-export":
        res = dual_export(
            video_path=Path(args.video),
            out_dir=Path(args.out),
            song=args.song,
            artist=args.artist,
            start_s=args.start,
            bpm=args.bpm,
            ref_audio=Path(args.audio) if args.audio else None,
            ref_audio_offset_s=args.audio_offset,
            audio_volume=args.volume,
            ig_query=args.ig_query,
            cuts=parse_cuts(args.cuts),
        )
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"Dual-export complete -> {args.out}")
            print(f"  Preview (con audio)  : {res['files']['preview_with_audio']}")
            print(f"  Upload (sin sonido)  : {res['files']['upload_without_audio']}")
            print(f"  IG Audio Sync        : {res['instagram_audio_search']} @ {res['start_timestamp']} ({res['bpm']} BPM)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
