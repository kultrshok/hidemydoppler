# Scrubgnome — User Guide

*Meet Twig. He helps you scrub hidden location clues out of your phone videos
before you share them.*

---

## What problem does this solve?

A video can quietly give away **where it was filmed** in two ways.

First, the file stores hidden tags: the time you recorded, your GPS coordinates, and
your phone model.

Second, the *sound* can give you away. The clever example Scrubgnome was built around:
when you record outside, your phone often picks up faint aircraft noise you barely
notice. The pitch of a plane passing overhead changes as it flies (the same effect you
hear when a siren goes by), and that pitch change, matched against public
flight-tracking data, can reveal where you were standing — down to about a city block,
sometimes from less than a minute of audio.

**Scrubgnome removes both** — the hidden tags, and the location-revealing sounds — so a
clip is much harder to trace back to you. Everything happens **on your own computer**.
Nothing is uploaded anywhere.

---

## Part 1 — What the launcher does to your computer

Double-clicking **Launch Scrubgnome.cmd** (Windows) runs a one-time setup, then
opens the app. Here is exactly what it touches:

**It asks for administrator rights once.** You'll see the standard Windows
"Do you want to allow this app to make changes?" prompt. That's needed to install
software for all users and add it to your system PATH.

**It installs four free, standard tools — only if they're missing:**

| Tool | What it's for | Where it goes |
|------|---------------|---------------|
| **Python** | runs the program | `C:\Program Files\Python3x` (official python.org installer) |
| **numpy, scipy** | the math for cleaning audio | inside Python |
| **ffmpeg** | reads/writes video & audio | `C:\Program Files\ffmpeg` |

If you already have these, it skips them. It shows a progress bar the whole time,
then launches the app automatically.

**What it does *not* do:** it doesn't touch your personal files, doesn't run in the
background after setup, doesn't phone home, and doesn't install anything beyond the
four tools above. To remove them later, uninstall "Python" and delete the
`ffmpeg` folder from Program Files.

> **Mac/Linux:** open the **Program** folder, run `./prepare_linux.sh` in a terminal, then `python3 ui.py`.
> New to Python entirely? See **INSTALL_PYTHON.md**.

---

## Part 2 — How it cleans your videos

Two simple ideas:

**1. It wipes the hidden tags.** The recording time, GPS location, and phone model
are deleted from the file. Your actual video and audio are copied across untouched —
no quality loss. A "leak score" shows you how exposed the file was before and after
(0 is clean).

**2. It erases the sounds you can't hear.** The plane tones the tracking trick needs
are mostly *below what your ears notice* — buried under voices, wind and traffic.
Scrubgnome finds those inaudible bits and replaces them with smooth, even
background hiss. Your voice and the sounds you *can* hear are left alone, and a
final "warmth" pass keeps everything sounding natural instead of thin or tinny.

The stronger settings also scramble the plane's tell-tale pitch slide so it can't be
matched to a flight path.

---

## Part 3 — How to use the program

1. **Launch it.** Double-click **Launch Scrubgnome.cmd**. The app opens in your
   web browser (it runs privately on your own computer).
2. **Load a file.** Click **Choose video/audio** and pick your clip. You'll see a
   table of the hidden tags it found and a leak score.
3. **Pick a protection level** (see below). One click. Twig works for a few seconds
   (longer for big files).
4. **Check the result.** The **Rescan + play** panel shows the cleaned file's tags
   (leak score should drop to 0) and plays it in the page. Use **Play original** to
   compare by ear.
5. **Find your file.** The cleaned copy is saved in the **`work`** folder next to
   the program, named like `yourclip_L4.mp4`.

**Hover any level button** and Twig explains it in plain words. Flip **Geek mode**
(top-right) if you want the full technical detail instead.

### The four levels

| Level | Use it when… | Trade-off |
|-------|--------------|-----------|
| **1 · Metadata only** | You listened and there's no plane noise | Audio untouched; just removes hidden tags |
| **2 · Standard** | Everyday use | Strong privacy, still sounds natural ← good default |
| **3 · Cleanest sound** | The audio really matters (keepsake clips) | Best sound, but only about 50/50 on privacy |
| **4 · Max privacy** | You want the location hidden, period | Privacy first; still cleaned up to sound as good as possible |

> **About Level 4's "100 %":** it throws everything at hiding the plane, but no tool
> can *promise* perfection against every possible snoop. Think "best possible
> effort," not a guarantee.

---

## Part 4 — Optional: Audacity helpers

If you use the free audio editor Audacity, two add-ons (in the `audacity` folder)
can **find** aircraft flyovers for you — one labels them, one quietly lowers their
volume. See `audacity/README.md` to install them.

Audacity can't open phone `.mp4` files on its own without extra setup. Easiest fix:
in Scrubgnome, load your clip and click **Export WAV for Audacity** — that makes
a plain audio file Audacity opens with no fuss.

---

## Part 5 — Away from home: the mobile edition

Not at your computer? Twig has a pocket edition, **Scrubgnome Away from Home**, for
scrubbing a clip right on the phone that shot it.

- **iPhone (or any phone or computer):** open
  **kultrshok.github.io/scrubgnome-afh** in Safari, then tap **Share → Add to Home
  Screen**. It works like an app, even offline.
- **Android:** install the app from the **Releases** or **Actions** page at
  **github.com/kultrshok/scrubgnome-afh**.

**What it does:** pick a video and it removes the hidden tags (time, GPS, phone model,
and hidden data tracks), with no quality loss. It saves a clean copy with a random
name, ready to post. It can also **listen for inaudible tracking tones**: high-pitched
beacons some ads use, too high for people to hear. If it hears one, it warns you.

**What it doesn't do:** it doesn't clean the audio. It won't erase airplane sounds or
remove the tones it finds. Think of it as **Level 1 in your pocket**. If the tone check
warns you, or you filmed outdoors with planes overhead, run the clip through this
desktop app at Level 2 or higher before you share it.

Like the desktop app, it never uploads your video. Everything happens on your phone.

---

## Quick tips

- Cleaning a long clip uses a fair bit of memory and takes a little time — that's
  normal.
- If the sound ever seems off, try a different level, or open **Advanced** for
  manual dials.
- Everything stays on your computer. Scrubgnome never uploads your videos.
- On the go? The mobile edition (Part 5) handles the hidden tags from your phone.
