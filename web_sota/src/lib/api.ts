// Same-origin by default (vite proxy); absolute only inside Tauri WebViews.
// Canonical shape: absolute backend URLs work from localhost tabs only —
// any other hostname (LAN, Tailscale) dies on CORS. See 1F audit.
function isTauri(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.__TAURI__ || w.__TAURI_INTERNALS__);
}

export const API_BASE = isTauri() ? "http://127.0.0.1:10841" : "";

export async function fetchHealth(): Promise<any> {
  const r = await fetch(`${API_BASE}/api/v1/health`);
  if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
  return r.json();
}

export async function fetchCapabilities(): Promise<any> {
  const r = await fetch(`${API_BASE}/api/v1/capabilities`);
  if (!r.ok) return {};
  return r.json();
}

export async function fetchSkills(): Promise<any[]> {
  try {
    const r = await fetch(`${API_BASE}/api/skills`);
    if (!r.ok) return [];
    const data = await r.json();
    return data?.skills ?? [];
  } catch {
    return [];
  }
}

export async function fetchLlmDiscover(): Promise<any> {
  try {
    const r = await fetch(`${API_BASE}/api/llm/discover`);
    if (!r.ok)
      return { ollama: { detected: false }, lm_studio: { detected: false } };
    return r.json();
  } catch {
    return { ollama: { detected: false }, lm_studio: { detected: false } };
  }
}
