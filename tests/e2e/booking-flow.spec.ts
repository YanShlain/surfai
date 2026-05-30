import { expect, test } from "@playwright/test";
import {
  clickAnyAvailableSeat,
  clickAnotherAvailableSeat,
  PORT_SUCCESS,
  proceedToPayment,
  readTimerSeconds,
  selectSeatAndProceed,
  selectTwoAvailableSeats,
  startOrder,
  submitPaymentCode,
} from "./helpers/booking";
import { NeonServer, startNeonServer } from "./helpers/server";

test.describe("MVP-E booking flow (E-E1, E-E2, E-E8, E-E9, E-E10, IR-1, IR-5)", () => {
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

  test("E-E1: completes happy path booking to CONFIRMED", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    await selectSeatAndProceed(page, "1B");

    await submitPaymentCode(page, "12345");

    await expect(page.locator("#order-status")).toHaveText("CONFIRMED", { timeout: 15000 });
    await expect(page.locator("#confirmation-message")).toContainText("are now booked");
  });

  test("IR-1: holds multiple seats through payment and confirmation", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    const heldSeats = await selectTwoAvailableSeats(page);
    expect(heldSeats.length).toBe(2);
    await proceedToPayment(page);

    await expect(page.locator("#held-seats")).toContainText(heldSeats[0]);
    await expect(page.locator("#held-seats")).toContainText(heldSeats[1]);

    await submitPaymentCode(page, "12345");
    await expect(page.locator("#order-status")).toHaveText("CONFIRMED", { timeout: 15000 });

    for (const seatID of heldSeats) {
      await expect(page.locator("#confirmation-message")).toContainText(seatID);
    }
  });

  test("IR-5: confirmed booking shows BOOKED seats on seat map", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    const heldSeatID = await clickAnyAvailableSeat(page);
    await proceedToPayment(page);

    await submitPaymentCode(page, "12345");
    await expect(page.locator("#order-status")).toHaveText("CONFIRMED", { timeout: 15000 });

    await page.getByRole("link", { name: /View seat map/i }).click();
    await expect(page).toHaveURL(/\/seats\?/);

    const bookedSeat = page.getByLabel(`${heldSeatID} BOOKED`);
    await expect(bookedSeat).toBeVisible();
    await expect(bookedSeat).toBeDisabled();
  });

  test("E-E2: seat change refreshes timer close to full duration", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    await selectSeatAndProceed(page, "1B");
    const orderID = await page.evaluate(() => localStorage.getItem("neon_order_id"));
    const flightID = new URL(page.url()).searchParams.get("flight_id");
    expect(orderID).toBeTruthy();
    expect(flightID).toBeTruthy();

    await page.goto(
      `${server.baseURL}/seats?flight_id=${encodeURIComponent(flightID || "")}&order_id=${encodeURIComponent(orderID || "")}`,
    );
    await page.waitForTimeout(2500);
    const beforeChange = await readTimerSeconds(page, "#timer-display");
    const currentHeld = ((await page.locator("#selection-summary").textContent()) || "")
      .replace(/^Held:\s*/, "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    await clickAnotherAvailableSeat(page, currentHeld);
    await page.getByRole("button", { name: /Proceed to payment/i }).click();
    const refreshedTimer = await readTimerSeconds(page, "#timer-display");

    expect(refreshedTimer).toBeGreaterThanOrEqual(110);
    expect(refreshedTimer).toBeGreaterThanOrEqual(beforeChange);
  });

  test("E-E10: proceed to payment preserves hold timer", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    await clickAnyAvailableSeat(page);
    await expect(page.locator("#timer-display")).not.toHaveText("—");

    await page.waitForTimeout(3000);
    const beforeProceed = await readTimerSeconds(page, "#timer-display");
    expect(beforeProceed).toBeGreaterThan(100);
    expect(beforeProceed).toBeLessThan(120);

    await page.getByRole("button", { name: /Proceed to payment/i }).click();
    await expect(page).toHaveURL(/\/payment\?/);

    const afterProceed = await readTimerSeconds(page, "#timer-display");
    expect(afterProceed).toBeLessThanOrEqual(beforeProceed);
    expect(afterProceed).toBeGreaterThan(beforeProceed - 10);
  });

  test("E-E8: seats page timer counts down locally between polls", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);
    await clickAnyAvailableSeat(page);

    await expect(page.locator("#timer-display")).not.toHaveText("—");
    await expect(page.locator("#seat-map")).toBeVisible();

    const initial = await readTimerSeconds(page, "#timer-display");
    expect(initial).toBeGreaterThan(10);

    await expect
      .poll(async () => readTimerSeconds(page, "#timer-display"), { timeout: 5000 })
      .toBeLessThanOrEqual(initial - 2);
  });

  test("E-E9: CREATED order shows no hold timer until a seat is held", async ({ page }) => {
    await page.goto(`${server.baseURL}/`);
    await startOrder(page, 0);

    await expect(page.locator("#order-status")).toHaveText("CREATED");
    await expect(page.locator("#timer-display")).toHaveText("—");

    await clickAnyAvailableSeat(page);
    await expect(page.locator("#order-status")).toHaveText("SEATS_HELD");
    await expect(page.locator("#timer-display")).not.toHaveText("—");
  });
});
