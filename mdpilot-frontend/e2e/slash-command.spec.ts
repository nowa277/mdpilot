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
    body: JSON.stringify({ title: "E2E Slash Command Test" }),
  });
  expect(resp.ok).toBeTruthy();
  const data = await resp.json();
  return data.id ?? data.chat_id ?? data.session_id;
}

/** Wait for an agent response to complete. */
async function waitForAgentResponse(page: Page, timeout = 60_000) {
  // Wait for streaming to finish — the stop button disappears when streaming ends
  await page
    .locator('button:has-text("Stop"), button[aria-label="Stop"]')
    .waitFor({ state: "hidden", timeout })
    .catch(() => {
      /* may not exist if already done */
    });

  // Extra buffer for DOM updates
  await page.waitForTimeout(3_000);
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("MDPilot E2E — Slash Command Flows", () => {
  test.beforeAll(async () => {
    await ensureBackendHealthy();
  });

  test("Tab completion: type / → filter force → Tab fills input", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Type "/" to open the slash command menu
    await textarea.fill("/");
    // The menu should appear — wait for the footer hint
    await expect(page.locator("text=↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭")).toBeVisible({
      timeout: 5_000,
    });

    // Continue typing to filter to "force-field"
    await textarea.fill("/force");
    await page.waitForTimeout(500);

    // The first item in the menu should be /force-field
    // Look inside the popup for any button that contains /force-field
    const menuItems = page.locator("text=/force-field").first();
    await expect(menuItems).toBeVisible({ timeout: 3_000 });

    // Press Tab to complete — should fill the textarea with "/force-field " (trailing space)
    await textarea.press("Tab");

    // Verify textarea value — after Tab, should have "/force-field " with a trailing space
    await expect(textarea).toHaveValue(/^\/force-field\s+/, { timeout: 3_000 });

    // Menu should close after Tab
    await expect(page.locator("text=↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭")).not.toBeVisible({
      timeout: 3_000,
    });
  });

  test("send /force-field with text → message bubble shows /force-field prefix", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Fill the command with text directly (bypass menu for this test)
    await textarea.fill("/force-field 测试力场选择");

    // Press Enter to submit
    // Note: since slashFilter is set because value starts with '/',
    // ChatInput.handleKeyDown will check if value includes space → submit
    await textarea.press("Enter");
    await page.waitForTimeout(1_000);

    // Wait for the user message bubble to appear
    const userBubble = page.locator('[data-role="user"]').first();
    await expect(userBubble).toBeVisible({ timeout: 5_000 });

    // The message bubble should display "/force-field 测试力场选择"
    const bubbleText = await userBubble.textContent();
    expect(bubbleText).toContain("/force-field");
    expect(bubbleText).toContain("测试力场选择");
  });

  test("agent responds with force-field knowledge injected", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Track SSE tool_call events to verify list_knowledge is NOT called
    const toolCalls: string[] = [];
    page.on("response", async (resp) => {
      const url = resp.url();
      if (!url.includes("/agent/stream")) return;
      try {
        const body = await resp.text();
        // Parse SSE lines for tool_call events
        for (const line of body.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === "tool_call" && evt.data?.name) {
              toolCalls.push(evt.data.name);
            }
          } catch { /* skip non-JSON lines */ }
        }
      } catch { /* ignore */ }
    });

    // Send a prompt via slash command
    await textarea.fill("/force-field 推荐一个蛋白质模拟的力场");
    await textarea.press("Enter");

    // Wait for the agent response (streaming stop button → hidden)
    await waitForAgentResponse(page, 90_000);

    // Wait for assistant message
    await page.waitForTimeout(2_000);

    // The assistant message should appear
    const assistantBubble = page.locator('[data-role="assistant"]').first();
    let assistantVisible = false;
    try {
      await assistantBubble.waitFor({ state: "visible", timeout: 15_000 });
      assistantVisible = true;
    } catch {
      // fall through
    }
    expect(assistantVisible).toBeTruthy();

    if (assistantVisible) {
      const responseText = await assistantBubble.textContent();
      // The agent should reference force-field knowledge
      const knowsForceField =
        responseText?.includes("ff14SB") ||
        responseText?.includes("ff19SB") ||
        responseText?.includes("AMBER") ||
        responseText?.includes("力场") ||
        responseText?.includes("force field") ||
        responseText?.includes("GAFF") ||
        responseText?.includes("OL3");
      expect(knowsForceField).toBeTruthy();
    }

    // Verify the agent did NOT call list_knowledge or search_knowledge
    // (the injected content should have been used directly)
    const knowledgeToolCalls = toolCalls.filter(
      (name) => name === "list_knowledge" || name === "search_knowledge" || name === "read_knowledge"
    );
    expect(knowledgeToolCalls).toEqual([]);
  });

  test("ArrowDown/ArrowUp navigate menu, Escape closes", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Type "/" to open menu
    await textarea.fill("/");
    await expect(page.locator("text=↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭")).toBeVisible({
      timeout: 5_000,
    });

    // Press ArrowDown — highlight should move
    await textarea.press("ArrowDown");
    await page.waitForTimeout(200);

    // Press ArrowDown again
    await textarea.press("ArrowDown");
    await page.waitForTimeout(200);

    // Press ArrowUp — highlight moves back
    await textarea.press("ArrowUp");
    await page.waitForTimeout(200);

    // Press Escape — menu should close
    await textarea.press("Escape");

    // Menu should be gone
    await expect(page.locator("text=↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭")).not.toBeVisible({
      timeout: 3_000,
    });

    // Textarea should still have "/" value
    await expect(textarea).toHaveValue("/");
  });

  test("bare /command without prompt falls back to skill execution message", async ({ page }) => {
    const chatId = await createChat();
    await page.goto(`/workspace/c/${chatId}`);
    await page.waitForLoadState("networkidle");

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 10_000 });

    // Send bare command without any text after it
    await textarea.fill("/force-field");
    await textarea.press("Enter");
    await page.waitForTimeout(1_000);

    // Wait for the user message bubble
    const userBubble = page.locator('[data-role="user"]').first();
    await expect(userBubble).toBeVisible({ timeout: 5_000 });

    // The message should show "/force-field" with a descriptive prompt
    const bubbleText = await userBubble.textContent();
    expect(bubbleText).toContain("/force-field");
    // The fallback prompt should include the skill description, not "请执行该技能"
    expect(bubbleText).toMatch(/力场|force.field/i);
  });
});
