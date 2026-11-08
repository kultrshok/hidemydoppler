"""Shared media helpers: ffprobe/ffmpeg wrappers and WAV I/O (no extra deps)."""
import json
import os
import subprocess
import tempfile

import numpy as np
from scipy.io import wavfile

SR = 48000  # working sample rate for all audio processing


def run(cmd):
    """Run a command, raise with stderr on failure."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr[-2000:]}")
    return p.stdout


def probe(path):
    """Full ffprobe dump (format + streams + all tags) as a dict."""
    out = run(["ffprobe", "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", "-show_chapters", path])
    return json.loads(out)


def is_video(path):
    return any(s.get("codec_type") == "video" for s in probe(path).get("streams", []))


def read_audio(path, sr=SR):
    """Decode any media file's first audio stream to mono float32 at `sr`."""
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-map", "0:a:0",
             "-ac", "1", "-ar", str(sr), "-c:a", "pcm_f32le", wav])
        rate, x = wavfile.read(wav)
    return x.astype(np.float32), rate


def write_wav(path, x, sr=SR):
    wavfile.write(path, sr, np.clip(x, -1, 1).astype(np.float32))


def replace_audio(src_media, new_wav, out_path, bitrate="192k"):
    """Remux: keep src video untouched (stream copy), swap in processed audio.
    Metadata is NOT carried over here; run scrub separately (modules stay independent).
    """
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src_media, "-i", new_wav,
           "-map", "0:v?", "-map", "1:a:0", "-c:v", "copy",
           "-c:a", "aac", "-b:a", bitrate, "-map_metadata", "0",
           "-movflags", "+faststart", out_path]
    run(cmd)


def extract_wav(src_media, out_wav):
    """Pull the first audio stream out to a WAV, original rate/channels kept.

    For opening the clip in an editor (Audacity) that can't import MP4/M4A
    without the FFmpeg shared libraries - this sidesteps that entirely.
    """
    run(["ffmpeg", "-v", "error", "-y", "-i", src_media, "-vn",
         "-map", "0:a:0", "-c:a", "pcm_s24le", out_wav])
    return out_wav
