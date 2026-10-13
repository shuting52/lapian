#!/usr/bin/env python3
"""Build a 10fps contact sheet for a time zone.

Usage: zone_montage.py <video> <start_sec> <duration_sec> <out.jpg>

Use it to verify a detect_cuts.py candidate: a hard cut shows an
instant content jump between adjacent tiles; a continuous whip-pan
shows progressive directional motion blur across tiles.
"""
import math
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 5:
        print("usage: zone_montage.py <video> <start> <dur> <out.jpg>",
              file=sys.stderr)
        sys.exit(2)
    video = sys.argv[1]
    start, dur, out = float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    n = int(10 * dur)
    cols, rows = 5, math.ceil(n / 5)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-ss", str(start), "-t", str(dur), "-i", video,
         "-vf", f"fps=10,scale=320:-1,tile={cols}x{rows}", out],
        check=True)
    print(f"{n} frames ({start}s +{dur}s) -> {out}")


if __name__ == "__main__":
    main()
