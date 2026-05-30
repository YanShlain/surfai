package booking

import (
	"os"
	"time"
)

const (
	WorkflowName        = "BookingWorkflow"
	TaskQueue           = "booking-task-queue"
	Namespace           = "flight-booking"
	QueryGetStatus      = "GetStatus"
	UpdateUpdateSeats   = "UpdateSeats"
	UpdateCancelOrder   = "CancelOrder"
	UpdateSubmitPayment = "SubmitPayment"
)

const minHoldDuration = 5 * time.Second

// HoldDuration returns hold timer length (15m default, overridable via HOLD_DURATION).
// Values below 5 seconds are ignored to prevent orders from expiring before seats can be held.
func HoldDuration() time.Duration {
	if raw := os.Getenv("HOLD_DURATION"); raw != "" {
		if d, err := time.ParseDuration(raw); err == nil && d >= minHoldDuration {
			return d
		}
	}
	return 15 * time.Minute
}
