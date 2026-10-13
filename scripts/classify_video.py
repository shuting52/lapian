#!/usr/bin/env python3
"""Heuristic video-type suggestion for the 拉片 workflow.

Reads meta.json, cuts.json, audio.json and computes a few extra signals
(motion level, mid-video motion dip, mean saturation), then suggests likely
content types with evidence.

The output is a SUGGESTION, not a decision: the analyst must confirm the
type before writing lapian.md. When in doubt, fall back to the generic
full-dimension workflow (domains.md 通用兜底).

Usage:
    classify_video.py <video> <meta.json> <cuts.json> <audio.json>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def motion_stats(video, fps=5):
    """Sample at `fps`, return (mean_motion, min_window_dip).
    min_window_dip = lowest 1.5s-window mean / global mean.
    A sustained slow-mo/morph beat shows as min_window_dip << 1."""
    from PIL import Image, ImageChops
    import glob
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                    "-vf", f"fps={fps},scale=160:-1", str(tmp / "f_%03d.jpg")],
                   check=True, capture_output=True)
    files = sorted(glob.glob(str(tmp / "f_*.jpg")))
    if len(files) < 6:
        return 0.0, 1.0
    prev = Image.open(files[0]).convert("L")
    vals = []
    for f in files[1:]:
        im = Image.open(f).convert("L")
        d = ImageChops.difference(im, prev)
        px = list(d.getdata())
        vals.append(sum(px) / len(px))
        prev = im
    n = len(vals)
    mean = sum(vals) / n
    wsize = max(3, int(1.5 * fps))
    best = 1.0
    for i in range(0, n - wsize + 1):
        wmean = sum(vals[i:i + wsize]) / wsize
        best = min(best, wmean / mean if mean > 0 else 1.0)
    return mean, best


def mean_saturation(video):
    """Mean HSV saturation over 5 sampled frames (0-255)."""
    from PIL import Image
    import glob
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                    "-vf", "fps=1,scale=80:-1", str(tmp / "s_%03d.jpg")],
                   check=True, capture_output=True)
    files = sorted(glob.glob(str(tmp / "s_*.jpg")))[:5]
    sats = []
    for f in files:
        hsv = Image.open(f).convert("HSV")
        s = list(hsv.getdata())
        sats.append(sum(px[1] for px in s) / len(s))
    return sum(sats) / max(1, len(sats))


def soft_change_count(video, threshold=0.15):
    """Count sub-hard-cut scene changes. A cluster of soft changes with zero
    hard cuts is the signature of an in-shot morph (e.g. outfit change)."""
    import glob
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                        "-vf", f"select='gt(scene,{threshold})'",
                        "-vsync", "vfr", str(tmp / "sc_%04d.jpg")],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return 0
    return len(glob.glob(str(tmp / "sc_*.jpg")))


def main():
    if len(sys.argv) < 5:
        print("usage: classify_video.py <video> <meta.json> <cuts.json> <audio.json>",
              file=sys.stderr)
        sys.exit(2)
    video, meta, cuts, audio = sys.argv[1:5]
    m, c, a = load(meta), load(cuts), load(audio)

    w, h = m.get("width", 0), m.get("height", 0)
    vertical = h > w if w and h else None
    dur = m.get("duration_sec", 0)
    raw_cuts = c.get("cuts", [])
    # 忽略片尾 0.6s 内的检出（只是视频结束，不是切点）
    n_cuts = sum(1 for t in raw_cuts if t < dur - 0.6)
    loud = a.get("mean_volume_db", -99) > -20
    has_audio = a.get("has_audio", False)

    if not m:
        print(json.dumps({"suggestions": [
            {"type": "通用（缺少输入文件）", "confidence": "—",
             "evidence": ["meta.json 缺失或不可读，走全维度流程"]}],
            "signals": {}, "confirmed_type": None}, ensure_ascii=False, indent=2))
        return

    mean_motion, motion_dip = motion_stats(video)
    sat = mean_saturation(video)
    n_soft = soft_change_count(video) if n_cuts == 0 else 0

    suggestions = []

    def add(t, conf, ev):
        suggestions.append({"type": t, "confidence": conf, "evidence": ev})

    # 换装变身（优先判定，避免被舞蹈规则吞掉）：
    # 无硬切 + 中段持续低运动量（morph/慢放 beat）+ 短片长
    if n_cuts == 0 and motion_dip < 0.75 and dur < 30:
        add("换装变身", "高" if vertical else "中",
            [f"无硬切，最低1.5s窗口运动量降至{motion_dip:.0%}（morph/慢放特征）", f"片长{dur:.0f}s"])
    elif n_cuts == 0 and n_soft >= 3 and dur < 30:
        add("换装变身", "高" if vertical else "中",
            [f"无硬切但有{n_soft}处软场景变化（疑似镜内morph）", f"片长{dur:.0f}s"])
    # 舞蹈 / 动作模仿：竖屏、单镜头、响亮音频、高运动量、无中段大低谷
    if vertical and n_cuts == 0 and has_audio and loud and mean_motion > 5 \
            and motion_dip >= 0.75:
        add("舞蹈/动作模仿", "高",
            [f"竖屏{h}x{w}", "单镜头无切点", f"音频响亮({a['mean_volume_db']:.1f}dB)",
             f"运动量高({mean_motion:.1f})"])
    # 影视短剧：横屏、多切点
    if not vertical and n_cuts >= 2:
        add("影视短剧", "中", [f"横屏{w}x{h}", f"{n_cuts}个切点"])
    # 白模/白膜：低饱和 + 慢速运镜（低运动量）
    if sat < 40 and mean_motion < 5 and n_cuts <= 1:
        add("白模/白膜视频", "中", [f"平均饱和度低({sat:.0f})", f"运动量低({mean_motion:.1f})"])
    # AI 电商：竖屏、切点少、中等时长（弱信号，仅提示）
    if vertical and n_cuts <= 2 and 10 < dur < 60 and mean_motion < 8:
        add("AI电商", "低", ["竖屏", f"{n_cuts}个切点", "运动量中等偏低（需人工确认是否有产品特写）"])

    if not suggestions:
        add("通用（未识别出强特征）", "—", ["走全维度流程，人工判定类型"])

    print(json.dumps({"suggestions": suggestions,
                      "signals": {"vertical": vertical, "duration_sec": dur,
                                  "n_cuts": n_cuts, "mean_motion": round(mean_motion, 1),
                                  "motion_dip": round(motion_dip, 2),
                                  "mean_saturation": round(sat, 1),
                                  "mean_volume_db": a.get("mean_volume_db")},
                      "confirmed_type": None},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
