import { MessageSquare, RefreshCw, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const MODES = [
  {
    name: "mirror",
    desc: "Target becomes an exact copy of source. Deletes target-only files.",
  },
  {
    name: "update",
    desc: "Copies new/changed files. Preserves target-only files.",
  },
  {
    name: "backup",
    desc: "Copies only files missing from target. Never overwrites.",
  },
];

export function Sync() {
  return (
    <div className="space-y-6" data-testid="sync-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Folder Synchronization
          </h2>
          <p className="text-sm text-slate-300">
            sync_folders via MCP — always preview with dry_run first
          </p>
        </div>
        <Button
          className="bg-emerald-600 hover:bg-emerald-700"
          data-testid="sync-cta"
          asChild
        >
          <Link to="/chat">
            <RefreshCw className="mr-2 h-4 w-4" /> Plan a sync
          </Link>
        </Button>
      </div>

      <div
        className="rounded-md border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-200"
        data-testid="sync-warning"
      >
        <p className="flex items-start gap-2">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Mirror mode deletes files in the target that do not exist in the
            source. There is no scheduled runner in this dashboard — syncs
            execute when you call sync_folders with dry_run=false.
          </span>
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3" data-testid="sync-modes">
        {MODES.map((m) => (
          <Card key={m.name} className="border-slate-800 bg-slate-950/50">
            <CardHeader>
              <CardTitle className="font-mono text-lg text-white">
                {m.name}
              </CardTitle>
              <CardDescription className="text-sm text-slate-300">
                {m.desc}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="overflow-auto rounded bg-slate-950 p-3 text-xs text-emerald-300">
                {`sync_folders(source_path='C:/src', target_path='E:/bak', sync_mode='${m.name}', dry_run=True)`}
              </pre>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          className="border-slate-700 text-slate-200 hover:bg-slate-800"
          asChild
        >
          <Link to="/chat">
            <MessageSquare className="mr-2 h-4 w-4" /> Ask AI Command
          </Link>
        </Button>
      </div>
    </div>
  );
}
