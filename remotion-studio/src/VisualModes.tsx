import React from "react";
import { AbsoluteFill, Img, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { HEIGHT, SAFE, SMALL, WIDTH } from "./theme";
import type { ChibiConfig, SceneLayout, Theme, VisualMode } from "./types";

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

/**
 * Option B: Beat-Synced Chibi / Anime Sprite Dance Overlay
 * Inspired by @shotbykusa (#35 "Watch my 9mm go, bang!"), @sinnerm3 (#33), @d2_shots (#34).
 * Composites foot-aligned transparent poses with BPM bounce, squash/stretch, ground reflection, and bang VFX.
 */
export const ChibiDanceOverlay: React.FC<{
  chibi: ChibiConfig;
  layout: SceneLayout[];
  bpm: number;
  accent: string;
}> = ({ chibi, layout, bpm, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const poses = chibi.poses ?? [];
  if (!poses.length) return null;

  const effectiveBpm = chibi.bpm ?? bpm ?? 148;
  const { beatIndex, phase, hit } = beatMetrics(frame, fps, effectiveBpm);

  // Determine which scene index is currently playing
  const sceneIdx = layout.findIndex((l) => frame >= l.from && frame < l.from + l.frames);
  const isBangScene = chibi.bangScene != null && sceneIdx === chibi.bangScene;
  const bangStart = isBangScene ? layout[sceneIdx].from : -999;
  const bangAge = frame - bangStart;

  // Pick pose: cycle first N-1 dance poses on beat, lock to last pose on bangScene
  const danceCount = poses.length > 1 && chibi.bangScene != null ? poses.length - 1 : poses.length;
  const poseSrc = isBangScene ? poses[poses.length - 1] : poses[beatIndex % danceCount];

  // Snappy anime bounce + squash & stretch synced to BPM
  const hop = Math.sin(phase * Math.PI) * (isBangScene ? 12 : 28);
  const squashX = 1 + hit * 0.065;
  const squashY = 1 - hit * 0.055;
  const swayDeg = isBangScene ? -2.5 : (beatIndex % 2 === 0 ? 1 : -1) * (4.2 * Math.sin(phase * Math.PI));
  const bangPop = isBangScene
    ? 1 + 0.14 * Math.exp(-Math.max(0, bangAge) * 0.25) * spring({ frame: bangAge, fps, config: { damping: 14, stiffness: 260 } })
    : 1;

  const cx = (chibi.x ?? 0.5) * WIDTH;
  const bottomY = (chibi.y ?? 0.72) * HEIGHT;
  const spriteH = Math.round(520 * (chibi.scale ?? 1));
  const showShadow = chibi.shadow !== false;

  // Impact burst flash on the first 10 frames of bangScene
  const burstOpacity = isBangScene ? interpolate(bangAge, [0, 3, 12], [0.95, 0.85, 0], CLAMP) : 0;
  const burstScale = isBangScene ? interpolate(bangAge, [0, 12], [0.4, 1.55], CLAMP) : 0.4;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Subtle beat flash on bang hit */}
      {burstOpacity > 0.01 ? (
        <AbsoluteFill style={{ background: "#FFFFFF", opacity: burstOpacity * 0.24 }} />
      ) : null}

      {/* Comic/glass radial impact burst behind bang pose */}
      {burstOpacity > 0.01 ? (
        <svg
          width={WIDTH}
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          style={{ position: "absolute", inset: 0, opacity: burstOpacity }}
        >
          <g transform={`translate(${cx - 170}, ${bottomY - spriteH * 0.62}) scale(${burstScale})`}>
            {Array.from({ length: 14 }, (_, i) => {
              const ang = (i / 14) * Math.PI * 2;
              const r1 = 22;
              const r2 = i % 2 === 0 ? 130 : 88;
              return (
                <line
                  key={i}
                  x1={Math.cos(ang) * r1}
                  y1={Math.sin(ang) * r1}
                  x2={Math.cos(ang) * r2}
                  y2={Math.sin(ang) * r2}
                  stroke={i % 2 === 0 ? "#FFFFFF" : accent}
                  strokeWidth={i % 2 === 0 ? 5 : 3}
                  strokeLinecap="round"
                />
              );
            })}
            <circle cx={0} cy={0} r={24} fill="#FFFFFF" fillOpacity={0.9} />
            <circle cx={0} cy={0} r={44} fill="none" stroke="#FFFFFF" strokeWidth={4} strokeOpacity={0.75} />
          </g>
        </svg>
      ) : null}

      {/* Ground contact shadow + wet asphalt reflection (signature look of #35 @shotbykusa) */}
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
              background: "radial-gradient(ellipse at center, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0) 72%)",
              transform: `scale(${1 - hop / 180})`,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: cx,
              top: bottomY - 6,
              height: spriteH,
              transform: `translate(-50%, 0) scaleY(-0.55) scaleX(${squashX * bangPop}) rotate(${swayDeg}deg)`,
              transformOrigin: "top center",
              opacity: 0.22,
              filter: "blur(3px)",
              maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.9), rgba(0,0,0,0) 68%)",
              WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,0.9), rgba(0,0,0,0) 68%)",
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
          filter: "drop-shadow(0 10px 18px rgba(0,0,0,0.55))",
        }}
      >
        <Img src={staticFile(poseSrc)} style={{ height: spriteH, width: "auto", display: "block" }} />
      </div>
    </AbsoluteFill>
  );
};
