import { demoSummary, demoDashboard, demoFftRecord } from "../demo.js?v=demo-datasets-v7";

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

export async function fetchDashboard(datasetId, until, start) {
  const params = new URLSearchParams();
  if (until) params.set("until", until);
  if (start) params.set("start", start);
  const query = params.size ? `?${params}` : "";
  const data = await fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}${query}`);
  if (String(datasetId) === "1" && data.fft) {
    const velocity = data.fft.records?.find((record) => record.measureMode?.code === "3");
    if (velocity && velocity.id !== data.fft.recordId) {
      const fft = await fetchFftRecord(datasetId, velocity.id, until, start);
      data.fft = { ...fft, records: data.fft.records };
    } else {
      data.fft = demoFftRecord(data.fft, datasetId);
    }
  }
  return demoDashboard(data);
}

export function fetchFftRecord(datasetId, recordId, until, start) {
  const params = new URLSearchParams();
  if (until) params.set("until", until);
  if (start) params.set("start", start);
  const query = params.size ? `?${params}` : "";
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}/fft/${recordId}${query}`).then((fft) => demoFftRecord(fft, datasetId));
}
