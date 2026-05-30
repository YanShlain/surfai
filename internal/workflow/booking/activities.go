package booking

import (
	"context"
	"errors"
	"os"
	"time"

	"go.temporal.io/sdk/temporal"

	"neon/domain"
)

// Activities perform seat mutations and payment simulation for the booking workflow.
type Activities struct {
	Seats      domain.SeatRepository
	PaymentRNG PaymentRNG
}

func (a *Activities) paymentRNG() PaymentRNG {
	if a.PaymentRNG != nil {
		return a.PaymentRNG
	}
	return defaultPaymentRNG{}
}

// SeatMutationInput identifies seats to change for an order on a flight.
type SeatMutationInput struct {
	FlightID string
	SeatIDs  []string
	OrderID  string
}

// SeatSwapInput atomically releases and holds seats for an order.
type SeatSwapInput struct {
	FlightID   string
	OrderID    string
	ReleaseIDs []string
	HoldIDs    []string
}

// SwapSeats atomically releases prior holds and applies new ones.
func (a *Activities) SwapSeats(ctx context.Context, in SeatSwapInput) error {
	if err := a.Seats.SwapHold(ctx, in.FlightID, in.OrderID, in.ReleaseIDs, in.HoldIDs); err != nil {
		if errors.Is(err, domain.ErrHoldConflict) {
			return temporal.NewNonRetryableApplicationError("seat hold conflict", "hold_conflict", err)
		}
		if errors.Is(err, domain.ErrInvalidRelease) {
			return temporal.NewNonRetryableApplicationError("seat release failed", "seat_release_failed", err)
		}
		return err
	}
	return nil
}

// ReleaseSeats releases held seats for an order.
func (a *Activities) ReleaseSeats(ctx context.Context, in SeatMutationInput) error {
	if len(in.SeatIDs) == 0 {
		return nil
	}
	if err := a.Seats.Release(ctx, in.FlightID, in.SeatIDs, in.OrderID); err != nil {
		if errors.Is(err, domain.ErrInvalidRelease) {
			return temporal.NewNonRetryableApplicationError("seat release failed", "seat_release_failed", err)
		}
		return err
	}
	return nil
}

// ValidatePayment simulates gateway validation (10s, 15% failure).
// Code format is validated upstream by the workflow update handler.
func (a *Activities) ValidatePayment(ctx context.Context, in PaymentValidationInput) error {
	if raw := os.Getenv("PAYMENT_VALIDATION_DELAY"); raw != "" {
		if delay, err := time.ParseDuration(raw); err == nil && delay > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(delay):
			}
		}
	}
	if simulatePaymentFailure(a.paymentRNG()) {
		return temporal.NewNonRetryableApplicationError("payment validation failed", "payment_validation_failed", nil)
	}
	return nil
}

// ConfirmSeats transitions held seats to BOOKED for an order.
func (a *Activities) ConfirmSeats(ctx context.Context, in SeatMutationInput) error {
	if len(in.SeatIDs) == 0 {
		return nil
	}
	if err := a.Seats.Confirm(ctx, in.FlightID, in.SeatIDs, in.OrderID); err != nil {
		if errors.Is(err, domain.ErrInvalidConfirm) {
			return temporal.NewNonRetryableApplicationError("seat confirm failed", "seat_confirm_failed", err)
		}
		return err
	}
	return nil
}
