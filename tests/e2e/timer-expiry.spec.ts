import { expect, test } from "@playwright/test";
import {
  clickAnyAvailableSeat,
  PORT_TIMER_RACE,
  proceedToPayment,
  readTimerSeconds,
  selectSeatAndProceed,
  startOrder,
} from "./helpers/booking";
import { NeonServer, startNeonServer } from "./helpers/server";

test.describe("MVP-E timer expiry (E-E4, IR-7)", () => {
  let server: NeonServer;

  test.beforeEach(async () => {
    server = await startNeonServer({
      port: PORT_TIMER_RACE,
      env: {
        // HoldDuration() ignores values below 5s (see internal/workflow/booking/config.go).
        HOLD_DURATION: "6s",
        PAYMENT_NEVER_FAIL: "1",
        PAYMENT_VALIDATION_DELAY: "8s",
      },
    });
  });

  test.afterEach(async () => {
    if (server) {
      await server.stop();
    }
  });

  test("E-E4: timer expiry rejects in-flight payment", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    await selectSeatAndProceed(page, "1B");

    const orderID = new URL(page.url()).searchParams.get("order_id");
    expect(orderID).toBeTruthy();

    const holdTimer = await readTimerSeconds(page, "#timer-display");
    expect(holdTimer).toBeGreaterThan(0);
    expect(holdTimer).toBeLessThanOrEqual(10);

    await page.locator("#payment-code").fill("12345");
    await page.getByRole("button", { name: "Submit payment" }).click();

    await expect
      .poll(
        async () => {
          const res = await page.request.get(
            `${server.baseURL}/api/v1/orders/${encodeURIComponent(orderID!)}`,
          );
          if (!res.ok()) {
            return "";
          }
          const body = (await res.json()) as { status?: string };
          return body.status ?? "";
        },
        { timeout: 20000 },
      )
      .toBe("EXPIRED");

    await page.reload();

    await expect(page.locator("#order-status")).toHaveText("EXPIRED");
    await expect(page.locator("#error")).toContainText("hold expired");
    await expect(page.locator("#payment-events")).toContainText("Payment rejected (timer expired)");
  });

  test("IR-7: expired order releases seats for a new booking", async ({ browser }) => {
    const holderCtx = await browser.newContext();
    const observerCtx = await browser.newContext();
    const holderPage = await holderCtx.newPage();
    const observerPage = await observerCtx.newPage();

    await holderPage.goto(`${server.baseURL}/`);
    await startOrder(holderPage, 0);
    const heldSeatID = await clickAnyAvailableSeat(holderPage);
    await proceedToPayment(holderPage);

    const orderID = new URL(holderPage.url()).searchParams.get("order_id");
    expect(orderID).toBeTruthy();

    await holderPage.locator("#payment-code").fill("12345");
    await holderPage.getByRole("button", { name: "Submit payment" }).click();

    await expect
      .poll(
        async () => {
          const res = await holderPage.request.get(
            `${server.baseURL}/api/v1/orders/${encodeURIComponent(orderID!)}`,
          );
          if (!res.ok()) {
            return "";
          }
          const body = (await res.json()) as { status?: string };
          return body.status ?? "";
        },
        { timeout: 20000 },
      )
      .toBe("EXPIRED");

    await observerPage.goto(`${server.baseURL}/`);
    await startOrder(observerPage, 0);
    await observerPage.getByRole("button", { name: /Refresh map/i }).click();
    await expect(observerPage.getByLabel(`${heldSeatID} AVAILABLE`)).toBeEnabled();

    await holderCtx.close();
    await observerCtx.close();
  });
});
