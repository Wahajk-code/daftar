/**
 * The browser's way to talk to the API: always through the web server at /api (the BFF), which adds the token from an
 * HttpOnly cookie. Nothing here ever sees a token.
 */
import { ApiError } from "./errors";
import type { Problem } from "./types";

type Query = Record<string, string | number | boolean | null | undefined | ReadonlyArray<string | number>>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  /** The `version` of the record you loaded; sent as If-Match. */
  version?: number;
  /** Makes a post or void safe to repeat. */
  idempotencyKey?: string;
  signal?: AbortSignal;
}

export function queryString(query: Query | undefined): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
    else params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** A new key for one attempt at an action. Keep it for retries of that same attempt; make a new one for a new attempt. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

function retryAfter(response: Response): number | null {
  const header = response.headers.get("retry-after");
  const seconds = header ? Number(header) : NaN;
  return Number.isFinite(seconds) ? seconds : null;
}

async function problemOf(response: Response): Promise<ApiError> {
  let body: Partial<Problem> | null = null;
  try {
    body = (await response.json()) as Partial<Problem>;
  } catch {
    body = null;
  }
  return new ApiError(response.status, body, retryAfter(response));
}

let leaving = false;

/** A session that has really ended sends the person to sign in, once, remembering where they were. */
function sessionEnded(): void {
  if (leaving || typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  leaving = true;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = new URL(`/login?next=${next}`, window.location.origin).href;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const init: RequestInit = { method: options.method ?? "GET", headers, signal: options.signal, credentials: "same-origin" };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  if (options.version !== undefined) headers["If-Match"] = String(options.version);
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let response: Response;
  try {
    response = await fetch(`/api${path}${queryString(options.query)}`, init);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, null, null);
  }
  if (!response.ok) {
    const error = await problemOf(response);
    if (response.status === 401 && error.code === "UNAUTHENTICATED") sessionEnded();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Download a file the API builds (a CSV). The browser saves it under the name the API chose. */
export async function download(path: string, query?: Query): Promise<void> {
  const response = await fetch(`/api${path}${queryString(query)}`, { credentials: "same-origin" });
  if (!response.ok) throw await problemOf(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? "daftar-export.csv";
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Send a file with progress, which fetch cannot report. */
export function upload<T>(path: string, file: File, onProgress: (fraction: number) => void): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `/api${path}`);
    request.setRequestHeader("Accept", "application/json");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    request.onerror = () => reject(new ApiError(0, null, null));
    request.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        body = null;
      }
      if (request.status >= 200 && request.status < 300) {
        onProgress(1);
        resolve(body as T);
        return;
      }
      const wait = Number(request.getResponseHeader("retry-after"));
      const error = new ApiError(request.status, body as Partial<Problem> | null, Number.isFinite(wait) && wait > 0 ? wait : null);
      if (request.status === 401) sessionEnded();
      reject(error);
    };
    const form = new FormData();
    form.append("file", file);
    request.send(form);
  });
}
