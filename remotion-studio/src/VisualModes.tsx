import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { HEIGHT, SAFE, SMALL, WIDTH } from "./theme";
import type { ChibiConfig, Scene, SceneLayout, Theme, VisualMode } from "./types";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Normalized beat phase [0, 1) and sharp beat impulse [1 -> 0] for a given BPM. */
function beatMetrics(frame: number, fps: number, bpm: number) {
  const safeBpm = Math.max(60, Math.min(220, bpm || 120));
  const beats = (frame / fps) * (safeBpm / 60);
  const beatIndex = Math.floor(beats);
  const phase = beats - beatIndex;
  // Exponential decay hit right on every beat
  const hit = Math.exp(-phase * 6.5);
  return { beats, beatIndex, phase, hit };
}

/**
 * Option A Mode 1: Dark Particle Data-Network (inspired by @sniper600news #22).
 * Deterministic glowing nodes, dynamic connection links, and BPM pulse rings on deep obsidian.
 */
const ParticleNetwork: React.FC<{ theme: Theme; bpm: number; seed: string }> = ({ theme, bpm, seed }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { hit } = beatMetrics(frame, fps, bpm);

  const count = 42;
  const nodes = Array.from({ length: count }, (_, i) => {
    const r1 = random(`${seed}-x-${i}`);
    const r2 = random(`${seed}-y-${i}`);
    const r3 = random(`${seed}-s-${i}`);
    const r4 = random(`${seed}-p-${i}`);
    const cx = (0.08 + r1 * 0.84) * WIDTH + Math.sin(t * (0.45 + r3 * 0.6) + r4 * 6.28) * 44;
    const cy = (0.1 + r2 * 0.8) * HEIGHT + Math.cos(t * (0.38 + r3 * 0.5) + r4 * 6.28) * 52;
    const accent = i % 5 === 0;
    const radius = (accent ? 4.5 : 2.6) + hit * (accent ? 3.5 : 1.4);
    return { cx, cy, accent, radius };
  });

  const links: { x1: number; y1: number; x2: number; y2: number; op: number; accent: boolean }[] = [];
  for (let i = 0; i < count; i++) {
    for (let j = i + 1; j < count; j++) {
      const dx = nodes[i].cx - nodes[j].cx;
      const dy = nodes[i].cy - nodes[j].cy;
      const d = Math.hypot(dx, dy);
      if (d < 245) {
        links.push({
          x1: nodes[i].cx,
          y1: nodes[i].cy,
          x2: nodes[j].cx,
          y2: nodes[j].cy,
          op: (1 - d / 245) * (0.28 + hit * 0.25),
          accent: nodes[i].accent || nodes[j].accent,
        });
      }
    }
  }

  const ringR = 140 + (1 - hit) * 260;

  return (
    <AbsoluteFill style={{ background: "#06080D" }}>
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <defs>
          <radialGradient id="netGlow" cx="50%" cy="46%" r="55%">
            <stop offset="0%" stopColor={theme.accent} stopOpacity={0.14 + hit * 0.08} />
            <stop offset="55%" stopColor="#141C2B" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#06080D" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={WIDTH} height={HEIGHT} fill="url(#netGlow)" />
        <circle
          cx={WIDTH / 2}
          cy={HEIGHT * 0.45}
          r={ringR}
          fill="none"
          stroke={theme.accent}
          strokeWidth={2}
          strokeOpacity={hit * 0.45}
        />
        {links.map((l, idx) => (
          <line
            key={idx}
            x1={l.x1}
            y1={l.y1}
            x2={l.x2}
            y2={l.y2}
            stroke={l.accent ? theme.accent : theme.fg}
            strokeOpacity={l.op}
            strokeWidth={l.accent ? 1.6 : 1.1}
          />
        ))}
        {nodes.map((n, idx) => (
          <circle
            key={idx}
            cx={n.cx}
            cy={n.cy}
            r={n.radius}
            fill={n.accent ? theme.accent : theme.fg}
            fillOpacity={n.accent ? 0.92 : 0.62}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

/**
 * Option A Mode 2: Hypnotic Neon Ellipse Geometry (inspired by #21).
 * Glowing ellipse with rhythmic bouncing chords & iridescent interference arcs.
 */
const EllipseLaser: React.FC<{ theme: Theme; bpm: number }> = ({ theme, bpm }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { hit } = beatMetrics(frame, fps, bpm);

  const cx = WIDTH / 2;
  const cy = HEIGHT * 0.45;
  const rx = 385;
  const ry = 590;
  const focusY = Math.sqrt(ry * ry - rx * rx) * 0.82;

  const numChords = 28;
  const chords = Array.from({ length: numChords }, (_, i) => {
    const a1 = t * 0.85 + i * 0.24;
    const a2 = a1 + Math.PI * (0.72 + 0.22 * Math.sin(t * 0.5 + i * 0.12));
    const x1 = cx + rx * Math.cos(a1);
    const y1 = cy + ry * Math.sin(a1);
    const x2 = cx + rx * Math.cos(a2);
    const y2 = cy + ry * Math.sin(a2);
    const hue = (18 + i * 11 + frame * 1.4) % 360;
    const op = interpolate(i, [0, numChords - 1], [0.12, 0.72], CLAMP);
    return { x1, y1, x2, y2, hue, op };
  });

  return (
    <AbsoluteFill style={{ background: "#050609" }}>
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx}
          ry={ry}
          fill="none"
          stroke={theme.fg}
          strokeWidth={3.5 + hit * 2.5}
          strokeOpacity={0.65 + hit * 0.3}
        />
        {chords.map((c, idx) => (
          <line
            key={idx}
            x1={c.x1}
            y1={c.y1}
            x2={c.x2}
            y2={c.y2}
            stroke={`hsl(${c.hue}, 88%, 62%)`}
            strokeWidth={1.8}
            strokeOpacity={c.op * (0.7 + hit * 0.35)}
          />
        ))}
        {/* Dual foci */}
        <circle cx={cx} cy={cy - focusY} r={10 + hit * 8} fill="#FFFFFF" fillOpacity={0.95} />
        <circle cx={cx} cy={cy - focusY} r={28 + hit * 18} fill={theme.accent} fillOpacity={0.28} />
        <circle cx={cx} cy={cy + focusY} r={10 + hit * 8} fill="#FFFFFF" fillOpacity={0.95} />
        <circle cx={cx} cy={cy + focusY} r={28 + hit * 18} fill="#38BDF8" fillOpacity={0.25} />
      </svg>
    </AbsoluteFill>
  );
};

/**
 * Option A Mode 3: Animated Beat-Synced Pipeline / Editing Timeline HUD (inspired by @cal1star #36).
 * Sits cleanly inside the lower safe margin showing live tracks, moving playhead, and audio bars.
 */
export const TimelineHud: React.FC<{ layout: SceneLayout[]; theme: Theme; bpm: number }> = ({ layout, theme, bpm }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { hit } = beatMetrics(frame, fps, bpm);
  const progress = Math.min(1, frame / Math.max(1, durationInFrames - 1));
  const barW = WIDTH - SAFE.left - SAFE.right;

  return (
    <div
      style={{
        position: "absolute",
        left: SAFE.left,
        right: SAFE.right,
        bottom: SAFE.bottom + 18,
        height: 118,
        borderRadius: 16,
        background: "rgba(10, 13, 20, 0.78)",
        border: "1px solid rgba(255, 255, 255, 0.14)",
        padding: "12px 16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: SMALL.family, fontSize: 18, color: "rgba(245,243,238,0.8)", letterSpacing: "0.06em" }}>
        <span>TIMELINE // BEAT SYNC</span>
        <span style={{ color: theme.accent }}>{Math.round(bpm)} BPM · {(frame / fps).toFixed(1)}s</span>
      </div>
      {/* Track segments */}
      <div style={{ position: "relative", height: 32, display: "flex", gap: 4 }}>
        {layout.map((l, idx) => {
          const active = frame >= l.from && frame < l.from + l.frames;
          const pct = (l.frames / Math.max(1, durationInFrames)) * 100;
          return (
            <div
              key={idx}
              style={{
                width: `${pct}%`,
                height: "100%",
                borderRadius: 6,
                background: active ? theme.accent : "rgba(245,243,238,0.16)",
                border: active ? "1px solid #FFFFFF" : "1px solid rgba(255,255,255,0.08)",
              }}
            />
          );
        })}
        {/* Playhead */}
        <div
          style={{
            position: "absolute",
            left: `${progress * 100}%`,
            top: -4,
            bottom: -4,
            width: 3,
            background: "#FFFFFF",
            boxShadow: `0 0 10px ${theme.accent}`,
          }}
        />
      </div>
      {/* Audio beat bars */}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 24 }}>
        {Array.from({ length: 36 }, (_, i) => {
          const wave = 0.25 + 0.75 * Math.abs(Math.sin(i * 0.7 + frame * 0.28)) * (0.45 + hit * 0.55);
          const passed = i / 36 <= progress;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                height: `${Math.round(wave * 100)}%`,
                borderRadius: 2,
                background: passed ? theme.accent : "rgba(245,243,238,0.28)",
                maxWidth: Math.max(6, Math.floor(barW / 40)),
              }}
            />
          );
        })}
      </div>
    </div>
  );
};

export const ProceduralBackdrop: React.FC<{ mode: VisualMode; theme: Theme; bpm: number; seed: string }> = ({ mode, theme, bpm, seed }) => {
  if (mode === "particles") return <ParticleNetwork theme={theme} bpm={bpm} seed={seed} />;
  if (mode === "ellipse") return <EllipseLaser theme={theme} bpm={bpm} />;
  if (mode === "timeline") return <ParticleNetwork theme={theme} bpm={bpm} seed={seed} />;
  return null;
};

const isVideoAsset = (src: string) => /\.(mp4|mov|webm|m4v)$/i.test(src);

/**
 * Pure-Visual Fancy Cinema Layer (inspired by #35 @shotbykusa & #24 @verissimo_garage).
 * Combines smooth Ken Burns motion, BPM bass-hit micro-zoom, RGB chromatic speed-ramp flash on cuts,
 * camera recoil shake on bang hits, and a clean editorial corner vignette (zero muddy haze).
 */
export const CinematicVisualLayer: React.FC<{
  src: string;
  frames: number;
  bpm: number;
  first: boolean;
  isBang: boolean;
  zoomFrom?: number;
  zoomTo?: number;
  panX?: number;
  dim?: number | null;
  bgColor: string;
}> = ({ src, frames, bpm, first, isBang, zoomFrom = 1.09, zoomTo = 1.02, panX = 0, dim = 0, bgColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { hit } = beatMetrics(frame, fps, bpm);

  // Smooth Ken Burns drift + crisp bass pump on every beat
  const baseScale = interpolate(frame, [0, Math.max(1, frames)], [zoomFrom, zoomTo], CLAMP);
  const beatPump = hit * 0.024;
  // Speed-ramp zoom slam on scene cuts (frames 0..6)
  const cutSlam = first ? 0 : interpolate(frame, [0, 6], [0.16, 0], CLAMP);
  const scale = baseScale + beatPump + cutSlam;

  const driftX = interpolate(frame, [0, Math.max(1, frames)], [-panX / 2, panX / 2], CLAMP);

  // Camera recoil shake on the first 9 frames of a BANG! impact
  const shakeDecay = isBang ? Math.exp(-frame * 0.36) * (frame < 10 ? 1 : 0) : 0;
  const shakeX = isBang ? Math.sin(frame * 2.7) * 22 * shakeDecay : 0;
  const shakeY = isBang ? Math.cos(frame * 3.4) * 16 * shakeDecay : 0;

  // RGB chromatic split offset during the first 6 frames of a cut (or bang impact)
  const rgbShift = !first && frame < 6 ? interpolate(frame, [0, 6], [16, 0], CLAMP) : isBang && frame < 5 ? interpolate(frame, [0, 5], [14, 0], CLAMP) : 0;
  const cutFlash = !first && frame < 5 ? interpolate(frame, [0, 5], [0.34, 0], CLAMP) : 0;

  const baseStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    transform: `translate(${(driftX + shakeX).toFixed(1)}px, ${shakeY.toFixed(1)}px) scale(${scale.toFixed(4)})`,
    filter: cutFlash > 0.01 ? `brightness(${(1 + cutFlash * 0.9).toFixed(2)}) saturate(1.12)` : "contrast(1.04) saturate(1.06)",
  };

  const renderMedia = (extraStyle?: React.CSSProperties) =>
    isVideoAsset(src) ? (
      <OffthreadVideo src={staticFile(src)} muted style={{ ...baseStyle, ...extraStyle }} />
    ) : (
      <Img src={staticFile(src)} style={{ ...baseStyle, ...extraStyle }} />
    );

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: bgColor }}>
      {renderMedia()}
      {/* RGB chromatic aberration speed-ramp ghosts on transitions/impacts */}
      {rgbShift > 0.5 ? (
        <>
          <AbsoluteFill style={{ opacity: 0.34, mixBlendMode: "screen", filter: "hue-rotate(-35deg) saturate(1.8)" }}>
            {renderMedia({
              transform: `translate(${(driftX + shakeX - rgbShift).toFixed(1)}px, ${shakeY.toFixed(1)}px) scale(${(scale + 0.025).toFixed(4)})`,
            })}
          </AbsoluteFill>
          <AbsoluteFill style={{ opacity: 0.34, mixBlendMode: "screen", filter: "hue-rotate(140deg) saturate(1.8)" }}>
            {renderMedia({
              transform: `translate(${(driftX + shakeX + rgbShift).toFixed(1)}px, ${shakeY.toFixed(1)}px) scale(${(scale + 0.025).toFixed(4)})`,
            })}
          </AbsoluteFill>
        </>
      ) : null}
      {/* Optional explicit dim (defaults to 0 for vibrant cinema) */}
      {dim && dim > 0 ? <AbsoluteFill style={{ background: bgColor, opacity: dim }} /> : null}
      {/* Clean subtle editorial vignette around far edges */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(85% 75% at 50% 48%, rgba(0,0,0,0) 58%, rgba(4,6,10,0.42) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

/** Understated luxury editorial corner signature (optional, zero sales clutter). */
export const SubtleWatermark: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      position: "absolute",
      top: SAFE.top + 8,
      left: 0,
      right: 0,
      textAlign: "center",
      fontFamily: SMALL.family,
      fontWeight: 600,
      fontSize: 22,
      letterSpacing: "0.32em",
      textTransform: "uppercase",
      color: "rgba(255, 255, 255, 0.42)",
      textShadow: "0 2px 10px rgba(0, 0, 0, 0.65)",
      pointerEvents: "none",
    }}
  >
    {text}
  </div>
);

/**
 * Option B: Beat-Synced Chibi / Anime Sprite Dance Overlay
 * Inspired by @shotbykusa (#35 "Watch my 9mm go, bang!"), @sinnerm3 (#33), @d2_shots (#34).
 * Supports multiple bangScenes, per-scene positioning, wet-asphalt reflection, and cracked-glass VFX.
 */
export const ChibiDanceOverlay: React.FC<{
  chibi: ChibiConfig;
  scenes: Scene[];
  layout: SceneLayout[];
  bpm: number;
  accent: string;
}> = ({ chibi, scenes, layout, bpm, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const poses = chibi.poses ?? [];
  if (!poses.length) return null;

  const effectiveBpm = chibi.bpm ?? bpm ?? 155;
  const { beatIndex, phase, hit } = beatMetrics(frame, fps, effectiveBpm);

  const sceneIdx = Math.max(0, layout.findIndex((l) => frame >= l.from && frame < l.from + l.frames));
  const curScene = scenes[sceneIdx];
  const bangSet = new Set<number>([
    ...(chibi.bangScene != null ? [chibi.bangScene] : []),
    ...(chibi.bangScenes ?? []),
  ]);
  const isBangScene = bangSet.has(sceneIdx);
  const bangStart = isBangScene && layout[sceneIdx] ? layout[sceneIdx].from : -999;
  const bangAge = frame - bangStart;

  // Cycle dance poses on every beat, lock to finger-gun pose (last pose) during any bangScene
  const danceCount = poses.length > 1 && bangSet.size > 0 ? poses.length - 1 : poses.length;
  const poseSrc = isBangScene ? poses[poses.length - 1] : poses[beatIndex % danceCount];

  // Snappy anime bounce + squash & stretch synced to BPM
  const hop = Math.sin(phase * Math.PI) * (isBangScene ? 10 : 30);
  const squashX = 1 + hit * 0.07;
  const squashY = 1 - hit * 0.06;
  const swayDeg = isBangScene ? -3.0 : (beatIndex % 2 === 0 ? 1 : -1) * (4.8 * Math.sin(phase * Math.PI));
  const bangPop = isBangScene
    ? 1 + 0.16 * Math.exp(-Math.max(0, bangAge) * 0.24) * spring({ frame: bangAge, fps, config: { damping: 14, stiffness: 280 } })
    : 1;

  const cx = (curScene?.chibiX ?? chibi.x ?? 0.5) * WIDTH;
  const bottomY = (curScene?.chibiY ?? chibi.y ?? 0.77) * HEIGHT;
  const spriteH = Math.round(520 * (curScene?.chibiScale ?? chibi.scale ?? 1));
  const showShadow = chibi.shadow !== false;

  // Cracked-glass bullet-hole impact + spark burst on bang hit (persists briefly like #35 @ 4.2s)
  const flashOp = isBangScene ? interpolate(bangAge, [0, 2, 10], [0.32, 0.18, 0], CLAMP) : 0;
  const crackOp = isBangScene ? interpolate(bangAge, [0, 2, 22, 32], [0.95, 0.92, 0.72, 0], CLAMP) : 0;
  const crackScale = isBangScene ? interpolate(bangAge, [0, 4, 18], [0.55, 1.08, 1.18], CLAMP) : 0.55;
  const burstX = cx - spriteH * 0.42;
  const burstY = bottomY - spriteH * 0.64;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Brief warm muzzle flash wash on exact gunshot frame */}
      {flashOp > 0.01 ? (
        <AbsoluteFill
          style={{
            background: "radial-gradient(circle at 38% 58%, rgba(255,244,220,0.85) 0%, rgba(255,140,80,0.22) 45%, rgba(0,0,0,0) 75%)",
            opacity: flashOp,
          }}
        />
      ) : null}

      {/* Cracked glass bullet-hole + radial spark shatter VFX (signature #35 @4.2s effect) */}
      {crackOp > 0.01 ? (
        <svg
          width={WIDTH}
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          style={{ position: "absolute", inset: 0, opacity: crackOp }}
        >
          <g transform={`translate(${burstX}, ${burstY}) scale(${crackScale})`}>
            {/* Concentric glass fracture rings */}
            <circle cx={0} cy={0} r={22} fill="rgba(255,255,255,0.88)" />
            <circle cx={0} cy={0} r={44} fill="none" stroke="rgba(255,255,255,0.82)" strokeWidth={3.5} strokeDasharray="16 8" />
            <circle cx={0} cy={0} r={82} fill="none" stroke="rgba(230,245,255,0.58)" strokeWidth={2} strokeDasharray="24 14" />
            <circle cx={0} cy={0} r={126} fill="none" stroke="rgba(255,255,255,0.34)" strokeWidth={1.5} strokeDasharray="18 22" />
            {/* Radial jagged glass crack rays */}
            {Array.from({ length: 16 }, (_, i) => {
              const ang = (i / 16) * Math.PI * 2 + (i % 3) * 0.07;
              const r1 = 16;
              const rMid = 62 + (i % 3) * 18;
              const r2 = i % 2 === 0 ? 168 : 112;
              const mx = Math.cos(ang + 0.08) * rMid;
              const my = Math.sin(ang + 0.08) * rMid;
              return (
                <polyline
                  key={i}
                  points={`${(Math.cos(ang) * r1).toFixed(1)},${(Math.sin(ang) * r1).toFixed(1)} ${mx.toFixed(1)},${my.toFixed(1)} ${(Math.cos(ang) * r2).toFixed(1)},${(Math.sin(ang) * r2).toFixed(1)}`}
                  fill="none"
                  stroke={i % 4 === 0 ? accent : "#FFFFFF"}
                  strokeWidth={i % 2 === 0 ? 3.2 : 1.8}
                  strokeOpacity={i % 2 === 0 ? 0.9 : 0.65}
                  strokeLinecap="round"
                />
              );
            })}
          </g>
        </svg>
      ) : null}

      {/* Ground contact shadow + glossy wet-asphalt reflection */}
      {showShadow ? (
        <>
          <div
            style={{
              position: "absolute",
              left: cx - spriteH * 0.28,
              top: bottomY - 16,
              width: spriteH * 0.56,
              height: 36,
              borderRadius: "50%",
              background: "radial-gradient(ellipse at center, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0) 74%)",
              transform: `scale(${1 - hop / 180})`,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: cx,
              top: bottomY - 6,
              height: spriteH,
              transform: `translate(-50%, 0) scaleY(-0.58) scaleX(${squashX * bangPop}) rotate(${swayDeg}deg)`,
              transformOrigin: "top center",
              opacity: 0.26,
              filter: "blur(3.5px)",
              maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.92), rgba(0,0,0,0) 70%)",
              WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,0.92), rgba(0,0,0,0) 70%)",
            }}
          >
            <Img src={staticFile(poseSrc)} style={{ height: spriteH, width: "auto", display: "block" }} />
          </div>
        </>
      ) : null}

      {/* Main animated chibi character sprite */}
      <div
        style={{
          position: "absolute",
          left: cx,
          top: bottomY - hop,
          transform: `translate(-50%, -100%) scale(${squashX * bangPop}, ${squashY * bangPop}) rotate(${swayDeg}deg)`,
          transformOrigin: "bottom center",
          filter: "drop-shadow(0 14px 22px rgba(0,0,0,0.62))",
        }}
      >
        <Img src={staticFile(poseSrc)} style={{ height: spriteH, width: "auto", display: "block" }} />
      </div>
    </AbsoluteFill>
  );
};
