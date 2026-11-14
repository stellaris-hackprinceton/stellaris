"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Local camera/recording state, independent of any backend run state.
 *
 *   idle → requesting_permission → previewing → recording → reviewing
 *   requesting/previewing/recording → error (denied, unavailable, device lost) → idle
 *   reviewing → discard → idle
 *
 * Invariants:
 * - Camera access starts only from enable(), i.e. a user action. Video only, no microphone.
 * - Every exit (stop, discard, error, unmount) stops the MediaRecorder and every track.
 * - The review Blob gets one object URL, revoked when replaced, discarded or unmounted.
 */
export type CameraPhase = "idle" | "requesting_permission" | "previewing" | "recording" | "reviewing" | "error";
export type CameraError = "denied" | "unavailable" | "device_lost" | "no_supported_format" | "recorder_failed";

export type Recording = {
  blob: Blob;
  url: string;
  mime_type: string;
  recorded_at: string;
  duration_ms: number;
  stop_reason: "user" | "duration_limit" | "size_limit" | "device_lost";
};

type Limits = { accepted_mime_types: string[]; max_video_duration_ms: number; max_file_bytes: number };

const CANDIDATES = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4;codecs=avc1", "video/mp4"];

const baseType = (m: string) => m.split(";")[0].trim().toLowerCase();

/** A recorder MIME type the browser supports AND the server accepts, or null. */
export function pickRecorderMime(accepted: string[]): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  const ok = new Set(accepted.map(baseType));
  return CANDIDATES.find((m) => ok.has(baseType(m)) && MediaRecorder.isTypeSupported(m)) ?? null;
}

export function cameraSupported(): boolean {
  return typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== "undefined";
}

export function useCamera(limits: Limits | undefined) {
  const [phase, setPhase] = useState<CameraPhase>("idle");
  const [error, setError] = useState<CameraError | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const bytes = useRef(0);
  const startedAt = useRef(0);
  const recordedAt = useRef("");
  const stopReason = useRef<Recording["stop_reason"]>("user");
  const timer = useRef<number | null>(null);
  const urlRef = useRef<string | null>(null);
  const discardOnStop = useRef(false);
  const mounted = useRef(true);

  const clearTimer = () => { if (timer.current != null) { window.clearInterval(timer.current); timer.current = null; } };

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (mounted.current) setStream(null);
  }, []);

  const revokeUrl = () => { if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = null; } };

  const stopRecorder = useCallback((reason: Recording["stop_reason"], discard = false) => {
    const r = recorderRef.current;
    clearTimer();
    if (r && r.state !== "inactive") {
      stopReason.current = reason;
      discardOnStop.current = discard;
      r.stop(); // onstop assembles the Blob (unless discarding) and stops tracks
    } else {
      stopTracks();
    }
  }, [stopTracks]);

  const fail = useCallback((e: CameraError) => {
    discardOnStop.current = true;
    stopRecorder("device_lost", true);
    stopTracks();
    setError(e);
    setPhase("error");
  }, [stopRecorder, stopTracks]);

  const enable = useCallback(async () => {
    if (!cameraSupported()) { setError("unavailable"); setPhase("error"); return; }
    setError(null);
    setPhase("requesting_permission");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (!mounted.current) { s.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = s;
      s.getVideoTracks().forEach((t) => t.addEventListener("ended", () => fail("device_lost")));
      setStream(s);
      setPhase("previewing");
    } catch (e) {
      const name = (e as DOMException)?.name;
      setError(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unavailable");
      setPhase("error");
    }
  }, [fail]);

  const start = useCallback(() => {
    const s = streamRef.current;
    if (!s || !limits) return;
    const mime = pickRecorderMime(limits.accepted_mime_types);
    if (!mime) { setError("no_supported_format"); setPhase("error"); stopTracks(); return; }
    let r: MediaRecorder;
    try { r = new MediaRecorder(s, { mimeType: mime }); } catch { setError("recorder_failed"); setPhase("error"); stopTracks(); return; }
    chunks.current = [];
    bytes.current = 0;
    discardOnStop.current = false;
    stopReason.current = "user";
    recordedAt.current = new Date().toISOString();
    r.ondataavailable = (ev) => {
      if (ev.data.size === 0) return;
      chunks.current.push(ev.data);
      bytes.current += ev.data.size;
      // Early local guard only; the backend's limits remain authoritative.
      if (bytes.current >= limits.max_file_bytes * 0.95) stopRecorder("size_limit");
    };
    r.onerror = () => fail("recorder_failed");
    r.onstop = () => {
      const duration = performance.now() - startedAt.current;
      recorderRef.current = null;
      stopTracks();
      if (discardOnStop.current || !mounted.current) { chunks.current = []; return; }
      const blob = new Blob(chunks.current, { type: mime });
      chunks.current = [];
      revokeUrl();
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      setRecording({ blob, url, mime_type: baseType(mime), recorded_at: recordedAt.current, duration_ms: duration, stop_reason: stopReason.current });
      setPhase("reviewing");
    };
    recorderRef.current = r;
    startedAt.current = performance.now();
    setElapsed(0);
    r.start(1000);
    setPhase("recording");
    timer.current = window.setInterval(() => {
      const t = performance.now() - startedAt.current;
      setElapsed(t);
      if (t >= limits.max_video_duration_ms) stopRecorder("duration_limit");
    }, 250);
  }, [limits, fail, stopRecorder, stopTracks]);

  const stop = useCallback(() => stopRecorder("user"), [stopRecorder]);

  /** Leave capture: stops camera/recording and drops any unuploaded review. */
  const discard = useCallback(() => {
    stopRecorder("user", true);
    stopTracks();
    revokeUrl();
    setRecording(null);
    setError(null);
    setElapsed(0);
    setPhase("idle");
  }, [stopRecorder, stopTracks]);

  // Unmount (route change, project change, capture panel closed): release everything.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimer();
      const r = recorderRef.current;
      if (r && r.state !== "inactive") { discardOnStop.current = true; r.stop(); }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      revokeUrl();
    };
  }, []);

  return { phase, error, stream, elapsed, recording, enable, start, stop, discard };
}
