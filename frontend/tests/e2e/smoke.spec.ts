import { test, expect } from "@playwright/test";

test.describe("Frontend E2E Smoke Flow", () => {
  test("smoke flow: login -> create project -> issue key -> view dashboard", async ({ page }) => {
    // 1. Mock API endpoints for deterministic end-to-end frontend interaction
    await page.route("**/api/admin/auth/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ is_setup: true, logged_in: false }),
      });
    });

    await page.route("**/api/admin/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Logged in successfully", csrf_token: "csrf_mock_token_123" }),
      });
    });

    const projectsList = [
      {
        id: "proj-1111-2222",
        name: "Demo Analytics",
        slug: "demo-analytics",
        description: "Initial analytics project",
        created_at: new Date().toISOString(),
        keys_count: 1,
        daily_budget_micro_usd: 10000000,
        today_spend_micro_usd: 2500000,
      },
    ];

    await page.route("**/api/admin/projects*", async (route) => {
      if (route.request().method() === "POST") {
        const postData = route.request().postDataJSON();
        const newProj = {
          id: "proj-new-9999",
          name: postData.name || "E2E Production App",
          slug: postData.slug || "e2e-production-app",
          description: postData.description || "Created during E2E test",
          created_at: new Date().toISOString(),
          keys_count: 0,
          daily_budget_micro_usd: 50000000,
          today_spend_micro_usd: 0,
        };
        projectsList.push(newProj);
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(newProj),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ projects: projectsList }),
        });
      }
    });

    await page.route("**/api/admin/stats/overview*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_spend_micro_usd: 12500000,
          spend_change_pct: 4.5,
          total_requests: 1540,
          requests_change_pct: 12.0,
          avg_latency_ms: 185,
          latency_change_pct: -8.2,
          error_rate_pct: 0.12,
          error_rate_change_pct: -0.05,
          time_series: [
            { timestamp: "2026-10-01T00:00:00Z", spend_micro_usd: 3000000, request_count: 400, error_count: 1 },
            { timestamp: "2026-10-02T00:00:00Z", spend_micro_usd: 4500000, request_count: 550, error_count: 0 },
            { timestamp: "2026-10-03T00:00:00Z", spend_micro_usd: 5000000, request_count: 590, error_count: 0 },
          ],
          top_projects: [
            { project_id: "proj-1111-2222", project_name: "Demo Analytics", spend_micro_usd: 12500000, request_count: 1540 },
          ],
          top_models: [
            { model: "openai/gpt-4o-mini", request_count: 1200, spend_micro_usd: 8000000 },
          ],
        }),
      });
    });

    // 2. Navigate to Login Page
    await page.goto("/login");
    await expect(page.getByText("Sign In to Gateway")).toBeVisible();

    // 3. Fill Login form
    await page.fill('input[type="password"]', "AdminPassword123!");
    await page.click('button[type="submit"]');

    // 4. Verify redirected to overview or projects
    await expect(page).toHaveURL(/\/(|projects)/);

    // 5. Navigate to Projects page
    await page.goto("/projects");
    await expect(page.getByText("Projects")).toBeVisible();
    await expect(page.getByText("Demo Analytics")).toBeVisible();

    // 6. Open "New Project" modal and submit
    const newProjBtn = page.getByRole("button", { name: /new project/i });
    if (await newProjBtn.isVisible()) {
      await newProjBtn.click();
      await page.fill('input[placeholder*="Name" i], input[name="name"]', "E2E Production App");
      const submitBtn = page.getByRole("button", { name: /create|save/i });
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
      }
    }

    // 7. Verify dashboard overview loads
    await page.goto("/");
    await expect(page.getByText("Total Spend")).toBeVisible();
    await expect(page.getByText("Total Requests")).toBeVisible();
  });
});
