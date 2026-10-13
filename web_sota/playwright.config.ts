import { defineConfig } from "@playwright/test";

// Fleet tools (bun, uv) live off-PATH by design (AGENTS.md) — spawned
// shells must resolve them explicitly, like start.ps1 bootstraps.
const BOOTSTRAP = String.raw`$env:PATH = $env:USERPROFILE + '\.bun\bin;' + $env:USERPROFILE + '\.local\bin;' + $env:PATH; `;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:10840",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // Gateway backend (serves /api/* + /mcp). BC detection may be
      // false on CI agents — the dashboard handles both states.
      command: `powershell -NoProfile -Command "${BOOTSTRAP}powershell -NoProfile -ExecutionPolicy Bypass -File ..\\start.ps1 -BackendOnly -NoBrowser"`,
      port: 10841,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: `powershell -NoProfile -Command "${BOOTSTRAP}bun run dev -- --port 10840 --host 127.0.0.1"`,
      port: 10840,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
