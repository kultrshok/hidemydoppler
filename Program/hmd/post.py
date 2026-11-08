"""Post-processing - undo the "tinny" quality the cleaner can introduce.

Why the cleaned audio sounds thin/tinny:
  Module 2 replaces every inaudible bin with random-phase noise and zeroes
  bins under the hearing threshold. Two side effects colour the sound:
    1. Low-level harmonics that gave voices their "body" (low-mids) are the
       most likely to fall under the masking threshold, so they get thinned
       out - the long-term spectral tilt shifts brighter.
    2. Random phase in the high band adds a papery / airy hiss.

This module corrects both WITHOUT undoing the privacy work. The Doppler
evidence is a narrow tone that slowly sweeps; restoring the BROAD spectral
envelope (tens of Bark bands, averaged over the whole clip) and taming the
very top does nothing to re-create that one moving line.

  restore_envelope  match the output's long-term 1/3-octave magnitude
                    envelope back to the original's (fixes the tilt / thinness)
  tame_highs        gentle high shelf to take the edge off the papery hiss
"""
import numpy as np
from scipy.signal import stft, istft

from .media import SR

_NPERSEG = 4096
_NOVERLAP = 3072


def _third_octave_env(mag, f, smooth=1 / 3):
    """Smooth a magnitude spectrum over fractional-octave bands (log f)."""
    env = np.empty_like(mag)
    lo = f * 2 ** (-smooth / 2)
    hi = f * 2 ** (smooth / 2)
    idx = np.arange(len(f))
    for i in range(len(f)):
        sel = (f >= lo[i]) & (f <= hi[i])
        env[i] = mag[sel].mean() if sel.any() else mag[i]
    return env


def restore_envelope(orig, cleaned, sr=SR, strength=1.0, max_boost_db=12.0,
                     fmax=16000.0):
    """Re-tilt `cleaned` so its average spectrum matches `orig`.

    strength     0..1, how fully to match (1 = full correction).
    max_boost_db clamp so a near-silent band can't be boosted into a roar.
    fmax         leave content above this untouched (keeps the top airy, not
                 re-energised from noise).
    """
    f, _, Xo = stft(orig, fs=sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    f, _, Xc = stft(cleaned, fs=sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    mo = np.abs(Xo).mean(axis=1) + 1e-9
    mc = np.abs(Xc).mean(axis=1) + 1e-9
    eo = _third_octave_env(mo, f)
    ec = _third_octave_env(mc, f)
    gain_db = np.clip(20 * np.log10(eo / ec) * strength, -max_boost_db, max_boost_db)
    gain_db[f > fmax] = 0.0
    g = (10 ** (gain_db / 20.0))[:, None]
    _, y = istft(Xc * g, fs=sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    return _fit(y, len(cleaned))


def tame_highs(x, sr=SR, corner=7000.0, cut_db=4.0):
    """One-pole high-shelf cut above `corner` to soften papery hiss."""
    f, _, X = stft(x, fs=sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    shelf = 1.0 / (1.0 + np.maximum(f - corner, 0) / corner)   # 1 -> toward 0
    gain = 10 ** ((cut_db * (shelf - 1.0)) / 20.0)             # 0 dB low, -cut_db high
    _, y = istft(X * gain[:, None], fs=sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    return _fit(y, len(x))


def _fit(y, n):
    y = y[:n].astype(np.float32)
    return np.pad(y, (0, n - len(y))) if len(y) < n else y


def warmth(orig, cleaned, sr=SR, strength=1.0, tame=True):
    """Full 'de-tinny' pass: envelope restore (+ optional high-shelf tame)."""
    y = restore_envelope(orig, cleaned, sr, strength=strength)
    if tame:
        y = tame_highs(y, sr)
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 0.99:
        y = y * (0.99 / peak)
    return y
