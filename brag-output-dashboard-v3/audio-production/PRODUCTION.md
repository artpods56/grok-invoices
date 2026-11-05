# Narrated README demo

Completed on the preview branch with ElevenLabs MCP. The final video is `../narrated.mp4`; the original `../brag.mp4` remains preserved.

## Casting and story

George (warm male narrator) describes the platform; Jessica (bright conversational female voice) asks the client a question only in the micro-demo. Stock voice IDs and selected generation IDs are in `generation-manifest.json`. Model: Eleven v4. The question is a scripted illustration, not a recording of a live bot or telephone integration.

The five lines are in `voice-script.json`. Their measured source durations are 3.04, 3.68, 5.04, 4.16 and 3.92 seconds. They start at 0.15, 3.60, 7.55, 13.85 and 19.30 seconds. No voice is sped up or cut. The last complete brand frame at 22.3 seconds holds through the end, giving a total of 23.6 seconds.

## Music and mix

Eleven Music v2 generated a 23-second instrumental ambient technology bed: calm, optimistic, 88 BPM, warm pads, sparse digital plucks, muted pulse and gentle bass. No vocals were requested. The exact prompt remains in the ElevenLabs flow `79ewMAhxZEGXTmBX7Ak1`.

Speech is normalized to -19 LUFS before the final mix, music to -37 LUFS, with sidechain ducking under voices. A quiet two-note synthetic cue marks the client assistant entrance. Old stock music and card effects are replaced in the narrated cut. Final two-pass normalization targets -16 LUFS and -1 dBTP. The encoded MP4 measures -16.06 LUFS and -1.45 dBTP.

## Reproduction and verification

From the repository root, with Python and FFmpeg on PATH:

```sh
python brag-output-dashboard-v3/audio-production/mix.py
```

This reconstructs the mix from committed source takes, writes `composition/assets/music/narrated-mix.wav` and muxes a new `narrated.mp4`. The HyperFrames composition also references the mixed soundtrack and extended outro. The deterministic mixer preserves the inspected visual master and holds its final frame; a fresh HyperFrames render may continue the subtle background motion during that hold.

Verification: source duration measurements; Scribe readback of all five speech-node transcripts; full final MP4 decode; codec, dimensions, frame count and loudness checks. See `verification.json`. Automated transcription and loudness checks do not constitute a subjective listening review. Scene and final-frame inspection covers visual output. No live KSeF, bot or phone call was exercised.

## Delivery

README contains a thumbnail and a link to the actual committed MP4 on `preview/narrated-dashboard-demo`. The owner will review and merge. No merge or production deployment is part of this delivery. Signed provider URLs and authentication material are excluded from committed provenance.
