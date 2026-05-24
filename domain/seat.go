package domain

import "time"

// SeatStatus represents the lifecycle state of a seat.
type SeatStatus string

const (
	SeatStatusAvailable SeatStatus = "AVAILABLE"
	SeatStatusHeld      SeatStatus = "HELD"
	SeatStatusBooked    SeatStatus = "BOOKED"
)

// Seat is a single seat on a flight.
type Seat struct {
	FlightID string
	SeatID   string
	Status   SeatStatus
	OrderID  string
}

// Flight is a scheduled flight with fixed capacity.
type Flight struct {
	ID          string
	DepartureAt time.Time
	Capacity    int
}
