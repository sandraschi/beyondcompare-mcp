// Same-origin by default (vite proxy); absolute only inside Tauri WebViews.
// Canonical shape: absolute backend URLs work from localhost tabs only —
// any other hostname (LAN, Tailscale) dies on CORS. See 1F audit.
function isTauri(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.__TAURI__ || w.__TAURI_INTERNALS__);
}

export const API_BASE = isTauri() ? "http://127.0.0.1:10841" : "";

// Single source of truth for backend routes. Every page imports these
// instead of inlining "/api/..." strings, so a renamed backend route breaks
// TypeScript (import) rather than failing silently at runtime. The
// tests/test_route_contract.py gate asserts each of these exists on the
// FastAPI app.
export const ENDPOINTS = {
  health: "/api/v1/health",
  diagnostics: "/api/v1/diagnostics",
  capabilities: "/api/capabilities",
  skills: "/api/skills",
  logs: "/api/logs",
  logsV1: "/api/v1/logs",
  logsExport: "/api/logs/export",
  fleetApps: "/api/fleet/apps",
  llmDiscover: "/api/llm/discover",
  llmProviders: "/api/llm/providers",
  llmModels: "/api/llm/models",
  llmChat: "/api/llm/chat",
  llmChatStream: "/api/llm/chat/stream",
  llmOnboarding: "/api/llm/onboarding",
} as const;

export async function fetchHealth(): Promise<any> {
  const r = await fetch(`${API_BASE}${ENDPOINTS.health}`);
  if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
  return r.json();
}

export async function fetchCapabilities(): Promise<any> {
  const r = await fetch(`${API_BASE}${ENDPOINTS.capabilities}`);
  if (!r.ok) throw new Error(`Capabilities check failed: ${r.status}`);
  return r.json();
}

export async function fetchSkills(): Promise<any[]> {
  try {
    const r = await fetch(`${API_BASE}${ENDPOINTS.skills}`);
    if (!r.ok) return [];
    const data = await r.json();
    return data?.skills ?? [];
  } catch {
    return [];
  }
}

export async function fetchLlmDiscover(): Promise<any> {
  try {
    const r = await fetch(`${API_BASE}${ENDPOINTS.llmDiscover}`);
    if (!r.ok)
      return { ollama: { detected: false }, lm_studio: { detected: false } };
    return r.json();
  } catch {
    return { ollama: { detected: false }, lm_studio: { detected: false } };
  }
}
