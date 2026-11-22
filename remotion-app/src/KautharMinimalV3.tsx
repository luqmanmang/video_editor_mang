import React from "react";
import {AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, staticFile} from "remotion";

/** Minimal A-roll-first pilot. Existing source captions are burned into A-roll. */
const FPS = 30;
const segments = [
  {file:"01_hook.mp4", duration:5.92},
  {file:"02_experience.mp4", duration:8.89},
  {file:"03_time.mp4", duration:3.10},
  {file:"04_time_why.mp4", duration:5.79},
  {file:"05_give.mp4", duration:3.35},
  {file:"06_give_example.mp4", duration:6.04},
  {file:"07_payoff.mp4", duration:4.50},
].map((s)=>({...s,frames:Math.round(s.duration*FPS)}));
const offsets = segments.map((_,i)=>segments.slice(0,i).reduce((a,s)=>a+s.frames,0));
const LENGTH=segments.reduce((a,s)=>a+s.frames,0);

/** Illustrative CC0 footage, muted; the source spoken audio continues underneath. */
const inserts=[
  {source:"stock/experience.webm", from:8.20, duration:2.65, captions:[
    {start:0,end:1.3,text:"kalau kita berbelanja"},
    {start:1.3,end:2.65,text:"untuk pengalaman"}
  ]},
  {source:"stock/giving.webm",from:27.60,duration:2.75,captions:[
    {start:0,end:1.4,text:"kita mungkin belanja orang makan"},
    {start:1.4,end:2.75,text:"kita bagi hadiah"}
  ]},
];

/* Caption words are provisional extracts from the source transcript:
   require actual audiovisual listening/alignment before public release. */
const BrollInsert: React.FC<{item: typeof inserts[number]}> = ({item}) => {
  return <AbsoluteFill style={{background:"#111"}}>
    <OffthreadVideo src={staticFile(item.source)} muted style={{width:"100%",height:"100%",objectFit:"cover"}} />
    {item.captions.map((line,i)=><Sequence key={i} from={Math.round(line.start*FPS)} durationInFrames={Math.round((line.end-line.start)*FPS)}>
      <AbsoluteFill style={{justifyContent:"flex-end",alignItems:"center",paddingBottom:130,pointerEvents:"none"}}>
        <div style={{fontFamily:"Arial,sans-serif",color:"#fff",background:"rgba(0,0,0,0.70)",
          borderRadius:8,padding:"9px 15px",maxWidth:"88%",textAlign:"center",fontSize:34,
          fontWeight:600,lineHeight:1.26,textShadow:"0px 2px 5px #000"}}>{line.text}</div>
      </AbsoluteFill>
    </Sequence>)}
  </AbsoluteFill>;
};

const Video:React.FC=()=>(
  <AbsoluteFill style={{background:"#101010"}}>
    {segments.map((seg,i)=>(
      <Sequence key={seg.file} from={offsets[i]} durationInFrames={seg.frames}>
        <OffthreadVideo src={staticFile("media/"+seg.file)} muted
          style={{width:"100%",height:"100%",objectFit:"cover"}}/>
        <Audio src={staticFile("media/"+seg.file)} volume={(f)=>Math.max(0,Math.min(.98,f/3,(seg.frames-f)/3))}/>
      </Sequence>
    ))}
    <Audio src={staticFile("media/ambient.wav")} volume={0.045}/>
    {inserts.map((item,i)=>(
      <Sequence key={i} from={Math.round(item.from*FPS)} durationInFrames={Math.round(item.duration*FPS)}>
        <BrollInsert item={item}/>
      </Sequence>
    ))}
  </AbsoluteFill>
);
export const KautharMinimalV3:React.FC=()=>(
  <Composition id="KautharMinimalV3" component={Video}
    width={720} height={1280} fps={FPS} durationInFrames={LENGTH}/>
);
