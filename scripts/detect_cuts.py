#!/usr/bin/env python3
"""Detect candidate hard-cut timestamps via ffmpeg scene detection.

Usage: detect_cuts.py <video> <out.json> [threshold=0.4]

Outputs {"threshold": 0.4, "cuts": [28.43, 65.33]}.
Candidates are NOT confirmed cuts: fast whip-pans in handheld footage
also trigger the detector. Verify each candidate with zone_montage.py
before cutting the shot list.
"""
import json
import re
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: detect_cuts.py <video> <out.json> [threshold]",
              file=sys.stderr)
        sys.exit(2)
    video, out = sys.argv[1], sys.argv[2]
    th = float(sys.argv[3]) if len(sys.argv) > 3 else 0.4
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", video,
         "-filter:v", f"select='gt(scene,{th})',showinfo",
         "-f", "null", "-"],
        capture_output=True, text=True)
    raw = sorted({round(float(m.group(1)), 2)
                  for m in re.finditer(r"pts_time:([0-9.]+)", p.stderr)})
    merged: list[float] = []
    for c in raw:
        if not merged or c - merged[-1] > 0.5:
            merged.append(c)
    json.dump({"threshold": th, "cuts": merged},
              open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({"cuts": merged}, ensure_ascii=False))


if __name__ == "__main__":
    main()
