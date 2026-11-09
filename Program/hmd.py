#!/usr/bin/env python3
"""Scrubgnome - privacy pass for phone videos (Modules 1 + 2).

  python3 hmd.py report  in.mp4             # list metadata leaks
  python3 hmd.py scrub   in.mp4 out.mp4 [--fake-time ISO]
  python3 hmd.py clean   in.mp4 out.mp4 [--offset-db 5] [--playback-spl 90]
  python3 hmd.py protect in.mp4 out.mp4     # clean, then scrub
"""
import argparse, os, tempfile
from hmd import scrub as S, clean as C, media as M

def show(findings):
    for cat, where, k, v in findings:
        print(f"  [{cat:8}] {where}: {k} = {v}")
    print(f"  leak score: {S.score(findings)}/100")

def do_clean(src, dst, a):
    x, sr = M.read_audio(src)
    y, stats = C.clean(x, sr, a.offset_db, a.playback_spl, warmth=a.warmth,
                       phase_mode=a.phase_mode, smooth_frames=a.smooth_frames)
    print("  cleaner:", stats)
    if M.is_video(src) or dst.lower().endswith((".mp4", ".mov", ".m4a")):
        with tempfile.TemporaryDirectory() as td:
            w = os.path.join(td, "c.wav"); M.write_wav(w, y, sr)
            M.replace_audio(src, w, dst)
    else:
        M.write_wav(dst, y, sr)

p = argparse.ArgumentParser()
p.add_argument("cmd", choices=["report", "scrub", "clean", "protect"])
p.add_argument("src"); p.add_argument("dst", nargs="?")
p.add_argument("--fake-time"); p.add_argument("--offset-db", type=float, default=5.0)
p.add_argument("--playback-spl", type=float, default=90.0)
p.add_argument("--warmth", type=float, default=1.0, help="0..1 de-tinny strength (default 1.0; 0 = off)")
p.add_argument("--phase-mode", choices=["noise","random","preserve"], default="noise", dest="phase_mode", help="masked-bin re-phasing (default noise = smoothest, no wind)")
p.add_argument("--smooth-frames", type=int, default=7, dest="smooth_frames", help="temporal smoothing of the noise bed, in STFT frames (default 7)")
a = p.parse_args()
if a.cmd == "report":
    show(S.report(a.src))
elif a.cmd == "scrub":
    print("before:"); show(S.report(a.src))
    print("after:"); show(S.scrub(a.src, a.dst, a.fake_time))
elif a.cmd == "clean":
    do_clean(a.src, a.dst, a)
else:
    with tempfile.TemporaryDirectory() as td:
        mid = os.path.join(td, "mid.mp4"); do_clean(a.src, mid, a)
        print("before:"); show(S.report(a.src))
        print("after:"); show(S.scrub(mid, a.dst, a.fake_time))
