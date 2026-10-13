import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchCapabilities, fetchHealth } from "@/lib/api";

export function Actions() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 8000,
  });
  const cap = useQuery({
    queryKey: ["capabilities"],
    queryFn: fetchCapabilities,
    refetchInterval: 60000,
  });

  return (
    <div className="space-y-6" data-testid="actions-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Fleet actions
        </h2>
        <p className="text-sm text-slate-300">
          Live gateway status and MCP tool surface
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2" data-testid="actions-grid">
        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader>
            <CardTitle className="text-white">Gateway health</CardTitle>
            <CardDescription className="text-sm text-slate-300">
              GET /api/v1/health
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-300">
            {health.isLoading && <p>Loading…</p>}
            {health.isError && (
              <p className="text-rose-400">{(health.error as Error).message}</p>
            )}
            {health.data?.beyond_compare && (
              <>
                <p>
                  Beyond Compare:{" "}
                  <Badge
                    variant="outline"
                    className="border-slate-600 text-slate-200"
                  >
                    {health.data.beyond_compare.detected
                      ? "detected"
                      : "missing"}
                  </Badge>
                </p>
                <p className="font-mono text-sm break-all">
                  {health.data.beyond_compare.executable}
                </p>
                <p className="text-sm text-slate-300">
                  Uptime {Math.round(health.data.system.uptime_s)}s
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader>
            <CardTitle className="text-white">MCP tools</CardTitle>
            <CardDescription className="text-sm text-slate-300">
              GET /api/capabilities
            </CardDescription>
          </CardHeader>
          <CardContent>
            {cap.isLoading && (
              <p className="text-sm text-slate-300">Loading…</p>
            )}
            {cap.isError && (
              <p className="text-rose-400">{(cap.error as Error).message}</p>
            )}
            {!cap.isLoading && !cap.isError && !cap.data?.tool_surface && (
              <p className="text-sm text-slate-300">
                Tool list unavailable — start the backend and retry.
              </p>
            )}
            {cap.data?.tool_surface && (
              <div
                className="space-y-2 text-sm text-slate-300"
                data-testid="actions-tools"
              >
                <p className="text-slate-200">
                  Atomic ({cap.data.tool_surface.atomic?.length ?? 0})
                </p>
                <p className="font-mono break-all">
                  {(cap.data.tool_surface.atomic ?? []).join(", ")}
                </p>
                <p className="text-slate-200 pt-2">Agentic</p>
                <p className="font-mono break-all">
                  {(cap.data.tool_surface.agentic ?? []).join(", ")}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-950/50">
        <CardHeader>
          <CardTitle className="text-white">
            Using from Cursor / Claude
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-300">
          <p>
            MCP endpoint (HTTP):{" "}
            <code className="text-slate-200">
              /mcp (same origin; absolute http://127.0.0.1:10841/mcp inside
              Tauri)
            </code>{" "}
            (default path; set <code className="text-slate-200">MCP_PATH</code>{" "}
            if overridden).
          </p>
          <p>
            For multi-step natural language goals, call{" "}
            <code className="text-slate-200">
              beyondcompare_agentic_workflow
            </code>{" "}
            when your client supports sampling.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
