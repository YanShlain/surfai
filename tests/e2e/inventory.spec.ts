import { expect, test } from "@playwright/test";
import {
  clickAnyAvailableSeat,
  failPaymentConsecutively,
  PORT_FAILURE,
  PORT_SUCCESS,
  proceedToPayment,
  startOrder,
} from "./helpers/booking";
import { NeonServer, startNeonServer } from "./helpers/server";

test.describe("MVP-E inventory and concurrency (E-E5, E-E6, E-E7, IR-6)", () => {
  test.describe("success profile", () => {
    let server: NeonServer;

    test.beforeEach(async () => {
      server = await startNeonServer({
        port: PORT_SUCCESS,
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

    test("E-E5: flight inventories are isolated", async ({ browser }) => {
      const holderCtx = await browser.newContext();
      const otherFlightCtx = await browser.newContext();
      const page = await holderCtx.newPage();
      const secondFlightPage = await otherFlightCtx.newPage();

      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      const heldSeatID = await clickAnyAvailableSeat(page);
      await page.getByRole("button", { name: /Proceed to payment/i }).click();

      await secondFlightPage.goto(`${server.baseURL}/`);
      await startOrder(secondFlightPage, 1);
      await expect(secondFlightPage.getByLabel(`${heldSeatID} AVAILABLE`)).toBeEnabled();

      await holderCtx.close();
      await otherFlightCtx.close();
    });

    test("E-E6: second user sees held seats as unavailable", async ({ browser }) => {
      const holder = await browser.newContext();
      const observer = await browser.newContext();
      const holderPage = await holder.newPage();
      const observerPage = await observer.newPage();

      await holderPage.goto(`${server.baseURL}/`);
      await startOrder(holderPage, 0);
      const heldSeatID = await clickAnyAvailableSeat(holderPage);
      await holderPage.getByRole("button", { name: /Proceed to payment/i }).click();

      await observerPage.goto(`${server.baseURL}/`);
      await startOrder(observerPage, 0);
      await expect(observerPage.getByLabel(`${heldSeatID} HELD`)).toBeDisabled({
        timeout: 5000,
      });

      await holder.close();
      await observer.close();
    });

    test("E-E7: blocks new booking during active order and allows after terminal", async ({
      page,
    }) => {
      await page.goto(`${server.baseURL}/`);
      await startOrder(page, 0);
      await page.goto(`${server.baseURL}/`);

      await page.locator(".select-btn").nth(1).click();
      await expect(page.locator("#error")).toContainText("already have an active booking");

      await page.getByRole("link", { name: /Continue booking/i }).click();
      await page.getByRole("button", { name: /Cancel order/i }).click();
      await page.goto(`${server.baseURL}/`);

      await page.locator(".select-btn").nth(1).click();
      await expect(page).toHaveURL(/\/seats\?/);
    });
  });

  test.describe("payment failure release (IR-6)", () => {
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

    test("IR-6: seats are released after payment exhaustion", async ({ browser }) => {
      const holderCtx = await browser.newContext();
      const observerCtx = await browser.newContext();
      const holderPage = await holderCtx.newPage();
      const observerPage = await observerCtx.newPage();

      await holderPage.goto(`${server.baseURL}/`);
      await startOrder(holderPage, 0);
      const heldSeatID = await clickAnyAvailableSeat(holderPage);
      await proceedToPayment(holderPage);

      await failPaymentConsecutively(holderPage, "11111");
      await expect(holderPage.locator("#order-status")).toHaveText("PAYMENT_FAILED", {
        timeout: 15000,
      });

      await observerPage.goto(`${server.baseURL}/`);
      await startOrder(observerPage, 0);
      await expect(observerPage.getByLabel(`${heldSeatID} AVAILABLE`)).toBeEnabled({
        timeout: 5000,
      });

      await holderCtx.close();
      await observerCtx.close();
    });
  });
});
