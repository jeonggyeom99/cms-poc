async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function fetchDatasetSummaries() {
  const { items } = await fetchJson("/api/datasets");
  return items;
}

export function fetchDashboard(datasetId) {
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}`);
}

export function fetchFftRecord(datasetId, recordId) {
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}/fft/${recordId}`);
}
