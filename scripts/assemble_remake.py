#!/usr/bin/env python3
"""Assemble an AI e-commerce remake video from per-shot clips and voiceovers.

Usage: assemble_remake.py <remake-plan.json> <clips_dir> <voice_dir> <out.mp4>
                           [--font FONT] [--no-sub]

remake-plan.json: remake_plan.py output (per-shot timecode/subtitle/swap filled)
clips_dir : per-shot visuals clips/SH01.mp4 (missing mp4 may be SH01.png/jpg
            still, auto slow push-in applied)
voice_dir : per-shot voiceovers voice/SH01.wav (wav/mp3/m4a ok)
out.mp4   : output film

Assembly rules: voiceovers are concatenated into ONE track and encoded to AAC
a single time (never concat split AAC with -c copy); per-shot audio is padded
with apad+atrim to the exact shot duration; final duration must be within
0.5s of the source.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STILL_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg"}


def fail(msg):
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def find_file(d, stem, exts):
    for e in sorted(exts):
        p = d / (stem + e)
        if p.exists():
            return p
    return None


def find_font(cli_font):
    if cli_font:
        return cli_font
    try:
        out = subprocess.run(["fc-list", ":lang=zh", "file"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            f = line.split(":")[0].strip()
            if f.lower().endswith((".ttf", ".otf", ".ttc")):
                return f
    except FileNotFoundError:
        pass
    for p in Path("/usr/share/fonts").rglob("*"):
        if p.suffix.lower() in (".ttf", ".otf", ".ttc") and any(
                k in p.name.lower() for k in ("noto", "wqy", "cjk", "droid")):
            return str(p)
    return None


def wrap_cjk(text, max_chars):
    """Wrap CJK text to max_chars per line (1 char ~ 1em wide)."""
    max_chars = max(4, max_chars)
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= max_chars:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def fesc(path):
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def main():
    args = sys.argv[1:]
    if len(args) < 4:
        print("usage: assemble_remake.py <remake-plan.json> <clips_dir> "
              "<voice_dir> <out.mp4> [--font FONT] [--no-sub]",
              file=sys.stderr)
        sys.exit(2)
    plan_f, clips_d, voice_d, out_f = args[0], Path(args[1]), Path(args[2]), args[3]
    cli_font, no_sub = None, False
    i = 4
    while i < len(args):
        if args[i] == "--font" and i + 1 < len(args):
            cli_font = args[i + 1]
            i += 2
        elif args[i] == "--no-sub":
            no_sub = True
            i += 1
        else:
            i += 1

    plan = json.load(open(plan_f, encoding="utf-8"))
    shots = plan["shots"]
    W, H, FPS = (plan["source"]["target_w"], plan["source"]["target_h"],
                 plan["source"]["fps"])
    total = plan["source"]["duration_sec"]
    if not shots:
        fail("remake-plan.json has no shots")

    font = find_font(cli_font)
    if not font and not no_sub:
        fail("no CJK font found: pass --font /path/to/font.ttf")

    subdir = Path(tempfile.mkdtemp(prefix="lapian_sub_"))
    try:
        _run(plan, shots, W, H, FPS, total, clips_d, voice_d, out_f,
             font, no_sub, subdir)
    finally:
        shutil.rmtree(subdir, ignore_errors=True)


def _run(plan, shots, W, H, FPS, total, clips_d, voice_d, out_f,
         font, no_sub, subdir):
    # --- inputs & filters ---
    inputs, fc = [], []
    vlabels, alabels = [], []
    ninputs = 0
    for n, s in enumerate(shots):
        sid, D = s["id"], s["end"] - s["start"]
        frames = max(1, round(D * FPS))
        clip = find_file(clips_d, sid, {".mp4", ".mov"})
        if clip is None:
            clip = find_file(clips_d, sid, STILL_EXTS)
        if clip is None:
            fail("%s: no visual in %s (need %s.mp4 or still)"
                 % (sid, clips_d, sid))
        voice = find_file(voice_d, sid, AUDIO_EXTS)
        if voice is None:
            fail("%s: no voiceover in %s" % (sid, voice_d))
        vi = ninputs
        if clip.suffix.lower() in STILL_EXTS:
            inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(clip)]
            fc.append(
                "[%d:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                "crop=%d:%d,setsar=1,zoompan=z='min(zoom+0.0012\\,1.12)':"
                "d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d,"
                "trim=duration=%s,setpts=PTS-STARTPTS[v%d]"
                % (vi, W, H, W, H, frames, W, H, FPS, D, n))
        else:
            inputs += ["-i", str(clip)]
            fc.append(
                "[%d:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                "crop=%d:%d,setsar=1,fps=%d,trim=duration=%s,"
                "setpts=PTS-STARTPTS[v%d]" % (vi, W, H, W, H, FPS, D, n))
        ninputs += 1
        ai = ninputs
        inputs += ["-i", str(voice)]
        ninputs += 1
        fc.append("[%d:a]aresample=44100,apad,atrim=0:%s,asetpts=PTS-STARTPTS[a%d]"
                 % (ai, D, n))
        vlabels.append("[v%d]" % n)
        alabels.append("[a%d]" % n)

    n = len(shots)
    fc.append("%sconcat=n=%d:v=1:a=0[vcat]" % ("".join(vlabels), n))
    fc.append("%sconcat=n=%d:v=0:a=1[acat]" % ("".join(alabels), n))

    # --- subtitles (textfile + wrap, no overflow) ---
    vcur = "[vcat]"
    if not no_sub:
        for k, s in enumerate(shots):
            st, en = s["start"], s["end"]
            raw = s.get("subtitle", {}).get("text", "").strip()
            if not raw:
                continue
            style = s.get("subtitle", {}).get("style", "plain")
            if style == "hook":
                fs = int(H * 0.075)
            elif style == "feature":
                fs = int(H * 0.055)
            elif style == "cta":
                fs = int(H * 0.065)
            else:
                fs = int(H * 0.055)
            wrapped = wrap_cjk(raw, int(W / (fs * 1.02)))
            tf = subdir / ("sub_%d.txt" % k)
            tf.write_text(wrapped, encoding="utf-8")
            en_expr = "gte(t\\,%s)*lt(t\\,%s)" % (st, en)
            base = ("drawtext=fontfile='%s':textfile='%s':fontsize=%d:"
                    % (font, fesc(str(tf)), fs))
            if style == "hook":
                fc.append(
                    "%s%sfontcolor=#FFD21F:borderw=3:bordercolor=black:"
                    "x=(w-text_w)/2:y=h*0.16:enable='%s'[vsub%d]"
                    % (vcur, base, en_expr, k))
            elif style == "feature":
                _lines = wrapped.count("\n") + 1
                bar_h = int(_lines * fs * 1.45)
                bar_y = int(H - H * 0.068) - bar_h
                fc.append(
                    "%sdrawbox=y=%d:w=iw:h=%d:color=0xCC0000:t=fill:"
                    "enable='%s'[vbox%d]" % (vcur, bar_y, bar_h, en_expr, k))
                fc.append(
                    "[vbox%d]%sfontcolor=white:"
                    "x=(w-text_w)/2:y=%d+(%d-text_h)/2:enable='%s'[vsub%d]"
                    % (k, base, bar_y, bar_h, en_expr, k))
            elif style == "cta":
                fc.append(
                    "%s%sfontcolor=white:borderw=3:bordercolor=black:"
                    "x=(w-text_w)/2:y=(h-text_h)/2:enable='%s'[vsub%d]"
                    % (vcur, base, en_expr, k))
            else:
                fc.append(
                    "%s%sfontcolor=white:borderw=2:bordercolor=black:"
                    "x=(w-text_w)/2:y=h-text_h-90:enable='%s'[vsub%d]"
                    % (vcur, base, en_expr, k))
            vcur = "[vsub%d]" % k

    cmd = (["ffmpeg", "-y"] + inputs
           + ["-filter_complex", ";".join(fc),
              "-map", vcur, "-map", "[acat]",
              "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
              "-r", str(FPS),
              "-c:a", "aac", "-b:a", "128k",  # voiceover encoded once
              out_f])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        fail("ffmpeg assembly failed: %s" % r.stderr[-1500:])

    # --- duration check ---
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", out_f],
        capture_output=True, text=True, check=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    if abs(dur - total) > 0.5:
        fail("output %.1fs vs source %ss: drift over 0.5s" % (dur, total))
    print("PASS: %s (%d shots, %.1fs, subtitles %s)"
          % (out_f, n, dur, "off" if no_sub else "on"))


if __name__ == "__main__":
    main()
