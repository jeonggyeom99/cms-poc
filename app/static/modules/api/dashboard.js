import { demoSummary, demoDashboard } from "../demo.js";

async function fetchJson(url) {
  // CSV data is loaded when the API application starts. Avoid reusing a
  // cached error/empty response after the data directory or server changes.
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function fetchDatasetSummaries() {
  const { items } = await fetchJson("/api/datasets");
  return items.map(demoSummary);
}

export function fetchDashboard(datasetId, until, start) {
  const params = new URLSearchParams();
  if (until) params.set("until", until);
  if (start) params.set("start", start);
  const query = params.size ? `?${params}` : "";
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}${query}`).then(demoDashboard);
}

export function fetchFftRecord(datasetId, recordId, until, start) {
  const params = new URLSearchParams();
  if (until) params.set("until", until);
  if (start) params.set("start", start);
  const query = params.size ? `?${params}` : "";
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}/fft/${recordId}${query}`);
}
