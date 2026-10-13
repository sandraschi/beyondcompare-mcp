import { expect, test } from "@playwright/test";

// Dashboard smoke: hero, live backend, navigation across all pages.
// Backend + frontend are started by playwright.config.ts webServer.

test("dashboard shows hero, live backend, and onboarding state", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("dashboard")).toBeVisible();
  // Backend is up in e2e (webServer) — KPI must flip to online.
  await expect(page.getByTestId("kpi-gateway")).toContainText("online", {
    timeout: 30_000,
  });
  await expect(page.getByTestId("dashboard-kpis")).toBeVisible();
});

test("sidebar navigates Inbox / Skills / Help", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Inbox" }).click();
  await expect(page.getByTestId("inbox-page")).toBeVisible();
  await page.getByRole("link", { name: "Skills" }).click();
  await expect(page.getByTestId("skills-page")).toBeVisible();
  await page.getByRole("link", { name: "Help" }).click();
  await expect(page.getByTestId("help-page")).toBeVisible();
  await expect(page.getByTestId("help-tools")).toBeVisible();
});

test("chat page loads skill-first controls", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByTestId("chat-page")).toBeVisible();
  await expect(page.getByTestId("personality-select")).toBeVisible();
  await expect(page.getByTestId("chat-input")).toBeVisible();
  await expect(page.getByTestId("example-prompts")).toBeVisible();
});

test("compare and sync pages render honest launcher content", async ({
  page,
}) => {
  await page.goto("/compare");
  await expect(page.getByTestId("compare-page")).toBeVisible();
  await expect(page.getByTestId("compare-grid")).toBeVisible();
  await page.goto("/sync");
  await expect(page.getByTestId("sync-page")).toBeVisible();
  await expect(page.getByTestId("sync-warning")).toBeVisible();
  await expect(page.getByTestId("sync-modes")).toBeVisible();
});

test("backend REST reachable through vite proxy", async ({ request }) => {
  // Proves the /api proxy target (was stale :11065, now :10841).
  const health = await request.get("/api/v1/health");
  expect(health.ok()).toBeTruthy();
  const body = await health.json();
  expect(body.status).toBe("online");
  const skills = await request.get("/api/skills");
  expect(skills.ok()).toBeTruthy();
});
