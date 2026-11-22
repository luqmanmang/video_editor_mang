# Independent Video QA
Review rendered frames and audio, never infer visual success solely from CLI exit 0.
Visual: A-roll present, no decorative headline, no graphic replacing >1/2 of talking-head timeline, face visible during hook and payoff, subtitle not doubled.
Story: Hook→viewer prediction→WTS→payoff trace; no context distortion; quotation/subtitles match actual speech.
Cut: inspect 3 frames before and after boundary, avoid mid-word/unnatural jump/audio clipping; first 3–5 s deserves denser review.
Technical: ffprobe codec/duration/fps/resolution, ffmpeg full decode, loudness scan, visual contact sheet. Human playback is mandatory to claim editorial completion.
Asset: rights and SHA256 manifest. Fail if B-roll claimed but rendered file does not contain a verified B-roll clip.
Record explicit PASS/FAIL/BLOCKED per dimension, not fabricated score.
