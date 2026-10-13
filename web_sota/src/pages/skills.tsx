import { BookOpen, Brain } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { API_BASE, ENDPOINTS } from "@/lib/api";

type Skill = {
  name: string;
  uri: string;
  description: string;
  content?: string;
};

export function Skills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selected, setSelected] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch(`${API_BASE}${ENDPOINTS.skills}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        const list: Skill[] = d.skills ?? [];
        setSkills(list);
        if (list.length > 0) setSelected(list[0]);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6" data-testid="skills-page">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Skills</h2>
        <p className="text-sm text-slate-300">
          Agent guidance served by the backend (skill:// resources). The Chat
          page loads these as its system preprompt.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-300">Loading skills...</p>}
      {error && (
        <div className="rounded-md border border-red-800 bg-red-950/30 p-4 text-sm text-red-200">
          Failed to load skills: {error}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      )}
      {!loading && !error && skills.length === 0 && (
        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-12 text-center">
          <Brain className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-2 text-sm text-slate-200">No skills registered.</p>
        </div>
      )}

      {skills.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2" data-testid="skills-list">
            {skills.map((s) => (
              <button
                type="button"
                key={s.uri}
                data-testid="skill-item"
                onClick={() => setSelected(s)}
                className={`flex w-full items-center gap-3 rounded-md border p-3 text-left transition-colors ${
                  selected?.uri === s.uri
                    ? "border-blue-600 bg-blue-950/30"
                    : "border-slate-800 bg-slate-950/50 hover:bg-slate-900/50"
                }`}
              >
                <BookOpen className="h-5 w-5 shrink-0 text-blue-400" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">
                    {s.name}
                  </p>
                  <p className="truncate text-sm text-slate-300">
                    {s.description}
                  </p>
                </div>
              </button>
            ))}
          </div>
          <Card
            className="border-slate-800 bg-slate-950/50 lg:col-span-2"
            data-testid="skill-detail"
          >
            <CardHeader>
              <CardTitle className="text-lg text-white">
                {selected?.name}
              </CardTitle>
              <CardDescription className="font-mono text-sm text-slate-300">
                {selected?.uri}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-md border border-slate-800 bg-slate-900 p-4 text-xs text-slate-200">
                {selected?.content || "No content."}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
