import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { API_BASE, fetchHealth } from "@/lib/api";

function LLMSettings() {
  const [providers, setProviders] = useState<
    Record<string, { name: string }[]>
  >({});
  const [selectedProvider, setSelectedProvider] = useState("ollama");
  const [selectedModel, setSelectedModel] = useState("");
  useEffect(() => {
    fetch(`${API_BASE}/api/llm/providers`)
      .then((r) => r.json())
      .then((d) => {
        setProviders(d);
        const savedP = localStorage.getItem("llm_provider") || "ollama";
        const savedM = localStorage.getItem("llm_model") || "";
        setSelectedProvider(savedP);
        const models = d[savedP === "ollama" ? "ollama" : "lm_studio"] || [];
        setSelectedModel(
          savedM && models.some((m: { name: string }) => m.name === savedM)
            ? savedM
            : models[0]?.name || "",
        );
      })
      .catch(() => {
        setProviders({ ollama: [{ name: "llama3.2:3b" }] });
        setSelectedModel(localStorage.getItem("llm_model") || "llama3.2:3b");
      });
  }, []);
  const save = (p: string, m: string) => {
    localStorage.setItem("llm_provider", p);
    localStorage.setItem("llm_model", m);
  };
  const models =
    providers[selectedProvider === "ollama" ? "ollama" : "lm_studio"] || [];
  return (
    <div className="space-y-3" data-testid="llm-provider-card-local">
      <select
        data-testid="llm-provider-select"
        className="h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-200"
        value={selectedProvider}
        onChange={(e) => {
          setSelectedProvider(e.target.value);
          save(e.target.value, "");
        }}
      >
        <option value="ollama">Ollama (local, free)</option>
        <option value="lm_studio">LM Studio (local, free)</option>
      </select>
      <select
        data-testid="llm-model-select"
        className="h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-200"
        value={selectedModel}
        onChange={(e) => {
          setSelectedModel(e.target.value);
          save(selectedProvider, e.target.value);
        }}
      >
        {models.map((m) => (
          <option key={m.name} value={m.name}>
            {m.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Settings() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Settings
        </h2>
        <p className="text-sm text-slate-300">
          Gateway-detected Beyond Compare and local LLM preferences
        </p>
      </div>

      <div className="grid gap-6" data-testid="settings-grid">
        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader>
            <CardTitle className="text-white">Beyond Compare</CardTitle>
            <CardDescription className="text-sm text-slate-300">
              From GET /api/v1/health (server process)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-300">
            {health.isLoading && <p>Loading.</p>}
            {health.isError && (
              <p className="text-rose-400">{(health.error as Error).message}</p>
            )}
            {health.data && (
              <>
                <p>
                  Detected: {health.data.beyond_compare.detected ? "yes" : "no"}
                </p>
                <p className="font-mono text-sm break-all text-slate-300">
                  {health.data.beyond_compare.executable}
                </p>
                <p className="text-sm text-slate-300">
                  Override with env{" "}
                  <code className="text-slate-300">BEYOND_COMPARE_PATH</code>{" "}
                  and restart the gateway.
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card
          className="border-slate-800 bg-slate-950/50"
          data-testid="llm-settings"
        >
          <CardHeader>
            <CardTitle className="text-white">Local LLM</CardTitle>
            <CardDescription className="text-sm text-slate-300">
              Provider and model selection
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LLMSettings />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
