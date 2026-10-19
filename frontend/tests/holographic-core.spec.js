import { test, expect } from "@playwright/test";

test("renders a moving, non-empty holographic canvas", async ({ page }) => {
  await page.goto("/core-smoke.html");
  const canvas = page.locator("canvas.holo-canvas");
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.getAttribute("data-mode")).toBe("IDLE");
  await page.waitForTimeout(700);
  const metrics = await canvas.evaluate((node) => {
    const ctx = node.getContext("2d");
    const { width, height } = node;
    const pixels = ctx.getImageData(0, 0, width, height).data;
    let lit = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) lit++;
    return { width, height, lit, dpr: window.devicePixelRatio };
  });
  expect(metrics.width).toBeGreaterThan(100);
  expect(metrics.height).toBeGreaterThan(100);
  expect(metrics.lit).toBeGreaterThan(100);
});

for (const [label, mode, expectedLabel] of [
  ["Listening", "USER_LISTENING", "LISTENING"],
  ["Thinking", "PROCESSING", "THINKING"],
  ["Executing", "WORKING", "EXECUTING TASK"],
  ["Speaking", "NOX_SPEAKING", "VOICE"],
  ["Success", "SUCCESS", "TASK COMPLETE"],
  ["Error", "ERROR", "VOICE ISSUE"],
  ["Paused", "PAUSED", "PAUSED"],
  ["Idle", "IDLE", "CORE IDLE"]
]) {
  test(`switches the core to ${label} state without breaking rendering`, async ({ page }) => {
    await page.goto("/core-smoke.html");
    await page.getByRole("button", { name: label, exact: true }).click();
    const canvas = page.locator("canvas.holo-canvas");
    await expect.poll(() => canvas.getAttribute("data-mode")).toBe(mode);
    await expect(canvas).toBeVisible();
    await expect(page.locator(".holo-caption")).toContainText(expectedLabel);
  });
}

test("adapts to a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/core-smoke.html");
  const canvas = page.locator("canvas.holo-canvas");
  await expect(canvas).toBeVisible();
  const size = await canvas.evaluate((node) => ({ width: node.width, height: node.height }));
  expect(size.width).toBeGreaterThan(0);
  expect(size.height).toBeGreaterThan(0);
});
