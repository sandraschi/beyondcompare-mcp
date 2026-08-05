export const API_BASE = "http://127.0.0.1:10841";

export async function fetchHealth(): Promise<Record<string, unknown>> {
  const r = await fetch(`${API_BASE}/api/v1/health`);
  if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
  return r.json();
}
