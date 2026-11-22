import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, interpolate, OffthreadVideo,
  Sequence, staticFile, useCurrentFrame,
} from "remotion";

/**
 * Kauthar 720p A/B private headline pilot.
 * Uses the *previously edited* Kauthar V3.1 media, without altering speech.
 * Headline masking is a deliberate opaque TikTok-style panel, NOT inpainting.
 * B-roll captions from V3.1 remain provisional and require human listening.
 * Creator/source rights remain UNCLEARED. PRIVATE PREVIEW ONLY.
 */
const FPS = 30;
const parts = [
  {file: "00_prediction_setup.mp4", duration: 14.56, base: 1.17, motion: false},
  {file: "02_experience.mp4", duration: 8.89, base: 1.00, motion: true},
  {file: "03_time.mp4", duration: 3.10, base: 1.00, motion: false},
  {file: "04_time_why.mp4", duration: 5.79, base: 1.00, motion: true},
  {file: "05_give.mp4", duration: 3.35, base: 1.00, motion: false},
  {file: "06_give_example.mp4", duration: 6.04, base: 1.00, motion: true},
  {file: "07_payoff.mp4", duration: 4.50, base: 1.00, motion: true},
].map((s) => ({...s, frames: Math.round(s.duration * FPS)}));
const offsets = parts.map((_, i) =>
  parts.slice(0, i).reduce((total, part) => total + part.frames, 0));
const LENGTH = parts.reduce((total, part) => total + part.frames, 0);

type Caption = {start: number; end: number; text: string};
const inserts: {file: string; from: number; duration: number; captions: Caption[]}[] = [
  {file: "stock/experience.mp4", from: 16.84, duration: 2.65,
    captions: [
      {start: 0, end: 1.30, text: "kalau kita berbelanja"},
      {start: 1.30, end: 2.65, text: "untuk pengalaman"},
    ]},
  {file: "stock/giving.mp4", from: 36.24, duration: 2.75,
    captions: [
      {start: 0, end: 1.40, text: "kita mungkin belanja orang makan"},
      {start: 1.40, end: 2.75, text: "kita bagi hadiah"},
    ]},
];

const SubtleARoll: React.FC<{part: typeof parts[number]}> = ({part}) => {
  const f = useCurrentFrame();
  let z = 1;
  if (part.motion && part.frames > 60) {
    const inEnd = Math.max(1, Math.round(part.frames * 0.28));
    const outStart = Math.max(inEnd + 1, Math.round(part.frames * 0.72));
    z = interpolate(f, [0, inEnd, outStart, part.frames],
      [1, 1.025, 1.025, 1], {
        extrapolateLeft: "clamp", extrapolateRight: "clamp",
        easing: Easing.inOut(Easing.cubic),
      });
  }
  return (
    <AbsoluteFill style={{overflow: "hidden", background: "#111"}}>
      <OffthreadVideo src={staticFile("media/" + part.file)} muted
        style={{
          width: "100%", height: "100%", objectFit: "cover",
          transform: "scale(" + (part.base * z) + ")",
          transformOrigin: part.file === "00_prediction_setup.mp4"
            ? "center bottom" : "center center",
        }}/>
    </AbsoluteFill>
  );
};

const BrollInsert: React.FC<{item: typeof inserts[number]}> = ({item}) => (
  <AbsoluteFill style={{background: "#111"}}>
    <OffthreadVideo src={staticFile(item.file)} muted
      style={{width: "100%", height: "100%", objectFit: "cover"}}/>
    {item.captions.map((cue, index) => (
      <Sequence key={index} from={Math.round(cue.start * FPS)}
        durationInFrames={Math.round((cue.end - cue.start) * FPS)}>
        <AbsoluteFill style={{
          alignItems: "center", justifyContent: "flex-end",
          paddingBottom: 151, pointerEvents: "none",
        }}>
          <div style={{
            fontFamily: "Arial, sans-serif", fontSize: 30,
            fontWeight: 700, lineHeight: 1.2, color: "#fff",
            background: "rgba(0,0,0,0.80)", borderRadius: 9,
            padding: "8px 15px", maxWidth: "85%", textAlign: "center",
          }}>{cue.text}</div>
        </AbsoluteFill>
      </Sequence>
    ))}
  </AbsoluteFill>
);

type HeadlineVariant = "A" | "B";
const copy: Record<HeadlineVariant, [string, string]> = {
  A: ["NAK BAHAGIA,", "BELANJA UNTUK APA?"],
  B: ["RUMAH BESAR", "BUKAN JAWAPANNYA?"],
};

/**
 * Measured from Kauthar source screenshots: old baked panel spans approximately
 * x=76..648, y=185..314 of 720x1280; opaque replacement is x=62..658,
 * y=169..315. Headline visible only while original top text is present.
 * Source face/hair can rise near y=312 in later opening frames; check QA.
 */
const Headline: React.FC<{variant: HeadlineVariant}> = ({variant}) => (
  <AbsoluteFill style={{pointerEvents: "none"}}>
    <div style={{
      position: "absolute", top: 168, left: 62, width: 596,
      height: 147, background: "#FFFFFF", borderRadius: 14,
      display: "flex", flexDirection: "column",
      justifyContent: "center", alignItems: "center",
      boxSizing: "border-box", padding: "10px 15px",
      boxShadow: "0 2px 3px rgba(0,0,0,0.06)",
    }}>
      {copy[variant].map((line, i) => (
        <div key={i} style={{
          fontFamily: "Arial, sans-serif",
          fontWeight: 800, fontSize: variant === "A" ? 43 : 45,
          color: "#101010", lineHeight: 1.18,
          letterSpacing: "-0.85px", whiteSpace: "nowrap",
          textAlign: "center",
        }}>{line}</div>
      ))}
    </div>
  </AbsoluteFill>
);

const KautharPilot: React.FC<{variant: HeadlineVariant}> = ({variant}) => (
  <AbsoluteFill style={{background: "#101010"}}>
    {parts.map((part, index) => (
      <Sequence key={part.file} from={offsets[index]}
        durationInFrames={part.frames}>
        <SubtleARoll part={part}/>
      </Sequence>
    ))}
    {/* Extracted from previously verified -15.98 LUFS 1080 private master.
        Preserves original composite dialogue/music without recreating cuts. */}
    <Audio src={staticFile("media/kauthar_ab_master_audio.m4a")} volume={1}/>
    {inserts.map((item, index) => (
      <Sequence key={index} from={Math.round(item.from * FPS)}
        durationInFrames={Math.round(item.duration * FPS)}>
        <BrollInsert item={item}/>
      </Sequence>
    ))}
    <Sequence from={0} durationInFrames={Math.round(8.55 * FPS)}>
      <Headline variant={variant}/>
    </Sequence>
  </AbsoluteFill>
);

export const KautharHeadlineA720: React.FC = () => (
  <Composition id="KautharHeadlineA720"
    component={() => <KautharPilot variant="A"/>}
    width={720} height={1280} fps={FPS} durationInFrames={LENGTH}/>
);
export const KautharHeadlineB720: React.FC = () => (
  <Composition id="KautharHeadlineB720"
    component={() => <KautharPilot variant="B"/>}
    width={720} height={1280} fps={FPS} durationInFrames={LENGTH}/>
);
