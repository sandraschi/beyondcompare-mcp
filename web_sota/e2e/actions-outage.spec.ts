import { expect, test } from "@playwright/test";

// Regression: fetchCapabilities once returned {} on HTTP failure while
// Actions dereferenced cap.data.tool_surface unguarded — a failed fetch
// unmounted the whole React tree (black window, dead app). The fetch now
// throws (so data stays undefined) and the render guards tool_surface.
test("actions survives a capabilities outage without unmounting", async ({
  page,
}) => {
  await page.route("**/api/capabilities", (route) => route.abort());
  await page.goto("/actions");
  // Sidebar (same React tree) must still be mounted.
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  // Either the query error or the fallback text shows — never a blank tree.
  await expect(page.getByTestId("actions-page")).toContainText(
    /Failed to fetch|Capabilities check failed|Tool list unavailable/,
  );
});

test("actions renders the live tool list when backend is healthy", async ({
  page,
}) => {
  await page.goto("/actions");
  await expect(page.getByTestId("actions-tools")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId("actions-tools")).toContainText(
    "compare_files",
  );
});
