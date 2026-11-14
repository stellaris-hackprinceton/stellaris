"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Artifact, ID, Upload, UploadRequest } from "@/contracts/api";
import { api } from "@/lib/api";
import { errorCode, newCommandKey } from "@/components/ui";

/**
 * UI states for one upload. Deliberately distinct from the backend Upload.status.
 *   selected → creating → transferring → finalizing → ready
 *   any active state → failed | cancelled → (retry) → resumes at the right step
 */
export type UploadPhase = "idle" | "selected" | "creating" | "transferring" | "finalizing" | "ready" | "failed" | "cancelled";

export type UploadInput = { blob: Blob; request: UploadRequest };

export type UploadState = {
  phase: UploadPhase;
  input: UploadInput | null;
  progress: { loaded_bytes: number; total_bytes: number | null } | null;
  artifact: Artifact | null;
  error: unknown;
  /** True when retrying cannot help with the same bytes (validation failed on the server). */
  terminal: boolean;
  /** True after an expired session: retry will open a new upload session. */
  expired: boolean;
};

const INITIAL: UploadState = { phase: "idle", input: null, progress: null, artifact: null, error: null, terminal: false, expired: false };
const isAbort = (e: unknown) => (e as { name?: string })?.name === "AbortError";

/**
 * Orchestrates create → content PUT → complete through C's typed upload facade.
 * - Keeps the local Blob for the page's lifetime so a failed transfer can be retried without re-recording.
 * - Create and complete keep one idempotency key each across retries.
 * - The content PUT is restartable (same bytes), not chunk-resumable.
 * - An ambiguous outcome is resolved by reading the Upload before deciding the next step.
 * - Cancel aborts the transfer only; there is no cancel-upload route and no artifact is deleted.
 */
export function useArtifactUpload(project_id: ID) {
  const [state, setState] = useState<UploadState>(INITIAL);
  const upload = useRef<Upload | null>(null);
  const createKey = useRef<string | null>(null);
  const completeKey = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const input = useRef<UploadInput | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; abort.current?.abort(); };
  }, []);

  const patch = useCallback((p: Partial<UploadState>) => { if (mounted.current) setState((s) => ({ ...s, ...p })); }, []);

  const run = useCallback(async () => {
    const inp = input.current;
    if (!inp) return;
    const ctrl = new AbortController();
    abort.current = ctrl;
    patch({ error: null, terminal: false, expired: false });
    try {
      // Re-sync with the server if we already have a session (ambiguous earlier outcome).
      if (upload.current) {
        patch({ phase: "creating" });
        upload.current = (await api.uploads.get(project_id, upload.current.id, { signal: ctrl.signal })).data;
        if (upload.current.status === "expired") throw Object.assign(new Error("expired"), { code: "UPLOAD_EXPIRED" });
        if (upload.current.status === "failed") {
          patch({ phase: "failed", error: upload.current.error ?? { code: "UPLOAD_FAILED", message: "The server rejected this file." }, terminal: true });
          return;
        }
      } else {
        patch({ phase: "creating" });
        createKey.current ??= newCommandKey();
        upload.current = (await api.uploads.create(project_id, inp.request, { idempotency_key: createKey.current, signal: ctrl.signal })).data;
      }

      const u = upload.current;
      if (u.status === "pending") {
        patch({ phase: "transferring", progress: { loaded_bytes: 0, total_bytes: inp.blob.size } });
        await api.uploads.putContent(project_id, u.id, inp.blob, {
          signal: ctrl.signal,
          on_progress: (p) => patch({ progress: p }),
        });
      }

      patch({ phase: "finalizing" });
      completeKey.current ??= newCommandKey();
      const artifact = (await api.uploads.complete(project_id, u.id, { idempotency_key: completeKey.current, signal: ctrl.signal })).data;
      patch({ phase: "ready", artifact, progress: null });
    } catch (err) {
      if (isAbort(err)) { patch({ phase: "cancelled" }); return; }
      const code = errorCode(err);
      if (code === "UPLOAD_EXPIRED") {
        // A new session is needed; the local bytes are still here.
        upload.current = null; createKey.current = null; completeKey.current = null;
        patch({ phase: "failed", error: err, expired: true });
        return;
      }
      const terminal = ["UPLOAD_TOO_LARGE", "PROJECT_QUOTA_EXCEEDED", "UNSUPPORTED_MEDIA_TYPE", "MEDIA_DECODE_FAILED",
        "HASH_MISMATCH", "VALIDATION_FAILED", "PROJECT_ARCHIVED", "UPLOAD_CONTENT_CONFLICT"].includes(code ?? "");
      patch({ phase: "failed", error: err, terminal });
    } finally {
      if (abort.current === ctrl) abort.current = null;
    }
  }, [patch, project_id]);

  const start = useCallback((inp: UploadInput) => {
    abort.current?.abort();
    input.current = inp;
    upload.current = null; createKey.current = null; completeKey.current = null;
    setState({ ...INITIAL, phase: "selected", input: inp });
    void run();
  }, [run]);

  const retry = useCallback(() => { void run(); }, [run]);
  const cancel = useCallback(() => { abort.current?.abort(); }, []);

  /** Forget this upload locally (after attaching, or when the user dismisses it). */
  const reset = useCallback(() => {
    abort.current?.abort();
    input.current = null; upload.current = null; createKey.current = null; completeKey.current = null;
    setState(INITIAL);
  }, []);

  const busy = state.phase === "selected" || state.phase === "creating" || state.phase === "transferring" || state.phase === "finalizing";
  return { ...state, busy, start, retry, cancel, reset };
}

export type ArtifactUploadController = ReturnType<typeof useArtifactUpload>;
