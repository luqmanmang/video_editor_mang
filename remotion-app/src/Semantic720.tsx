import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, OffthreadVideo, Sequence,
  interpolate, staticFile, useCurrentFrame,
} from "remotion";

/** Render-only contract from validated private timeline_compiler.py. */
type Clip = {
  clip_id: string; src: string; from_frame: number; duration_frames: number;
  trim_before_frames: number; base_scale: number; captions_burned: boolean;
};
type Zoom = {
  beat_id: string; mode: "SUBTLE" | "EMPHASIS";
  from_frame: number; duration_frames: number; max_relative_scale: number;
};
type CaptionCue = {start_frame: number; end_frame: number; text: string; segment_id: string};
type Broll = {
  beat_id: string; src: string; from_frame: number;
  duration_frames: number; muted: true; caption_cues: CaptionCue[];
};
export type SemanticTimeline = {
  schema_version: "1.0.0"; project_id: string;
  private_preview_only: true; publish_allowed: false;
  export: {width: 720; height: 1280; fps: 30};
  duration_in_frames: number; render_ready: boolean;
  blocked_reasons: string[];
  clips: Clip[]; brolls: Broll[]; motions: Zoom[];
  headline_requests: unknown[];
};
export type SemanticProps = {timeline: SemanticTimeline};

const blank: SemanticTimeline = {
  schema_version: "1.0.0", project_id: "preview-placeholder",
  private_preview_only: true, publish_allowed: false,
  export: {width: 720, height: 1280, fps: 30},
  duration_in_frames: 30, render_ready: true, blocked_reasons: [],
  clips: [], brolls: [], motions: [], headline_requests: [],
};
const clamp = {extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const};
const zoomAt = (absolute: number, motions: Zoom[]): number => {
  const event = motions.find((m) =>
    absolute >= m.from_frame && absolute < m.from_frame + m.duration_frames);
  if (!event) return 1;
  const elapsed = absolute - event.from_frame;
  const dur = Math.max(1, event.duration_frames);
  const push = Math.max(1, Math.floor(dur * 0.28));
  const pull = Math.max(push + 1, Math.floor(dur * 0.70));
  if (elapsed < push) {
    return interpolate(elapsed, [0, push], [1, event.max_relative_scale], {
      ...clamp, easing: Easing.inOut(Easing.cubic),
    });
  }
  if (elapsed <= pull) return event.max_relative_scale;
  return interpolate(elapsed, [pull, dur], [event.max_relative_scale, 1], {
    ...clamp, easing: Easing.inOut(Easing.cubic),
  });
};

const ARoll: React.FC<{clip: Clip; motions: Zoom[]}> = ({clip, motions}) => {
  const absolute = clip.from_frame + useCurrentFrame();
  const relative = zoomAt(absolute, motions);
  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={staticFile(clip.src)} muted trimBefore={clip.trim_before_frames}
        durationInFrames={clip.duration_frames}
        style={{
          width: "100%", height: "100%", objectFit: "cover",
          transform: "scale(" + clip.base_scale * relative + ")",
          transformOrigin: "center center",
        }}
      />
      <Audio src={staticFile(clip.src)}
        trimBefore={clip.trim_before_frames} volume={1}/>
    </AbsoluteFill>
  );
};

const SemanticVideo: React.FC<SemanticProps> = ({timeline}) => {
  if (timeline.export.width !== 720 || timeline.export.height !== 1280 ||
      timeline.export.fps !== 30) throw new Error("720x1280@30fps only");
  if (!timeline.render_ready || timeline.headline_requests.length)
    throw new Error("Unresolved headline/cut gate");
  return (
    <AbsoluteFill style={{background: "#101010"}}>
      {timeline.clips.map((c) => (
        <Sequence key={c.clip_id} from={c.from_frame}
          durationInFrames={c.duration_frames} name={"A-roll " + c.clip_id}>
          <ARoll clip={c} motions={timeline.motions}/>
        </Sequence>
      ))}
      {timeline.brolls.map((b) => (
        <Sequence key={b.beat_id} from={b.from_frame}
          durationInFrames={b.duration_frames} name={"B-roll " + b.beat_id}>
          <OffthreadVideo src={staticFile(b.src)} muted
            style={{width: "100%", height: "100%", objectFit: "cover"}}/>
          {b.caption_cues.map((cue) => (
            <Sequence key={cue.segment_id}
              from={cue.start_frame - b.from_frame}
              durationInFrames={cue.end_frame - cue.start_frame}
              layout="none">
              <AbsoluteFill style={{
                alignItems: "center", justifyContent: "flex-end",
                paddingBottom: 150, pointerEvents: "none",
              }}>
                <div style={{
                  maxWidth: "86%", padding: "9px 15px",
                  fontSize: 28, fontWeight: 700, lineHeight: 1.24,
                  fontFamily: "Arial, sans-serif", textAlign: "center",
                  color: "#FFFFFF", background: "rgba(0,0,0,0.78)",
                  borderRadius: 9, overflowWrap: "break-word",
                }}>{cue.text}</div>
              </AbsoluteFill>
            </Sequence>
          ))}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const Semantic720: React.FC = () => (
  <Composition id="Semantic720" component={SemanticVideo}
    width={720} height={1280} fps={30} durationInFrames={30}
    defaultProps={{timeline: blank}}
    calculateMetadata={({props}) => {
      const t = props.timeline;
      if (t.export.width !== 720 || t.export.height !== 1280 ||
          t.export.fps !== 30) throw new Error("Invalid export metadata");
      return {durationInFrames: Math.max(1, t.duration_in_frames)};
    }}
  />
);
