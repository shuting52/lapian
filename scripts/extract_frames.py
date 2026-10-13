#!/usr/bin/env python3
"""Extract analysis frames from a video.

Two passes:
  1. keyframes/  - one frame per detected scene change (shot boundaries)
  2. overview/   - one frame per second as a fallback timeline
"""
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: extract_frames.py <video> <out_dir>", file=sys.stderr)
        sys.exit(2)
    video, out = sys.argv[1], Path(sys.argv[2])
    key = out / "keyframes"
    ovr = out / "overview"
    key.mkdir(parents=True, exist_ok=True)
    ovr.mkdir(parents=True, exist_ok=True)

    run(["ffmpeg", "-y", "-v", "error", "-i", video,
         "-vf", "select='gt(scene,0.35)',scale=960:-1",
         "-vsync", "vfr", str(key / "kf_%04d.jpg")])
    run(["ffmpeg", "-y", "-v", "error", "-i", video,
         "-vf", "fps=1,scale=960:-1",
         str(ovr / "sec_%04d.jpg")])
    n_key = len(list(key.glob("*.jpg")))
    n_ovr = len(list(ovr.glob("*.jpg")))
    print(f"keyframes: {n_key} -> {key}")
    print(f"overview : {n_ovr} -> {ovr}")


if __name__ == "__main__":
    main()
