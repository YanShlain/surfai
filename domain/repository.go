package domain

import "context"

// SeatRepository manages seat inventory per flight.
type SeatRepository interface {
	ListByFlight(ctx context.Context, flightID string) ([]Seat, error)
	TryHold(ctx context.Context, flightID string, seatIDs []string, orderID string) error
	SwapHold(ctx context.Context, flightID, orderID string, releaseIDs, holdIDs []string) error
	ApplyHold(ctx context.Context, flightID, orderID string, seatIDs []string) error
	Release(ctx context.Context, flightID string, seatIDs []string, orderID string) error
	Confirm(ctx context.Context, flightID string, seatIDs []string, orderID string) error
}

// FlightRepository manages flight catalog data.
type FlightRepository interface {
	Get(ctx context.Context, flightID string) (*Flight, error)
	List(ctx context.Context) ([]Flight, error)
}
