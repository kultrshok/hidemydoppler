# Scrubgnome

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![Local only](https://img.shields.io/badge/data-stays%20on%20your%20machine-success.svg)

**A local, private video scrubber — strips hidden location clues from your clips
before you share them.**

Videos can quietly reveal *where they were filmed* in two ways: hidden file tags
(GPS, timestamp, device) and location-revealing background sounds. Scrubgnome removes
both. That includes the clever case it was built around — faint aircraft "Doppler"
tones overhead, whose pitch shift can be matched against public flight-tracking data
to pin a recording to within ~100 m. Everything runs on your own machine; nothing is
uploaded.

> Generated with AI. Maintained by **kultrshok**.

---

## Quick start

- **Windows:** double-click **`Launch Scrubgnome.cmd`**. It checks for Python,
  numpy, scipy and ffmpeg (one admin prompt), installs anything missing, then opens
  the app.
- **macOS / Linux:** in `Program/`, run `./prepare_linux.sh`, then `python3 ui.py`.

New to Python? See **`Guides/Install Python`**. Full walkthrough: **`Read Me First.pdf`**.

## What it does

- **Strips metadata** — time, GPS and device tags, with no quality loss.
- **Erases the inaudible aircraft tones** the geolocation trick relies on, while
  leaving your voice and audible sound intact (plus a de-tinny pass so it still
  sounds natural).
- **Four one-click levels** — from *metadata only* to *max privacy* — each explained
  in plain language (with a geek-mode toggle) by Twig, the mascot.

## Repo layout

```
Launch Scrubgnome.cmd   one-click Windows launcher
Read Me First.pdf          start here (plain-language guide)
Guides/                    User Guide, Install Python, Technical Whitepaper,
                           Audacity Add-ons (+ how to install)
Program/                   the app
  ui.py                    local web UI (127.0.0.1)
  hmd.py                   command-line interface
  hmd/                     scrub, clean, post, media modules
  setup_check.py           prerequisite checker/installer
  prepare_windows.ps1      Windows "check + launch"
  prepare_linux.sh         Linux prep
  assets/                  Twig art
  sample.mp4               a test clip
```

## How the cleaner works (short version)

Per STFT frame, bins below the Bark-band masking threshold (the stuff you can't
hear) are flattened and re-phased from a *continuous* noise signal — smooth comfort
noise that still decorrelates any steady tone, so the Doppler evidence washes out
without musical-noise artifacts. See `Guides/Technical Whitepaper` for the full
design, measurements, and limitations.

## Status & honesty

v1.0. Personal project. The cleaner reduces (and in testing largely erases) the
tonal evidence, but no scrubber can *guarantee* unrecoverability against every
possible matcher. The Audacity plug-ins are algorithm-validated but not yet tested
inside Audacity. Not affiliated with anyone; use at your own risk.

## License

MIT — see [LICENSE](LICENSE). © 2026 kultrshok.
Use at your own risk; no warranty.
