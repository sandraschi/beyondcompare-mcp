import { Activity, MessageSquare, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function Compare() {
  return (
    <div className="space-y-6" data-testid="compare-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Compare Sessions
          </h2>
          <p className="text-sm text-slate-300">
            Comparisons run through MCP tools or the AI Command page
          </p>
        </div>
        <Button
          className="bg-blue-600 hover:bg-blue-700"
          data-testid="compare-new"
          asChild
        >
          <Link to="/chat">
            <Activity className="mr-2 h-4 w-4" /> New Session
          </Link>
        </Button>
      </div>

      <div className="grid gap-6" data-testid="compare-grid">
        <Card className="border-slate-800 bg-slate-950/50">
          <CardHeader>
            <CardTitle className="text-white">How comparisons work</CardTitle>
            <CardDescription className="text-sm text-slate-300">
              This dashboard does not keep a session list — every comparison
              runs live via Beyond Compare
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-slate-200">
            <div className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
              <p className="font-medium text-white">compare_files</p>
              <p className="mt-1 text-sm text-slate-300">
                Diff two files, optional text report via output_report.
              </p>
              <pre className="mt-2 overflow-auto rounded bg-slate-950 p-3 text-xs text-emerald-300">
                {`compare_files(left_path='C:/source/config.txt', right_path='C:/backup/config.txt')`}
              </pre>
            </div>
            <div className="rounded-md border border-slate-800 bg-slate-900/40 p-4">
              <p className="font-medium text-white">compare_folders</p>
              <p className="mt-1 text-sm text-slate-300">
                Diff two trees; set include_subfolders=false for a shallow pass.
              </p>
              <pre className="mt-2 overflow-auto rounded bg-slate-950 p-3 text-xs text-emerald-300">
                {`compare_folders(left_path='C:/source/project', right_path='C:/backup/project')`}
              </pre>
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
              <Button
                variant="outline"
                className="border-slate-700 text-slate-200 hover:bg-slate-800"
                asChild
              >
                <Link to="/actions">
                  <Zap className="mr-2 h-4 w-4" /> Tool surface
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
