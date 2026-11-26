// Base URL: empty = same origin (Vite proxies /api to the backend). Set VITE_API to call a remote backend directly.
const BASE = import.meta.env.VITE_API || "";

async function call(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error("Can't reach the MovieMind backend. Start it with: python -m uvicorn main:app --port 8000 (in the backend folder).");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = body.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? "Invalid input: " + d.map((x) => x.loc.join(".")).join(", ") : `Request failed (${res.status})`);
  }
  return body;
}
const post = (path, data) => call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}) });

export const api = {
  health: () => call("/api/health"),
  catalog: (q, genre, limit = 24, offset = 0) =>
    call(`/api/catalog?q=${encodeURIComponent(q)}&genre=${encodeURIComponent(genre)}&limit=${limit}&offset=${offset}`),
  dashboard: (u) => call(`/api/dashboard/${u}`),
  recommend: (user_id, limit = 8) => post("/api/recommendations", { user_id, limit }),
  rate: (user_id, movie_id, rating) => post("/api/feedback", { user_id, movie_id, rating }),
  processDue: () => post("/api/process-due-feedback"),
  metrics: () => call("/api/metrics"),
  evaluate: () => call("/api/evaluate"),
  events: () => call("/api/events?limit=30"),
  reset: () => post("/api/admin/reset"),
};
