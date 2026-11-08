# hidemydoppler — Audacity helpers

Two Nyquist plug-ins that find aircraft flyovers in a recording. They flag or
duck the flyover so you know where to run the full privacy pass; they do **not**
measure the Doppler curve.

## Install
1. Copy both `.ny` files into Audacity's **Plug-Ins** folder:
   - Windows: `C:\Program Files\Audacity\Plug-Ins`
   - macOS: `~/Library/Application Support/audacity/Plug-Ins`
   - Linux: `~/.audacity-files/plug-ins` or `/usr/share/audacity/plug-ins`
2. Audacity → **Tools ▸ Noise Reduction and Repair / Add Plug-ins** (or
   **Tools ▸ Manage Plug-ins…** on older builds), enable both, restart.

## Use
- **Analyze ▸ Label Jet Flyovers** — adds a label track with one `flyover`
  region per detected pass. Nothing is changed; use it to see where they are.
- **Effect ▸ Jet Flyover Suppressor** — ducks the level during each detected
  flyover. Broadband, so it dims everything while the jet passes; start gentle.

## How detection works
A flyover is a **swell** of low-frequency energy. Each plug-in measures the
low band (below the split frequency) in 100 ms blocks, takes the clip's median
low-band level as "normal", and flags blocks that rise a set number of dB above
that baseline and stay there long enough. Steady low tones (a bass note, a
droning fan) raise the baseline too, so they don't trip it — only departures do.

## Controls
- **Flyover sensitivity (dB above baseline)** — lower = more sensitive. Default 4.
- **Minimum flyover length (s)** — ignore short low-frequency blips. Default 2 (labeller).
- **Low/high split frequency (Hz)** — where the "low band" ends. Default 500; drop
  toward 150–250 if voices are triggering it.
- **Reduction (dB)** / **Fade in/out (s)** — suppressor only.

Tune on real audio; the defaults are a starting point, not a guarantee.
