import { isDemoDataset, demoRelatedHistory } from "../demo.js?v=demo-related-v4";

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep the HTTP status when the response body is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

export function fetchHistory() {
  return fetchJson("/api/history");
}

export function fetchRelatedHistory(datasetId, recordId, selectedFaultType, until) {
  if (isDemoDataset(datasetId)) {
    return fetchHistory().then(({ items }) => ({ faultTag: { fault: "축", faultType: "Unbalance" }, items: demoRelatedHistory(items, until) }));
  }
  const query = new URLSearchParams({ record_id: recordId });
  if (selectedFaultType) query.set("selected_fault_type", selectedFaultType);
  if (until) query.set("until", until);
  return fetchJson(`/api/dashboard/${encodeURIComponent(datasetId)}/related-history?${query}`);
}
