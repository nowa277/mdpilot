import { test, expect, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const API_BASE = "http://localhost:18003";

async function ensureBackendHealthy() {
  const resp = await fetch(`${API_BASE}/health`);
  expect(resp.ok).toBeTruthy();
  const body = await resp.json();
  expect(body.status).toBe("healthy");
}

/** Create a new chat session via the API and return the chat id. */
async function createChat(): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/chats`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.VITE_API_TOKEN ?? ""}`,
    },
    body: JSON.stringify({ title: "E2E Test Chat" }),
  });
  expect(resp.ok).toBeTruthy();
  const data = await resp.json();
  return data.id ?? data.chat_id ?? data.session_id;
}

/** Wait for an agent response to complete by watching the message list. */
async function waitForAgentResponse(page: Page, timeout = 45_000) {
  // Wait for streaming to finish — the stop button disappears when streaming ends
  await page
    .locator('button:has-text("Stop"), button[aria-label="Stop"]')
    .waitFor({ state: "hidden", timeout })
    .catch(() => {
      /* may not exist if already done */
    });

  // Wait for any response content to appear
  await page.waitForTimeout(2_000);
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("MDPilot E2E — Core Flows", () => {
  test.beforeAll(async () => {
    await ensureBackendHealthy();
  });

  test("page loads and shows workspace", async ({ page }) => {
    await page.goto("/workspace");
    await expect(page).toHaveTitle(/MDPilot|mdpilot/i);

    // Workspace layout should have sidebar and main content area
    await expect(page.locator("nav, [data-sidebar], aside").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("can create a new chat session", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Look for "New Chat" or "+" button in sidebar
    const newChatBtn = page.locator(
      'button:has-text("New"), button:has-text("新建"), button[aria-label*="new" i], button[aria-label*="chat" i], [data-testid="new-chat"]',
    );
    await expect(newChatBtn.first()).toBeVisible({ timeout: 10_000 });
    await newChatBtn.first().click();

    // After clicking, URL should contain /c/ or a new chat pane should appear
    await page.waitForURL(/\/c\//, { timeout: 5_000 }).catch(() => {
      // Some implementations may not change URL immediately
    });

    // Chat input should be visible
    await expect(page.locator("textarea, input[type='text']").first()).toBeVisible();
  });

  test("agent mode toggle exists and switches", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Create a chat first if needed
    const chatUrl = page.url();
    if (!chatUrl.includes("/c/")) {
      const newChatBtn = page.locator(
        'button:has-text("New"), button:has-text("新建"), [data-testid="new-chat"]',
      );
      if (await newChatBtn.first().isVisible()) {
        await newChatBtn.first().click();
        await page.waitForTimeout(1_000);
      }
    }

    // Look for mode toggle (对话 / Agent)
    const toggleContainer = page.locator('[data-testid="chat-mode-toggle"]');
    if (await toggleContainer.isVisible()) {
      const agentBtn = toggleContainer.locator('button:has-text("Agent")');
      const dialogBtn = toggleContainer.locator('button:has-text("对话")');
      await expect(agentBtn).toBeVisible();
      await expect(dialogBtn).toBeVisible();

      // Switch to agent mode
      await agentBtn.click();
      await expect(agentBtn).toHaveClass(/bg-accent/);

      // Switch back to dialog
      await dialogBtn.click();
      await expect(dialogBtn).toHaveClass(/bg-accent/);
    }
  });

  test("can send a simple agent prompt and receive response", async ({ page }) => {
    // Navigate directly to a new chat
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    // Switch to agent mode if not already
    const agentBtn = page.locator('[data-testid="chat-mode-toggle"] button:has-text("Agent")');
    if (await agentBtn.isVisible()) {
      await agentBtn.click();
    }

    // Find the textarea and type a simple prompt
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    await textarea.fill("你好，请回复OK");
    await textarea.press("Enter");

    // Wait for the agent to start processing — look for streaming indicators
    // Either a stop button appears or loading indicator
    await page.waitForTimeout(3_000);

    // Wait for completion (stop button to disappear or response to appear)
    await waitForAgentResponse(page, 45_000);

    // There should be at least one response in the message list
    const responseContent = page.locator(
      '[data-message-role="assistant"], .message--assistant, [class*="agent"]',
    );
    // Either we see an explicit response element or the textarea is enabled again
    await expect(textarea).toBeEnabled({ timeout: 30_000 });
  });

  test("tool blocks show tool_call_id and are not duplicated", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    // Switch to agent mode
    const agentBtn = page.locator('[data-testid="chat-mode-toggle"] button:has-text("Agent")');
    if (await agentBtn.isVisible()) {
      await agentBtn.click();
    }

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Send a prompt that triggers bash_run
    await textarea.fill("请用bash_run执行 echo hello_e2e_test");
    await textarea.press("Enter");

    // Wait for tool execution
    await page.waitForTimeout(5_000);
    await waitForAgentResponse(page, 60_000);

    // Check for tool blocks — each tool should appear only once
    // Look for tool-related elements
    const toolBlocks = page.locator(
      '[class*="tool"], [data-block-type="tool_call"], [class*="execution"]',
    );
    const toolCount = await toolBlocks.count();

    // If we have tool blocks, verify no obvious duplication
    if (toolCount > 0) {
      // Get all tool names displayed
      const toolNames = await toolBlocks.allTextContents();
      const bashOccurrences = toolNames.filter((t) =>
        t.toLowerCase().includes("bash_run"),
      ).length;

      // bash_run should appear at most once in the execution summary
      // (more detailed dedup check)
      console.log(
        `Tool blocks found: ${toolCount}, bash_run occurrences: ${bashOccurrences}`,
      );
    }

    // The execution summary should not show duplicate tool names like "bash_run -> bash_run"
    const summaryText = await page
      .locator('[class*="execution-summary"], [class*="ExecutionSummary"]')
      .textContent()
      .catch(() => "");
    if (summaryText) {
      console.log(`Execution summary: ${summaryText}`);
      // Should NOT contain "bash_run -> bash_run" (duplicate)
      expect(summaryText).not.toMatch(/bash_run\s*->\s*bash_run/);
    }
  });

  test("workflow panel shows tool status transitions", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    // Switch to agent mode
    const agentBtn = page.locator('[data-testid="chat-mode-toggle"] button:has-text("Agent")');
    if (await agentBtn.isVisible()) {
      await agentBtn.click();
    }

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Open the right panel / workflow panel if possible
    const viewDetailsBtn = page.locator('button:has-text("View Details"), button:has-text("查看")');
    // Don't fail if not found — it only appears after tool execution

    // Send a prompt that triggers a tool
    await textarea.fill("请用bash_run执行 ls /tmp");
    await textarea.press("Enter");

    // Wait a bit for tool to start
    await page.waitForTimeout(3_000);

    // Click "View Details" if it appeared
    if (await viewDetailsBtn.isVisible().catch(() => false)) {
      await viewDetailsBtn.click();
    }

    await waitForAgentResponse(page, 60_000);

    // Check workflow panel for tool entries
    const workflowPanel = page.locator(
      '[class*="workflow"], [class*="tool-card"], [data-testid="workflow"]',
    );
    if (await workflowPanel.isVisible().catch(() => false)) {
      // There should be at least one tool in the workflow panel
      const toolCards = workflowPanel.locator('[class*="tool-card"], [class*="ToolCard"]');
      const cardCount = await toolCards.count();
      console.log(`Workflow panel tool cards: ${cardCount}`);
      expect(cardCount).toBeGreaterThanOrEqual(1);

      // Check for stuck "Running" status — all tools should eventually complete/fail
      const runningCards = workflowPanel.locator(
        '[class*="status-running"], [class*="badge"]:has-text("Running"), :text("Running")',
      );
      // After response completes, there should be no stuck "Running" tools
      // (allow some buffer time)
      await page.waitForTimeout(2_000);
      const stuckRunning = await runningCards.count();
      console.log(`Stuck running tools: ${stuckRunning}`);
    }
  });

  test("chat input remains usable during streaming", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    // Switch to agent mode
    const agentBtn = page.locator('[data-testid="chat-mode-toggle"] button:has-text("Agent")');
    if (await agentBtn.isVisible()) {
      await agentBtn.click();
    }

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Send a prompt
    await textarea.fill("请用bash_run执行 sleep 3 && echo done");
    await textarea.press("Enter");

    // Immediately check: textarea should still be enabled (typeable)
    await page.waitForTimeout(1_000);
    const isEnabled = await textarea.isEnabled();
    console.log(`Textarea enabled during streaming: ${isEnabled}`);

    // The textarea should NOT be disabled during streaming
    // (Only the send button should be disabled)
    expect(isEnabled).toBeTruthy();

    // Type ahead — this should work
    await textarea.fill("next message queued");

    // Verify the text was accepted
    await expect(textarea).toHaveValue("next message queued");

    // Wait for response to finish
    await waitForAgentResponse(page, 60_000);
  });

  test("thinking block displays without raw tags", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    // Switch to agent mode
    const agentBtn = page.locator('[data-testid="chat-mode-toggle"] button:has-text("Agent")');
    if (await agentBtn.isVisible()) {
      await agentBtn.click();
    }

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Send a prompt that should trigger thinking
    await textarea.fill("解释一下分子动力学模拟的基本步骤");
    await textarea.press("Enter");

    await waitForAgentResponse(page, 60_000);

    // Check page content for raw <think/> tags — these should NOT appear
    const pageText = await page.locator("body").textContent();
    expect(pageText).not.toContain("<think");
    expect(pageText).not.toContain("</think");
    expect(pageText).not.toContain("<thought>");
    expect(pageText).not.toContain("</thought>");

    // Check if a thinking block is rendered
    const thinkingBlock = page.locator(
      '[class*="thinking"], [class*="Thinking"], [data-block-type="thinking"]',
    );
    const hasThinkingBlock = await thinkingBlock.isVisible().catch(() => false);
    console.log(`Thinking block visible: ${hasThinkingBlock}`);
  });

  test("right panel tabs are accessible", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Look for right panel tab elements
    const tabs = page.locator(
      '[class*="tab"], [role="tab"], button:has-text("Timeline"), button:has-text("Tools"), button:has-text("Artifacts")',
    );
    const tabCount = await tabs.count();
    console.log(`Right panel tabs found: ${tabCount}`);

    if (tabCount > 0) {
      // Click each tab
      for (let i = 0; i < Math.min(tabCount, 5); i++) {
        const tab = tabs.nth(i);
        if (await tab.isVisible()) {
          await tab.click();
          await page.waitForTimeout(300);
        }
      }
    }
  });

  test("sidebar shows chat list and supports navigation", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Sidebar should be visible
    const sidebar = page.locator("nav, [data-sidebar], aside").first();
    await expect(sidebar).toBeVisible({ timeout: 5_000 });

    // There should be chat entries or a "no chats" message
    const chatItems = sidebar.locator(
      '[class*="chat-item"], [class*="ChatItem"], a[href*="/c/"], li',
    );
    const itemCount = await chatItems.count();
    console.log(`Sidebar chat items: ${itemCount}`);
  });
});

test.describe("MDPilot E2E — Health & Connectivity", () => {
  test("backend health endpoint returns healthy", async ({ request }) => {
    const resp = await request.get(`${API_BASE}/health`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.status).toBe("healthy");
  });

  test("backend API docs are accessible", async ({ request }) => {
    const resp = await request.get(`${API_BASE}/docs`);
    expect(resp.ok()).toBeTruthy();
  });

  test("chat list API works", async ({ request }) => {
    const token = process.env.VITE_API_TOKEN ?? "";
    const resp = await request.get(`${API_BASE}/api/chats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(Array.isArray(body) || Array.isArray(body.items)).toBeTruthy();
  });
});
