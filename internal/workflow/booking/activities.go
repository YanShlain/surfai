package booking

import (
	"context"
	"errors"

	"go.temporal.io/sdk/temporal"

	"neon/domain"
	"neon/internal/infrastructure/memory"
)

// Activities perform seat mutations for the booking workflow.
type Activities struct {
	Seats domain.SeatRepository
}

// SeatMutationInput identifies seats to change for an order on a flight.
type SeatMutationInput struct {
	FlightID string
	SeatIDs  []string
	OrderID  string
}

// HoldSeats marks seats as held for an order.
func (a *Activities) HoldSeats(ctx context.Context, in SeatMutationInput) error {
	if err := a.Seats.TryHold(ctx, in.FlightID, in.SeatIDs, in.OrderID); err != nil {
		if errors.Is(err, memory.ErrHoldConflict) {
			return temporal.NewNonRetryableApplicationError("seat hold conflict", "hold_conflict", err)
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
	return a.Seats.Release(ctx, in.FlightID, in.SeatIDs, in.OrderID)
}
