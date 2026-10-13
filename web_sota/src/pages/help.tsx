import { FolderOpen, Keyboard, LifeBuoy, Plug } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { API_BASE, ENDPOINTS } from "@/lib/api";

type Capabilities = {
  server?: { name?: string; version?: string; fastmcp?: string };
  tool_surface?: { atomic?: string[]; agentic?: string[] };
  endpoints?: Record<string, string>;
};

const DOC_LINKS = [
  {
    label: "README",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/README.md",
  },
  {
    label: "INSTALL",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/INSTALL.md",
  },
  {
    label: "Configuration",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/docs/CONFIGURATION.md",
  },
  {
    label: "Tools reference",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/docs/TOOLS.md",
  },
  {
    label: "Troubleshooting",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/docs/TROUBLESHOOTING.md",
  },
  {
    label: "Onboarding",
    href: "https://github.com/sandraschi/beyondcompare-mcp/blob/master/docs/ONBOARDING.md",
  },
];

const SHORTCUTS = [
  { keys: "Ctrl + Scroll", action: "Zoom the dashboard in/out" },
  { keys: "Ctrl + 0", action: "Reset zoom to 100%" },
  { keys: "Ctrl + L", action: "Toggle the logger panel" },
  { keys: "Ctrl + H", action: "Open this help page" },
  { keys: "Ctrl + K", action: "Focus page search" },
];

export function Help() {
  const [caps, setCaps] = useState<Capabilities>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API_BASE}${ENDPOINTS.capabilities}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setCaps(await r.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6" data-testid="help-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Help</h2>
        <p className="text-sm text-slate-300">
          {caps.server?.name ?? "Beyond Compare MCP"}{" "}
          {caps.server?.version ?? ""} · FastMCP {caps.server?.fastmcp ?? "3.x"}{" "}
          · Backend :10841 · Frontend :10840
        </p>
      </div>

      {loading && (
        <p className="text-sm text-slate-300">Loading capabilities...</p>
      )}
      {error && (
        <div className="rounded-md border border-red-800 bg-red-950/30 p-4 text-sm text-red-200">
          Backend unreachable ({error}). The reference below still applies —
          start the backend and retry.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          className="border-slate-800 bg-slate-950/50"
          data-testid="help-tools"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-white">
              <Plug className="h-5 w-5 text-blue-400" /> Tool surface
            </CardTitle>
            <CardDescription className="text-sm text-slate-300">
              {(caps.tool_surface?.atomic?.length ?? 0) +
                (caps.tool_surface?.agentic?.length ?? 0)}{" "}
              tools via MCP + REST
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              {(caps.tool_surface?.atomic ?? []).map((t) => (
                <li key={t}>
                  <code className="font-mono text-sm text-emerald-300">
                    {t}
                  </code>
                </li>
              ))}
              {(caps.tool_surface?.agentic ?? []).map((t) => (
                <li key={t}>
                  <code className="font-mono text-sm text-amber-300">{t}</code>
                </li>
              ))}
              {(caps.tool_surface?.atomic?.length ?? 0) === 0 && (
                <li>Start the backend to list live tools.</li>
              )}
            </ul>
          </CardContent>
        </Card>

        <Card
          className="border-slate-800 bg-slate-950/50"
          data-testid="help-docs"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-white">
              <FolderOpen className="h-5 w-5 text-blue-400" /> Documentation
            </CardTitle>
            <CardDescription className="text-sm text-slate-300">
              Start here when something breaks
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {DOC_LINKS.map((d) => (
                <li key={d.label}>
                  <a
                    href={d.href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-blue-300 underline hover:text-blue-200"
                  >
                    {d.label}
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card
          className="border-slate-800 bg-slate-950/50"
          data-testid="help-shortcuts"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-white">
              <Keyboard className="h-5 w-5 text-blue-400" /> Keyboard shortcuts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {SHORTCUTS.map((s) => (
                <li
                  key={s.keys}
                  className="flex items-center justify-between gap-4 text-sm"
                >
                  <code className="rounded border border-slate-700 bg-slate-900 px-2 py-0.5 font-mono text-sm text-slate-100">
                    {s.keys}
                  </code>
                  <span className="text-sm text-slate-300">{s.action}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card
          className="border-slate-800 bg-slate-950/50"
          data-testid="help-first-aid"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg text-white">
              <LifeBuoy className="h-5 w-5 text-blue-400" /> First aid
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-200">
            <p>
              <strong className="text-white">Dashboard shows offline:</strong>{" "}
              start the backend (
              <code className="font-mono text-sm">
                .\start.ps1 -BackendOnly
              </code>
              ), then check{" "}
              <code className="font-mono text-sm">GET /api/v1/health</code>.
            </p>
            <p>
              <strong className="text-white">Chat errors:</strong> open
              Settings, pick a detected provider + model. Chat never talks to
              Ollama directly — it proxies through the backend.
            </p>
            <p>
              <strong className="text-white">
                Beyond Compare not detected:
              </strong>{" "}
              set <code className="font-mono text-sm">BEYOND_COMPARE_PATH</code>{" "}
              to BCompare.exe (see Configuration).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
