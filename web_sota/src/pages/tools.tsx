import { Cpu, Shield, Terminal, Wrench } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function Tools() {
  const tools = [
    {
      name: "Hex Compare",
      desc: "Binary byte-by-byte comparison",
      icon: Terminal,
    },
    { name: "MP3 Compare", desc: "Tag and audio data alignment", icon: Cpu },
    { name: "Text Merge", desc: "Three-way text reconciliation", icon: Wrench },
    {
      name: "Registry Compare",
      desc: "Windows registry hive diffing",
      icon: Shield,
    },
  ];

  return (
    <div className="space-y-6" data-testid="tools-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Utility Tools
          </h2>
          <p className="text-sm text-slate-300">
            Specialized comparison and merging plugins
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2" data-testid="tools-grid">
        {tools.map((tool) => (
          <Card
            key={tool.name}
            data-testid="tool-card"
            className="border-slate-800 bg-slate-950/50 hover:bg-slate-900/50 transition-colors cursor-pointer group"
          >
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 rounded bg-blue-500/10 group-hover:bg-blue-500/20 transition-colors">
                <tool.icon className="h-6 w-6 text-blue-500" />
              </div>
              <div>
                <CardTitle className="text-white text-lg">
                  {tool.name}
                </CardTitle>
                <CardDescription className="text-sm text-slate-300">
                  {tool.desc}
                </CardDescription>
              </div>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  );
}
