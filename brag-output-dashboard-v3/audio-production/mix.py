"""Rebuild the narrated demo from committed ElevenLabs takes and the visual master."""

import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DURATION = 23.6
STARTS = {"hook": 0.15, "product": 3.6, "features": 7.55, "micro": 13.85, "outro": 19.3}


def run(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


with tempfile.TemporaryDirectory(prefix="grok-demo-mix-") as temporary:
    work = Path(temporary)
    for name in STARTS:
        run("-i", HERE / "generated" / f"{name}.mp3", "-af", "loudnorm=I=-19:TP=-2:LRA=7", "-ar", 48000, "-ac", 2, work / f"{name}.wav")
    run("-i", HERE / "generated/music.mp3", "-af", "loudnorm=I=-37:TP=-4:LRA=7,afade=t=in:d=0.4,afade=t=out:st=21.6:d=1.4,apad", "-t", DURATION, "-ar", 48000, "-ac", 2, work / "music.wav")
    # A quiet two-note cue marks the switch from narrator to client assistant.
    run("-f", "lavfi", "-i", "sine=frequency=660:duration=0.12:sample_rate=48000", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.18:sample_rate=48000", "-filter_complex", "[0:a]afade=t=out:st=0.02:d=0.1[a];[1:a]afade=t=out:st=0.02:d=0.16,adelay=140[b];[a][b]amix=inputs=2:normalize=0,volume=0.16,adelay=13580", "-ac", 2, work / "cue.wav")
    inputs = []
    filters = []
    for index, (name, start) in enumerate(STARTS.items()):
        inputs += ["-i", work / f"{name}.wav"]
        filters.append(f"[{index}:a]adelay={round(start * 1000)}:all=1[v{index}]")
    inputs += ["-i", work / "music.wav", "-i", work / "cue.wav"]
    filters += ["[v0][v1][v2][v3][v4]amix=inputs=5:normalize=0:duration=longest,apad,asplit=2[voice][side]", "[5:a][side]sidechaincompress=threshold=0.02:ratio=3:attack=15:release=220[bed]", "[voice][bed][6:a]amix=inputs=3:normalize=0:duration=longest[mix]"]
    run(*inputs, "-filter_complex", ";".join(filters), "-map", "[mix]", "-t", DURATION, work / "premix.wav")
    measurement = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(work / "premix.wav"), "-af", "loudnorm=I=-16:TP=-1:LRA=7:print_format=json", "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
    values, _ = json.JSONDecoder().raw_decode(measurement[measurement.rfind("{"):])
    normalization = f"loudnorm=I=-16:TP=-1:LRA=7:measured_I={values['input_i']}:measured_TP={values['input_tp']}:measured_LRA={values['input_lra']}:measured_thresh={values['input_thresh']}:offset={values['target_offset']}:linear=true"
    mix = ROOT / "composition/assets/music/narrated-mix.wav"
    run("-i", work / "premix.wav", "-af", normalization, "-ar", 48000, "-ac", 2, mix)
    # Keep the already inspected visual edit and let the last brand frame breathe.
    run("-i", ROOT / "brag.mp4", "-i", mix, "-map", "0:v:0", "-map", "1:a:0", "-vf", "trim=duration=22.3,tpad=stop_mode=clone:stop_duration=1.3", "-t", DURATION, "-c:v", "libx264", "-crf", 18, "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", ROOT / "narrated.mp4")
