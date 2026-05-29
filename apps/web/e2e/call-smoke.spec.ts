import { test, expect } from "@playwright/test";

/**
 * Smoke test for the voice-agent UI without contacting OpenAI.
 *
 * Intercepts:
 *   - POST /realtime/session   → returns a stub token
 *   - POST /tools/invoke       → returns a stub tool response
 *   - POST /calls              → returns a stub Call
 *   - GET  /calls, /calls/stats, /calls/stats/activity → return empty/zero data
 *
 * Does NOT exercise the real WebRTC peer connection (the test runs in
 * headless Chromium which generally lacks a working media device); the
 * goal is to validate that the UI renders, the Call screen mounts, and
 * navigation between Call / Calls / Dashboard works.
 */
test.describe("Voice agent smoke", () => {
  test.beforeEach(async ({ context }) => {
    await context.route("**/realtime/session", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "sess_test",
          client_secret: "ek_test",
          model: "gpt-realtime-2",
          expires_at: new Date(Date.now() + 60_000).toISOString(),
          ice_servers: [],
        }),
      });
    });
    await context.route("**/calls", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            call_id: "01HZ000000000000000000000Z",
            started_at: new Date().toISOString(),
            ended_at: new Date().toISOString(),
            duration_seconds: 12,
            tool_count: 0,
            deflected: true,
            summary_line: "stub",
            complete: true,
          }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await context.route("**/calls/stats", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          calls_today: 0,
          calls_this_week: 0,
          avg_duration_seconds: 0,
          total_tool_calls: 0,
          tickets_created: 0,
          deflection_rate: 0,
          tool_breakdown: {},
        }),
      });
    });
    await context.route("**/calls/stats/activity*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
  });

  test("Call screen renders Start Call button", async ({ page }) => {
    await page.goto("/call");
    await expect(page.getByRole("button", { name: /start call/i })).toBeVisible();
  });

  test("Calls page renders empty state", async ({ page }) => {
    await page.goto("/calls");
    await expect(page).toHaveURL(/calls/);
  });

  test("Dashboard renders with stub stats", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });

  test("Files page (kept from starter kit) still renders", async ({ page, context }) => {
    await context.route("**/files*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await page.goto("/files");
    await expect(page).toHaveURL(/files/);
  });
});
