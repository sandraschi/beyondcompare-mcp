import { useQuery } from "@tanstack/react-query";
import { Activity, Box, Cpu, GitMerge, Rocket } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE, fetchHealth } from "@/lib/api";

export function Dashboard() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10000,
  });
  const onboarding = useQuery({
    queryKey: ["onboarding"],
    queryFn: async () => {
      try {
        const r = await fetch(`${API_BASE}/api/llm/onboarding`);
        if (!r.ok) return null;
        return r.json();
      } catch {
        return null;
      }
    },
    refetchInterval: 30000,
  });

  const bcOk = health.data?.beyond_compare.detected ?? false;
  const version = health.data?.server.version ?? "…";
  const llmReady = Boolean(
    onboarding.data?.ollama_detected || onboarding.data?.lm_studio_detected,
  );
  const onboarded = bcOk && llmReady;

  return (
    <div className="space-y-6" data-testid="dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Compare Dashboard
          </h2>
          <p className="text-sm text-slate-300">Unified gateway · v{version}</p>
        </div>
        <Badge
          variant="outline"
          className="border-slate-600 text-slate-200"
          data-testid="backend-dot"
        >
          {health.isFetching ? "refreshing" : "live"}
        </Badge>
      </div>

      {!onboarded && (
        <div
          className="rounded-md border border-red-800 bg-red-950/30 p-4"
          data-testid="onboarding-cue"
        >
          <p className="text-sm text-red-100">
            {health.isError
              ? "Backend is offline — start it with .\\start.ps1 -BackendOnly, then finish setup."
              : !bcOk
                ? "Beyond Compare was not detected — set BEYOND_COMPARE_PATH, then pick an LLM below."
                : "No local LLM detected — install Ollama and pull a model, then pick it below."}
          </p>
          <Link
            to="/settings"
            data-testid="onboarding-cta"
            className="mt-3 inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
          >
            <Rocket className="h-4 w-4" /> Finish setup: provider + model
          </Link>
        </div>
      )}

      <div
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
        data-testid="dashboard-kpis"
      >
        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-200">
              Gateway
            </CardTitle>
            <Cpu className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div
              className="text-2xl font-bold text-white"
              data-testid="kpi-gateway"
            >
              {health.isError ? "offline" : "online"}
            </div>
            <p className="text-sm text-slate-300">
              {health.isError
                ? (health.error as Error).message
                : "REST + MCP on 10841"}
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-200">
              Compare engine
            </CardTitle>
            <Activity className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div
              className="text-2xl font-bold text-white"
              data-testid="kpi-engine"
            >
              {bcOk ? "Ready" : "Not found"}
            </div>
            <p className="text-sm text-slate-300 truncate">
              {health.data?.beyond_compare.executable ?? "—"}
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-200">
              Scripts dir
            </CardTitle>
            <Box className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-sm font-mono text-slate-200 truncate">
              {health.data?.beyond_compare.scripts_dir ?? "—"}
            </div>
            <p className="text-sm text-slate-300">BC temp scripts</p>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-200">
              Fleet
            </CardTitle>
            <GitMerge className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">10840 / 10841</div>
            <p className="text-sm text-slate-300">UI / gateway</p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-950/50">
        <CardHeader>
          <CardTitle className="text-white">Quick links</CardTitle>
        </CardHeader>
        <CardContent
          className="text-sm text-slate-300 space-y-2"
          data-testid="dashboard-links"
        >
          <p>
            <Link className="text-blue-400 hover:underline" to="/actions">
              Actions
            </Link>{" "}
            — tool surface and health detail
          </p>
          <p>
            <Link className="text-blue-400 hover:underline" to="/logs">
              Logs
            </Link>{" "}
            — gateway request ring buffer
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
