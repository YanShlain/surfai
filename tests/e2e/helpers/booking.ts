import { expect, Page } from "@playwright/test";

export const PORT_SUCCESS = 8080;
export const PORT_FAILURE = 8081;
// Avoid 8082 — a stale process from earlier runs can answer health checks without test env.
export const PORT_TIMER_RACE = 41882;
export const PORT_PAYMENT_RETRY = 41883;
export const PORT_PAYMENT_DELAY = 41884;
export const PORT_PAYMENT_UI = 41886;

export async function startOrder(page: Page, flightCardIndex: number): Promise<void> {
  await page.locator(".select-btn").nth(flightCardIndex).click();
  await expect(page).toHaveURL(/\/seats\?/);
}

export async function selectSeatAndProceed(page: Page, seatLabel: string): Promise<void> {
  const clicked = await clickSeatIfAvailable(page, seatLabel);
  if (!clicked) {
    await clickAnyAvailableSeat(page);
  }
  await proceedToPayment(page);
}

export async function clickSeatIfAvailable(page: Page, seatLabel: string): Promise<boolean> {
  const preferredSeat = page.getByLabel(`${seatLabel} AVAILABLE`);
  if (await preferredSeat.count()) {
    await preferredSeat.click();
    return true;
  }
  return false;
}

export async function clickAnyAvailableSeat(page: Page): Promise<string> {
  const seat = page.locator("button[aria-label$=' AVAILABLE']").first();
  const label = ((await seat.getAttribute("aria-label")) || "").trim();
  await seat.click();
  return label.split(" ")[0];
}

export async function clickAnotherAvailableSeat(
  page: Page,
  excludeSeatIDs: string[],
): Promise<string> {
  const seats = page.locator("button[aria-label$=' AVAILABLE']");
  const count = await seats.count();
  for (let i = 0; i < count; i++) {
    const label = ((await seats.nth(i).getAttribute("aria-label")) || "").trim();
    const seatID = label.split(" ")[0];
    if (!excludeSeatIDs.includes(seatID)) {
      await seats.nth(i).click();
      return seatID;
    }
  }
  throw new Error(`No available seat found outside [${excludeSeatIDs.join(", ")}]`);
}

export async function selectTwoAvailableSeats(page: Page): Promise<string[]> {
  await expect(page.locator("#seat-map")).toBeVisible();
  const available = page.locator("button[aria-label$=' AVAILABLE']");
  expect(await available.count()).toBeGreaterThanOrEqual(2);

  const firstID = (((await available.nth(0).getAttribute("aria-label")) || "").trim()).split(" ")[0];
  const secondID = (((await available.nth(1).getAttribute("aria-label")) || "").trim()).split(" ")[0];

  await page.getByLabel(`${firstID} AVAILABLE`).click();
  await page.getByLabel(`${secondID} AVAILABLE`).click();

  return [firstID, secondID];
}

export async function selectMultipleSeats(page: Page, seatLabels: string[]): Promise<string[]> {
  const held: string[] = [];
  for (const label of seatLabels) {
    const clicked = await clickSeatIfAvailable(page, label);
    if (clicked) {
      held.push(label);
    }
  }
  if (held.length < 2) {
    return selectTwoAvailableSeats(page);
  }
  return held;
}

export async function proceedToPayment(page: Page): Promise<void> {
  await page.getByRole("button", { name: /Proceed to payment/i }).click();
  await expect(page).toHaveURL(/\/payment\?/);
}

export async function submitPaymentCode(page: Page, code: string): Promise<void> {
  const submit = page.getByRole("button", { name: "Submit payment" });
  await page.locator("#payment-code").fill(code);
  await expect(submit).toBeEnabled({ timeout: 10000 });
  await submit.click();
}

export async function failPaymentConsecutively(page: Page, code: string): Promise<void> {
  const codeInput = page.locator("#payment-code");
  const submit = page.getByRole("button", { name: "Submit payment" });

  for (let attempt = 1; attempt <= 3; attempt++) {
    await codeInput.fill(code);
    await expect(submit).toBeEnabled({ timeout: 10000 });
    await submit.click();
    if (attempt < 3) {
      await expect(page.locator("#attempts-used")).toHaveText(
        `${attempt} / 3 attempts used`,
        { timeout: 10000 },
      );
      await expect(page.locator("#payment-feedback")).toContainText(/failed/i, {
        timeout: 10000,
      });
    }
  }
}

export async function readTimerSeconds(page: Page, selector: string): Promise<number> {
  const value = await page.locator(selector).textContent();
  const match = /^(\d+):(\d+)$/.exec((value || "").trim());
  if (!match) {
    return 0;
  }
  return Number(match[1]) * 60 + Number(match[2]);
}

export async function tryInvalidPaymentCode(page: Page, code: string): Promise<void> {
  await page.locator("#payment-code").fill(code);
}
