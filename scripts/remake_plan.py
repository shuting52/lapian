#!/usr/bin/env python3
"""Build a remake plan for AI e-commerce video remake.

Usage: remake_plan.py <shots.json> <meta.json> <copy.txt> <products_dir>
                       [-o remake-plan.json] [--target 1080x1920]

shots.json : shot list {"shots": [{"id": "SH01", "start": 0.0, "end": 3.2}, ...]}
meta.json  : probe_video.py output (needs duration_sec)
copy.txt   : voiceover copy, one segment per line. A line may start with a
             shot tag like [SH01] (brackets are the CJK fullwidth kind);
             lines without a tag map to shots in order.
products_dir: product photos directory (jpg/png/webp)

Output remake-plan.json: per-shot timecode, voiceover, subtitle slot,
product reference, and empty swap fields (subject_orig/new, background_new).
"""
import json
import re
import sys
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
# CJK fullwidth brackets used as shot tags in copy.txt, as code points
# so the source stays pure ASCII.
LBR = chr(0x3010)
RBR = chr(0x3011)


def parse_copy(text):
    """Return [(shot_id or None, copy_text), ...]."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^" + LBR + r"(SH\d+)" + RBR + r"\s*(.*)$", line)
        if not m:
            m = re.match(r"^(SH\d+)\s*[:\uff1a]\s*(.*)$", line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
        else:
            out.append((None, line))
    return out


def parse_fps(s, default=30):
    try:
        if isinstance(s, str) and "/" in s:
            a, b = s.split("/")
            return round(float(a) / float(b)) if float(b) else default
        return int(float(s))
    except (TypeError, ValueError):
        return default


def main():
    args = sys.argv[1:]
    if len(args) < 4:
        print("usage: remake_plan.py <shots.json> <meta.json> <copy.txt> "
              "<products_dir> [-o remake-plan.json] [--target 1080x1920]",
              file=sys.stderr)
        sys.exit(2)
    shots_f, meta_f, copy_f, products_d = args[0], args[1], args[2], args[3]
    out_f = "remake-plan.json"
    target = "1080x1920"
    i = 4
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            out_f = args[i + 1]
            i += 2
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        else:
            i += 1

    shots = json.load(open(shots_f, encoding="utf-8"))["shots"]
    meta = json.load(open(meta_f, encoding="utf-8"))
    total = meta.get("duration_sec", 0)
    fps = parse_fps(meta.get("fps"), 30)
    tw, th = target.lower().split("x")

    copy_segs = parse_copy(Path(copy_f).read_text(encoding="utf-8"))
    by_id = {sid: t for sid, t in copy_segs if sid}
    seq = [t for sid, t in copy_segs if not sid]

    pdir = Path(products_d)
    if pdir.is_dir():
        products = sorted(p.name for p in pdir.iterdir()
                          if p.suffix.lower() in IMG_EXTS)
    else:
        products = []

    warnings = []
    if len(copy_segs) != len(shots):
        warnings.append(
            "copy segments (%d) != shot count (%d): align copy first, "
            "do not touch the timeline" % (len(copy_segs), len(shots)))
    if not products:
        warnings.append("no product photos in %s: product must use real photos"
                        % products_d)

    plan_shots = []
    for idx, s in enumerate(shots):
        sid = s["id"]
        voice = by_id.get(sid, seq[idx] if idx < len(seq) else "")
        if not voice:
            warnings.append("%s has no voiceover copy" % sid)
        plan_shots.append({
            "id": sid,
            "start": s["start"],
            "end": s["end"],
            "duration": round(s["end"] - s["start"], 1),
            "voiceover": voice,
            "subtitle": {"text": "", "style": "plain"},
            "product_ref": products[idx % len(products)] if products else "",
            "clip": "clips/%s.mp4" % sid,
            "voice": "voice/%s.wav" % sid,
            "swap": {"subject_orig": "", "subject_new": "",
                     "background_new": ""},
        })

    plan = {
        "source": {
            "duration_sec": total,
            "target_w": int(tw),
            "target_h": int(th),
            "fps": fps,
        },
        "products": products,
        "shots": plan_shots,
        "warnings": warnings,
        "note": "fill subtitle.text and swap fields manually: subtitle keywords "
                "from copy (style follows sync-map.md); swap when writing prompts "
                "with assets/remake-prompt-template.md.",
    }
    Path(out_f).write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("saved -> %s (%d shots, %d product photos)"
          % (out_f, len(shots), len(products)))
    for w in warnings:
        print("WARN: %s" % w)


if __name__ == "__main__":
    main()
