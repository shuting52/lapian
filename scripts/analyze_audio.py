#!/usr/bin/env python3
"""Summarize the audio track: loudness + silent intervals.

Usage: analyze_audio.py <video> <out.json>

Outputs {"has_audio": true, "mean_volume_db": -20.7,
"max_volume_db": -4.4, "silent_intervals": [], ...}.
Content type (music / field sound / dialogue) still needs human
listening: never infer it from loudness alone, mark [待确认].
"""
import json
import re
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: analyze_audio.py <video> <out.json>", file=sys.stderr)
        sys.exit(2)
    video = sys.argv[1]
    has = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", video],
        capture_output=True, text=True).stdout.strip()
    if not has:
        json.dump({"has_audio": False},
                  open(sys.argv[2], "w", encoding="utf-8"), indent=2)
        print('{"has_audio": false}')
        return
    p1 = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", video, "-map", "a:0",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    mean = re.search(r"mean_volume: ([-\d.]+) dB", p1.stderr)
    maxv = re.search(r"max_volume: ([-\d.]+) dB", p1.stderr)
    p2 = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", video, "-map", "a:0",
         "-af", "silencedetect=n=-40dB:d=1.0", "-f", "null", "-"],
        capture_output=True, text=True)
    sil = [{"start": round(float(m.group(1)), 1),
            "end": round(float(m.group(2)), 1)}
           for m in re.finditer(r"silence_start: ([0-9.]+).*?"
                                r"silence_end: ([0-9.]+)", p2.stderr)]
    out = {"has_audio": True,
           "mean_volume_db": float(mean.group(1)) if mean else None,
           "max_volume_db": float(maxv.group(1)) if maxv else None,
           "silent_intervals": sil,
           "content_note": "内容类型（配乐/现场声/对白）需人耳确认，"
                           "勿仅凭音量推断"}
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
