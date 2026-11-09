# hidemydoppler v1.0 — Modules 1 + 2

## Quick start
- **Windows:** double-click **Launch hidemydoppler.cmd**. It checks for Python, numpy, scipy and
  ffmpeg (approve the one admin prompt), installs anything missing, then opens the app automatically.
- **Linux:** in the `Program/` folder, `./prepare_linux.sh` (or `--yes`), then `python3 ui.py`.

**Folder layout (what users see):** `Launch hidemydoppler.cmd` + `Read Me First.pdf` at top; `Guides/` (user guide, install help, whitepaper, Audacity add-ons); `Cleaned videos/` (output, created on first run); `Program/` (all code, this README, `hmd/`, `assets/`, `sample.mp4`).

Privacy pass for phone videos. Needs Python 3.9+, numpy, scipy, ffmpeg/ffprobe on PATH.
New to Python? See INSTALL_PYTHON.md.
Docs: **GUIDE.md** (plain-language) and **WHITEPAPER.md** (technical).
Run `python ui.py` for the dark-themed web UI at http://127.0.0.1:8765: prep check,
load + inspect, then **Protect** with one-click Level 1-4 presets (L1 metadata only,
L2 standard clean, L3 cleanest sound ~50% privacy, L4 max privacy), rescan + play.
Each level has a plain-language hover tooltip voiced by **Twig**; toggle **Geek mode**
(top right) for the full DSP/threat-model detail. Manual knobs live under "Advanced".
Twig branding lives in `assets/`. Or use the CLI below.
Run `python setup_check.py` first: it checks all of that and offers to install what is missing (`--yes` to auto-install, `--check` to only report).

```
python3 hmd.py report  in.mp4                 # list metadata leaks + leak score
python3 hmd.py scrub   in.mp4 out.mp4 [--fake-time 2025-01-01T12:00:00Z]
python3 hmd.py clean   in.mp4 out.mp4 [--offset-db 5] [--playback-spl 90]
python3 hmd.py protect in.mp4 out.mp4          # clean, then scrub
```

## Modules (hmd/)
- `scrub.py` — Module 1. Strips container + stream tags (time, GPS/ISO6709, make/model,
  encoder), chapters and data/telemetry side tracks. A/V are stream-copied (no quality loss).
  Optional decoy creation_time.
- `clean.py` — Module 2. Psychoacoustic masked-component substitution: per STFT frame, bins
  below the Bark-band masking threshold are replaced with same-level random-phase noise
  (like AAC's Perceptual Noise Substitution); bins below the absolute hearing threshold are zeroed.
  Audible sound is left alone.
- `post.py` — de-tinny post-processing: restores the cleaned audio's long-term
  tonal balance to the original (fixes thinness) and tames papery highs. Does not
  reintroduce the faint Doppler tones.
- `media.py` — ffmpeg/ffprobe/WAV helpers.

## Opening a clip in Audacity
Audacity needs FFmpeg's shared libraries (not the CLI) to import MP4/M4A. Easiest
path: in the UI, **Load file** then **Export WAV for Audacity** (saved in `work/`),
and open that WAV in Audacity - WAV needs no FFmpeg. CLI equivalent:
`ffmpeg -i clip.mp4 -vn -c:a pcm_s24le clip.wav`.

## audacity/ (optional in-editor helpers)
Two Nyquist plug-ins that detect aircraft flyovers (label them, or duck them) so
you can see/hear where to clean. See `audacity/README.md`. Detection only — they
don't measure the Doppler curve.

## Knobs
- `--offset-db` lower = more aggressive substitution.
- `--playback-spl` assumed SPL of 0 dBFS on playback; lower = more content counted as inaudible.
- `--warmth` 0..1 de-tinny strength after cleaning (default 1.0; 0 = off). Also a slider in the UI.
- `--phase-mode` how masked bins are re-phased: `noise` (default, smooth comfort
  noise - no wind/pops, still erases tones), `random` (legacy, can sound windy),
  `preserve` (cleanest sound but weakens privacy - a quiet tone stays coherent).
- `--smooth-frames` temporal smoothing of the noise bed in STFT frames (default 7).

## Known limits (v1.0)
- Whole file processed in memory (fine for a few minutes of audio).
- Audio is re-encoded to AAC 192k when cleaning video.
- Loudness shifts ~1-2 dB; an audible tone keeps most of its level (~-4 dB on its peak).
- Masked bins are filled with smooth continuous-noise-phase comfort noise, so the
  bed does not burble/wind the way per-frame random phase does.
- Sub-threshold steady tone test: 24 dB above floor -> ~8 dB after cleaning (20 s FFT
  integration). Reduced, not eliminated.
