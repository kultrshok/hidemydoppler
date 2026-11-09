#!/usr/bin/env python3
"""Scrubgnome system prep: checks and installs prerequisites.

  python setup_check.py          # check, ask before installing anything
  python setup_check.py --yes    # install missing items without asking
  python setup_check.py --check  # report only, change nothing

Needs: Python 3.9+, numpy, scipy, ffmpeg + ffprobe on PATH.
"""
import argparse
import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys

PY_MIN = (3, 9)
PY_PKGS = {"numpy": "numpy", "scipy": "scipy"}   # import name -> pip name
HERE = os.path.dirname(os.path.abspath(__file__))

OK, BAD, WARN = "[ OK ]", "[MISS]", "[WARN]"


def ask(msg, args):
    if args.check:
        return False
    if args.yes:
        return True
    try:
        return input(f"{msg} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def sh(cmd):
    print("   $", " ".join(cmd))
    return subprocess.run(cmd).returncode == 0


def check_python():
    v = sys.version_info
    good = v >= PY_MIN
    print(f"{OK if good else BAD} Python {v.major}.{v.minor}.{v.micro} "
          f"({sys.executable})")
    if not good:
        print(f"       Need {PY_MIN[0]}.{PY_MIN[1]}+. Install a newer Python, then rerun.")
    return good


def check_pip_pkgs(args):
    missing = []
    for mod, pipname in PY_PKGS.items():
        try:
            m = importlib.import_module(mod)
            print(f"{OK} {mod} {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"{BAD} {mod}")
            missing.append(pipname)
    if not missing:
        return True
    if not ask(f"Install {', '.join(missing)} with pip?", args):
        print(f"       Run: {sys.executable} -m pip install {' '.join(missing)}")
        return False
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *missing]
    if not sh(cmd):
        # Debian/Ubuntu "externally managed" Pythons need --user or a venv
        if not sh(cmd + ["--user"]):
            print("       pip failed. Try a venv:  python -m venv .venv  then rerun inside it.")
            return False
    importlib.invalidate_caches()
    return all(importlib.util.find_spec(m) for m in PY_PKGS)


def ffmpeg_install_cmds():
    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            return [["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                     "--accept-source-agreements", "--accept-package-agreements"]]
        if shutil.which("choco"):
            return [["choco", "install", "-y", "ffmpeg"]]
        if shutil.which("scoop"):
            return [["scoop", "install", "ffmpeg"]]
    elif system == "Darwin" and shutil.which("brew"):
        return [["brew", "install", "ffmpeg"]]
    elif system == "Linux":
        sudo = [] if os.geteuid() == 0 else ["sudo"]
        if shutil.which("apt-get"):
            return [sudo + ["apt-get", "update"],
                    sudo + ["apt-get", "install", "-y", "ffmpeg"]]
        if shutil.which("dnf"):
            # RHEL/Rocky/CentOS: ffmpeg lives in RPM Fusion (needs EPEL first)
            rel = subprocess.run(["rpm", "-E", "%rhel"], capture_output=True,
                                 text=True).stdout.strip()
            cmds = []
            if rel.isdigit():
                cmds += [sudo + ["dnf", "install", "-y", "epel-release"],
                         sudo + ["dnf", "install", "-y",
                                 f"https://mirrors.rpmfusion.org/free/el/"
                                 f"rpmfusion-free-release-{rel}.noarch.rpm"]]
                if rel in ("8", "9", "10"):
                    cmds.append(sudo + ["dnf", "config-manager", "--set-enabled",
                                        "crb" if rel != "8" else "powertools"])
            cmds.append(sudo + ["dnf", "install", "-y", "ffmpeg"])
            return cmds
        if shutil.which("pacman"):
            return [sudo + ["pacman", "-S", "--noconfirm", "ffmpeg"]]
    return None


def check_ffmpeg(args):
    found = {t: shutil.which(t) for t in ("ffmpeg", "ffprobe")}
    for t, p in found.items():
        print(f"{OK if p else BAD} {t} {p or ''}")
    if all(found.values()):
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True).stdout
        if " aac " not in out:
            print(f"{WARN} ffmpeg has no AAC encoder; `clean` on video will fail.")
        return True
    cmds = ffmpeg_install_cmds()
    if not cmds:
        print("       No supported package manager found. Get ffmpeg from "
              "https://ffmpeg.org/download.html and add it to PATH.")
        return False
    if not ask("Install ffmpeg now?", args):
        print("       Run:\n" + "\n".join("         " + " ".join(c) for c in cmds))
        return False
    for c in cmds:
        if not sh(c):
            print("       That step failed; fix it and rerun.")
            return False
    if platform.system() == "Windows":
        print(f"{WARN} Open a NEW terminal so the updated PATH is picked up, then rerun.")
        return bool(shutil.which("ffmpeg"))
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def smoke_test():
    """Import the modules and, if the bundled test clip exists, run a report."""
    sys.path.insert(0, HERE)
    try:
        from hmd import clean, scrub  # noqa: F401
    except Exception as e:  # pragma: no cover
        print(f"{BAD} hmd modules failed to import: {e}")
        return False
    print(f"{OK} hmd modules import")
    clip = os.path.join(HERE, "test.mp4")
    if os.path.exists(clip):
        findings = scrub.report(clip)
        print(f"{OK} report on test.mp4 ran (leak score {scrub.score(findings)}/100)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="install without asking")
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()

    print(f"Scrubgnome prep on {platform.system()} {platform.release()}\n")
    results = [check_python()]
    if results[0]:
        results += [check_pip_pkgs(args), check_ffmpeg(args)]
    if all(results):
        results.append(smoke_test())
    print("\nReady to go." if all(results) else "\nNot ready yet; see notes above.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
