#!/usr/bin/env python3
"""hidemydoppler local UI - stdlib only.

  python ui.py            # opens http://127.0.0.1:8765
  python ui.py --port N   # different port

Binds to localhost only. Uploaded/cleaned files live in ./work/.
"""
import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
# Friendly output location: when the code lives in a "Program" subfolder, put
# cleaned files in a "Cleaned videos" folder next to it (where users will look);
# otherwise keep them beside the code.
_ROOT = os.path.dirname(HERE) if os.path.basename(HERE).lower() == "program" else HERE
APP_DIR = _ROOT          # the hidemydoppler folder the uninstaller removes
WORK = os.path.join(_ROOT, "Cleaned videos")
os.makedirs(WORK, exist_ok=True)
sys.path.insert(0, HERE)

STATE = {"original": None, "cleaned": None}
CONFIG = {"hide_prep": False, "port": None}
SERVER = None   # set in main(), used by the /api/shutdown endpoint


def safe_name(name):
    name = os.path.basename(unquote(name or "upload.mp4"))
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "upload.mp4"


def report_json(path):
    from hmd import scrub
    f = scrub.report(path)
    return {"file": os.path.basename(path),
            "size_mb": round(os.path.getsize(path) / 1e6, 2),
            "score": scrub.score(f),
            "findings": [dict(cat=c, where=w, key=k, value=str(v)) for c, w, k, v in f]}


def run_prep():
    p = subprocess.run([sys.executable, os.path.join(HERE, "setup_check.py"), "--check"],
                       capture_output=True, text=True)
    return {"ok": p.returncode == 0, "output": p.stdout + p.stderr}


INSTALL = {"running": False, "done": False, "ok": None, "output": ""}


def _install_job():
    INSTALL.update(running=True, done=False, ok=None,
                   output="Installing missing prerequisites...\n"
                          "(If a password or admin prompt appears, answer it in the "
                          "terminal / pop-up.)\n\n")
    try:
        p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "setup_check.py"), "--yes"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            INSTALL["output"] += line
        INSTALL["ok"] = p.wait() == 0
    except Exception as e:
        INSTALL["output"] += f"\nInstaller crashed: {e}\n"
        INSTALL["ok"] = False
    INSTALL.update(running=False, done=True)


def run_clean(offset_db, playback_spl, warmth, phase_mode="noise",
              smooth_frames=7, tag="clean"):
    from hmd import clean as C, media as M, scrub as S
    src = STATE["original"]
    base, ext = os.path.splitext(os.path.basename(src))
    dst = os.path.join(WORK, f"{base}_{tag}{ext if M.is_video(src) else '.wav'}")
    mid = os.path.join(WORK, f".{base}_mid{ext if M.is_video(src) else '.wav'}")
    x, sr = M.read_audio(src)
    y, stats = C.clean(x, sr, offset_db, playback_spl, warmth=warmth,
                       phase_mode=phase_mode, smooth_frames=smooth_frames)
    if M.is_video(src):
        wav = os.path.join(WORK, ".tmp_clean.wav")
        M.write_wav(wav, y, sr)
        M.replace_audio(src, wav, mid)
        os.remove(wav)
        S.scrub(mid, dst)
        os.remove(mid)
    else:
        M.write_wav(dst, y, sr)
    STATE["cleaned"] = dst
    return {"stats": stats, "report": report_json(dst)}


# Level presets. Each maps a button to real parameters (see tooltips in the UI).
LEVELS = {
    1: {"kind": "scrub"},
    2: {"kind": "clean", "offset_db": 5, "playback_spl": 90, "warmth": 1.0,
        "phase_mode": "noise", "smooth_frames": 7},
    3: {"kind": "clean", "offset_db": 8, "playback_spl": 95, "warmth": 1.0,
        "phase_mode": "preserve", "smooth_frames": 7},
    4: {"kind": "clean", "offset_db": 2, "playback_spl": 80, "warmth": 1.0,
        "phase_mode": "noise", "smooth_frames": 9},
}


def run_protect(level):
    from hmd import media as M, scrub as S
    p = LEVELS[level]
    src = STATE["original"]
    if p["kind"] == "scrub":                       # Level 1: metadata only
        base, ext = os.path.splitext(os.path.basename(src))
        dst = os.path.join(WORK, f"{base}_L1{ext}")
        S.scrub(src, dst)
        STATE["cleaned"] = dst
        return {"level": level, "stats": {"mode": "metadata only (audio untouched)"},
                "report": report_json(dst)}
    out = run_clean(p["offset_db"], p["playback_spl"], p["warmth"],
                    phase_mode=p["phase_mode"], smooth_frames=p["smooth_frames"],
                    tag=f"L{level}")
    out["level"] = level
    return out


def _launch_uninstaller(keep_videos):
    """Write a detached self-deleting uninstaller, launch it, and return a note.

    It waits a few seconds for this server to exit (freeing the working dir),
    then removes the app tree. 'Cleaned videos' is kept unless keep_videos is
    False. Python/ffmpeg and pip packages are never touched."""
    app = APP_DIR
    import tempfile
    td = tempfile.gettempdir()
    if os.name == "nt":
        vids = "" if keep_videos else f'rmdir /s /q "{app}\\Cleaned videos"\r\n'
        script = (
            "@echo off\r\n"
            "timeout /t 3 /nobreak >nul\r\n"
            f'cd /d "{td}"\r\n'
            f'rmdir /s /q "{app}\\Program"\r\n'
            f'rmdir /s /q "{app}\\Guides"\r\n'
            f'del /f /q "{app}\\Launch hidemydoppler.cmd" "{app}\\Read Me First.pdf" '
            f'"{app}\\README.md" "{app}\\.gitignore" "{app}\\WHITEPAPER.pdf" 2>nul\r\n'
            f"{vids}"
            f'rmdir "{app}" 2>nul\r\n'
            '(goto) 2>nul & del "%~f0"\r\n'
        )
        path = os.path.join(td, "hmd_uninstall.bat")
        with open(path, "w") as f:
            f.write(script)
        DETACHED, NEWGROUP = 0x00000008, 0x00000200
        subprocess.Popen(["cmd", "/c", path], creationflags=DETACHED | NEWGROUP,
                         close_fds=True, cwd=td)
    else:
        vids = "" if keep_videos else f'rm -rf "{app}/Cleaned videos"\n'
        script = (
            "#!/bin/bash\n"
            "sleep 3\n"
            f'rm -rf "{app}/Program" "{app}/Guides"\n'
            f'rm -f "{app}/Launch hidemydoppler.cmd" "{app}/Read Me First.pdf" '
            f'"{app}/README.md" "{app}/.gitignore" "{app}/WHITEPAPER.pdf"\n'
            f"{vids}"
            f'rmdir "{app}" 2>/dev/null\n'
            'rm -- "$0"\n'
        )
        path = os.path.join(td, "hmd_uninstall.sh")
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        subprocess.Popen(["/bin/bash", path], start_new_session=True,
                         close_fds=True, cwd=td)
    return app


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _err(self, e):
        self._json({"error": str(e)}, 500)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                b = PAGE.replace("__HIDE_PREP__", "1" if CONFIG["hide_prep"] else "0").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                # Never let the browser serve a stale copy of the app.
                self.send_header("Cache-Control", "no-store, must-revalidate")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif u.path.startswith("/assets/"):
                self._asset(u.path[len("/assets/"):])
            elif u.path == "/api/ping":
                self._json({"app": "hidemydoppler", "version": VERSION,
                            "pid": os.getpid(), "port": CONFIG["port"]})
            elif u.path == "/api/prep":
                self._json(run_prep())
            elif u.path == "/api/install/status":
                self._json(INSTALL)
            elif u.path == "/api/rescan":
                which = q.get("which", ["cleaned"])[0]
                path = STATE.get(which) or STATE.get("original")
                if not path:
                    return self._json({"error": "No file loaded"}, 400)
                self._json(report_json(path) | {"which": which if STATE.get(which) else "original"})
            elif u.path.startswith("/media/"):
                self._media(q.get("which", ["cleaned"])[0])
            else:
                self.send_error(404)
        except Exception as e:
            self._err(e)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/upload":
                n = int(self.headers.get("Content-Length", 0))
                path = os.path.join(WORK, safe_name(self.headers.get("X-Filename")))
                with open(path, "wb") as f:
                    left = n
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                STATE.update(original=path, cleaned=None)
                self._json(report_json(path))
            elif u.path == "/api/shutdown":
                # Let a newer instance retire this one cleanly (localhost only).
                self._json({"ok": True, "pid": os.getpid()})
                if SERVER is not None:
                    threading.Thread(target=SERVER.shutdown, daemon=True).start()
            elif u.path == "/api/uninstall":
                keep = q.get("keep_videos", ["1"])[0] != "0"
                app = _launch_uninstaller(keep)
                self._json({"ok": True, "app_dir": app, "kept_videos": keep})
                # Give the response time to flush, then stop so the folder frees.
                if SERVER is not None:
                    threading.Timer(0.8, SERVER.shutdown).start()
            elif u.path == "/api/install":
                if not INSTALL["running"]:
                    threading.Thread(target=_install_job, daemon=True).start()
                self._json({"started": True})
            elif u.path == "/api/clean":
                if not STATE["original"]:
                    return self._json({"error": "Load a file first"}, 400)
                self._json(run_clean(float(q.get("offset", ["5"])[0]),
                                     float(q.get("spl", ["90"])[0]),
                                     float(q.get("warmth", ["1"])[0])))
            elif u.path == "/api/protect":
                if not STATE["original"]:
                    return self._json({"error": "Load a file first"}, 400)
                lvl = int(q.get("level", ["2"])[0])
                if lvl not in LEVELS:
                    return self._json({"error": "bad level"}, 400)
                self._json(run_protect(lvl))
            elif u.path == "/api/export-wav":
                if not STATE["original"]:
                    return self._json({"error": "Load a file first"}, 400)
                from hmd import media as M
                src = STATE["original"]
                base = os.path.splitext(os.path.basename(src))[0]
                dst = os.path.join(WORK, base + ".wav")
                M.extract_wav(src, dst)
                self._json({"path": dst, "name": os.path.basename(dst),
                            "size_mb": round(os.path.getsize(dst) / 1e6, 2)})
            else:
                self.send_error(404)
        except Exception as e:
            self._err(e)

    def _asset(self, name):
        name = os.path.basename(name)
        path = os.path.join(ASSETS, name)
        if not os.path.isfile(path):
            return self.send_error(404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _media(self, which):
        path = STATE.get(which) or STATE.get("original")
        if not path or not os.path.exists(path):
            return self.send_error(404)
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m:
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            elif m.group(2):
                start = size - int(m.group(2))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>hidemydoppler</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#262b36;--fg:#d8dde6;--mute:#8590a2;
--acc:#5fb3ff;--ok:#4cc38a;--warn:#e6b450;--bad:#ef6b6b;--twig:#5fbf3f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:12px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px}
header img.mascot{width:46px;height:46px;object-fit:contain;filter:drop-shadow(0 2px 4px #000);animation:twigbob 3.2s ease-in-out infinite}
@keyframes twigbob{0%,100%{transform:translateY(0) rotate(-1.5deg)}50%{transform:translateY(-3px) rotate(1.5deg)}}
@keyframes tippop{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){header img.mascot{animation:none}}
header h1{margin:0;font-size:19px;letter-spacing:.3px}
header .tag{color:var(--mute);font-size:12px;display:block}
#geek{margin-left:auto;background:#1b2a18;border-color:#2f4a28;color:#bfe6ad;display:flex;align-items:center;gap:6px}
#geek.on{background:var(--twig);color:#06210a;border-color:var(--twig);font-weight:600}
#geek img{width:20px;height:20px;object-fit:contain}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px;padding:16px 22px}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
h2{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:var(--mute)}
button,.file{background:#222835;color:var(--fg);border:1px solid #323a4a;border-radius:7px;
padding:7px 13px;font:inherit;cursor:pointer}button:hover,.file:hover{border-color:var(--acc)}
button.primary{background:var(--acc);color:#081320;border-color:var(--acc);font-weight:600}
button:disabled{opacity:.4;cursor:default}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=file]{display:none}input[type=number]{width:70px;background:#10131a;color:var(--fg);
border:1px solid #323a4a;border-radius:6px;padding:5px 7px}label{color:var(--mute);font-size:12px}
pre{background:#0b0d11;border:1px solid var(--line);border-radius:7px;padding:10px;margin:10px 0 0;
max-height:240px;overflow:auto;font:12px/1.4 ui-monospace,Consolas,monospace;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}
td,th{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;word-break:break-all}
th{color:var(--mute);font-weight:500}.tag2{padding:1px 7px;border-radius:9px;font-size:11px;font-weight:600}
.location{background:#3a1d22;color:var(--bad)}.time{background:#3a2f17;color:var(--warn)}
.device{background:#1b2a3d;color:var(--acc)}.other{background:#22262f;color:var(--mute)}
.score{font-size:26px;font-weight:700;margin-left:auto}.meta{color:var(--mute);font-size:12px}
video,audio{width:100%;margin-top:10px;border-radius:8px;background:#000}
.status{color:var(--mute);font-size:12px;margin-left:6px}.wide{grid-column:1/-1}
.levels{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.lvl{display:flex;flex-direction:column;align-items:flex-start;gap:2px;padding:11px 13px;text-align:left;
border-left:4px solid var(--line)}
.lvl b{font-size:14px}.lvl span{font-size:11.5px;color:var(--mute)}
.lvl.l1{border-left-color:#6b7280}.lvl.l2{border-left-color:var(--acc)}
.lvl.l3{border-left-color:var(--twig)}.lvl.l4{border-left-color:var(--bad)}
.lvl:hover{background:#1d222c}
details{margin-top:12px}summary{cursor:pointer;color:var(--mute);font-size:12px}
details .row{margin-top:10px}
#tip{position:fixed;z-index:50;max-width:430px;display:none;pointer-events:none;
background:#0c0e13;border:1px solid var(--twig);border-radius:12px;padding:12px;
box-shadow:0 10px 34px rgba(0,0,0,.55);gap:12px}
#tip.show{display:flex;animation:tippop .12s ease-out}
#tip img{width:104px;height:104px;object-fit:contain;flex:none;align-self:flex-start}
#tip .body{font-size:13px;line-height:1.5}
#tip .who{color:var(--twig);font-weight:700;font-size:11px;letter-spacing:.5px;text-transform:uppercase;margin-bottom:3px}
#tip .sig{color:var(--mute);font-size:11px;margin-top:7px}
#aidisc{position:fixed;right:11px;bottom:8px;z-index:5;font-size:11px;color:#55607a;opacity:.72;pointer-events:none;letter-spacing:.3px}
section.danger{border-color:#512329}section.danger h2{color:#e68a8a}
button.danger{background:#3a1d22;color:#ef9a9a;border-color:#5a2a30}button.danger:hover:not(:disabled){background:#4a2329;border-color:var(--bad)}
</style></head><body>
<header><img class="mascot" src="/assets/twig.png" alt="Twig">
<div><h1>hidemydoppler</h1><span class="tag">local privacy pass &middot; narrated by Twig</span></div>
<button id="geek" class="tiptrigger" data-tip="geek"><img src="/assets/twig-science.png">Geek mode: off</button>
</header>
<main>
<section id="prepPanel"><h2>1 &middot; System prep</h2>
<div class="row"><button id="prep">Run prep check</button>
<button id="install" class="primary" disabled title="Enabled when the prep check finds something missing">Install missing</button>
<span id="prepSt" class="status"></span></div>
<pre id="prepOut">Not run yet.</pre></section>

<section><h2>2 &middot; Load file</h2>
<div class="row"><label class="file">Choose video/audio<input id="file" type="file" accept="video/*,audio/*"></label>
<button id="towav" disabled title="Save the audio as a WAV you can open in Audacity">Export WAV for Audacity</button>
<span id="loadSt" class="status"></span><span id="score0" class="score"></span></div>
<div id="wavOut" class="meta"></div>
<div id="meta0" class="meta"></div><div id="tbl0"></div></section>

<section><h2>3 &middot; Protect &mdash; pick a level</h2>
<div class="levels">
<button class="lvl l1 tiptrigger" data-tip="L1" data-level="1" disabled><b>Level 1</b><span>Metadata only</span></button>
<button class="lvl l2 tiptrigger" data-tip="L2" data-level="2" disabled><b>Level 2</b><span>Standard clean</span></button>
<button class="lvl l3 tiptrigger" data-tip="L3" data-level="3" disabled><b>Level 3</b><span>Cleanest sound</span></button>
<button class="lvl l4 tiptrigger" data-tip="L4" data-level="4" disabled><b>Level 4</b><span>Max privacy</span></button>
</div>
<div class="row" style="margin-top:10px"><span id="protSt" class="status"></span></div>
<details><summary>Advanced (manual knobs)</summary>
<div class="row"><label>offset dB <input id="off" type="number" value="5" step="0.5"></label>
<label>playback SPL <input id="spl" type="number" value="90" step="1"></label>
<label>warmth <input id="warm" type="number" value="1" min="0" max="1" step="0.25"></label>
<button id="clean" class="primary" disabled>Clean + scrub</button><span id="cleanSt" class="status"></span></div>
</details>
<pre id="cleanOut">Load a file first.</pre></section>

<section><h2>4 &middot; Rescan + play</h2>
<div class="row"><button id="rescan" disabled>Rescan + play</button>
<button id="playOrig" disabled>Play original</button><span id="rsSt" class="status"></span>
<span id="score1" class="score"></span></div>
<div id="meta1" class="meta"></div><div id="tbl1"></div><div id="player"></div></section>
<section class="wide danger"><h2>Uninstall</h2>
<div class="row"><label><input type="checkbox" id="keepvids" checked> Keep my cleaned videos</label>
<button id="uninstall" class="danger tiptrigger" data-tip="uninstall" disabled>Uninstall hidemydoppler</button>
<span id="uninSt" class="status"></span></div>
<label class="meta" style="display:block;margin-top:8px"><input type="checkbox" id="uninConfirm"> I understand this removes hidemydoppler from this computer. This can't be undone.</label>
</section>
</main>
<div id="aidisc">generated with AI</div>
<div id="tip"><img src="/assets/twig-sign.png" alt="Twig"><div><div class="who">Twig says</div><div class="body"></div><div class="sig">&mdash; Twig</div></div></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
if("__HIDE_PREP__"==="1"){var pp=$('prepPanel');if(pp)pp.style.display='none';}

/* ---- Twig's explanations: plain (everyone) vs geek (full tech) ---- */
const TIPS={
 L1:{plain:"I just scrub the hidden tags off your file — the timestamp, GPS and phone model. That alone makes you much harder to pin down. Pick me when you’ve listened and there’s no jet roar to worry about: your sound stays 100% untouched.",
     geek:"Strips container + stream metadata (creation_time, ISO-6709 GPS, make/model, encoder) and any telemetry side-tracks; audio & video are stream-copied, zero quality loss. Removes the time anchor the ADS-B lookup needs. Does NOT touch the audio, so an audible Doppler swell is still recoverable."},
 L2:{plain:"I scrub the tags AND quietly erase the faint engine whine you can’t even hear — the bit a snoop’s computer leans on. Solid everyday pick: strong privacy, and your voice still sounds like you.",
     geek:"Metadata scrub + psychoacoustic pass: bins below the Bark masking threshold are refilled with continuous-noise-phase comfort noise (erases sub-audible tonal lines without musical noise), sub-ATH bins zeroed, then a de-tinny envelope restore. offset 5 dB, SPL 90, warmth 1, smoothing 7 frames, phase=noise."},
 L3:{plain:"For when the recording really matters. I hide the jet’s rise-and-fall as best I can WITHOUT changing how your audio sounds — so it’s the cleanest option, but call it about 50/50 on privacy. Great for keepsake clips where the sound is the whole point.",
     geek:"Gentle mask (offset 8 dB, SPL 95) with phase_mode=preserve: masked bins keep their original phase for pristine audio, but a reduced-magnitude steady tone stays partly coherent, so a determined matcher may still recover the curve. Best fidelity, partial privacy by design — hence ~50%."},
 L4:{plain:"The vault. I throw everything at hiding the jet so the location trick just fails, then make it sound as good as I can afterward. Reach for me when privacy beats audio quality, every time.",
     geek:"Aggressive mask (offset 2 dB, SPL 80) + noise-phase substitution + 9-frame smoothing + full metadata scrub + de-tinny. Flattens and decorrelates the Doppler ridge so curve-matching has nothing to lock onto. ('100%' is the goal, not a lab-measured guarantee — no scrubber can promise that.)"},
 uninstall:{plain:"This removes hidemydoppler from your computer - the program and the guides. I keep your \"Cleaned videos\" unless you untick the box. I do NOT remove Python or ffmpeg, since other programs may use them (take those out from Windows\u2019 normal uninstall if you want). This can\u2019t be undone.",
     geek:"Writes a detached self-deleting uninstaller to the temp dir, shuts down this local server (freeing the working directory), waits ~3s, then removes the app tree (Program/, Guides/, launcher, docs) and the folder itself. Keeps 'Cleaned videos' unless unchecked. Never touches the Python interpreter, ffmpeg, or pip packages."},
 geek:{plain:"Flip me on and these notes turn into the full technical details — parameters and the why behind each level. Flip back any time.",
     geek:"Geek mode ON. Tooltips now show DSP parameters and the threat-model rationale. Click to go back to plain language."}
};
let GEEK=false;
const tip=$('tip'),tipBody=tip.querySelector('.body');
function showTip(e){const k=e.currentTarget.dataset.tip;if(!TIPS[k])return;
  tipBody.innerHTML=esc(TIPS[k][GEEK?'geek':'plain']);tip.classList.add('show');moveTip(e);}
function moveTip(e){const pad=14,w=tip.offsetWidth,h=tip.offsetHeight;
  let x=e.clientX+18,y=e.clientY+18;
  if(x+w+pad>innerWidth)x=e.clientX-w-18;if(x<pad)x=pad;
  if(y+h+pad>innerHeight)y=innerHeight-h-pad;if(y<pad)y=pad;
  tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){tip.classList.remove('show');}
function wireTips(){document.querySelectorAll('.tiptrigger').forEach(el=>{
  el.addEventListener('mouseenter',showTip);el.addEventListener('mousemove',moveTip);
  el.addEventListener('mouseleave',hideTip);});}
$('geek').onclick=()=>{GEEK=!GEEK;$('geek').classList.toggle('on',GEEK);
  $('geek').lastChild.textContent='Geek mode: '+(GEEK?'on':'off');};

function scoreColor(s){return s>=50?'var(--bad)':s>0?'var(--warn)':'var(--ok)'}
function renderReport(r,n){
  $('score'+n).textContent=r.score+'/100';$('score'+n).style.color=scoreColor(r.score);
  $('meta'+n).textContent=r.file+' · '+r.size_mb+' MB · leak score';
  const rows=r.findings.map(f=>'<tr><td><span class="tag2 '+f.cat+'">'+f.cat+'</span></td><td>'+esc(f.where)+'</td><td>'+esc(f.key)+'</td><td>'+esc(f.value)+'</td></tr>').join('');
  $('tbl'+n).innerHTML='<table><tr><th>leak</th><th>where</th><th>key</th><th>value</th></tr>'+(rows||'<tr><td colspan=4>No tags found</td></tr>')+'</table>';
}
async function api(url,opt){const r=await fetch(url,opt);const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||r.status);return j}
function busy(st,msg){$(st).textContent=msg}
function setLevels(on){document.querySelectorAll('.lvl').forEach(b=>b.disabled=!on);}

async function prepCheck(){busy('prepSt','checking...');$('prepSt').style.color='';try{const j=await api('/api/prep');
  $('prepOut').textContent=j.output;busy('prepSt',j.ok?'ready':'not ready');$('prepSt').style.color=j.ok?'var(--ok)':'var(--bad)';
  $('install').disabled=j.ok;return j.ok}catch(e){busy('prepSt',e.message)}}
$('prep').onclick=prepCheck;
$('install').onclick=async()=>{$('install').disabled=true;$('prep').disabled=true;busy('prepSt','installing...');
  $('prepSt').style.color='var(--warn)';try{await api('/api/install',{method:'POST'});
  const poll=setInterval(async()=>{const j=await api('/api/install/status');$('prepOut').textContent=j.output;
    $('prepOut').scrollTop=$('prepOut').scrollHeight;
    if(j.done){clearInterval(poll);$('prep').disabled=false;const ok=await prepCheck();
      if(!ok)$('prepOut').textContent=j.output+'\n--- recheck ---\n'+$('prepOut').textContent;}},1000);}
  catch(e){busy('prepSt',e.message);$('install').disabled=false;$('prep').disabled=false}};

$('file').onchange=async e=>{const f=e.target.files[0];if(!f)return;busy('loadSt','uploading '+f.name+'...');
  try{const r=await api('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});
  renderReport(r,0);busy('loadSt','loaded');setLevels(true);$('clean').disabled=false;$('playOrig').disabled=false;$('rescan').disabled=false;$('towav').disabled=false;
  $('cleanOut').textContent='Ready. Pick a protection level above.';}catch(e){busy('loadSt',e.message)}};
$('towav').onclick=async()=>{$('towav').disabled=true;busy('loadSt','extracting WAV...');
  try{const j=await api('/api/export-wav',{method:'POST'});
  $('wavOut').textContent='Saved '+j.name+' ('+j.size_mb+' MB) in your "Cleaned videos" folder - open it in Audacity (File > Open).';busy('loadSt','WAV ready');}
  catch(e){busy('loadSt',e.message)}finally{$('towav').disabled=false}};

async function runProtect(level){setLevels(false);busy('protSt','Twig is working on Level '+level+'... (big files take a while)');
  try{const j=await api('/api/protect?level='+level,{method:'POST'});
  $('cleanOut').textContent=JSON.stringify(j.stats,null,2)+'\n\nSaved to your "Cleaned videos" folder: '+j.report.file;
  busy('protSt','Level '+level+' done ✓');$('rescan').click();}
  catch(e){busy('protSt',e.message);}finally{setLevels(true);}}
document.querySelectorAll('.lvl').forEach(b=>b.addEventListener('click',()=>runProtect(+b.dataset.level)));

$('clean').onclick=async()=>{busy('cleanSt','cleaning...');$('clean').disabled=true;
  try{const j=await api('/api/clean?offset='+$('off').value+'&spl='+$('spl').value+'&warmth='+$('warm').value,{method:'POST'});
  $('cleanOut').textContent=JSON.stringify(j.stats,null,2)+'\n\nSaved to your "Cleaned videos" folder: '+j.report.file;busy('cleanSt','done');
  $('rescan').click()}catch(e){busy('cleanSt',e.message)}finally{$('clean').disabled=false}};
function play(which,isVideo){const src='/media/x?which='+which+'&t='+Date.now();
  $('player').innerHTML=isVideo?'<video controls autoplay src="'+src+'"></video>':'<audio controls autoplay src="'+src+'"></audio>';}
$('rescan').onclick=async()=>{busy('rsSt','scanning...');try{const r=await api('/api/rescan?which=cleaned');
  renderReport(r,1);busy('rsSt','showing '+r.which);play(r.which,!/\.(wav|mp3|m4a|flac|ogg)$/i.test(r.file))}
  catch(e){busy('rsSt',e.message)}};
$('playOrig').onclick=async()=>{const r=await api('/api/rescan?which=original');renderReport(r,1);
  busy('rsSt','showing original');play('original',!/\.(wav|mp3|m4a|flac|ogg)$/i.test(r.file))};
$('uninConfirm').onchange=()=>{$('uninstall').disabled=!$('uninConfirm').checked;};
$('uninstall').onclick=async()=>{
  if(!confirm('Remove hidemydoppler from this computer now?'+($('keepvids').checked?'\n\nYour "Cleaned videos" folder will be kept.':'\n\nYour "Cleaned videos" folder will ALSO be deleted.')))return;
  $('uninstall').disabled=true;busy('uninSt','uninstalling...');
  try{const j=await api('/api/uninstall?keep_videos='+($('keepvids').checked?'1':'0'),{method:'POST'});
    document.body.innerHTML='<div style="max-width:560px;margin:14vh auto;text-align:center;font:15px/1.6 system-ui;color:#d8dde6">'
      +'<img src="/assets/twig-heart.png" style="width:120px"><h2>hidemydoppler is uninstalling</h2>'
      +'<p>The program is removing itself'+(j.kept_videos?' (your cleaned videos were kept)':' and your cleaned videos')+'. '
      +'You can close this tab.</p><p style="color:#8590a2;font-size:12px">Thanks for letting Twig help.</p></div>';
  }catch(e){busy('uninSt',e.message);$('uninstall').disabled=false;}};
wireTips();
</script></body></html>"""


def _port_busy(port):
    """True if something is already listening on 127.0.0.1:port."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def _ping(port):
    """Identify a hidemydoppler instance on `port`, else None.

    Tries /api/ping (this version). Falls back to sniffing the root page's title
    so that OLDER instances, which predate /api/ping, are still recognised."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.6) as r:
            info = json.loads(r.read().decode())
            if info.get("app") == "hidemydoppler":
                return info
    except Exception:
        pass
    try:  # older build: no ping endpoint, but its page says who it is
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.6) as r:
            head = r.read(600).decode("utf-8", "ignore").lower()
            if "<title>hidemydoppler" in head:
                return {"app": "hidemydoppler", "version": "older", "pid": None}
    except Exception:
        pass
    return None


def _ask_shutdown(port):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST")
        urllib.request.urlopen(req, timeout=0.6).read()
        return True
    except Exception:
        return False


def reap_old_instances(base, span=20, warn_only=False):
    """Find older hidemydoppler instances on base..base+span and stop them
    (or just warn). Returns a list of human-readable notes."""
    notes = []
    for p in range(base, base + span):
        if not _port_busy(p):
            continue
        info = _ping(p)
        if not info:
            continue  # something else is on this port; leave it alone
        pid = info.get("pid")
        tag = f"port {p} ({'pid ' + str(pid) + ', ' if pid else ''}version {info.get('version')})"
        if warn_only:
            notes.append(f"WARNING: older hidemydoppler still running on {tag}")
            continue
        if _ask_shutdown(p):
            for _ in range(20):                     # wait up to ~4 s to free up
                if not _port_busy(p):
                    break
                time.sleep(0.2)
            notes.append(f"stopped older instance on {tag}")
        else:
            notes.append(f"could not stop instance on {tag} - close it manually")
    return notes


def main():
    global SERVER
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--launched-from-prep", action="store_true",
                    help="hide the System Prep panel (prep just ran before launch)")
    ap.add_argument("--warn-old", action="store_true",
                    help="only warn about older instances instead of stopping them")
    a = ap.parse_args()
    CONFIG["hide_prep"] = a.launched_from_prep

    # Retire any older copies first so the fresh UI owns the expected port and a
    # browser never shows a stale version. Only confirmed hidemydoppler instances
    # are touched; anything else on a port is left alone.
    for note in reap_old_instances(a.port, warn_only=a.warn_old):
        print(note)

    # After stopping an old instance, our own shutdown request leaves that port
    # in TIME_WAIT briefly. allow_reuse_address lets us rebind over a TIME_WAIT
    # socket (there's no live listener now - the reaper closed it), while the
    # _port_busy gate still keeps us off a port with an ACTIVE listener.
    ThreadingHTTPServer.allow_reuse_address = True
    port = a.port
    for _ in range(20):
        if not _port_busy(port):
            try:
                srv = ThreadingHTTPServer(("127.0.0.1", port), H)
                break
            except OSError:
                pass
        port += 1
    else:
        print("Could not find a free port in range; is the app already open?")
        return

    SERVER = srv
    CONFIG["port"] = port
    url = f"http://127.0.0.1:{port}"
    note = "" if port == a.port else f"  (port {a.port} was busy)"
    print(f"hidemydoppler UI on {url}{note}  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
