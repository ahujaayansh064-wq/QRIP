// Thin fetch wrapper. The bearer token lives in localStorage under qrip_token.

// Same-origin by default. A static deployment (Netlify, Pages, S3) sets the
// backend's address in index.html's <meta name="qrip-api-base"> or on
// window.QRIP_API_BASE, with or without the trailing /api.
function resolveBase() {
  let configured = "";
  if (typeof window !== "undefined") {
    configured = window.QRIP_API_BASE || "";
    if (!configured) {
      const meta = document.querySelector('meta[name="qrip-api-base"]');
      configured = (meta && meta.content) || "";
    }
  }
  configured = String(configured).trim().replace(/\/+$/, "");
  if (!configured) return "/api";
  return configured.endsWith("/api") ? configured : configured + "/api";
}

const BASE = resolveBase();
const TOKEN_KEY = "qrip_token";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* private mode */ }
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(BASE + path, { ...options, headers });
  const type = response.headers.get("content-type") || "";
  if (!response.ok) {
    let detail = response.statusText;
    if (type.includes("json")) {
      const payload = await response.json().catch(() => ({}));
      detail = payload.detail || detail;
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return null;
  return type.includes("json") ? response.json() : response.blob();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, {
    method: "POST", body: body === undefined ? undefined : JSON.stringify(body),
  }),
  patch: (path, body) => request(path, {
    method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body),
  }),
  del: (path) => request(path, { method: "DELETE" }),
  postForm: (path, formData) => request(path, { method: "POST", body: formData }),

  async download(path, fallbackName) {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", "Bearer " + token);
    const response = await fetch(BASE + path, { headers });
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch { /* not json */ }
      throw new ApiError(response.status, detail);
    }
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = match ? match[1] : fallbackName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  },
};
