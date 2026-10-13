import { CheckCheck, Inbox as InboxIcon, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { API_BASE, ENDPOINTS } from "@/lib/api";

type InboxItem = {
  id: string;
  timestamp: string;
  level: string;
  kind: string;
  detail: string;
};

const READ_KEY = "beyondcompare-inbox-read";

function loadRead(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(READ_KEY) || "{}");
  } catch {
    return {};
  }
}

export function Inbox() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [read, setRead] = useState<Record<string, boolean>>(loadRead);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch(
          `${API_BASE}${ENDPOINTS.logs}?limit=100&sort=desc`,
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        setItems(d.entries ?? []);
        setTotal(d.total ?? 0);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const markRead = (id: string) => {
    setRead((prev) => {
      const next = { ...prev, [id]: true };
      localStorage.setItem(READ_KEY, JSON.stringify(next));
      return next;
    });
  };

  const markAllRead = () => {
    const next: Record<string, boolean> = { ...read };
    for (const it of items) next[it.id] = true;
    localStorage.setItem(READ_KEY, JSON.stringify(next));
    setRead(next);
  };

  const visible = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((it) => {
      if (showUnreadOnly && read[it.id]) return false;
      if (
        q &&
        !(
          it.detail.toLowerCase().includes(q) ||
          it.kind.toLowerCase().includes(q)
        )
      )
        return false;
      return true;
    });
  }, [items, search, showUnreadOnly, read]);

  const unread = items.filter((it) => !read[it.id]).length;

  return (
    <div className="space-y-6" data-testid="inbox-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Inbox
          </h2>
          <p className="text-sm text-slate-300">
            Gateway activity triage — {total} events, {unread} unread. Mark
            items read as you review them.
          </p>
        </div>
        <button
          type="button"
          data-testid="inbox-mark-all"
          onClick={markAllRead}
          disabled={items.length === 0}
          className="flex items-center gap-2 rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-30"
        >
          <CheckCheck className="h-4 w-4" /> Mark all read
        </button>
      </div>

      <div className="flex items-center gap-3" data-testid="inbox-controls">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-300" />
          <input
            data-testid="inbox-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search events..."
            className="h-9 w-64 rounded-md border border-slate-700 bg-slate-900 pl-8 pr-3 text-sm text-slate-100 placeholder:text-slate-300"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input
            data-testid="inbox-unread-only"
            type="checkbox"
            checked={showUnreadOnly}
            onChange={(e) => setShowUnreadOnly(e.target.checked)}
            className="h-4 w-4 accent-emerald-500"
          />
          Unread only
        </label>
      </div>

      {loading && <p className="text-sm text-slate-300">Loading inbox...</p>}
      {error && (
        <div className="rounded-md border border-red-800 bg-red-950/30 p-4 text-sm text-red-200">
          Failed to load inbox: {error}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      )}
      {!loading && !error && visible.length === 0 && (
        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-12 text-center">
          <InboxIcon className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-2 text-sm text-slate-200">
            Inbox zero — nothing matches.
          </p>
          <p className="text-sm text-slate-300">
            Gateway HTTP activity will appear here as it happens.
          </p>
        </div>
      )}

      <div className="space-y-2" data-testid="inbox-list">
        {visible.map((it) => {
          const isRead = Boolean(read[it.id]);
          return (
            <button
              type="button"
              key={it.id}
              data-testid="inbox-item"
              onClick={() => markRead(it.id)}
              className={`flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors ${
                isRead
                  ? "border-slate-800 bg-slate-950/30 opacity-70"
                  : "border-slate-700 bg-slate-900/60 hover:bg-slate-900"
              }`}
            >
              <span
                title={isRead ? "read" : "unread"}
                className={`mt-1 h-2 w-2 shrink-0 rounded-full ${isRead ? "bg-slate-600" : "bg-emerald-400"}`}
              />
              <div className="min-w-0 flex-1">
                <p className="break-all font-mono text-sm text-slate-100">
                  {it.detail}
                </p>
                <p className="mt-1 text-sm text-slate-300">
                  {it.timestamp
                    ? new Date(it.timestamp).toLocaleString()
                    : "no timestamp"}{" "}
                  · {it.kind} · {it.level}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
