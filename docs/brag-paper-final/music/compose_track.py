"""Original score for the Stellaris paper-drop film: "Release to Contact".

Instrumental downtempo electronica, 116 BPM, 4/4, D minor -> F major resolution.
Fully synthesized here (no samples, no third-party audio), so no licence is needed.
Arrangement follows the 118 s scene timeline in docs/brag-paper-final/animation-plan.md.

Usage: python3 compose_track.py OUT.wav [cues.json]
"""
import json, sys
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 48000
BPM = 116
BEAT = 60 / BPM
BAR = 4 * BEAT
DUR = 118.0
N = int(DUR * SR)
rng = np.random.default_rng(116)

# Chord cycle (one chord per bar), MIDI notes. Dm9 | Bbmaj7 | Fmaj7 | Csus2
CHORDS = [[50, 53, 57, 60, 64], [46, 50, 53, 57, 62], [41, 45, 48, 52, 57], [48, 50, 55, 60, 62]]
BASS = [38, 34, 41, 36]
FINAL = [41, 45, 48, 52, 55, 57, 64]  # Fmaj9 with added 13th colour
# Motif: 16th-step pattern (None = rest), degrees relative to chord tones.
MOTIF = [0, None, 2, None, 4, 3, None, 2, None, 0, None, 3, 4, None, 2, None]

hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
t_of = lambda bar, beat=0.0: bar * BAR + beat * BEAT


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def place(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def env(n, a, d):
    e = np.ones(n)
    na, nd = int(a * SR), int(d * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nd:
        e[-nd:] *= np.linspace(1, 0, nd)
    return e


def kick():
    t = np.arange(int(0.45 * SR)) / SR
    f = 44 + 80 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)


def rim():
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 40)
    noise = hp(lp(rng.standard_normal(n), 5200), 900) * np.exp(-t * 32)
    return 0.5 * body + 0.6 * noise


def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 70))


def pluck(m, dur=0.42):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    tri = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
    sig = 0.7 * tri + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 18)
    return sig * np.exp(-t * 6.5) * env(n, 0.004, 0.03)


def pad(notes, dur, bright=1400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        for det in (-0.08, 0.0, 0.07):
            f = hz(m + det)
            ph = rng.uniform(0, 1)
            s += 2 * ((f * t + ph) % 1.0) - 1
    s = lp(s / (3 * len(notes)), bright)
    return s * env(n, 0.6, 0.9)


def bass_note(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.25 * lp(2 * ((f * t) % 1.0) - 1, 420)
    return s * env(n, 0.01, 0.12) * (0.75 + 0.25 * np.exp(-t * 3))


def reverb_ir(sec=2.6):
    n = int(sec * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-t * 3.2)
    return lp(ir, 6000) * 0.12


# Arrangement by bar (bar k starts at k * BAR seconds). See SECTIONS below for scene mapping.
NBARS = int(np.ceil(DUR / BAR))
SECTIONS = [
    # (first_bar, last_bar_exclusive, name, layers)
    (0, 2, "hook", {"pad"}),
    (2, 5, "convergence", {"pad", "tick", "motif_soft"}),
    (5, 6, "brand", {"pad", "accent", "bass"}),
    (6, 12, "chat", {"pad", "kick", "bass", "hat"}),
    (12, 28, "sources-plan-simulation", {"pad", "kick", "bass", "hat", "rim", "motif"}),
    (28, 35, "physical-build", {"pad", "kick", "bass", "hat", "openhat", "rim", "motif", "bright"}),
    (35, 45, "upload-measurement", {"pad", "kick", "bass", "hat", "rim", "motif"}),
    (45, 52, "interpretation", {"pad", "bass", "motif_soft"}),
    (52, 56, "technical-context", {"pad", "kick", "bass", "hat", "motif_soft"}),
    (56, NBARS, "resolution", {"final"}),
]


def layers_for(bar):
    for a, b, name, ls in SECTIONS:
        if a <= bar < b:
            return name, ls
    return "resolution", {"final"}


L = {k: np.zeros(N) for k in ("drums", "bass", "pad", "motif", "fx")}
K, RIM, = kick(), rim()
cues = []
for bar in range(NBARS):
    name, ls = layers_for(bar)
    ch = CHORDS[bar % 4]
    t0 = t_of(bar)
    if bar == 0 or layers_for(bar - 1)[0] != name:
        cues.append({"time_s": round(t0, 4), "bar": bar, "section": name})
    if "final" in ls:
        if bar == SECTIONS[-1][0]:
            place(L["pad"], pad(FINAL, DUR - t0, bright=1700), t0, 1.1)
            place(L["bass"], bass_note(29, DUR - t0), t0, 0.9)
            for i, m in enumerate([65, 69, 72, 76, 79]):
                place(L["motif"], pluck(m, 1.6), t0 + i * BEAT / 2, 0.45)
            place(L["drums"], K, t0, 0.6)
        continue
    bright = 2300 if "bright" in ls else 1400
    place(L["pad"], pad(ch, BAR + 0.9, bright), t0, 1.0)
    if "bass" in ls:
        root = BASS[bar % 4]
        for beat, d in ((0, 1.4), (1.5, 0.45), (2.5, 1.2)):
            place(L["bass"], bass_note(root, d * BEAT), t_of(bar, beat), 0.8)
    if "kick" in ls:
        for beat in (0, 2.5) if bar % 2 else (0, 2):
            place(L["drums"], K, t_of(bar, beat), 0.95)
    if "rim" in ls:
        for beat in (1, 3):
            place(L["drums"], RIM, t_of(bar, beat) + 0.012, 0.35)
    if "hat" in ls or "tick" in ls:
        for e in range(8):
            swing = 0.035 * BEAT if e % 2 else 0.0
            g = (0.10 if e % 2 else 0.16) * (0.5 if "tick" in ls else 1.0)
            place(L["drums"], hat(), t_of(bar, e / 2) + swing, g)
    if "openhat" in ls:
        for beat in (1.5, 3.5):
            place(L["drums"], hat(True), t_of(bar, beat), 0.09)
    if "accent" in ls:
        place(L["fx"], pad([62, 69, 74, 76], 2.8, 3000) * np.exp(-np.arange(int(2.8 * SR)) / SR * 1.2), t0, 0.9)
    if "motif" in ls or "motif_soft" in ls:
        g = 0.32 if "motif" in ls else 0.18
        tones = sorted(set(ch)) + [m + 12 for m in sorted(set(ch))]
        for s, deg in enumerate(MOTIF):
            if deg is None:
                continue
            if "motif_soft" in ls and s % 4 not in (0, 2):
                continue
            place(L["motif"], pluck(tones[deg] + 12), t_of(bar, s / 4), g)

# Slow sidechain-style duck of pad/bass under kicks for pulse without loudness.
duck = np.ones(N)
for c in range(NBARS):
    if "kick" in layers_for(c)[1]:
        for beat in (0, 2):
            i = int(t_of(c, beat) * SR)
            n = int(0.28 * SR)
            if i < N:
                seg = 1 - 0.35 * np.exp(-np.arange(min(n, N - i)) / SR * 14)
                duck[i:i + len(seg)] *= seg

# Echo on motif (dotted 8th), then stereo mix with reverb send.
d = int(0.75 * BEAT * SR)
m = L["motif"].copy()
for k, g in ((1, 0.38), (2, 0.16)):
    m[d * k:] += g * L["motif"][:-d * k]
dry = {
    "drums": (L["drums"], 0.0, 0.08),
    "bass": (lp(L["bass"], 900) * duck, 0.0, 0.03),
    "pad": (L["pad"] * duck, 0.0, 0.35),
    "motif": (m, 0.18, 0.30),
    "fx": (L["fx"], 0.0, 0.5),
}
mix = np.zeros((2, N))
send = np.zeros(N)
for name, (sig, pan, rv) in dry.items():
    mix[0] += sig * np.sqrt(0.5 - pan / 2) * 1.414
    mix[1] += sig * np.sqrt(0.5 + pan / 2) * 1.414
    send += sig * rv
ir = reverb_ir()
for ch in range(2):
    mix[ch] += fftconvolve(send, ir[ch])[:N]
# Fade in 0.4 s; fade out across the final 2 s (close holds settled identity).
fade = np.ones(N)
fade[: int(0.4 * SR)] = np.linspace(0, 1, int(0.4 * SR))
fade[-int(2.0 * SR):] *= np.linspace(1, 0, int(2.0 * SR)) ** 1.5
mix *= fade
mix = np.tanh(1.2 * mix / np.max(np.abs(mix))) / np.tanh(1.2) * 0.89

out = sys.argv[1]
from scipy.io import wavfile
wavfile.write(out, SR, (mix.T * 32767).astype(np.int16))
beats = [round(b * BEAT, 4) for b in range(int(DUR / BEAT) + 1)]
meta = {"title": "Release to Contact", "bpm": BPM, "bar_s": round(BAR, 4), "duration_s": DUR,
        "key": "D minor -> F major", "sections": cues, "beats_s": beats,
        "downbeats_s": [round(b * BAR, 4) for b in range(NBARS)]}
if len(sys.argv) > 2:
    json.dump(meta, open(sys.argv[2], "w"), indent=1)
print(json.dumps({k: meta[k] for k in ("title", "bpm", "bar_s", "sections")}, indent=1))
