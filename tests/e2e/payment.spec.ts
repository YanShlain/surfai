import { expect, test } from "@playwright/test";
import {
  failPaymentConsecutively,
  PORT_FAILURE,
  PORT_PAYMENT_DELAY,
  PORT_PAYMENT_RETRY,
  PORT_PAYMENT_UI,
  readTimerSeconds,
  selectSeatAndProceed,
  startOrder,
  submitPaymentCode,
  tryInvalidPaymentCode,
} from "./helpers/booking";
import { NeonServer, startNeonServer } from "./helpers/server";

test.describe("MVP-E payment validation (E-E3, IR-2, IR-3, IR-4)", () => {
  test.describe("success profile", () => {
    let server: NeonServer;

    test.beforeEach(async () => {
      server = await startNeonServer({
        port: PORT_PAYMENT_UI,
        env: {
          PAYMENT_NEVER_FAIL: "1",
        },
      });
    });

    test.afterEach(async () => {
      if (server) {
        await server.stop();
      }
    });

    test("IR-2: rejects invalid payment codes in the UI", async ({ page }) => {
      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      await selectSeatAndProceed(page, "1B");

      await tryInvalidPaymentCode(page, "1234");
      await expect(page.getByRole("button", { name: "Submit payment" })).toBeDisabled();
      await expect(page.locator("#order-status")).toHaveText("SEATS_HELD");

      await tryInvalidPaymentCode(page, "abcde");
      await expect(page.getByRole("button", { name: "Submit payment" })).toBeDisabled();
      await expect(page.locator("#order-status")).toHaveText("SEATS_HELD");

      await page.locator("#payment-code").fill("12345");
      await expect(page.getByRole("button", { name: "Submit payment" })).toBeEnabled();
    });
  });

  test.describe("retry after one failure (IR-3)", () => {
    let server: NeonServer;

    test.beforeEach(async () => {
      server = await startNeonServer({
        port: PORT_PAYMENT_RETRY,
        env: {
          PAYMENT_FAIL_UNTIL: "1",
        },
      });
    });

    test.afterEach(async () => {
      if (server) {
        await server.stop();
      }
    });

    test("IR-3: first payment failure then success on retry", async ({ page }) => {
      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      await selectSeatAndProceed(page, "1B");

      const orderID = new URL(page.url()).searchParams.get("order_id");
      expect(orderID).toBeTruthy();

      await submitPaymentCode(page, "12345");
      await expect(page.locator("#order-status")).toHaveText("SEATS_HELD", { timeout: 10000 });

      const afterFail = await page.request.get(
        `${server.baseURL}/api/v1/orders/${encodeURIComponent(orderID!)}`,
      );
      expect(afterFail.ok()).toBeTruthy();
      const failBody = (await afterFail.json()) as { payment_failures?: number };
      expect(failBody.payment_failures).toBe(1);
      await expect(page.locator("#attempts-used")).toHaveText("1 / 3 attempts used");
      await expect(page.locator("#payment-events")).toContainText(/failed/i, {
        timeout: 10000,
      });

      await submitPaymentCode(page, "12345");
      await expect(page.locator("#order-status")).toHaveText("CONFIRMED", { timeout: 15000 });
      await expect(page.locator("#confirmation-message")).toContainText("are now booked");
    });
  });

  test.describe("payment validation delay (IR-4)", () => {
    let server: NeonServer;

    test.beforeEach(async () => {
      server = await startNeonServer({
        port: PORT_PAYMENT_DELAY,
        env: {
          PAYMENT_NEVER_FAIL: "1",
          PAYMENT_VALIDATION_DELAY: "5s",
        },
      });
    });

    test.afterEach(async () => {
      if (server) {
        await server.stop();
      }
    });

    test("IR-4: shows AWAITING_PAYMENT and timer keeps counting during validation", async ({
      page,
    }) => {
      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      await selectSeatAndProceed(page, "1B");

      const orderID = new URL(page.url()).searchParams.get("order_id");
      expect(orderID).toBeTruthy();

      const timerBefore = await readTimerSeconds(page, "#timer-display");
      expect(timerBefore).toBeGreaterThan(0);

      await page.locator("#payment-code").fill("12345");
      const submitDone = page.getByRole("button", { name: "Submit payment" }).click();

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
          { timeout: 15000, intervals: [100, 200, 500] },
        )
        .toBe("AWAITING_PAYMENT");

      await expect
        .poll(
          async () => {
            const res = await page.request.get(
              `${server.baseURL}/api/v1/orders/${encodeURIComponent(orderID!)}`,
            );
            if (!res.ok()) {
              return timerBefore;
            }
            const body = (await res.json()) as { timer_remaining_seconds?: number };
            return body.timer_remaining_seconds ?? timerBefore;
          },
          { timeout: 10000 },
        )
        .toBeLessThan(timerBefore);

      await expect(page.locator("#order-status")).toHaveText("CONFIRMED", { timeout: 20000 });
      await submitDone;
    });
  });

  test.describe("payment exhaustion (E-E3)", () => {
    let server: NeonServer;

    test.beforeEach(async () => {
      server = await startNeonServer({
        port: PORT_FAILURE,
        env: {
          PAYMENT_ALWAYS_FAIL: "1",
        },
      });
    });

    test.afterEach(async () => {
      if (server) {
        await server.stop();
      }
    });

    test("E-E3: three consecutive failures reach PAYMENT_FAILED", async ({ page }) => {
      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      await selectSeatAndProceed(page, "1B");

      await failPaymentConsecutively(page, "11111");

      await expect(page.locator("#order-status")).toHaveText("PAYMENT_FAILED", { timeout: 15000 });
      await expect(page.locator("#error")).toContainText(/maximum payment retries/i);
      await expect(page.locator("#payment-panel")).toHaveClass(/hidden/);
      await expect(page.evaluate(() => localStorage.getItem("neon_order_id"))).resolves.toBeNull();
      await expect(page.locator("#attempts-used")).toHaveText("3 / 3 attempts used");
      await expect(page.locator("#payment-events")).toContainText(/attempts exhausted/i);
    });
  });
});
