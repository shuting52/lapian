#!/usr/bin/env python3
"""Detect black segments (fades to black / black tails).

Usage: detect_black.py <video> <out.json>

Outputs {"black_segments": [{"start": 65.33, "end": 65.4, "duration": 0.07}]}.
A 2-frame black tail is a hard ending, NOT a fade-out: report it
as-is instead of writing "淡出".
"""
import json
import re
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: detect_black.py <video> <out.json>", file=sys.stderr)
        sys.exit(2)
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", sys.argv[1],
         "-vf", "blackdetect=d=0.05:pix_th=0.05",
         "-f", "null", "-"],
        capture_output=True, text=True)
    segs = []
    for m in re.finditer(r"black_start:([0-9.]+).*?black_end:([0-9.]+)",
                         p.stderr):
        s, e = float(m.group(1)), float(m.group(2))
        segs.append({"start": round(s, 2), "end": round(e, 2),
                     "duration": round(e - s, 2)})
    json.dump({"black_segments": segs},
              open(sys.argv[2], "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({"black_segments": segs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
