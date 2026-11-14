import type { ErrorNoticeProps } from "./Feedback";

/**
 * Reads an API error defensively. C's ApiError carries code/message/request_id; anything else
 * (network failure, programming error) falls back to a generic message without leaking internals.
 */
export function describeError(error: unknown, title = "Something went wrong"): ErrorNoticeProps {
  if (error && typeof error === "object") {
    const e = error as { code?: unknown; message?: unknown; request_id?: unknown; status?: unknown };
    const code = typeof e.code === "string" && e.code ? e.code : undefined;
    const request_id = typeof e.request_id === "string" ? e.request_id : null;
    if (code) return { title, message: typeof e.message === "string" ? e.message : undefined, code, request_id };
    if (e.status === 0 || error instanceof TypeError) {
      return { title, message: "The server could not be reached. Check your connection and try again." };
    }
  }
  return { title, message: "Please try again." };
}

export function errorCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && typeof (error as { code?: unknown }).code === "string") {
    return (error as { code: string }).code;
  }
  return undefined;
}

/** A stable idempotency key for one user action. */
export function newCommandKey(): string {
  return crypto.randomUUID();
}
