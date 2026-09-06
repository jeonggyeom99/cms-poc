async function fetchJson(url) {
  // CSV data is loaded when the API application starts. Avoid reusing a
  // cached error/empty response after the data directory or server changes.
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function fetchDatasetSummaries() {
  const { items } = await fetchJson("/api/datasets");
  return items;
}

export function fetchDashboard(datasetId, until) {
  const query = until ? `?until=${encodeURIComponent(until)}` : "";
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}${query}`);
}

export function fetchFftRecord(datasetId, recordId, until) {
  const query = until ? `?until=${encodeURIComponent(until)}` : "";
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}/fft/${recordId}${query}`);
}
