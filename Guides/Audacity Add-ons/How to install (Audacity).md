# Scrubgnome — Audacity Add-ons: Install & Use

Two free add-ons that find aircraft flyovers in a recording so you can see or
hush them. They work inside **Audacity**, the free audio editor
(<https://www.audacityteam.org>).

- **Label Jet Flyovers** — marks each flyover with a label (changes nothing).
- **Jet Flyover Suppressor** — lowers the volume during each flyover.

Both only *detect and dim* flyovers. For the full privacy scrub (stripping the
inaudible tones and the hidden tags), use the Scrubgnome app itself.

---

## Before you start — get your clip into Audacity

Audacity can't open a phone `.mp4` on its own without extra setup, so give it a
plain audio file instead:

1. Open the Scrubgnome app (**Launch Scrubgnome**).
2. **Load file** → pick your clip.
3. Click **Export WAV for Audacity**. The `.wav` lands in your **Cleaned videos**
   folder.
4. In Audacity, **File ▸ Open** that `.wav`.

(You can also open any `.wav`, `.mp3` or `.flac` you already have.)

---

## Part 1 — Install the plug-ins

The two files you need are in this folder:
`Label Jet Flyovers.ny` and `Jet Flyover Suppressor.ny`.

Copy them into Audacity's **Plug-Ins** folder:

**Windows**
1. Press `Win + R`, paste this, and press Enter:
   `C:\Program Files\Audacity\Plug-Ins`
2. Copy both `.ny` files into that window.
   (If Windows asks for permission, click **Continue**.)

**macOS**
1. In Finder, press `Cmd + Shift + G` and paste:
   `~/Library/Application Support/audacity/Plug-Ins`
2. Copy both `.ny` files into that folder.

**Linux**
Copy both `.ny` files into one of these (whichever exists):
`~/.audacity-files/plug-ins` or `/usr/share/audacity/plug-ins`

---

## Part 2 — Turn them on in Audacity

1. Open (or restart) Audacity.
2. Go to **Tools ▸ Plugin Manager…**
   *(older versions: **Tools ▸ Add / Remove Plug-ins**).*
3. In the list, find **Label Jet Flyovers** and **Jet Flyover Suppressor**.
4. Select each one and click **Enable**, then **OK**.
5. Restart Audacity once more if the menus don't update.

You only do this once. After that they live in Audacity's menus.

---

## Part 3 — Find the flyovers ("Label Jet Flyovers")

1. Open your clip and **select the whole track** (`Ctrl + A`, or `Cmd + A` on Mac).
2. Go to the **Analyze** menu ▸ **Label Jet Flyovers…**
3. Adjust the settings if you like (defaults are a good start — see below), then **OK**.
4. A **label track** appears under your audio with a `flyover` marker on each pass
   it found. Click a label to jump to that spot and listen.

Nothing is changed — this just shows you where the planes are. If it finds
nothing, lower the **sensitivity** number and run it again.

---

## Part 4 — Hush the flyovers ("Jet Flyover Suppressor")

1. Select the whole track (`Ctrl + A`), or just the part you want treated.
2. Go to the **Effect** menu ▸ **Jet Flyover Suppressor…**
3. Set how much to duck and how smoothly (see below), then **OK**.
4. Audacity lowers the volume during each detected flyover. Press **Space** to
   listen; **Ctrl + Z** undoes it if you want to retry with different settings.

It's a broadband duck, so it dims *everything* while the jet passes — start gentle
and nudge up.

---

## The settings (both plug-ins)

| Setting | What it does | Start at |
|---|---|---|
| **Flyover sensitivity (dB above baseline)** | lower = catches fainter/more flyovers | 4 |
| **Minimum flyover length (seconds)** | ignores short low-frequency blips | 2 |
| **Low/high split frequency (Hz)** | where the "low rumble" band ends; drop toward 150–250 if voices trip it | 500 |
| **Reduction (dB)** *(suppressor only)* | how much to lower the flyover | 12 |
| **Fade in/out (seconds)** *(suppressor only)* | how smoothly the duck comes and goes | 0.5 |

How it decides: a flyover is a **swell** of low-frequency sound that rises above the
clip's normal level and stays up for a couple of seconds. Steady low sounds (a bass
note, a fan) don't trip it — only rises do. Defaults are a starting point, not a
guarantee; tune them on your own audio.

---

## Troubleshooting

- **The plug-ins aren't in the menus.** Re-check the Plug-Ins folder path, then
  enable them in **Tools ▸ Plugin Manager** and restart Audacity.
- **"Label Jet Flyovers" found nothing.** Lower the sensitivity (try 2–3), and make
  sure the whole track is selected.
- **It flags voices or music, not planes.** Lower the split frequency toward
  150–250 Hz so only deep rumble counts.
- **The duck is too strong / too obvious.** Lower the Reduction dB, or raise the
  Fade in/out seconds for a gentler come-and-go.
- **Can't open your `.mp4`.** Use **Export WAV for Audacity** in the app first
  (see the top of this page).
