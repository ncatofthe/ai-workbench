import { expect, test, type Page, type Route } from "@playwright/test";

const RUN_ID = "e2e-smoke-run";
const PROJECT_ID = "e2e-project";

test.describe("AI Workbench browser smoke", () => {
  test("app shell and primary routes render with mocked read-only APIs", async ({ page }) => {
    const api = await installApiMocks(page);

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("AI Workbench")).toBeVisible();
    await expect(page.getByRole("link", { name: /Projects/ })).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);

    await page.getByRole("link", { name: /Projects/ }).click();
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await expect(page.getByText("E2E Smoke Project")).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);

    await page.getByRole("link", { name: /New Task/ }).click();
    await expect(page.getByRole("heading", { name: "New Task" })).toBeVisible();
    await expect(page.getByText("Every run must be tied to a validated project profile.")).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);

    await page.getByRole("link", { name: /Tools/ }).click();
    await expect(page.getByRole("heading", { name: "Tools" })).toBeVisible();
    await expect(page.getByText("Workbench Test Runner")).toBeVisible();
    await expect(page.getByText("Project Scope")).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);
  });

  test("RunDetail cockpit and delivery tabs render read-only surfaces", async ({ page }) => {
    const api = await installApiMocks(page);

    await page.goto(`/runs/${RUN_ID}`);
    await expect(page.getByRole("heading", { name: `Run: ${RUN_ID}` })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Review SaaS delivery readiness" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Context Cockpit" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Delivery Report" })).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);

    await page.getByRole("button", { name: "Context Cockpit" }).click();
    const cockpit = page
      .getByText("Read-only project context and next-step orientation.")
      .locator("xpath=ancestor::div[contains(@class, 'space-y-4')][1]");
    await expect(cockpit.getByText("Next Safest Action")).toBeVisible();
    await expect(cockpit.getByText("Source of Truth")).toBeVisible();
    await expect(cockpit.getByText("Module Map")).toBeVisible();
    await expect(cockpit.getByText("Delivery Status")).toBeVisible();
    await expect(cockpit.getByText("Module Awareness")).toBeVisible();
    await expect(cockpit.getByText("Classification-only", { exact: true })).toBeVisible();
    await expect(cockpit.getByRole("button", { name: /Apply|Approve|Run Tests|Create Proposal|Scan|Save/i })).toHaveCount(0);
    expect(api.unexpectedPosts()).toEqual([]);

    await page.getByRole("button", { name: "Delivery Report" }).click();
    await expect(page.getByText("Delivery summary is read-only")).toBeVisible();
    await page.getByRole("button", { name: "Refresh delivery summary" }).click();
    await expect(page.getByText("Readiness:")).toBeVisible();
    await expect(page.getByText("Module awareness")).toBeVisible();
    await expect(page.getByText(/Touched:\s*auth/)).toBeVisible();
    expect(api.unexpectedPosts()).toEqual([]);
  });
});

async function installApiMocks(page: Page) {
  const unexpectedPostUrls: string[] = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api") && request.method() !== "GET") {
      unexpectedPostUrls.push(`${request.method()} ${url.pathname}`);
    }
  });

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api") || url.pathname === "/health") {
      if (request.method() !== "GET") {
        await route.fulfill({
          status: 418,
          contentType: "application/json",
          body: JSON.stringify({ error: "Unexpected mutation request in smoke test" }),
        });
        return;
      }
      await fulfillApiGet(route, url.pathname);
      return;
    }
    await route.continue();
  });

  return {
    unexpectedPosts: () => unexpectedPostUrls,
  };
}

async function fulfillApiGet(route: Route, pathname: string) {
  const json = apiResponseFor(pathname);
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(json),
  });
}

function apiResponseFor(pathname: string) {
  if (pathname === "/health") return { status: "ok", ollama: "disconnected" };
  if (pathname === "/api/agents") return [{ id: "orchestrator", name: "Orchestrator", description: "Local coordinator", provider: "ollama" }];
  if (pathname === "/api/agents/registry") return [];
  if (pathname === "/api/models/profiles") return [];
  if (pathname === "/api/models/registry") return [];
  if (pathname === "/api/projects") return [mockProject()];
  if (pathname === "/api/workspace/status") return mockWorkspace();
  if (pathname === `/api/projects/${PROJECT_ID}/workspace/status`) return mockWorkspace();
  if (pathname === `/api/projects/${PROJECT_ID}/git/status`) return mockGitStatus();
  if (pathname === `/api/projects/${PROJECT_ID}/git/diff`) return mockGitDiff();
  if (pathname === `/api/projects/${PROJECT_ID}/tool-calls`) return [];
  if (pathname === "/api/runs") return [mockRun()];
  if (pathname === `/api/runs/${RUN_ID}`) return mockRun();
  if (pathname === `/api/runs/${RUN_ID}/steps`) return [mockStep()];
  if (pathname === `/api/runs/${RUN_ID}/agents`) return [];
  if (pathname === `/api/runs/${RUN_ID}/tool-calls`) return [];
  if (pathname === `/api/runs/${RUN_ID}/model-routes`) return [];
  if (pathname === `/api/runs/${RUN_ID}/project-context-cockpit`) return mockCockpit();
  if (pathname === `/api/runs/${RUN_ID}/delivery-summary`) return mockDeliverySummary();
  if (pathname === `/api/runs/${RUN_ID}/model-routes` || pathname.includes("/model-routes")) return [];
  return {};
}

function mockProject() {
  return {
    id: PROJECT_ID,
    name: "E2E Smoke Project",
    path: "/workspace/e2e-smoke-project",
    description: "Mocked project for browser smoke tests.",
    stack: "React + FastAPI",
    package_manager: "npm",
    test_command: "npm test",
    build_command: "npm run build",
    safe_commands: ["npm test"],
    blocked_commands: [],
    ignore_paths: [],
    created_at: "2026-05-30T00:00:00Z",
    updated_at: null,
  };
}

function mockRun() {
  return {
    id: RUN_ID,
    task_id: "task-e2e-smoke",
    project_id: PROJECT_ID,
    project_path: "/workspace/e2e-smoke-project",
    current_step_id: "step-1",
    agent_id: "orchestrator",
    status: "completed",
    mode: "offline",
    prompt: "Review SaaS delivery readiness",
    plan: "1. Inspect context. 2. Review delivery.",
    result: "",
    logs: [],
    artifacts: [],
    run_dir: "runs/e2e-smoke-run",
    created_at: "2026-05-30T00:00:00Z",
    finished_at: null,
  };
}

function mockStep() {
  return {
    id: "step-1",
    run_id: RUN_ID,
    parent_step_id: "",
    agent_id: "qa-expert",
    status: "completed",
    title: "Review SaaS delivery readiness",
    input: "[requirements: REQ-AUTH-1] Check delivery readiness.",
    output: "Ready for operator review.",
    error: "",
    started_at: "2026-05-30T00:01:00Z",
    finished_at: "2026-05-30T00:02:00Z",
    created_at: "2026-05-30T00:00:30Z",
  };
}

function mockWorkspace() {
  return {
    branch: "main",
    clean: true,
    changes: [],
    raw: "",
    error: "",
    returncode: 0,
    cwd: "/workspace/e2e-smoke-project",
  };
}

function mockGitStatus() {
  return {
    project_id: PROJECT_ID,
    project_path: "/workspace/e2e-smoke-project",
    command: ["git", "status", "--short"],
    returncode: 0,
    stdout: "",
    stderr: "",
    changed_files: [],
    clean: true,
  };
}

function mockGitDiff() {
  return {
    project_id: PROJECT_ID,
    project_path: "/workspace/e2e-smoke-project",
    commands: [["git", "diff", "--stat"]],
    returncode: 0,
    stat: "",
    name_only: [],
    diff: "",
    stderr: "",
    truncated: false,
  };
}

function mockCockpit() {
  return {
    run_id: RUN_ID,
    has_project: true,
    project_id: PROJECT_ID,
    project_name: "E2E Smoke Project",
    source_of_truth: {
      available: true,
      version: 1,
      product_name: "Internal Task Manager",
      requirement_count: 3,
      risk_count: 1,
      open_question_count: 0,
    },
    module_map: {
      available: true,
      version: 1,
      module_count: 4,
      key_modules: ["auth", "tasks", "frontend"],
    },
    run: {
      readiness: "ready_for_review",
      completed_steps: 1,
      total_steps: 1,
      pending_approval_count: 0,
      guard_blocker_count: 0,
      tests_failed_count: 0,
    },
    module_awareness: {
      touched_modules: ["auth"],
      expected_modules: ["auth"],
      blocked_policy_count: 0,
      warning_count: 1,
      recommended_tests: ["auth smoke tests"],
    },
    next_action: {
      label: "Review delivery report",
      reason: "All mocked smoke data is ready for operator review.",
      target_panel: "delivery",
      severity: "ready",
    },
    safety_notes: ["Smoke fixture is read-only."],
  };
}

function mockDeliverySummary() {
  return {
    run_id: RUN_ID,
    project_id: PROJECT_ID,
    project_name: "E2E Smoke Project",
    readiness: "ready_for_review",
    total_steps: 1,
    ready_steps: 1,
    blocked_steps: 0,
    needs_test_steps: 0,
    failed_test_steps: 0,
    approval_pending_steps: 0,
    changed_files: ["backend/src/auth.py"],
    requirement_ids: ["REQ-AUTH-1"],
    guards_total: 1,
    proposals_total: 1,
    applies_total: 1,
    tests_total: 1,
    approvals_total: 0,
    unresolved_issues: [],
    warnings: ["Module policy is report-only."],
    recommended_next_action: "Review delivery report.",
    module_summary: {
      has_module_data: true,
      touched_modules: ["auth"],
      expected_modules: ["auth"],
      unknown_files: [],
      sensitive_modules: ["auth"],
      warning_count: 1,
      blocked_policy_count: 0,
      recommended_tests: ["auth smoke tests"],
      per_step: [],
    },
  };
}
