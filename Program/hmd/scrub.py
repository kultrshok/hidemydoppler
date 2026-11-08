"""Module 1 - Metadata scrubber.

Why it matters: the Doppler attack needs to know roughly WHEN a clip was
recorded so it can pull the right ADS-B flight tracks. A creation timestamp
shrinks that search from "any day, any hour" to a few minutes. GPS tags skip
the attack entirely. This module finds and strips them.
"""
import re

from .media import probe, run

# Tag-name patterns grouped by what they leak to the attacker.
LEAK_PATTERNS = {
    "time": [r"creation_?time", r"\bdate\b", r"creationdate", r"timecode",
             r"modif", r"^time$"],
    "location": [r"location", r"iso6709", r"\bgps", r"xyz", r"latitude",
                 r"longitude", r"altitude"],
    "device": [r"\bmake\b", r"\bmodel\b", r"software", r"encoder",
               r"com\.android", r"com\.apple", r"manufacturer", r"serial",
               r"lens", r"firmware"],
}


def _classify(key):
    k = key.lower()
    hits = [cat for cat, pats in LEAK_PATTERNS.items()
            if any(re.search(p, k) for p in pats)]
    # A location key also contains "com.apple" etc.; report the worst category.
    for worst in ("location", "time", "device"):
        if worst in hits:
            return worst
    return "other"


def report(path):
    """Return a list of findings: (category, where, key, value)."""
    info = probe(path)
    findings = []
    for k, v in info.get("format", {}).get("tags", {}).items():
        findings.append((_classify(k), "container", k, v))
    for s in info.get("streams", []):
        where = f"stream {s['index']} ({s.get('codec_type')}/{s.get('codec_name')})"
        if s.get("codec_type") in ("data", "subtitle", "attachment"):
            findings.append(("location", where, "<side track>",
                             "telemetry/timed-metadata track (may carry GPS)"))
        for k, v in s.get("tags", {}).items():
            findings.append((_classify(k), where, k, v))
    if info.get("chapters"):
        findings.append(("other", "container", "chapters", str(len(info["chapters"]))))
    return findings


def score(findings):
    """Simple 0-100 leak score: location 50, time 35, device 15 (capped)."""
    cats = {f[0] for f in findings}
    s = 0
    s += 50 if "location" in cats else 0
    s += 35 if "time" in cats else 0
    s += 15 if "device" in cats else 0
    return s


def scrub(src, dst, fake_time=None):
    """Strip all container/stream metadata, side tracks and chapters.

    Audio/video are stream-copied (no quality loss). If `fake_time` is given
    (ISO 8601), a decoy creation_time is written instead of none, which can
    send a time-gated attacker to the wrong flight data.
    """
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src,
           "-map", "0:v?", "-map", "0:a?",          # drop data/subtitle tracks
           "-map_metadata", "-1", "-map_metadata:s", "-1", "-map_chapters", "-1",
           "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
           "-metadata:s:v", "handler_name=", "-metadata:s:a", "handler_name=",
           "-c", "copy", "-movflags", "+faststart"]
    if fake_time:
        cmd += ["-metadata", f"creation_time={fake_time}"]
    cmd.append(dst)
    run(cmd)
    return report(dst)
