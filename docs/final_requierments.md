# Reviewed Requirements: Flight Booking System (Temporal)

**Status:** UPDATED
**Last updated:** 2026-05-30
**Confidence:** 98.75%

---

## 1. Executive Summary
A multi-flight seat reservation and payment system orchestrated by **Temporal**. Users select a flight (order created in `CREATED` state with no timer), then hold seats (15-minute timer starts on first seat selection), and pay via a 5-digit code. The system handles simulated payment failures (15%) and terminates the order after 3 consecutive failed attempts, ensuring seat inventory integrity across multiple flights.

## 2. Functional Requirements

### 2.1 Seat Management & Timer
- **Multi-Flight:** Inventory is isolated per `flight_id`. Seat `1A` on Flight A is distinct from `1A` on Flight B.
- **Hold Limit:** A user can hold up to the total capacity of the plane in a single order.
- **Timer start:** The 15-minute booking timer starts when the user **first selects seats** (`PATCH /orders/{id}/seats` with non-empty seats). The `CREATED` state has no running timer.
- **Timer refresh:** The timer **resets to a full 15 minutes** on every seat selection change.
- **Timer never pauses:** The timer continues running during payment validation (`AWAITING_PAYMENT`).
- **Expiry:** If the timer hits zero, all held seats are released immediately, even if a payment validation is currently in progress.

### 2.2 Payment Logic
- **Code Format:** Exactly 5 digits.
- **Validation:** 10-second timeout per attempt; 15% simulated failure rate.
- **Retries:** Up to **3 consecutive failed payment attempts** terminates the order. There is no distinction between payment codes — any 3 failures in a row exhaust the order.
- **Success:** Seats transition from `HELD` to `BOOKED`.
- **Failure message:** When all 3 attempts fail: *"The maximum payment retries is reached the booking process is cancelled."*
- **Failure:** If all 3 attempts fail, or if the timer expires, the order is terminated and held seats are released.

### 2.3 Edge Cases
- **Flight Departure:** If a flight departs while an order is active, the order is allowed to continue until the 15-minute timer expires or payment succeeds.
- **Race Condition:** If the timer expires while a payment activity is running, the payment must be rejected/refunded (simulated) and the seats released.

## 3. Technical Constraints & NFRs
- **Orchestration:** A single Temporal workflow must own the entire order lifecycle (timer, state transitions, payment retries).
- **Consistency:** Strong consistency is required for seat holds to prevent double-booking on the same flight.
- **Stack:** Go (API & Workers), Temporal, Web Frontend.

## 4. State Machine (Order)
1.  `CREATED`: Order started when user selects a flight; **no timer yet**; no seats held.
2.  `SEATS_HELD`: Seats held; timer running (starts on first hold, refreshes on changes).
3.  `AWAITING_PAYMENT`: Payment validation active; **Timer still running**.
4.  `CONFIRMED`: Terminal success.
5.  `EXPIRED`: Terminal failure (timer hit zero while seats were held).
6.  `CANCELLED`: Terminal failure (user abandoned).
7.  `PAYMENT_FAILED`: Terminal failure (3 consecutive failed payment attempts).

## 5. Scenarios

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| S-1 | Happy Path | Select flight → Select seats → Pay → Success. |
| S-2 | Timer Refresh | Select seats (8m left) → Change seats → Timer resets to 15m. |
| S-3 | Payment Exhaustion | Fail payment 3 times in a row → Order fails with cancellation message; seats released. |
| S-4 | Late Payment | Payment starts at 14:55 → Timer hits 15:00 → Order expires; payment rejected. |
| S-5 | Multi-Flight | Hold `1A` on Flight 101; `1A` on Flight 102 remains available. |
