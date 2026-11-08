"""Module 2 - Perceptual cleaner (masked-component substitution).

Why it matters: the Doppler attack lives on sound you can't hear - faint
fan/turbine tones buried under voices, wind and street noise. Your ears
ignore them because louder sound nearby in frequency "masks" them, but a
spectrogram integrated over many seconds still pulls the curve out.

What this does, per STFT frame:
  1. Split the spectrum into ~25 critical bands (Bark scale).
  2. Estimate the masking threshold in each band from the energy in that
     band and its neighbours (Schroeder spreading function).
  3. Any bin whose energy is below the threshold is, by definition, not
     audible. Its exact content is thrown away and replaced with noise of
     the band's band's average level and random phase - the same trick
     AAC calls Perceptual Noise Substitution. Ambience sounds the same;
     faint tonal lines (the Doppler evidence) become plain noise.
  4. Bins below the absolute threshold of hearing are zeroed.

Audible components (voices, music, an obvious overhead jet) are left alone.
Removing an AUDIBLE flyover is Module 3's job.
"""
import numpy as np
from scipy.signal import stft, istft

from .media import SR

NPERSEG = 2048      # 42.7 ms @ 48 kHz, ~23 Hz bins
NOVERLAP = 1536     # 75 % overlap


def bark(f):
    return 13.0 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def ath_db_spl(f):
    """Terhardt absolute threshold of hearing (dB SPL)."""
    f = np.maximum(f, 20.0) / 1000.0
    return 3.64 * f ** -0.8 - 6.5 * np.exp(-0.6 * (f - 3.3) ** 2) + 1e-3 * f ** 4


def spreading_matrix(nbands):
    """S[target, masker] linear power gain (Schroeder et al. 1979)."""
    z = np.arange(nbands) + 0.5
    dz = z[:, None] - z[None, :]
    sf_db = 15.81 + 7.5 * (dz + 0.474) - 17.5 * np.sqrt(1 + (dz + 0.474) ** 2)
    return 10 ** (sf_db / 10.0)


def clean(x, sr=SR, offset_db=5.0, playback_spl=90.0, seed=0, warmth=1.0,
          phase_mode="noise", smooth_frames=7):
    """Return (cleaned_audio, stats).

    offset_db     masking offset below the spread band energy. Lower = more
                  aggressive (more content counts as inaudible).
    playback_spl  assumed SPL of a 0 dBFS sine on playback, for the absolute
                  threshold. 90 dB is a loud listen; lower = more aggressive.
    warmth        0..1 de-tinny strength (post.warmth). 0 disables post-processing.
    phase_mode    how masked bins are re-phased (they always get the band-floor
                  magnitude, which is what erases the tonal evidence):
                    "noise"  - phase taken from one CONTINUOUS noise signal.
                               Reconstructs as smooth broadband comfort noise,
                               so NO wind/pops, yet still decorrelates any steady
                               tone so it integrates away. Default, recommended.
                    "random" - independent random phase per bin per frame. Also
                               decorrelates, but the per-frame jumps are the
                               "musical noise" that sounds like wind. Legacy.
                    "preserve" - keep the original phase. Cleanest sound but a
                               reduced-magnitude tone stays COHERENT and still
                               shows up on the attacker's spectrogram, so this
                               weakens the privacy. Offered for comparison only.
    smooth_frames  temporally smooth the substitution level over this many STFT
                  frames (odd). Stops the noise bed fluttering frame to frame.
                  1 disables; ~5 (≈55 ms) is a good default.
    """
    rng = np.random.default_rng(seed)
    f, _, X = stft(x, fs=sr, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    # scipy scales by 1/sum(window): a full-scale sine -> |X| = 0.5 at its bin.
    P = (2.0 * np.abs(X)) ** 2          # 0 dBFS sine -> 1.0

    z = bark(f)
    band = np.minimum(z.astype(int), 24)
    nb = band.max() + 1

    # Band energies E[b, t]
    E = np.zeros((nb, P.shape[1]))
    np.add.at(E, band, P)

    # Masking threshold per band, then broadcast back to bins
    T_band = (spreading_matrix(nb) @ E) * 10 ** (-offset_db / 10.0)
    T_bin = T_band[band, :]

    masked = P < T_bin

    # Substitute masked bins with noise at the band's mean masked-bin power
    # (energy-preserving, so ambience keeps its loudness)
    Pm = np.where(masked, P, 0.0)
    num = np.zeros_like(E); cnt = np.zeros_like(E)
    np.add.at(num, band, Pm); np.add.at(cnt, band, masked.astype(float))
    lvl = num / np.maximum(cnt, 1.0)

    # Temporally smooth the substitution level so the noise bed doesn't flutter
    # frame to frame (that flutter is the burbling / wind-like modulation).
    sf = int(smooth_frames)
    if sf > 1 and lvl.shape[1] >= sf:
        k = np.ones(sf) / sf
        lvl = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, lvl)

    # Incoherent overlap-add (random/noise phase) loses power by hop/N; coherent
    # (preserve) does not. Correct so loudness is unchanged either way.
    inc_gain = np.sqrt(NPERSEG / (NPERSEG - NOVERLAP))

    if phase_mode == "preserve":
        sub = (np.sqrt(lvl[band, :]) / 2.0) * np.exp(1j * np.angle(X))
    elif phase_mode == "random":
        sub = (inc_gain * np.sqrt(lvl[band, :]) / 2.0) * \
              np.exp(1j * rng.uniform(0, 2 * np.pi, size=X.shape))
    else:  # "noise": phase of one continuous noise signal -> smooth comfort noise.
        # Its phase is temporally coherent (it's a real signal), so overlap-add
        # keeps ~full power: no incoherent-gain correction here.
        _, _, XN = stft(rng.standard_normal(len(x)).astype(np.float32), fs=sr,
                        window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
        nphase = XN[:, : lvl.shape[1]] / (np.abs(XN[:, : lvl.shape[1]]) + 1e-12)
        sub = (np.sqrt(lvl[band, :]) / 2.0) * nphase

    ath_lin = 10 ** ((ath_db_spl(f) - playback_spl) / 10.0)[:, None]
    silent = P < ath_lin

    Y = np.where(masked, sub, X)
    Y = np.where(silent, 0.0, Y)

    _, y = istft(Y, fs=sr, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    y = y[: len(x)].astype(np.float32)
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))

    # De-tinny: restore the original's long-term tonal balance (and tame the
    # papery top). warmth=0 skips it; 1.0 = full envelope match.
    if warmth > 0:
        from . import post
        y = post.warmth(x, y, sr, strength=float(warmth))

    stats = {
        "bins_substituted_pct": float(round(100.0 * masked.mean(), 1)),
        "bins_zeroed_pct": float(round(100.0 * (silent & ~masked).mean(), 1)),
        "rms_change_db": float(round(20 * np.log10((np.sqrt(np.mean(y ** 2)) + 1e-12)
                                             / (np.sqrt(np.mean(x ** 2)) + 1e-12)), 2)),
    }
    return y, stats
