package booking

import (
	"time"

	"neon/domain"
)

// WorkflowInput is passed when starting BookingWorkflow.
type WorkflowInput struct {
	OrderID      string
	FlightID     string
	HoldDuration time.Duration
}

// StatusResponse is returned by GetStatus query and order API responses.
type StatusResponse struct {
	OrderID               string              `json:"order_id"`
	FlightID              string              `json:"flight_id"`
	Status                domain.OrderStatus  `json:"status"`
	HeldSeatIDs           []string            `json:"held_seat_ids"`
	TimerRemainingSeconds int                 `json:"timer_remaining_seconds"`
	LastError             string              `json:"-"`
}

// UpdateSeatsRequest is the payload for UpdateSeats workflow update.
type UpdateSeatsRequest struct {
	SeatIDs []string `json:"seat_ids"`
}

func timerRemaining(deadline time.Time, now time.Time) int {
	if deadline.IsZero() {
		return 0
	}
	remaining := int(deadline.Sub(now).Seconds())
	if remaining < 0 {
		return 0
	}
	return remaining
}

func cloneStrings(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	out := make([]string, len(in))
	copy(out, in)
	return out
}
