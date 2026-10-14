#!/usr/bin/env python3
"""Verify an AI e-commerce remake plan and its assembled output.

Usage: verify_remake.py <remake-plan.json> <out.mp4>

remake-plan.json: remake_plan.py 产物
out.mp4         : assemble_remake.py 产物

检查：镜头编号连续、timecode 首尾相接、每镜画面/配音文件存在、
成片时长与原片误差 ≤0.5s、分辨率与目标一致。
字幕/swap 未填只告警（人工环节），不判 FAIL。
"""
import json
import subprocess
import sys
from pathlib import Path

TOL = 0.06


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: verify_remake.py <remake-plan.json> <out.mp4>", file=sys.stderr)
        sys.exit(2)
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    out_f = sys.argv[2]
    shots = plan["shots"]
    src = plan["source"]
    total, W, H = src["duration_sec"], src["target_w"], src["target_h"]

    if not shots:
        fail("换皮计划里没有镜头")
    for i, s in enumerate(shots, 1):
        want = f"SH{i:02d}"
        if s["id"] != want:
            fail(f"镜头编号应为 {want}，实际为 {s['id']}")
        if s["end"] <= s["start"]:
            fail(f"{s['id']} 起止时间非法")
    if abs(shots[0]["start"]) > TOL:
        fail(f"SH01 起始不是 0，而是 {shots[0]['start']}")
    for a, b in zip(shots, shots[1:]):
        if abs(a["end"] - b["start"]) > TOL:
            fail(f"{a['id']} 结束 {a['end']} 与 {b['id']} 开始 {b['start']} 不相接")

    for s in shots:
        sid = s["id"]
        candidates = [Path(s["clip"]), Path("clips") / f"{sid}.mp4",
                      Path("clips") / f"{sid}.png", Path("clips") / f"{sid}.jpg"]
        if not any(p.exists() for p in candidates):
            fail(f"{sid} 找不到画面文件（{s['clip']}）")
        vaud = [Path(s["voice"])] + [Path("voice") / f"{sid}{e}"
                                     for e in (".wav", ".mp3", ".m4a")]
        if not any(p.exists() for p in vaud):
            fail(f"{sid} 找不到配音文件（{s['voice']}）")
        if not s.get("subtitle", {}).get("text", "").strip():
            print(f"WARN: {sid} 字幕文字未填")
        sw = s.get("swap", {})
        if not sw.get("subject_new"):
            print(f"WARN: {sid} swap.subject_new 未填（重绘提示词待写）")
        if not s.get("product_ref"):
            print(f"WARN: {sid} 未关联产品图")

    if not Path(out_f).exists():
        fail(f"成片 {out_f} 不存在：先跑 assemble_remake.py")
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", out_f],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(probe.stdout)
    dur = float(data["format"]["duration"])
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    if abs(dur - total) > 0.5:
        fail(f"成片时长 {dur:.1f}s 与原片 {total}s 误差超 0.5s")
    if v.get("width") != W or v.get("height") != H:
        fail(f"成片分辨率 {v.get('width')}x{v.get('height')} 与目标 {W}x{H} 不符")

    print(f"PASS: {len(shots)} 镜连续，文件齐备，成片 {dur:.1f}s / {W}x{H}")


if __name__ == "__main__":
    main()
