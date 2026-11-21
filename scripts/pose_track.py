#!/usr/bin/env python3
"""30fps Real-Motion Pose Tracker (MediaPipe PoseLandmarker -> Live2D Anime Rig JSON).

100% free, local CPU pipeline ($0 API cost). Extracts 33 real body landmarks frame by frame
from any human dance reference video (e.g. Muestras #10 @leytink or #31 @kkarenzeng), smooths
trajectories with zero-phase Gaussian filtering, simulates secondary anime physics (tie swing,
hair inertia, skirt bounce, 2.5D shoulder turn yaw), and writes a compact motion JSON consumed
by Remotion's `BandidaRigOverlay`.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = ROOT / ".cache" / "models" / "pose_landmarker_full.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)

# MediaPipe Pose landmark indices
NOSE = 0
L_EAR, R_EAR = 7, 8
L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HP, R_HP = 23, 24
L_KN, R_KN = 25, 26
L_AN, R_AN = 27, 28


def ensure_model(model_path: Path = DEFAULT_MODEL) -> Path:
    if model_path.exists() and model_path.stat().st_size > 1_000_000:
        return model_path
    model_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MediaPipe PoseLandmarker model to {model_path}...", file=sys.stderr)
    urllib.request.urlretrieve(MODEL_URL, model_path)
    return model_path


def seg_angle_deg(p1: np.ndarray, p2: np.ndarray) -> float:
    """Angle in degrees where 0 deg = straight down (+Y), positive = clockwise toward screen-left (-X)."""
    dx = float(p2[0] - p1[0])
    dy = float(p2[1] - p1[1])
    # In CSS rotate(deg) with downward-pointing sprite:
    # positive CSS deg rotates clockwise (bottom swings to screen-left, -X).
    return math.degrees(math.atan2(-dx, dy))


def unwrap_deg(arr: np.ndarray) -> np.ndarray:
    rad = np.deg2rad(arr)
    return np.rad2deg(np.unwrap(rad))


def smooth_1d(arr: np.ndarray, sigma: float = 1.35) -> np.ndarray:
    if len(arr) < 5 or sigma <= 0:
        return arr.copy()
    radius = max(1, int(round(sigma * 3)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(arr, radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_crop(crop_str: str | None, width: int, height: int) -> tuple[int, int, int, int]:
    """Parse normalized crop 'x0,y0,x1,y1' (0..1) into pixel rectangle."""
    if not crop_str:
        return 0, 0, width, height
    parts = [float(p.strip()) for p in crop_str.split(",")]
    if len(parts) != 4:
        sys.exit("Error: --crop must be 'x0,y0,x1,y1' in 0..1 normalized coordinates.")
    x0 = int(clamp(parts[0], 0, 0.95) * width)
    y0 = int(clamp(parts[1], 0, 0.95) * height)
    x1 = int(clamp(parts[2], 0.05, 1.0) * width)
    y1 = int(clamp(parts[3], 0.05, 1.0) * height)
    return x0, y0, max(x0 + 32, x1), max(y0 + 32, y1)


def extract_track(
    video_path: Path,
    fps: int = 30,
    start: float = 0.0,
    duration: float | None = None,
    crop: str | None = None,
    target_duration: float | None = None,
    sigma: float = 1.4,
    model_path: Path = DEFAULT_MODEL,
) -> dict:
    import tempfile

    model_file = ensure_model(model_path)

    # Probe source dimensions for crop filter
    probe = cv2.VideoCapture(str(video_path))
    if not probe.isOpened():
        sys.exit(f"Error: could not open video {video_path}")
    src_w = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    probe.release()

    x0, y0, x1, y1 = parse_crop(crop, src_w, src_h)
    cw, ch = x1 - x0, y1 - y0
    # Fast FFmpeg sequential decode/crop/scale (100x faster than cv2.CAP_PROP_POS_FRAMES on iPhone HEVC/H.264)
    scale_h = min(640, ch)
    vf = f"crop={cw}:{ch}:{x0}:{y0},scale=-2:{scale_h},fps={fps}"

    with tempfile.TemporaryDirectory() as td:
        tmp_mp4 = Path(td) / "seq.mp4"
        ff_cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path)]
        if duration:
            ff_cmd += ["-t", f"{duration:.3f}"]
        ff_cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-an", str(tmp_mp4)]
        subprocess.run(ff_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cap = cv2.VideoCapture(str(tmp_mp4))
        dec_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        dec_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        base_options = mp.tasks.BaseOptions(model_asset_path=str(model_file))
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.35,
            min_pose_presence_confidence=0.35,
            min_tracking_confidence=0.35,
        )

        raw_pts: list[np.ndarray | None] = []
        i = 0
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            while True:
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    break
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int(round((i / fps) * 1000)) + 1
                res = detector.detect_for_video(mp_img, ts_ms)
                if res.pose_landmarks and len(res.pose_landmarks) > 0:
                    lms = res.pose_landmarks[0]
                    arr = np.array([[lm.x * dec_w, lm.y * dec_h, lm.z * dec_w] for lm in lms], dtype=np.float64)
                    raw_pts.append(arr)
                else:
                    raw_pts.append(None)
                i += 1
        cap.release()

    num_samples = len(raw_pts)
    span = num_samples / max(1.0, float(fps))
    cw, ch = dec_w, dec_h

    detected = sum(1 for p in raw_pts if p is not None)
    if detected < 5:
        sys.exit(f"Error: MediaPipe detected too few pose frames ({detected}/{num_samples}) in {video_path}")

    # Linearly interpolate any missing frames across the track
    valid_idx = [i for i, p in enumerate(raw_pts) if p is not None]
    pts = np.zeros((num_samples, 33, 3), dtype=np.float64)
    for lm_i in range(33):
        for axis in range(3):
            vals = np.array([raw_pts[idx][lm_i, axis] for idx in valid_idx], dtype=np.float64)
            pts[:, lm_i, axis] = np.interp(np.arange(num_samples), valid_idx, vals)

    # Normalize scale by median torso height (shoulder midpoint -> hip midpoint)
    sh_mid = 0.5 * (pts[:, L_SH, :2] + pts[:, R_SH, :2])
    hp_mid = 0.5 * (pts[:, L_HP, :2] + pts[:, R_HP, :2])
    torso_vecs = hp_mid - sh_mid
    torso_lens = np.linalg.norm(torso_vecs, axis=1)
    med_torso = float(np.median(torso_lens))
    if med_torso < 10.0:
        med_torso = float(ch * 0.25)

    # Median standing reference
    med_hx = float(np.median(hp_mid[:, 0]))
    med_hy = float(np.median(hp_mid[:, 1]))
    med_sh_w = float(np.median(np.abs(pts[:, R_SH, 0] - pts[:, L_SH, 0])))
    if med_sh_w < 8.0:
        med_sh_w = med_torso * 0.72

    n = num_samples
    hx = (hp_mid[:, 0] - med_hx) / med_torso
    hy = (hp_mid[:, 1] - med_hy) / med_torso

    # Torso lean (neck-to-hip vector angle; flip because sh->hp is straight down = 0)
    torso_deg = np.array([seg_angle_deg(sh_mid[i], hp_mid[i]) for i in range(n)])
    # Negate so leaning upper body right gives positive clockwise tilt!
    torso_deg = -unwrap_deg(torso_deg)

    # Hip pelvis tilt (left hip -> right hip horizontal angle)
    hip_tilt = np.array(
        [math.degrees(math.atan2(pts[i, R_HP, 1] - pts[i, L_HP, 1], pts[i, R_HP, 0] - pts[i, L_HP, 0])) for i in range(n)]
    )
    # Center around 0 (since L_HP is on screen-right for front-facing camera, vector L->R points left ~180 deg)
    hip_tilt = np.array([((a + 180.0) % 360.0) - 180.0 if abs(a) > 90 else a for a in hip_tilt])
    # Recompute clean signed slope using screen-left hip -> screen-right hip
    hip_slope = np.zeros(n)
    for i in range(n):
        p_a, p_b = pts[i, L_HP, :2], pts[i, R_HP, :2]
        if p_a[0] > p_b[0]:
            p_a, p_b = p_b, p_a
        hip_slope[i] = math.degrees(math.atan2(p_b[1] - p_a[1], max(6.0, p_b[0] - p_a[0])))

    # 2.5D Shoulder Yaw [-1 .. 1]: combines apparent shoulder width narrowing + Z-depth difference
    sh_dx = pts[:, L_SH, 0] - pts[:, R_SH, 0]  # positive when facing camera (subject's left is viewer's right)
    sh_dz = pts[:, L_SH, 2] - pts[:, R_SH, 2]
    yaw_raw = np.clip(sh_dz / max(12.0, med_sh_w * 1.15), -0.95, 0.95)
    # Facing flip factor (if dancer turns fully away, sh_dx < 0)
    sh_width_ratio = np.clip(np.abs(sh_dx) / max(12.0, med_sh_w), 0.35, 1.18)

    # Head tilt from ears + nose offset
    head_deg = np.zeros(n)
    for i in range(n):
        e_a, e_b = pts[i, L_EAR, :2], pts[i, R_EAR, :2]
        if e_a[0] > e_b[0]:
            e_a, e_b = e_b, e_a
        ear_tilt = math.degrees(math.atan2(e_b[1] - e_a[1], max(6.0, e_b[0] - e_a[0])))
        nose_dx = (pts[i, NOSE, 0] - sh_mid[i, 0]) / med_torso
        head_deg[i] = clamp(ear_tilt * 0.95 + nose_dx * 16.0, -34.0, 34.0)

    # Limb segment angles (viewer space: subject's RIGHT = viewer's LEFT side of body when facing front)
    # Note: MediaPipe L_SH is subject's anatomical left (viewer's right when facing camera).
    r_ua = unwrap_deg(np.array([seg_angle_deg(pts[i, R_SH, :2], pts[i, R_EL, :2]) for i in range(n)]))
    r_fa = unwrap_deg(np.array([seg_angle_deg(pts[i, R_EL, :2], pts[i, R_WR, :2]) for i in range(n)]))
    l_ua = unwrap_deg(np.array([seg_angle_deg(pts[i, L_SH, :2], pts[i, L_EL, :2]) for i in range(n)]))
    l_fa = unwrap_deg(np.array([seg_angle_deg(pts[i, L_EL, :2], pts[i, L_WR, :2]) for i in range(n)]))

    r_th = unwrap_deg(np.array([seg_angle_deg(pts[i, R_HP, :2], pts[i, R_KN, :2]) for i in range(n)]))
    r_sh = unwrap_deg(np.array([seg_angle_deg(pts[i, R_KN, :2], pts[i, R_AN, :2]) for i in range(n)]))
    l_th = unwrap_deg(np.array([seg_angle_deg(pts[i, L_HP, :2], pts[i, L_KN, :2]) for i in range(n)]))
    l_sh = unwrap_deg(np.array([seg_angle_deg(pts[i, L_KN, :2], pts[i, L_AN, :2]) for i in range(n)]))

    # Apply smooth zero-phase Gaussian filter to eliminate webcam/video jitter
    hx = smooth_1d(hx, sigma)
    hy = smooth_1d(hy, sigma)
    torso_deg = np.clip(smooth_1d(torso_deg, sigma), -32.0, 32.0)
    hip_slope = np.clip(smooth_1d(hip_slope, sigma), -26.0, 26.0)
    head_deg = np.clip(smooth_1d(head_deg, sigma), -34.0, 34.0)
    yaw_s = smooth_1d(yaw_raw, sigma * 1.4)
    sh_wr = smooth_1d(sh_width_ratio, sigma * 1.4)

    r_ua = smooth_1d(r_ua, sigma)
    r_fa = smooth_1d(r_fa, sigma)
    l_ua = smooth_1d(l_ua, sigma)
    l_fa = smooth_1d(l_fa, sigma)
    r_th = np.clip(smooth_1d(r_th, sigma), -78.0, 78.0)
    r_sh = np.clip(smooth_1d(r_sh, sigma), -95.0, 95.0)
    l_th = np.clip(smooth_1d(l_th, sigma), -78.0, 78.0)
    l_sh = np.clip(smooth_1d(l_sh, sigma), -95.0, 95.0)

    # Secondary spring-damped anime physics for crimson tie, back hair, and pleated skirt flare
    tie_deg = np.zeros(n)
    tie_vel = 0.0
    hair_lag = np.zeros(n)
    hair_vel = 0.0
    skirt_flare = np.zeros(n)
    dt = 1.0 / fps

    for i in range(n):
        vx = (hx[i] - hx[i - 1]) / dt if i > 0 else 0.0
        vy = (hy[i] - hy[i - 1]) / dt if i > 0 else 0.0
        # Target tie angle reacts to gravity (-torso_deg) + lateral inertial whip (-vx)
        target_tie = clamp(-torso_deg[i] * 0.85 - vx * 12.0, -42.0, 42.0)
        acc_tie = (target_tie - tie_deg[i - 1 if i > 0 else 0]) * 52.0 - tie_vel * 7.5
        tie_vel += acc_tie * dt
        tie_deg[i] = clamp((tie_deg[i - 1] if i > 0 else target_tie) + tie_vel * dt, -46.0, 46.0)

        target_hair = clamp(-vx * 18.0 - torso_deg[i] * 0.4, -22.0, 22.0)
        acc_hair = (target_hair - hair_lag[i - 1 if i > 0 else 0]) * 44.0 - hair_vel * 6.8
        hair_vel += acc_hair * dt
        hair_lag[i] = clamp((hair_lag[i - 1] if i > 0 else 0.0) + hair_vel * dt, -24.0, 24.0)

        # Skirt flares outward on jumps/drops and rapid hip velocity
        skirt_flare[i] = clamp(1.0 + abs(vx) * 0.045 + max(0.0, -vy) * 0.06, 0.96, 1.18)

    frames = []
    for i in range(n):
        frames.append(
            {
                "hx": round(float(clamp(hx[i], -0.9, 0.9)), 3),
                "hy": round(float(clamp(hy[i], -0.85, 0.65)), 3),
                "t": round(float(torso_deg[i]), 2),
                "ht": round(float(hip_slope[i]), 2),
                "hd": round(float(head_deg[i]), 2),
                "yw": round(float(yaw_s[i]), 3),
                "sw": round(float(sh_wr[i]), 3),
                "rUA": round(float(r_ua[i]), 1),
                "rFA": round(float(r_fa[i]), 1),
                "lUA": round(float(l_ua[i]), 1),
                "lFA": round(float(l_fa[i]), 1),
                "rTh": round(float(r_th[i]), 1),
                "rSh": round(float(r_sh[i]), 1),
                "lTh": round(float(l_th[i]), 1),
                "lSh": round(float(l_sh[i]), 1),
                "tie": round(float(tie_deg[i]), 2),
                "hr": round(float(hair_lag[i]), 2),
                "sf": round(float(skirt_flare[i]), 3),
            }
        )

    # Optionally extend smoothly via crossfaded loop to match exact Reel duration (e.g. 14.0s)
    if target_duration and target_duration > span:
        target_n = int(round(target_duration * fps))
        blend_len = min(18, len(frames) // 4)
        extended = list(frames)
        while len(extended) < target_n:
            chunk = list(frames)
            # Smoothly crossfade seam between previous tail and new loop head
            for b in range(blend_len):
                if len(extended) - blend_len + b < 0:
                    continue
                alpha = (b + 1) / (blend_len + 1)
                prev = extended[len(extended) - blend_len + b]
                nxt = chunk[b]
                extended[len(extended) - blend_len + b] = {
                    k: round(prev[k] * (1.0 - alpha) + nxt[k] * alpha, 3) for k in prev
                }
            extended.extend(chunk[blend_len:])
        frames = extended[:target_n]

    return {
        "source": video_path.name,
        "fps": fps,
        "detected_frames": detected,
        "sampled_frames": num_samples,
        "frame_count": len(frames),
        "duration_seconds": round(len(frames) / fps, 3),
        "frames": frames,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Extract 30fps MediaPipe Pose motion JSON for Remotion 2D Live2D Rig")
    p.add_argument("video", help="Input reference dance video (.mp4/.mov)")
    p.add_argument("--out", required=True, help="Output motion JSON path")
    p.add_argument("--fps", type=int, default=30, help="Target FPS (default 30)")
    p.add_argument("--start", type=float, default=0.0, help="Start offset in seconds")
    p.add_argument("--duration", type=float, help="Clip duration in seconds to track")
    p.add_argument("--target-duration", type=float, help="Smoothly crossfade-loop output to exact Reel length (s)")
    p.add_argument("--crop", help="Normalized ROI crop 'x0,y0,x1,y1' (e.g. '0.0,0.10,0.68,0.88' to isolate single dancer)")
    p.add_argument("--sigma", type=float, default=1.4, help="Gaussian smoothing sigma in frames (default 1.4)")
    args = p.parse_args()

    vid = Path(args.video).resolve()
    if not vid.exists():
        sys.exit(f"Error: video not found: {vid}")

    track = extract_track(
        vid,
        fps=args.fps,
        start=args.start,
        duration=args.duration,
        crop=args.crop,
        target_duration=args.target_duration,
        sigma=args.sigma,
    )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(track, separators=(",", ":")), encoding="utf-8")
    print(
        f"Tracked {track['detected_frames']}/{track['sampled_frames']} frames -> "
        f"{track['frame_count']} frames ({track['duration_seconds']}s @ {track['fps']}fps) saved to {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
