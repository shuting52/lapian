#!/usr/bin/env python3
"""Verify shot list continuity against video metadata.

Usage: verify_lapian.py <shots.json> <meta.json>

shots.json: {"shots": [{"id": "SH01", "start": 0.0, "end": 3.2}, ...]}
meta.json : output of probe_video.py (needs duration_sec)

Checks: ids are sequential SH01..., first shot starts at 0,
shots are contiguous, last shot ends at total duration.
"""
import json
import sys

TOL = 0.06  # timecode 保留 1 位小数时的容差


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: verify_lapian.py <shots.json> <meta.json>", file=sys.stderr)
        sys.exit(2)
    shots = json.load(open(sys.argv[1], encoding="utf-8"))["shots"]
    total = json.load(open(sys.argv[2], encoding="utf-8"))["duration_sec"]

    if not shots:
        fail("镜头清单为空")
    for i, s in enumerate(shots, 1):
        want = f"SH{i:02d}"
        if s["id"] != want:
            fail(f"镜头编号应为 {want}，实际为 {s['id']}")
        if s["end"] <= s["start"]:
            fail(f"{s['id']} 起止时间非法：{s['start']} -> {s['end']}")
    if abs(shots[0]["start"]) > TOL:
        fail(f"SH01 起始不是 0，而是 {shots[0]['start']}")
    for a, b in zip(shots, shots[1:]):
        if abs(a["end"] - b["start"]) > TOL:
            fail(f"{a['id']} 结束 {a['end']} 与 {b['id']} 开始 {b['start']} 不相接")
    if abs(shots[-1]["end"] - total) > 0.15:
        fail(f"末镜头结束 {shots[-1]['end']} 与总时长 {total} 不符")

    print(f"PASS: {len(shots)} 个镜头，编号连续，timecode 首尾相接，总时长 {total}s")


if __name__ == "__main__":
    main()
