export type SceneType = "hook" | "text" | "stat" | "item" | "quote" | "end" | "visual";

export type Scene = {
  type: SceneType;
  /** Main words on screen (hook, text, quote, end, item body). */
  text?: string;
  /** hook and text: a word or number set very large on its own line above the text. */
  big?: string;
  /** Word or phrase (or list of them) to mark in the accent colour. */
  highlight?: string | string[];
  /** stat: the number, e.g. "96.5", "1,200", 40. */
  value?: string | number;
  prefix?: string;
  suffix?: string;
  /** stat: what the number means. */
  label?: string;
  /** item: the list position, e.g. 3. */
  rank?: number | string;
  /** item: the headline of the list item. */
  title?: string;
  /** quote: who said it. */
  author?: string;
  /** end: the smaller line under the main text. */
  sub?: string;
  /** Optional photo or video behind this scene (file in public/assets). */
  image?: string;
  /** Override the computed on-screen time. */
  seconds?: number;
  /** visual scene camera zoom start/end (defaults 1.09 -> 1.02). */
  zoomFrom?: number;
  zoomTo?: number;
  /** visual scene gentle horizontal camera pan in pixels. */
  panX?: number;
  /** Per-scene chibi horizontal anchor override (0..1). */
  chibiX?: number;
  /** Per-scene chibi vertical feet baseline override (0..1). */
  chibiY?: number;
  /** Per-scene chibi scale multiplier override. */
  chibiScale?: number;
  /** Scene ambient tint color (rgba/hex) to color-match the chibi into the night backdrop. */
  sceneTint?: string;
  /** Backlight rim-glow color wrapping the chibi silhouette. */
  rimColor?: string;
  /** Per-scene chibi exposure multiplier (e.g. 0.78-0.90 for dark night scenes). */
  chibiBrightness?: number;
};

export type Theme = {
  bg: string;
  fg: string;
  accent: string;
  /** Text colour on top of the accent box. */
  accentText: string;
  font: FontName;
  uppercase: boolean;
};

export type FontName = "Anton" | "Poppins" | "Inter";

export type Block = { fontSize: number; lines: string[][]; marks: boolean[][] };

export type SceneLayout = {
  from: number;
  frames: number;
  /** Frames the word-by-word reveal takes. */
  reveal: number;
  blocks: Record<string, Block>;
};

export type VisualMode = "ambient" | "particles" | "ellipse" | "timeline";

export type ChibiConfig = {
  /** Array of local transparent PNG pose paths (relative to short.json). Optional when `video` is provided. */
  poses?: string[];
  /** Optional 24-30fps alpha-transparent dance video (.webm VP9 yuva420p from fal.ai Bria VRMBG 3.0 or FFmpeg chroma-key). */
  video?: string;
  /** Optional start offset in seconds for `video` playback (default 0). */
  videoStart?: number;
  /** Optional playback speed multiplier for `video` (default 1.0). */
  videoPlaybackRate?: number;
  /** Horizontal anchor as fraction of width (0..1, default 0.5). */
  x?: number;
  /** Feet baseline vertical anchor as fraction of height (0..1, default 0.72). */
  y?: number;
  /** Character scale multiplier (default 1.0). */
  scale?: number;
  /** Optional dance BPM override (defaults to top-level bpm or 155). */
  bpm?: number;
  /** Pose switches per beat (e.g. 2 = double-time fluid dance for 8-12 pose packs). */
  poseRate?: number;
  /** Blend character smoothly into dark night scenes (exposure, soft focus, rim wrap, default true). */
  nightGrade?: boolean;
  /** Render ground shadow & wet floor reflection (default true). */
  shadow?: boolean;
  /** Single 0-based scene index that triggers the final 'bang!' pose + impact VFX. */
  bangScene?: number;
  /** Array of 0-based scene indices that trigger 'bang!' pose + glass shatter + recoil shake. */
  bangScenes?: number[];
};

export type GlitchConfig = {
  /** Overall glitch intensity 0..1 (default 0.65). */
  intensity?: number;
  /** Show subtle unified CRT scanlines + film grain (default true). */
  scanlines?: boolean;
  /** Show subtle animated film grain over whole composition (default true). */
  grain?: boolean;
  /** Drifting nocturnal street smoke / exhaust mist wrapping lower frame & character feet (default true). */
  smoke?: boolean;
  /** Silky dark/luminous dissolve feather across scene cut boundaries (default true). */
  dissolve?: boolean;
};

export type ShortProps = {
  theme?: string | Partial<Theme> | null;
  font?: FontName | null;
  fps?: number | null;
  /** 1 is normal. Above 1 is faster, below 1 slower. */
  pace?: number | null;
  /** Snap every cut to the beat of the music (unless exactTiming is true). */
  bpm?: number | null;
  /** Preserve exact scene.seconds cut timestamps instead of rounding to BPM grid. */
  exactTiming?: boolean | null;
  music?: { src: string; volume?: number; start?: number } | null;
  /** Photo or looping video behind every scene. */
  background?: string | null;
  /** Dim opacity applied over photo/video backdrops (0..0.9, default 0.66). */
  backdropDim?: number | null;
  /** Procedural Option A visual engine: ambient (default), particles, ellipse, or timeline. */
  visualMode?: VisualMode | null;
  /** Option B beat-synced chibi/anime dance overlay configuration. */
  chibi?: ChibiConfig | null;
  /** Unified post-processing glitch / databug / scanline / film grain layer over whole frame. */
  glitch?: GlitchConfig | boolean | null;
  /** Optional understated editorial signature watermark (e.g. "saditlm"). */
  watermark?: string | null;
  /** Small credit line, e.g. "Data: USGS". */
  footer?: string | null;
  /** Shown on the end scene, e.g. "@yourhandle". */
  handle?: string | null;
  highlightStyle?: "box" | "color" | null;
  /** Show "2/5" on list items. */
  progress?: boolean | null;
  /** Built-in sound effects (cut whoosh, highlight pop, count ticks, hook hit). On unless false. */
  sfx?: boolean | null;
  /** Sound effect volume, 0 to 1 (default 1). */
  sfxVolume?: number | null;
  scenes: Scene[];
  /** Filled in by calculateMetadata. */
  layout?: SceneLayout[];
  warnings?: string[];
  resolvedTheme?: Theme;
};
