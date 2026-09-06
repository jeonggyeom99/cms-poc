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
