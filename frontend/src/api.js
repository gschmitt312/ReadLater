const BASE = "/api";

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function fetchManager(identifier, refresh = false) {
  const q = refresh ? "?refresh=true" : "";
  return getJSON(`${BASE}/manager/${encodeURIComponent(identifier)}${q}`);
}

export function fetchCompare(a, b) {
  return getJSON(`${BASE}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
}

export async function searchManagers(q) {
  const data = await getJSON(`${BASE}/search?q=${encodeURIComponent(q)}`);
  return data.results || [];
}
