import React from "react";
import {
  AbsoluteFill,
  Audio,
  Composition,
  Easing,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

/** Educational private demonstration using independently edited creator excerpts. */
const FPS = 30;
const segments = [
  { file: "01_hook.mp4", seconds: 5.92, section: "MASALAH" },
  { file: "02_experience.mp4", seconds: 8.89, section: "PENGALAMAN" },
  { file: "03_time.mp4", seconds: 3.10, section: "MASA" },
  { file: "04_time_why.mp4", seconds: 5.79, section: "MASA" },
  { file: "05_give.mp4", seconds: 3.35, section: "ORANG LAIN" },
  { file: "06_give_example.mp4", seconds: 6.04, section: "ORANG LAIN" },
  { file: "07_payoff.mp4", seconds: 4.50, section: "PAYOFF" },
].map((item) => ({ ...item, frames: Math.round(item.seconds * FPS) }));
const offsets = segments.map((_, i) =>
  segments.slice(0, i).reduce((n, v) => n + v.frames, 0),
);
const LENGTH = segments.reduce((n, v) => n + v.frames, 0);

const C = {
  bg: "#08111f",
  navy: "#142139",
  white: "#f1f6ff",
  muted: "#a4b0ce",
  cyan: "#60d8ff",
  purple: "#a393ff",
  green: "#bbffb1",
  gold: "#ffdd91",
};

const full: React.CSSProperties = {
  width: "100%",
  height: "100%",
};

const SceneBg: React.FC = () => (
  <AbsoluteFill
    style={{
      background: "radial-gradient(ellipse at 72% 24%, #29315b 0%, #121a31 43%, #070f1f 90%)",
    }}
  >
    <AbsoluteFill
      style={{
        opacity: 0.26,
        backgroundSize: "45px 45px",
        backgroundImage:
          "linear-gradient(#b6cdfc18 1px, transparent 1px),linear-gradient(90deg,#b6cdfc18 1px,transparent 1px)",
      }}
    />
    <div
      style={{
        position: "absolute",
        width: 510,
        height: 510,
        left: -210,
        bottom: -100,
        borderRadius: 999,
        background: "#5873e94a",
        filter: "blur(95px)",
      }}
    />
  </AbsoluteFill>
);

const TextTag: React.FC<{ text: string; accent?: string }> = ({
  text,
  accent = C.cyan,
}) => (
  <div
    style={{
      alignSelf: "flex-start",
      color: accent,
      background: "#112139ec",
      border: "1px solid #96b9f044",
      padding: "12px 20px",
      borderRadius: 14,
      fontSize: 22,
      fontWeight: 800,
      letterSpacing: 3,
    }}
  >
    {text}
  </div>
);

const ComingIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  x?: number;
  y?: number;
}> = ({ children, delay = 0, x = 0, y = 40 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = spring({
    fps,
    frame: frame - delay,
    config: { damping: 18, stiffness: 125, mass: 0.9 },
  });
  return (
    <div
      style={{
        opacity: interpolate(frame, [delay, delay + 12], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
        transform: `translate(${(1 - t) * x}px,${(1 - t) * y}px)`,
      }}
    >
      {children}
    </div>
  );
};

const ExperienceBroll: React.FC = () => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, 150], [0, 1], {
    extrapolateRight: "clamp",
  });
  const cards = [
    { icon: "✈", title: "TRAVEL", detail: "Kenangan baru", rotate: -13, x: -170, y: -40, color: "#253c60" },
    { icon: "♡", title: "BERSAMA", detail: "Orang tersayang", rotate: 8, x: 110, y: 40, color: "#243056" },
    { icon: "☼", title: "MOMENT", detail: "Lebih bermakna", rotate: -3, x: -15, y: 185, color: "#344567" },
  ];
  return (
    <AbsoluteFill>
      <SceneBg />
      <div style={{ position: "absolute", top: 126, left: 58, right: 50 }}>
        <TextTag text="01 / PENGALAMAN" />
        <div style={{ fontSize: 61, fontWeight: 900, lineHeight: 1.12, marginTop: 33, letterSpacing: -3 }}>
          BUKAN SEMUA <span style={{ color: C.cyan }}>NILAI</span><br />ADA PADA BARANG.
        </div>
        <div style={{ color: C.muted, fontSize: 28, marginTop: 27 }}>
          Memori yang kita bina bersama.
        </div>
      </div>
      <AbsoluteFill style={{ top: 460 }}>
        {cards.map((c, i) => (
          <div
            key={c.title}
            style={{
              position: "absolute",
              left: 210 + c.x,
              top: 90 + c.y,
              width: 410,
              height: 390,
              padding: 29,
              borderRadius: 29,
              color: C.white,
              background: c.color,
              border: "2px solid #cad7ff4b",
              boxShadow: "0 32px 80px #0009",
              transform: `translateY(${Math.sin(f / 23 + i) * 9}px) translateX(${(1 - t) * (i - 1) * 115}px) rotate(${c.rotate}deg)`,
              opacity: interpolate(f, [i * 10, i * 10 + 18], [0, 1], {
                extrapolateLeft: "clamp", extrapolateRight: "clamp"
              }),
            }}
          >
            <div
              style={{
                height: 226, borderRadius: 22, display: "flex", alignItems: "center", justifyContent: "center",
                background: i === 0 ? "linear-gradient(135deg,#72d5f7,#1d5d96)" : i === 1 ? "linear-gradient(135deg,#b0a1ef,#514a86)" : "linear-gradient(135deg,#ffcd84,#915d4b)",
                fontSize: 116, fontWeight: 400,
              }}
            >
              {c.icon}
            </div>
            <div style={{ fontSize: 37, marginTop: 15, fontWeight: 900 }}>{c.title}</div>
            <div style={{ fontSize: 22, marginTop: 4, color: "#becae9" }}>{c.detail}</div>
          </div>
        ))}
      </AbsoluteFill>
      <div style={{ position: "absolute", bottom: 172, left: 60, right: 60, fontSize: 30, textAlign: "center", color: "#d4dff4" }}>
        <span style={{ color: C.green, fontWeight: 900 }}>PENGALAMAN</span> &gt; SEKADAR PEMBELIAN
      </div>
    </AbsoluteFill>
  );
};

const ClockBroll: React.FC = () => {
  const f = useCurrentFrame();
  const turn = interpolate(f, [0, 170], [-48, 35], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <AbsoluteFill>
      <SceneBg />
      <div style={{ position: "absolute", top: 129, left: 60 }}>
        <TextTag text="02 / MASA" accent={C.gold} />
        <div style={{ fontSize: 70, fontWeight: 900, lineHeight: 1.06, marginTop: 34, letterSpacing: -2 }}>
          DUIT BOLEH<br /><span style={{ color: C.gold }}>BELI BALIK MASA.</span>
        </div>
        <div style={{ fontSize: 27, marginTop: 25, color: C.muted }}>
          Supaya kita boleh fokus pada benda bermakna.
        </div>
      </div>
      <div style={{ position: "absolute", top: 510, left: 78, width: 564, height: 564, borderRadius: "50%", border: "15px solid #99bbed", boxShadow: "0 0 120px #4d79fc55, inset 0 0 80px #75b5ff22", background: "radial-gradient(circle,#182c51,#101d38)" }}>
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i / 12) * Math.PI * 2;
          return (
            <div key={i} style={{
              position: "absolute", width: 10, height: i % 3 === 0 ? 35 : 20,
              left: 257 + Math.sin(a) * 233, top: 257 - Math.cos(a) * 233,
              background: i % 3 === 0 ? "#e3ebff" : "#91a8cc",
              borderRadius: 10, transform: `translate(-50%,-50%) rotate(${i * 30}deg)`,
            }} />
          );
        })}
        <div style={{
          position: "absolute", width: 15, height: 194, background: C.cyan,
          left: 260, top: 101, borderRadius: 20, transformOrigin: "center bottom",
          transform: `rotate(${turn}deg)`, boxShadow: "0 0 21px #72dffcaa"
        }} />
        <div style={{
          position: "absolute", width: 17, height: 134, background: C.white,
          left: 258, top: 159, borderRadius: 20, transformOrigin: "center bottom", transform: `rotate(${turn / 2 + 85}deg)`
        }} />
        <div style={{ position: "absolute", left: 251, top: 247, width: 37, height: 37, borderRadius: "50%", background: C.gold }} />
      </div>
      <ComingIn delay={20} x={80}>
        <div style={{
          position: "absolute", right: 41, top: 880, background: "#eff4ff", color: "#142547", padding: "25px 24px",
          borderRadius: 24, boxShadow: "0 18px 60px #0007", width: 240,
        }}>
          <div style={{ color: "#566891", fontSize: 21, fontWeight: 700 }}>DIBELI BALIK</div>
          <div style={{ fontWeight: 900, fontSize: 65, marginTop: 3 }}>TIME</div>
          <div style={{ fontWeight: 700, fontSize: 19, marginTop: 3 }}>UNTUK DIRI KITA</div>
        </div>
      </ComingIn>
      <div style={{ position: "absolute", bottom: 140, left: 60, right: 50, fontSize: 31, color: C.white, textAlign: "left" }}>
        KURANGKAN KERJA REPEAT.<br /><span style={{ color: C.cyan, fontWeight: 900 }}>TAMBAH MASA YANG BERMAKNA.</span>
      </div>
    </AbsoluteFill>
  );
};

const GiftBroll: React.FC = () => {
  const f = useCurrentFrame();
  const pulse = 1 + Math.sin(f / 8) * .04;
  const rise = interpolate(f, [5, 38], [105, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <SceneBg />
      <div style={{ position: "absolute", top: 130, left: 60, right: 50 }}>
        <TextTag text="03 / ORANG LAIN" accent={C.green} />
        <div style={{ fontSize: 67, fontWeight: 900, lineHeight: 1.05, marginTop: 30, letterSpacing: -3 }}>
          BERIKAN <span style={{ color: C.green }}>NILAI</span><br />PADA ORANG LAIN.
        </div>
        <div style={{ fontSize: 27, marginTop: 22, color: C.muted }}>
          Belanja makan, hadiah, kongsi rezeki.
        </div>
      </div>
      <div style={{
        position: "absolute", top: 600, left: 115, width: 490, height: 450,
        transform: `translateY(${rise}px) scale(${pulse})`,
        filter: "drop-shadow(0 38px 42px #0009)",
      }}>
        <div style={{ position: "absolute", left: 55, top: 123, width: 380, height: 305, background: "linear-gradient(130deg,#75d6eb,#2d7bb2)", borderRadius: 20, border: "6px solid #b2edff" }} />
        <div style={{ position: "absolute", left: 36, top: 100, width: 420, height: 92, background: "linear-gradient(160deg,#c4eaff,#5baddf)", borderRadius: 17, boxShadow: "0 12px 30px #0005" }} />
        <div style={{ position: "absolute", left: 215, top: 104, width: 66, height: 322, background: "linear-gradient(90deg,#a3a2ff,#6859d7)" }} />
        <div style={{ position: "absolute", left: 92, top: 18, width: 170, height: 102, border: "32px solid #a798ff", borderRadius: "100% 100% 40% 100%", transform: "rotate(22deg)" }} />
        <div style={{ position: "absolute", left: 238, top: 18, width: 165, height: 103, border: "32px solid #a798ff", borderRadius: "100% 100% 100% 40%", transform: "rotate(-25deg)" }} />
      </div>
      {Array.from({ length: 15 }, (_, i) => {
        const x = 75 + (i * 151) % 570, y = 495 + (i * 109) % 510;
        const v = Math.sin(f / 15 + i) * 10;
        return <div key={i} style={{
          position: "absolute", left: x, top: y + v,
          width: 6 + (i % 3) * 4, height: 6 + (i % 3) * 4,
          borderRadius: "50%", background: i % 2 ? C.gold : C.green,
          opacity: interpolate(f, [i * 3, i * 3 + 18], [0, 0.95], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          }),
        }} />;
      })}
      <ComingIn delay={25} x={-45}>
        <div style={{
          position: "absolute", left: 65, right: 65, bottom: 160,
          fontSize: 34, color: C.white, fontWeight: 900,
          padding: "29px 32px", border: "1px solid #9cbad555",
          background: "#132741c9", borderRadius: 25, textAlign: "center",
        }}>
          "BAHAGIA" BUKAN SEMESTINYA<br />TAMBAH <span style={{ color: C.green }}>BARANG.</span>
        </div>
      </ComingIn>
    </AbsoluteFill>
  );
};

const TalkingHead: React.FC<{ file: string; label: string; frames: number }> = ({
  file, label, frames,
}) => {
  const f = useCurrentFrame();
  const scale = interpolate(f, [0, frames], [1.015, 1.055], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "#090e18" }}>
      <OffthreadVideo
        src={staticFile("media/" + file)}
        muted
        style={{ ...full, objectFit: "cover", transform: `scale(${scale})` }}
      />
      <AbsoluteFill style={{ background: "linear-gradient(#040b1b8c,transparent 22%,transparent 72%,#0b10226b)" }} />
      <div style={{
        position: "absolute", top: 100, left: 38, fontSize: 21,
        fontWeight: 900, letterSpacing: 2, color: C.white,
        padding: "14px 21px", border: "1px solid #ffffff55",
        background: "#0b1326aa", borderRadius: 12,
      }}>{label}</div>
      <div style={{
        position: "absolute", bottom: 125, right: 25,
        color: "#e1e6f3dd", background: "#091b2bbb", padding: "6px 10px",
        borderRadius: 8, fontSize: 15, letterSpacing: 1
      }}>KAUTHAR ROZMAL · PRIVATE EDIT</div>
    </AbsoluteFill>
  );
};

const PayoffCards: React.FC = () => (
  <AbsoluteFill>
    <SceneBg />
    <div style={{ position: "absolute", top: 126, left: 58, right: 55 }}>
      <TextTag text="KESIMPULAN" accent={C.green} />
      <div style={{ fontSize: 74, fontWeight: 900, marginTop: 35, letterSpacing: -2, lineHeight: 1.03 }}>
        BELANJA UNTUK<br /><span style={{ color: C.green }}>MAKNA.</span>
      </div>
      <div style={{ marginTop: 27, fontSize: 27, color: C.muted }}>
        Tiga cara alternatif guna duit.
      </div>
    </div>
    {[
      { n: "01", t: "PENGALAMAN", s: "Bina kenangan", color: C.cyan },
      { n: "02", t: "MASA", s: "Dapatkan masa kembali", color: C.gold },
      { n: "03", t: "ORANG LAIN", s: "Kongsi kegembiraan", color: C.green },
    ].map((c, i) => (
      <ComingIn key={c.n} delay={i * 12} x={65}>
        <div style={{
          position: "absolute", top: 575 + i * 205, left: 60, right: 60, height: 160,
          display: "flex", alignItems: "center", gap: 26, padding: 30,
          background: "linear-gradient(120deg,#223454f8,#111f37ed)",
          border: "2px solid #afc7f247", borderRadius: 24,
          boxShadow: "0 16px 45px #0007"
        }}>
          <div style={{ color: c.color, fontSize: 50, fontWeight: 900 }}>{c.n}</div>
          <div>
            <div style={{ fontSize: 37, fontWeight: 900, color: C.white }}>{c.t}</div>
            <div style={{ fontSize: 25, color: C.muted, marginTop: 3 }}>{c.s}</div>
          </div>
        </div>
      </ComingIn>
    ))}
    <div style={{ position: "absolute", bottom: 172, left: 65, fontSize: 20, color: C.muted }}>
      EDITORIAL COMPILATION • NOT FINANCIAL ADVICE
    </div>
  </AbsoluteFill>
);

const startSec = (s: number) => Math.round(s * FPS);
const Broll = ({ from, duration, children }: { from: number; duration: number; children: React.ReactNode }) => (
  <Sequence from={startSec(from)} durationInFrames={startSec(duration)}>
    <AbsoluteFill>{children}</AbsoluteFill>
  </Sequence>
);

const ProductionMark: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{
        position: "absolute", top: 22, left: 0, height: 5, width: (f / LENGTH * 100) + "%",
        background: "linear-gradient(90deg,#9b92ff,#61d8ff)", boxShadow: "0 0 14px #60d8ff77"
      }} />
      <div style={{
        position: "absolute", left: 35, bottom: 37, fontSize: 17,
        letterSpacing: 2, color: "#f4f5ffb0", textShadow: "0 1px 5px #000",
      }}>STORY EDIT / 01</div>
    </AbsoluteFill>
  );
};

export const KautharPilot: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg, fontFamily: "Arial, Helvetica, sans-serif" }}>
    {segments.map((seg, i) => (
      <Sequence key={seg.file} from={offsets[i]} durationInFrames={seg.frames}>
        <TalkingHead file={seg.file} label={seg.section} frames={seg.frames} />
        <Audio
          src={staticFile("media/" + seg.file)}
          volume={(f) => Math.max(0, Math.min(0.96, f / 3, (seg.frames - f) / 3))}
        />
      </Sequence>
    ))}
    <Audio src={staticFile("media/ambient.wav")} volume={0.11} />
    {/* The HyperFrames graph is a real pre-rendered motion-video insert. */}
    <Broll from={1.20} duration={3.20}>
      <OffthreadVideo src={staticFile("motion/spike_drop.mp4")} muted style={{ ...full, objectFit: "cover" }} />
    </Broll>
    {/* These explain the narration visually rather than faking real-world footage. */}
    <Broll from={8.10} duration={5.3}><ExperienceBroll /></Broll>
    <Broll from={17.08} duration={5.35}><ClockBroll /></Broll>
    <Broll from={26.47} duration={4.35}><GiftBroll /></Broll>
    <Broll from={34.00} duration={3.55}><PayoffCards /></Broll>
    <Sequence from={startSec(1.20)} durationInFrames={10}>
      <Audio src={staticFile("media/whoosh.wav")} volume={0.28} />
    </Sequence>
    <Sequence from={startSec(8.1)} durationInFrames={10}>
      <Audio src={staticFile("media/whoosh.wav")} volume={0.22} />
    </Sequence>
    <Sequence from={startSec(17.08)} durationInFrames={10}>
      <Audio src={staticFile("media/whoosh.wav")} volume={0.22} />
    </Sequence>
    <Sequence from={startSec(26.47)} durationInFrames={10}>
      <Audio src={staticFile("media/chime.wav")} volume={0.20} />
    </Sequence>
    <Sequence from={startSec(34)} durationInFrames={10}>
      <Audio src={staticFile("media/chime.wav")} volume={0.18} />
    </Sequence>
    <ProductionMark />
  </AbsoluteFill>
);

export const MyComposition: React.FC = () => (
  <Composition
    id="KautharPremiumPilot"
    component={KautharPilot}
    durationInFrames={LENGTH}
    fps={FPS}
    width={720}
    height={1280}
  />
);
