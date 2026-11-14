#!/usr/bin/env python3
"""Stellaris pipeline bouncing_ball_v1 (runs inside the isolated scientific worker).

Input : /input/manifest.json (worker manifest; read-only) and the one input video it lists.
Output: /output/result.json (worker result schema, docs/frontend-backend-contract.md section 10), derived artifacts
        (track CSV, summary JSON, annotated PNG frames, chart PNG), and /output/provenance.json
        (worker-reported method details; embedded by the backend in the run provenance).

Method (single ball, simple mostly static background, fixed camera):
  1. Decode with PyAV and use each frame's decoded presentation timestamp (pts * time_base,
     relative to the stream start). Frames without a timestamp are skipped and counted.
     Display-matrix / rotate-tag orientation is applied so pixel coordinates refer to the
     displayed frame (origin top-left, x right, y down), like experiment calibration points.
  2. Background = per-pixel median of up to 31 frames sampled evenly over the analysed
     interval. Foreground = max-channel |frame - background| above a threshold estimated
     from the background residuals (median + 6 * 1.4826 * MAD, floor 18).
  3. Each frame: connected components filtered by area (at least 1e-4 of the working-frame
     pixels), aspect ratio, and fill ratio; the component nearest the constant-velocity
     prediction (within a gate, with a consistent radius) is the ball; centroid weighted by
     the difference image. After five consecutive misses the old track history is discarded
     before reacquisition. Frames without an accepted component are recorded as `missing` or
     `rejected` with a reason. No position is interpolated or invented. The minimum component
     area means balls too small at the chosen working resolution are not supported.
  4. Ground contacts = prominent local maxima of image y. Each flight between contacts is
     fitted with y(t) = a t^2 + b t + c (least squares). Apex = vertex of the fitted
     parabola, accepted only if the vertex is bracketed by >= 2 detections on each side,
     a > 0, and the fit RMS is small.
  5. Common ground baseline = median ball-centre image y at the impact instants, each
     estimated by intersecting the fitted parabolas of the flights before and after a
     contact. (Fallback with a warning: the lowest sampled contact frame.) Apex height =
     baseline - apex y, i.e. the rise of the ball centre above its centre at impact.
  6. Height ratios h[k+1]/h[k] of consecutive bounces. Under a fixed-mass model with a
     common horizontal baseline, negligible air drag, and potential energy measured at the
     apex, the ratio equals the fraction of vertical mechanical energy retained per bounce.
  7. Metres only when the run snapshot has a reference-length calibration (scale from the
     backend); otherwise everything stays in pixels.
"""

import csv
import json
import math
import os
import platform
import sys

import av
import cv2
import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PIPELINE = "bouncing_ball_v1"
PIPELINE_VERSION = "1.0.0"
MANIFEST = "/input/manifest.json"
OUT = "/output"

ALLOWED_PARAMETERS = {"start_time_s", "end_time_s", "object_hint"}
WORK_MAX_DIM = 960
BG_SAMPLES = 31
MIN_THRESHOLD = 18.0
THRESHOLD_SEED = 0
MIN_FIT_POINTS = 5
CONTACT_WINDOW_S = 0.15
MAX_ANNOTATED = 12
MAX_FAILED_LISTED = 1000
RESET_AFTER_MISSES = 5
MIN_COMPONENT_AREA_FRACTION = 1e-4

cv2.setNumThreads(1)


class PipelineError(Exception):
    pass


def num(value, digits=6):
    """Finite float rounded for JSON, or None."""
    if value is None:
        return None
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


# -- decoding -----------------------------------------------------------------------

def rotation_of(frame, tag):
    """Counter-clockwise display rotation in degrees and where it came from."""
    rot = getattr(frame, "rotation", None)  # PyAV >= 13: display matrix side data.
    if isinstance(rot, (int, float)) and not isinstance(rot, bool) and rot != 0:
        return float(rot), "frame_display_matrix"
    if tag not in (None, ""):
        try:
            return -float(tag), "stream_rotate_tag"  # Legacy tag is clockwise.
        except ValueError:
            pass
    return 0.0, "none"


def iterate_frames(path, info):
    """Yield (frame_index, time_s or None, av frame, rotate_tag) in presentation order."""
    container = av.open(path, mode="r")
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        tb = stream.time_base
        origin = float(stream.start_time * tb) if (stream.start_time is not None and tb is not None) else None
        tag = (stream.metadata or {}).get("rotate")
        info.setdefault("codec", stream.codec_context.name)
        info.setdefault("time_base", str(tb))
        info.setdefault("average_rate", str(stream.average_rate))
        info.setdefault("stream_start_time_s", origin)
        info.setdefault("timestamp_origin", "stream_start_time" if origin is not None else "first_decoded_frame")
        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None or tb is None:
                yield index, None, frame, tag
                continue
            t = float(frame.pts * tb)
            if origin is None:
                origin = t
            t -= origin
            if -1e-6 < t < 0:
                t = 0.0
            yield index, t, frame, tag
    finally:
        container.close()


def oriented(frame, tag, info):
    img = frame.to_ndarray(format="bgr24")
    rot, source = rotation_of(frame, tag)
    k = int(round(rot / 90.0)) % 4
    if "rotation_deg" not in info:
        info["rotation_deg"], info["rotation_source"], info["rotation_quarter_turns_ccw"] = rot, source, k
        if abs(rot - round(rot / 90.0) * 90.0) > 1.0:
            info["rotation_note"] = "Rotation is not a multiple of 90 degrees; rounded to the nearest quarter turn."
    if k:
        img = np.ascontiguousarray(np.rot90(img, k))
    return img


class Scaler:
    def __init__(self, shape):
        h, w = shape[:2]
        self.full = (w, h)
        self.s = min(1.0, WORK_MAX_DIM / float(max(w, h)))
        self.size = (max(1, int(round(w * self.s))), max(1, int(round(h * self.s))))

    def small(self, img):
        return img if self.s >= 1.0 else cv2.resize(img, self.size, interpolation=cv2.INTER_AREA)

    def to_full(self, v):
        return v if self.s >= 1.0 else (v + 0.5) / self.s - 0.5

    def len_full(self, v):
        return v / self.s


# -- detection ----------------------------------------------------------------------

K3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
K5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))


def background_and_threshold(samples):
    stack = np.stack(samples)
    bg = np.empty(stack.shape[1:], dtype=np.uint8)
    for r in range(0, stack.shape[1], 32):
        bg[r:r + 32] = np.clip(np.rint(np.median(stack[:, r:r + 32], axis=0)), 0, 255).astype(np.uint8)
    rng = np.random.default_rng(THRESHOLD_SEED)
    picks = []
    for sample in samples[:: max(1, len(samples) // 8)]:
        d = cv2.absdiff(sample, bg).max(axis=2).ravel()
        picks.append(d[rng.integers(0, d.size, min(d.size, 20000))])
    d = np.concatenate(picks).astype(np.float64)
    med = float(np.median(d))
    mad = float(np.median(np.abs(d - med)))
    return bg, max(MIN_THRESHOLD, med + 6.0 * 1.4826 * mad), {"residual_median": med, "residual_mad": mad}


def candidates(small, bg, threshold, min_area, max_area):
    diff = cv2.absdiff(small, bg).max(axis=2)
    mask = (diff > threshold).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, K3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, K5)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    found = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < min_area or area > max_area:
            continue
        if not 0.4 <= w / float(h) <= 2.5 or area / float(w * h) < 0.45:
            continue
        sub = (labels[y:y + h, x:x + w] == i)
        weights = diff[y:y + h, x:x + w].astype(np.float64) * sub
        total = weights.sum()
        if total <= 0:
            continue
        ys, xs = np.mgrid[0:h, 0:w]
        found.append({"cx": x + float((xs * weights).sum() / total), "cy": y + float((ys * weights).sum() / total),
                      "area": area, "r": math.sqrt(area / math.pi)})
    return found, n - 1


class Tracker:
    def __init__(self, frame_dim):
        self.history = []  # (t, cx, cy, r) at working scale
        self.misses = 0
        self.gate_floor = 0.25 * frame_dim

    def predict(self, t):
        if not self.history or self.misses >= RESET_AFTER_MISSES:
            return None
        if len(self.history) >= 2:
            (t1, x1, y1, _), (t2, x2, y2, _) = self.history[-2], self.history[-1]
            if 0 < t2 - t1 <= 0.3:
                k = (t - t2) / (t2 - t1)
                return x2 + k * (x2 - x1), y2 + k * (y2 - y1)
        return self.history[-1][1], self.history[-1][2]

    def ref_radius(self):
        if not self.history:
            return None
        return float(np.median([h[3] for h in self.history[-15:]]))

    def choose(self, t, found):
        # A reacquisition starts a new track. Old radii and velocities may describe
        # foreground noise or a distractor that caused the preceding lost track.
        if self.misses >= RESET_AFTER_MISSES:
            self.history.clear()
        if not found:
            self.misses += 1
            return None, "no foreground component passed the size/shape filters"
        pred, r_ref = self.predict(t), self.ref_radius()
        pool = found
        if r_ref is not None and self.misses < RESET_AFTER_MISSES:
            pool = [c for c in found if 0.5 * r_ref <= c["r"] <= 2.0 * r_ref]
            if not pool:
                self.misses += 1
                return None, "candidate radius inconsistent with the tracked ball"
        if pred is not None:
            gate = max(6.0 * (r_ref or 1.0), self.gate_floor)
            best = min(pool, key=lambda c: math.hypot(c["cx"] - pred[0], c["cy"] - pred[1]))
            if math.hypot(best["cx"] - pred[0], best["cy"] - pred[1]) > gate:
                self.misses += 1
                return None, "nearest candidate outside the tracking gate"
        else:
            best = max(pool, key=lambda c: c["area"])
        self.history.append((t, best["cx"], best["cy"], best["r"]))
        self.misses = 0
        return best, None


# -- trajectory analysis ------------------------------------------------------------

def fit_parabola(t, y):
    tm = float(t.mean())
    tau = t - tm
    X = np.column_stack([tau ** 2, tau, np.ones_like(tau)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(t) - 3
    s2 = float(resid @ resid) / dof if dof > 0 else float("nan")
    cov = s2 * np.linalg.inv(X.T @ X)
    a, b, c = (float(v) for v in coef)
    return {"a": a, "b": b, "c": c, "tm": tm, "cov": cov, "rms": float(np.sqrt(np.mean(resid ** 2))), "n": len(t)}


def parabola_at(fit, t):
    tau = t - fit["tm"]
    return fit["a"] * tau ** 2 + fit["b"] * tau + fit["c"]


def poly_coefficients(fit):
    a, b, c, tm = fit["a"], fit["b"], fit["c"], fit["tm"]
    return a, b - 2 * a * tm, a * tm * tm - b * tm + c


def find_contacts(t, y, prominence, min_gap):
    contacts = []
    for i in range(1, len(t) - 1):
        lo, hi = max(0, i - 2), min(len(t), i + 3)
        if y[i] < y[lo:hi].max():
            continue
        left = (t >= t[i] - CONTACT_WINDOW_S) & (t < t[i])
        right = (t > t[i]) & (t <= t[i] + CONTACT_WINDOW_S)
        if left.sum() < 2 or right.sum() < 2:
            continue
        if y[i] - y[left].min() < prominence or y[i] - y[right].min() < prominence:
            continue
        if contacts and t[i] - t[contacts[-1]] < min_gap:
            if y[i] > y[contacts[-1]]:
                contacts[-1] = i
            continue
        contacts.append(i)
    return contacts


def analyse_flights(t, y, contacts):
    bounds = [-1] + contacts + [len(t)]
    flights = []
    for k in range(len(bounds) - 1):
        idx = np.arange(bounds[k] + 1, bounds[k + 1])
        flight = {"index": k, "edge": k == 0 or k == len(bounds) - 2, "point_indices": idx.tolist(),
                  "n_points": int(len(idx)), "fit": None, "apex": None, "status": None, "reason": None}
        flights.append(flight)
        if len(idx) < MIN_FIT_POINTS:
            flight["status"], flight["reason"] = "missing", f"only {len(idx)} detections in this flight (need {MIN_FIT_POINTS})"
            continue
        fit = fit_parabola(t[idx], y[idx])
        flight["fit"] = fit
        span = float(y[idx].max() - y[idx].min())
        rms_limit = max(2.0, 0.03 * span)
        if fit["a"] <= 0:
            flight["status"], flight["reason"] = "rejected", "fitted curvature is not downward-accelerating"
            continue
        if fit["rms"] > rms_limit:
            flight["status"], flight["reason"] = "rejected", (
                f"poor parabolic fit (RMS {fit['rms']:.2f} px > {rms_limit:.2f} px); a contact may have been missed")
            continue
        a, b, c = fit["a"], fit["b"], fit["c"]
        tau = -b / (2 * a)
        t_apex = fit["tm"] + tau
        before = int((t[idx] < t_apex).sum())
        after = int((t[idx] > t_apex).sum())
        if before < 2 or after < 2:
            flight["status"], flight["reason"] = "missing", (
                f"apex not bracketed by detections ({before} before, {after} after)")
            continue
        grad = np.array([b * b / (4 * a * a), -b / (2 * a), 1.0])
        var = float(grad @ fit["cov"] @ grad)
        flight["apex"] = {"t": t_apex, "y": c - b * b / (4 * a), "se": math.sqrt(var) if math.isfinite(var) and var >= 0 else None}
        flight["status"] = "valid"
    return flights


def impacts_between(flights, t, contacts):
    found = []
    for k, ci in enumerate(contacts):
        f1, f2 = flights[k], flights[k + 1]
        if not (f1["fit"] and f2["fit"] and f1["status"] in ("valid", "missing") and f2["status"] in ("valid", "missing")):
            continue
        if f1["fit"]["a"] <= 0 or f2["fit"]["a"] <= 0:
            continue
        p1, p2 = poly_coefficients(f1["fit"]), poly_coefficients(f2["fit"])
        roots = np.roots([p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]])
        lo = t[f1["point_indices"][-1]] if f1["point_indices"] else t[ci]
        hi = t[f2["point_indices"][0]] if f2["point_indices"] else t[ci]
        real = [float(r.real) for r in roots if abs(r.imag) < 1e-9 and lo - 1e-6 <= r.real <= hi + 1e-6]
        if not real:
            continue
        ti = min(real, key=lambda r: abs(r - t[ci]))
        yi = 0.5 * (parabola_at(f1["fit"], ti) + parabola_at(f2["fit"], ti))
        found.append({"contact_index": int(ci), "t": ti, "y": yi})
    return found


# -- output helpers -----------------------------------------------------------------

def write_json(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    os.replace(tmp, path)


def draw_text(img, text, org, scale, color):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), max(2, int(4 * scale)), cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, max(1, int(2 * scale)), cv2.LINE_AA)


def main():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    params = manifest.get("parameters") or {}
    unknown = sorted(set(params) - ALLOWED_PARAMETERS)
    if unknown:
        raise PipelineError(f"Unknown parameters: {unknown}")
    videos = [a for a in manifest["inputs"] if a["kind"] == "video"]
    if len(videos) != 1:
        raise PipelineError("bouncing_ball_v1 requires exactly one input video.")
    video = videos[0]
    vid_id = video["artifact_id"]
    t0 = float(params.get("start_time_s", 0.0))
    t1 = params.get("end_time_s")
    t1 = float(t1) if t1 is not None else None
    object_hint = params.get("object_hint", "ball")
    simulated = video["origin"] == "simulated"
    origin = "simulated" if simulated else "derived"
    cal_mode = manifest["calibration"]["mode"]
    conversion = manifest.get("calibration_conversion") or {}
    mpp = conversion.get("meters_per_pixel") if cal_mode == "reference_length" else None
    mpp_rel = conversion.get("relative_uncertainty") if mpp is not None else None
    warnings = []
    info = {}
    duration_s = (video.get("metadata") or {}).get("duration_ms", 0) / 1000.0
    end = t1 if t1 is not None else duration_s
    span = max(end - t0, 1e-6)
    print(f"{PIPELINE} {PIPELINE_VERSION}: analysing [{t0:.3f}, {('end' if t1 is None else f'{t1:.3f}')}] s of {vid_id}",
          flush=True)

    # Pass 1: background samples and frame inventory.
    sample_times = [t0 + (k + 0.5) * span / BG_SAMPLES for k in range(BG_SAMPLES)]
    samples, ptr, untimed, frames_in_interval, scaler = [], 0, 0, 0, None
    gen = iterate_frames(video["path"], info)
    try:
        for _index, t, frame, tag in gen:
            if t is None:
                untimed += 1
                continue
            if t < t0:
                continue
            if t1 is not None and t > t1:
                break
            frames_in_interval += 1
            if ptr < len(sample_times) and t >= sample_times[ptr]:
                img = oriented(frame, tag, info)
                scaler = scaler or Scaler(img.shape)
                samples.append(scaler.small(img))
                while ptr < len(sample_times) and t >= sample_times[ptr]:
                    ptr += 1
    finally:
        gen.close()
    if untimed:
        warnings.append({"code": "UNTIMED_FRAMES",
                         "message": f"{untimed} decoded frames had no presentation timestamp and were not analysed."})

    meta = video.get("metadata") or {}
    rows, det = [], []
    threshold, residuals = None, {}
    if scaler is not None:
        full_w, full_h = scaler.full
        if (meta.get("width_px"), meta.get("height_px")) not in ((full_w, full_h), (None, None)):
            warnings.append({"code": "ORIENTATION_MISMATCH", "message": (
                f"Decoded oriented frames are {full_w}x{full_h} px but upload inspection reported "
                f"{meta.get('width_px')}x{meta.get('height_px')} px; orientation handling may differ.")})
            if mpp is not None:
                mpp = mpp_rel = None
                warnings.append({"code": "CALIBRATION_DISABLED", "message":
                                 "Metric conversion disabled because calibration points may refer to a differently oriented frame."})
    if len(samples) >= 3:
        bg, threshold, residuals = background_and_threshold(samples)
        frame_area = bg.shape[0] * bg.shape[1]
        # Exclude tiny background speckles before they can seed the track's radius.
        min_area, max_area = max(9, int(MIN_COMPONENT_AREA_FRACTION * frame_area)), int(0.2 * frame_area)
        tracker = Tracker(max(bg.shape[:2]))
        # Pass 2: per-frame detection.
        gen = iterate_frames(video["path"], {})
        try:
            for index, t, frame, tag in gen:
                if t is None or t < t0:
                    continue
                if t1 is not None and t > t1:
                    break
                small = scaler.small(oriented(frame, tag, {}))
                found, raw = candidates(small, bg, threshold, min_area, max_area)
                best, reason = tracker.choose(t, found)
                row = {"frame_index": index, "time_s": t, "status": "detected" if best else ("rejected" if found else "missing"),
                       "x_px": None, "y_px": None, "radius_px": None, "area_px": None, "candidates": len(found),
                       "raw_components": raw, "reason": reason or ""}
                if best:
                    row.update(x_px=scaler.to_full(best["cx"]), y_px=scaler.to_full(best["cy"]),
                               radius_px=scaler.len_full(best["r"]), area_px=best["area"] / (scaler.s ** 2))
                    det.append(len(rows))
                rows.append(row)
        finally:
            gen.close()
    else:
        warnings.append({"code": "INSUFFICIENT_EVIDENCE", "message":
                         f"Only {len(samples)} frames were available in the interval; a background model needs at least 3."})

    analysed = len(rows)
    n_det = len(det)
    failed = [r for r in rows if r["status"] != "detected"]
    if failed:
        warnings.append({"code": "MISSING_DETECTIONS", "message":
                         f"{len(failed)} of {analysed} analysed frames have no accepted ball detection "
                         f"({sum(r['status'] == 'missing' for r in failed)} missing, "
                         f"{sum(r['status'] == 'rejected' for r in failed)} rejected). No positions were interpolated."})

    t_arr = np.array([rows[i]["time_s"] for i in det], dtype=np.float64)
    y_arr = np.array([rows[i]["y_px"] for i in det], dtype=np.float64)
    frame_h = scaler.full[1] if scaler else 0
    dt_med = float(np.median(np.diff(t_arr))) if len(t_arr) >= 2 else None
    prominence = max(3.0, 0.01 * frame_h)
    contacts = find_contacts(t_arr, y_arr, prominence, 2.5 * dt_med) if dt_med else []
    flights = analyse_flights(t_arr, y_arr, contacts) if len(t_arr) else []
    impacts = impacts_between(flights, t_arr, contacts) if flights else []

    baseline = baseline_se = None
    baseline_method = None
    if impacts:
        ys = np.array([imp["y"] for imp in impacts])
        baseline = float(np.median(ys))
        baseline_se = float(np.std(ys, ddof=1) / math.sqrt(len(ys))) if len(ys) >= 2 else None
        baseline_method = ("median ball-centre image y at impact instants estimated by intersecting fitted "
                           f"parabolas of adjacent flights ({len(ys)} impacts)")
    elif contacts:
        baseline = float(y_arr[contacts].max())
        baseline_method = "lowest sampled contact frame (fallback; biased toward smaller heights)"
        warnings.append({"code": "BASELINE_FROM_CONTACT_FRAMES", "message":
                         "Impact instants could not be estimated from adjacent flight fits; the baseline is the lowest "
                         "sampled contact position, which underestimates apex heights."})
    if len(impacts) == 1:
        warnings.append({"code": "BASELINE_SINGLE_IMPACT", "message":
                         "The baseline comes from one impact, so its uncertainty (and that of the heights) is unknown."})
    if impacts and len(impacts) >= 2:
        spread = max(i["y"] for i in impacts) - min(i["y"] for i in impacts)
        if spread > max(3.0, 0.01 * frame_h):
            warnings.append({"code": "BASELINE_SPREAD", "message":
                             f"Impact positions vary by {spread:.1f} px; the ground may not be level in the image or "
                             "perspective changes along the path."})

    # Rows -> heights.
    for r in rows:
        r["height_above_baseline_px"] = (baseline - r["y_px"]) if (baseline is not None and r["y_px"] is not None) else None
        r["height_above_baseline_m"] = (r["height_above_baseline_px"] * mpp
                                        if (mpp is not None and r["height_above_baseline_px"] is not None) else None)

    os.makedirs(os.path.join(OUT, "tracks"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "charts"), exist_ok=True)
    with open(os.path.join(OUT, "tracks", "track.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["frame_index", "time_s", "status", "x_px", "y_px", "radius_px", "area_px",
                    "height_above_baseline_px", "height_above_baseline_m", "candidates", "reason"])
        for r in rows:
            w.writerow([r["frame_index"], f"{r['time_s']:.6f}", r["status"]] +
                       ["" if r[k] is None else f"{r[k]:.4f}" for k in
                        ("x_px", "y_px", "radius_px", "area_px", "height_above_baseline_px")] +
                       ["" if r["height_above_baseline_m"] is None else f"{r['height_above_baseline_m']:.6f}",
                        r["candidates"], r["reason"]])

    def det_row(i):  # detection-array index -> CSV row index
        return det[i]

    def nearest_det(t):
        return int(np.argmin(np.abs(t_arr - t)))

    measurements, claims, artifacts = [], [], []
    base_assumptions = [
        "Single ball against a mostly static background with a fixed camera.",
        "Ball moves in a plane parallel to the image plane; perspective and lens distortion are not corrected.",
        f"Common ground baseline: {baseline_method}." if baseline_method else "No ground baseline could be estimated.",
        "Heights are rises of the ball centre above its centre at impact (equal to rises of the ball's lowest point "
        "for a rigid ball of constant apparent size).",
    ]
    if simulated:
        base_assumptions.insert(0, "SIMULATED INPUT: the analysed video is synthetic, not an observed experiment.")
    track_ev = lambda row_index, frame_index=None, time_s=None: {  # noqa: E731
        "artifact": {"output_artifact_key": "track_csv"}, "frame_index": frame_index,
        "time_s": num(time_s), "row_index": row_index}
    video_ev = lambda frame_index, time_s: {  # noqa: E731
        "artifact": {"input_artifact_id": vid_id}, "frame_index": frame_index, "time_s": num(time_s), "row_index": None}

    def measurement(key, series, quantity, value, unit, time_s, unc, method, status, evidence, assumptions):
        measurements.append({
            "local_key": key, "series": series, "quantity": quantity,
            "value": num(value) if status == "valid" else None, "unit": unit, "time_s": num(time_s),
            "uncertainty": {"absolute": num(unc) if status == "valid" else None,
                            "method": method if (status == "valid" and unc is not None) else None},
            "status": status, "evidence": evidence, "calibration_mode": cal_mode, "data_origin": origin,
            "assumptions": assumptions})

    if analysed:
        measurement("detection_fraction", "tracking", "detected_frame_fraction", n_det / analysed, "1", None, None, None,
                    "valid", [track_ev(None), video_ev(rows[0]["frame_index"], rows[0]["time_s"])],
                    [f"{n_det} of {analysed} decoded frames in the interval have an accepted detection."])

    # Apex heights (one measurement per flight whose apex was attempted).
    apex_keys, annotate = {}, {}
    heights = {}
    for f in flights:
        k = f["index"]
        if f["edge"] and f["status"] != "valid":
            continue  # Partial flight cut by the interval edge: no bounce observed, nothing to report.
        key = f"apex_{k + 1:02d}"
        apex_keys[k] = key
        if f["status"] == "valid":
            a = f["apex"]
            i = nearest_det(a["t"])
            h = (baseline - a["y"]) if baseline is not None else None
            if h is None:
                status, reason = "missing", "no ground baseline is available"
            elif h <= 0:
                status, reason = "rejected", "apex is not above the estimated baseline"
            else:
                status, reason = "valid", None
            se = math.sqrt(a["se"] ** 2 + baseline_se ** 2) if (a["se"] is not None and baseline_se is not None) else None
            heights[k] = (h, se, a["t"], i) if status == "valid" else None
            frame_index = rows[det_row(i)]["frame_index"]
            if len(annotate) < MAX_ANNOTATED:
                annotate[frame_index] = {"key": f"apex_{k + 1:02d}_frame", "label": key, "flight": k, "det": i}
            evidence = [track_ev(det_row(i), frame_index, rows[det_row(i)]["time_s"]),
                        video_ev(frame_index, rows[det_row(i)]["time_s"])]
            if frame_index in annotate and annotate[frame_index]["flight"] == k:
                evidence.append({"artifact": {"output_artifact_key": annotate[frame_index]["key"]},
                                 "frame_index": 0, "time_s": None, "row_index": None})
            assumptions = base_assumptions + ([f"Not reported: {reason}."] if reason else []) + [
                f"Apex from a least-squares parabola over {f['n_points']} detections (fit RMS {f['fit']['rms']:.3f} px)."]
            method = ("parabola-vertex standard error combined with baseline standard error; excludes perspective, "
                      "motion blur, and segmentation bias")
            measurement(key + "_px", "apex_height_px", "apex_height", h, "px", a["t"], se, method, status, evidence,
                        assumptions)
            if mpp is not None:
                se_m = (math.sqrt((se * mpp) ** 2 + (h * mpp * mpp_rel) ** 2)
                        if (se is not None and mpp_rel is not None and h is not None) else None)
                measurement(key + "_m", "apex_height_m", "apex_height", h * mpp if h is not None else None, "m", a["t"],
                            se_m, method + "; plus reference-length relative uncertainty", status, evidence,
                            assumptions + ["Metres use the run's reference-length calibration (meters_per_pixel)."])
            g_px = 2 * f["fit"]["a"]
            g_se = 2 * math.sqrt(f["fit"]["cov"][0, 0]) if f["fit"]["cov"][0, 0] >= 0 else None
            g_method = "least-squares standard error of the quadratic coefficient (frame timestamps taken as exact)"
            measurement(f"flight_{k + 1:02d}_accel_px", "flight_fit", "vertical_acceleration", g_px, "px/s^2", a["t"],
                        g_se, g_method, "valid", [track_ev(det_row(f["point_indices"][0]))],
                        base_assumptions[:2] + ["Constant downward acceleration during free flight; drag neglected."])
            if mpp is not None:
                measurement(f"flight_{k + 1:02d}_accel_m", "flight_fit", "vertical_acceleration", g_px * mpp, "m/s^2",
                            a["t"], (math.sqrt((g_se * mpp) ** 2 + (g_px * mpp * mpp_rel) ** 2)
                                     if (g_se is not None and mpp_rel is not None) else None),
                            g_method + "; plus reference-length relative uncertainty", "valid",
                            [track_ev(det_row(f["point_indices"][0]))],
                            base_assumptions[:2] + ["Constant downward acceleration during free flight; drag neglected.",
                                                    "Compare with 9.81 m/s^2 to check the calibration and frame timing."])
        else:
            heights[k] = None
            ev = [track_ev(det_row(f["point_indices"][0])) if f["point_indices"] else track_ev(None)]
            if f["point_indices"]:
                r0 = rows[det_row(f["point_indices"][0])]
                ev.append(video_ev(r0["frame_index"], r0["time_s"]))
                if len(annotate) < MAX_ANNOTATED:
                    annotate[r0["frame_index"]] = {"key": f"apex_{k + 1:02d}_frame", "label": key + " (not measured)",
                                                   "flight": k, "det": f["point_indices"][0]}
            measurement(key + "_px", "apex_height_px", "apex_height", None, "px", None, None, None, f["status"], ev,
                        base_assumptions + [f"Not measured: {f['reason']}."])

    # Ratios between consecutive reported flights.
    ratio_values = []
    ordered = sorted(heights)
    for k1, k2 in zip(ordered, ordered[1:]):
        if k2 != k1 + 1:
            continue
        a, b = heights[k1], heights[k2]
        key = f"ratio_{k1 + 1:02d}_{k2 + 1:02d}"
        model = ["Fixed ball mass; air drag negligible; common horizontal ground baseline.",
                 "Apex potential energy relative to the baseline represents the vertical mechanical energy of each flight."]
        if a is None or b is None:
            ev = [track_ev(None)]
            for k in (k1, k2):
                if heights.get(k):
                    ev = [track_ev(det_row(heights[k][3]))]
            text = f"Not computed: apex {k1 + 1 if a is None else k2 + 1} was not measured."
            measurement(key, "height_ratio", "apex_height_ratio", None, "1", None, None, None, "missing", ev,
                        base_assumptions + [text])
            measurement(key + "_energy", "energy_retention", "vertical_energy_retention_fraction", None, "1", None, None,
                        None, "missing", ev, base_assumptions + model + [text])
            continue
        r = b[0] / a[0]
        unc = r * math.sqrt((a[1] / a[0]) ** 2 + (b[1] / b[0]) ** 2) if (a[1] is not None and b[1] is not None) else None
        method = "first-order propagation of the two height uncertainties (shared-baseline correlation ignored)"
        ev = [track_ev(det_row(a[3]), rows[det_row(a[3])]["frame_index"], rows[det_row(a[3])]["time_s"]),
              track_ev(det_row(b[3]), rows[det_row(b[3])]["frame_index"], rows[det_row(b[3])]["time_s"]),
              {"artifact": {"output_artifact_key": "chart"}, "frame_index": None, "time_s": None, "row_index": None}]
        measurement(key, "height_ratio", "apex_height_ratio", r, "1", b[2], unc, method, "valid", ev,
                    base_assumptions + ["Ratio of consecutive apex heights h[k+1]/h[k] (dimensionless; scale cancels)."])
        measurement(key + "_energy", "energy_retention", "vertical_energy_retention_fraction", r, "1", b[2], unc, method,
                    "valid", ev, base_assumptions + model)
        ratio_values.append((key, r))

    mean_key = None
    if ratio_values:
        vals = np.array([v for _, v in ratio_values])
        mean_key = "mean_ratio"
        se = float(np.std(vals, ddof=1) / math.sqrt(len(vals))) if len(vals) >= 2 else None
        measurement(mean_key, "summary", "mean_apex_height_ratio", float(vals.mean()), "1", None, se,
                    "standard error of the mean of consecutive ratios (scatter only)", "valid",
                    [{"artifact": {"output_artifact_key": "summary_json"}, "frame_index": None, "time_s": None,
                      "row_index": None},
                     {"artifact": {"output_artifact_key": "chart"}, "frame_index": None, "time_s": None, "row_index": None}],
                    base_assumptions + [f"Mean of {len(vals)} consecutive apex-height ratios."])

    n_valid_heights = sum(1 for v in heights.values() if v)
    if n_valid_heights < 2:
        warnings.append({"code": "INSUFFICIENT_EVIDENCE", "message":
                         f"Only {n_valid_heights} bounce apex height(s) could be measured; at least two are needed for a "
                         "height ratio. Check the interval, lighting, and that one ball is clearly visible."})
    if simulated:
        warnings.append({"code": "SIMULATED_INPUT", "message":
                         "The input video is labelled simulated; all derived values are simulated, not observations."})
    warnings = [w for i, w in enumerate(warnings) if w not in warnings[:i]]

    # Pass 3: annotated frames.
    overlay = [(rows[i]["x_px"], rows[i]["y_px"]) for i in det]
    if det and len(annotate) < MAX_ANNOTATED + 1:
        best_k = max((k for k, v in heights.items() if v), key=lambda k: heights[k][0], default=None)
        overview_frame = rows[det_row(heights[best_k][3])]["frame_index"] if best_k is not None else rows[det[0]]["frame_index"]
        annotate.setdefault(overview_frame, {"key": "overview_frame", "label": "trajectory overview", "flight": None,
                                             "det": None})
    written = {}
    if annotate:
        needed = set(annotate)
        last = max(needed)
        row_by_frame = {r["frame_index"]: r for r in rows}
        gen = iterate_frames(video["path"], {})
        try:
            for index, t, frame, tag in gen:
                if index > last:
                    break
                if index not in needed:
                    continue
                img = oriented(frame, tag, {})
                h_img, w_img = img.shape[:2]
                scale = max(0.4, w_img / 1200.0)
                for x, y in overlay[:5000]:
                    cv2.circle(img, (int(round(x)), int(round(y))), max(1, int(2 * scale)), (0, 220, 255), -1, cv2.LINE_AA)
                if baseline is not None:
                    yb = int(round(baseline))
                    cv2.line(img, (0, yb), (w_img - 1, yb), (255, 200, 0), max(1, int(2 * scale)), cv2.LINE_AA)
                    draw_text(img, "baseline (centre at impact)", (8, max(15, yb - 6)), 0.5 * scale, (255, 200, 0))
                row = row_by_frame.get(index)
                if row and row["status"] == "detected":
                    cv2.circle(img, (int(round(row["x_px"])), int(round(row["y_px"]))), int(round(row["radius_px"])) + 2,
                               (0, 255, 0), max(1, int(2 * scale)), cv2.LINE_AA)
                spec = annotate[index]
                lines = [f"{spec['label']}  frame {index}  t={t:.3f} s"]
                k = spec["flight"]
                if k is not None and heights.get(k):
                    hk = heights[k]
                    ya = int(round(baseline - hk[0]))
                    cv2.line(img, (0, ya), (w_img - 1, ya), (0, 0, 255), max(1, int(scale)), cv2.LINE_AA)
                    lines.append(f"apex height {hk[0]:.1f} px" + (f" = {hk[0] * mpp:.3f} m" if mpp is not None else ""))
                elif k is not None:
                    lines.append("apex not measured: " + str(flights[k]["reason"])[:60])
                if simulated:
                    lines.insert(0, "SIMULATED INPUT - NOT OBSERVED DATA")
                for j, text in enumerate(lines):
                    draw_text(img, text, (8, int(22 * scale) * (j + 1) + 4), 0.6 * scale,
                              (80, 80, 255) if text.startswith("SIMULATED") else (255, 255, 255))
                name = f"frames/{spec['key']}.png"
                if cv2.imwrite(os.path.join(OUT, name), img):
                    written[spec["key"]] = (name, index)
        finally:
            gen.close()

    # Chart.
    chart_ok = False
    if len(t_arr):
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=110)
        unit = "m" if mpp is not None else "px"
        conv = mpp if mpp is not None else 1.0
        if baseline is not None:
            ax.plot(t_arr, (baseline - y_arr) * conv, ".", ms=3, color="#1f77b4", label="detected ball centre")
            for f in flights:
                if f["fit"] and f["status"] == "valid":
                    tt = np.linspace(t_arr[f["point_indices"][0]], t_arr[f["point_indices"][-1]], 100)
                    ax.plot(tt, (baseline - parabola_at(f["fit"], tt)) * conv, "-", lw=1, color="#ff7f0e")
            pts = [(v[2], v[0] * conv) for v in heights.values() if v]
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "v", color="#d62728", ms=8, label="apex (parabola vertex)")
            ax.axhline(0, color="#555555", lw=0.8)
            ax.set_ylabel(f"height above baseline ({unit})")
        else:
            ax.plot(t_arr, y_arr, ".", ms=3, label="detected ball centre (image y)")
            ax.invert_yaxis()
            ax.set_ylabel("image y (px, increasing downward)")
        miss_t = [r["time_s"] for r in rows if r["status"] != "detected"]
        if miss_t:
            ax.plot(miss_t, [ax.get_ylim()[0]] * len(miss_t), "x", color="#7f7f7f", ms=4, label="frame without detection")
        ax.set_xlabel("time (s, decoded timestamps)")
        ax.set_title(f"{PIPELINE}: bounce apex heights" + ("  [SIMULATED INPUT]" if simulated else ""))
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "charts", "apex_heights.png"), format="png")
        plt.close(fig)
        chart_ok = True

    summary = {
        "pipeline": PIPELINE, "pipeline_version": PIPELINE_VERSION, "input_artifact_id": vid_id,
        "simulated_input": simulated, "object_hint": object_hint,
        "interval_s": {"start": t0, "end": t1}, "frames_in_interval": frames_in_interval, "frames_analysed": analysed,
        "frames_detected": n_det, "frames_untimed": untimed, "median_frame_interval_s": num(dt_med),
        "threshold": num(threshold), "contact_prominence_px": num(prominence),
        "baseline": {"image_y_px": num(baseline), "standard_error_px": num(baseline_se), "method": baseline_method,
                     "impacts": [{"time_s": num(i["t"]), "image_y_px": num(i["y"])} for i in impacts]},
        "contacts": [{"time_s": num(t_arr[i]), "image_y_px": num(y_arr[i])} for i in contacts],
        "flights": [{"index": f["index"] + 1, "edge_of_interval": f["edge"], "detections": f["n_points"],
                     "status": f["status"], "reason": f["reason"],
                     "fit": None if not f["fit"] else {"a_px_per_s2": num(f["fit"]["a"]), "rms_px": num(f["fit"]["rms"])},
                     "apex": None if not f["apex"] else {"time_s": num(f["apex"]["t"]), "image_y_px": num(f["apex"]["y"]),
                                                         "standard_error_px": num(f["apex"]["se"])},
                     "apex_height_px": num(heights[f["index"]][0]) if heights.get(f["index"]) else None}
                    for f in flights],
        "ratios": [{"key": k, "value": num(v)} for k, v in ratio_values],
        "meters_per_pixel": num(mpp, 9), "calibration_mode": cal_mode,
        "csv_row_index": "0-based data row in tracks/track.csv, excluding the header",
        "warnings": warnings,
    }
    write_json(os.path.join(OUT, "bounce_summary.json"), summary)

    origin_art = origin
    artifacts.append({"local_key": "track_csv", "path": "tracks/track.csv", "kind": "dataset", "origin": origin_art,
                      "mime_type": "text/csv", "parents": [{"input_artifact_id": vid_id}]})
    artifacts.append({"local_key": "summary_json", "path": "bounce_summary.json", "kind": "dataset",
                      "origin": origin_art, "mime_type": "application/json",
                      "parents": [{"output_artifact_key": "track_csv"}]})
    if chart_ok:
        artifacts.append({"local_key": "chart", "path": "charts/apex_heights.png", "kind": "chart", "origin": origin_art,
                          "mime_type": "image/png", "parents": [{"output_artifact_key": "track_csv"}]})
    for key, (name, _index) in written.items():
        artifacts.append({"local_key": key, "path": name, "kind": "image", "origin": origin_art, "mime_type": "image/png",
                          "parents": [{"input_artifact_id": vid_id}, {"output_artifact_key": "track_csv"}]})

    # Drop evidence references to outputs that were not produced (e.g. a frame that failed to encode).
    produced = {a["local_key"] for a in artifacts}
    for m in measurements:
        m["evidence"] = [e for e in m["evidence"]
                         if "output_artifact_key" not in e["artifact"] or e["artifact"]["output_artifact_key"] in produced]

    prefix = "SIMULATED INPUT (not an observed experiment): " if simulated else ""
    valid_heights = [(k, v) for k, v in sorted(heights.items()) if v]
    if valid_heights:
        unit = "px"
        listing = ", ".join(f"h{k + 1} = {v[0]:.1f} {unit}" + (f" ({v[0] * mpp:.3f} m)" if mpp is not None else "")
                            for k, v in valid_heights)
        keys = [apex_keys[k] + "_px" for k, _ in valid_heights] + (["detection_fraction"] if analysed else [])
        claims.append({
            "local_key": "observed_apexes", "kind": "observation",
            "text": f"{prefix}The tracked ball was detected in {n_det} of {analysed} analysed frames, and "
                    f"{len(valid_heights)} bounce apex heights above the estimated ground baseline were measured: {listing}.",
            "measurement_keys": keys, "citations": [],
            "evidence": [track_ev(None)], "assumptions": base_assumptions,
            "limitations": ["Single fixed camera; no perspective correction.",
                            "Uncertainties are statistical fit errors only and exclude systematic effects."]})
    if ratio_values:
        mean_r = float(np.mean([v for _, v in ratio_values]))
        claims.append({
            "local_key": "energy_retention", "kind": "inference",
            "text": f"{prefix}Consecutive apex-height ratios average {mean_r:.3f}, so under the stated model each bounce "
                    f"retained about {100 * mean_r:.1f}% of the ball's vertical mechanical energy "
                    f"(equivalent coefficient of restitution about {math.sqrt(mean_r):.3f}).",
            "measurement_keys": [k for k, _ in ratio_values] + [k + "_energy" for k, _ in ratio_values] + [mean_key],
            "citations": [], "evidence": [track_ev(None)],
            "assumptions": base_assumptions + ["Fixed ball mass; air drag negligible; common horizontal ground baseline.",
                                               "Coefficient of restitution taken as the square root of the height ratio."],
            "limitations": ["Ratios from heights near the noise level are less reliable.",
                            "Horizontal motion and spin are ignored."]})

    write_json(os.path.join(OUT, "provenance.json"), {
        "pipeline": PIPELINE, "pipeline_version": PIPELINE_VERSION,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                    "pyav": av.__version__, "matplotlib": matplotlib.__version__},
        "parameters": {"start_time_s": t0, "end_time_s": t1, "object_hint": object_hint},
        "decode": info,
        "detection_method": ("median background over up to %d sampled frames; max-channel absolute difference "
                             "threshold; morphological open/close; connected components filtered by area/aspect/fill; "
                             "nearest-to-prediction selection with radius consistency; difference-weighted centroid; "
                             "discard track history after %d misses before reacquisition"
                             % (BG_SAMPLES, RESET_AFTER_MISSES)),
        "detection_limits": {"minimum_component_area_fraction_of_work_frame": MIN_COMPONENT_AREA_FRACTION,
                             "reacquire_after_consecutive_misses": RESET_AFTER_MISSES,
                             "reacquisition_discards_prior_track_history": True},
        "threshold": num(threshold), "threshold_residuals": {k: num(v) for k, v in residuals.items()},
        "random_seed": THRESHOLD_SEED, "work_scale": num(scaler.s) if scaler else None,
        "baseline": summary["baseline"],
        "calibration": {"mode": cal_mode, "meters_per_pixel": num(mpp, 9), "relative_uncertainty": num(mpp_rel, 9)},
        "failed_detections": {
            "count": len(failed),
            "listed": [{"frame_index": r["frame_index"], "time_s": num(r["time_s"]), "status": r["status"],
                        "reason": r["reason"]} for r in failed[:MAX_FAILED_LISTED]],
            "truncated": len(failed) > MAX_FAILED_LISTED},
        "warnings": warnings,
    })
    write_json(os.path.join(OUT, "result.json"),
               {"measurements": measurements, "claims": claims, "artifacts": artifacts, "warnings": warnings})
    print(f"{PIPELINE}: {n_det}/{analysed} frames detected, {len(contacts)} contacts, "
          f"{n_valid_heights} apex heights, {len(ratio_values)} ratios", flush=True)


if __name__ == "__main__":
    try:
        main()
    except PipelineError as exc:
        print(f"{PIPELINE} error: {exc}", file=sys.stderr, flush=True)
        sys.exit(2)
