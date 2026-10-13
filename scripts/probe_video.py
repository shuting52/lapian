#!/usr/bin/env python3
"""Probe a video file and print/optionally save its metadata as JSON."""
import json
import subprocess
import sys
from pathlib import Path


def probe(video: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", video],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    vstreams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    astreams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    v = vstreams[0] if vstreams else {}
    dar = v.get("display_aspect_ratio")
    return {
        "file": str(Path(video).name),
        "duration_sec": round(float(data.get("format", {}).get("duration", 0)), 1),
        "width": v.get("width"),
        "height": v.get("height"),
        "aspect_ratio": dar,
        "fps": v.get("avg_frame_rate"),
        "video_codec": v.get("codec_name"),
        "has_audio": bool(astreams),
        "audio_codec": astreams[0].get("codec_name") if astreams else None,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: probe_video.py <video> [meta.json]", file=sys.stderr)
        sys.exit(2)
    meta = probe(sys.argv[1])
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"saved -> {sys.argv[2]}", file=sys.stderr)


if __name__ == "__main__":
    main()
